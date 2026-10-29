"""Group trips: shared taste, real weather, coordinated outfits, votes, packing lists, notes,
live activity (SSE), invite links, and a public read-only page. See THREAT_MODEL.md."""

import asyncio
import hashlib
import json
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from app.db import connect, get_db, get_db_path
from app.deps import get_catalog, get_embedder, get_llm
from app.models import Item
from app.routers.me import current_user
from app.services.aesthetics import bank_for, style_tags
from app.services.catalog import Catalog
from app.services.color import dominant_colors
from app.services.embedder import Embedder
from app.services.trip_planner import group_palette, group_taste, overlap_word, packing_list, plan_slot
from app.services.upload_pipeline import process_upload
from app.services.weather import Fetch, geocode, http_get_json, trip_weather
from app.text import clean_name
from app.uploads import read_image

router = APIRouter(tags=["trips"])

Db = Annotated[sqlite3.Connection, Depends(get_db)]
CatalogDep = Annotated[Catalog, Depends(get_catalog)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
Role = Literal["owner", "editor", "viewer"]
RANK = {"viewer": 0, "editor": 1, "owner": 2}
MAX_TRIP_DAYS = 21
MAX_INSPIRATION_PER_UPLOAD = 10


def get_weather_fetch() -> Fetch:
    """Overridden in tests so they never hit the network."""
    return http_get_json


FetchDep = Annotated[Fetch, Depends(get_weather_fetch)]


# --- rate limiting (in-memory, per user; production would do this at the edge) ----------------

_hits: dict[tuple[str, int], deque[float]] = defaultdict(deque)


def rate_limit(action: str, user_id: int, limit: int, per_s: float = 60.0) -> None:
    now = time.monotonic()
    q = _hits[(action, user_id)]
    while q and now - q[0] > per_s:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Try again in a minute.")
    q.append(now)


# --- auth helpers ------------------------------------------------------------------------------


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_user(user: Annotated[sqlite3.Row | None, Depends(current_user)]) -> sqlite3.Row:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign up first (it only takes a name).")
    return user


UserDep = Annotated[sqlite3.Row, Depends(require_user)]


def role_of(db: sqlite3.Connection, trip_id: int, user_id: int) -> Role | None:
    row = db.execute("SELECT role FROM trip_members WHERE trip_id = ? AND user_id = ?", (trip_id, user_id)).fetchone()
    return row["role"] if row else None


def require_role(db: sqlite3.Connection, trip_id: int, user: sqlite3.Row, minimum: Role) -> Role:
    if db.execute("SELECT 1 FROM trips WHERE id = ?", (trip_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    role = role_of(db, trip_id, user["id"])
    if role is None:
        raise HTTPException(status_code=404, detail="Trip not found.")  # don't reveal private trips exist
    if RANK[role] < RANK[minimum]:
        raise HTTPException(status_code=403, detail=f"You need {minimum} access for that.")
    return role


def log(db: sqlite3.Connection, trip_id: int, actor: str, text: str) -> None:
    db.execute("INSERT INTO trip_activity (trip_id, actor, text) VALUES (?, ?, ?)", (trip_id, actor, text))


# --- models ------------------------------------------------------------------------------------


class PlaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SlotIn(BaseModel):
    day: date
    label: str = Field(min_length=1, max_length=60)


class TripIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    place: PlaceIn
    start_date: date
    end_date: date
    slots: list[SlotIn] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def _dates(self) -> "TripIn":
        if self.end_date < self.start_date:
            raise ValueError("end_date is before start_date")
        if (self.end_date - self.start_date).days >= MAX_TRIP_DAYS:
            raise ValueError(f"trips can be at most {MAX_TRIP_DAYS} days")
        return self


class InviteIn(BaseModel):
    role: Literal["editor", "viewer"] = "editor"
    days_valid: int = Field(default=7, ge=1, le=30)


class VoteIn(BaseModel):
    item_id: str
    value: Literal[-1, 0, 1]  # 0 clears your vote


class NoteIn(BaseModel):
    day: date
    text: str = Field(min_length=1, max_length=1000)


# --- helpers -----------------------------------------------------------------------------------

_weather_cache: dict[tuple, tuple[float, dict]] = {}


def weather_for(trip: sqlite3.Row, fetch: Fetch) -> dict:
    key = (trip["latitude"], trip["longitude"], trip["start_date"], trip["end_date"], date.today().isoformat())
    cached = _weather_cache.get(key)
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    try:
        w = trip_weather(trip["latitude"], trip["longitude"], date.fromisoformat(trip["start_date"]), date.fromisoformat(trip["end_date"]), fetch=fetch).to_dict()
    except Exception:
        return {"source": "unavailable", "source_detail": "Couldn't reach Open-Meteo right now.", "attribution": "", "days": []}
    _weather_cache[key] = (time.time(), w)
    return w


def _taste(db: sqlite3.Connection, trip_id: int):  # type: ignore[no-untyped-def]
    rows = db.execute("SELECT user_id, vector, colors FROM trip_inspiration WHERE trip_id = ?", (trip_id,)).fetchall()
    by_user: dict[int, list[np.ndarray]] = defaultdict(list)
    colors = []
    for r in rows:
        by_user[r["user_id"]].append(np.frombuffer(r["vector"], dtype=np.float32))
        colors.append(json.loads(r["colors"]))
    return group_taste(by_user), colors, len(rows)


def _names(db: sqlite3.Connection, trip_id: int) -> dict[int, str]:
    rows = db.execute("SELECT u.id, u.display_name FROM trip_members m JOIN users u ON u.id = m.user_id WHERE m.trip_id = ?", (trip_id,))
    return {r["id"]: r["display_name"] for r in rows}


def _trip(db: sqlite3.Connection, trip_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return row


# --- endpoints ---------------------------------------------------------------------------------


@router.get("/geocode")
def search_places(q: Annotated[str, Query(min_length=2, max_length=80)], fetch: FetchDep) -> list[dict]:
    """Destination search via Open-Meteo geocoding."""
    try:
        return [p.__dict__ for p in geocode(q, fetch)]
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Couldn't reach the place search service.") from exc


@router.post("/trips", status_code=201)
def create_trip(body: TripIn, db: Db, user: UserDep) -> dict:
    name = clean_name(body.name, 80)
    if not name:
        raise HTTPException(status_code=422, detail="Trip name can't be blank.")
    place = clean_name(body.place.name + (f", {body.place.country}" if body.place.country else ""), 120)
    cur = db.execute(
        "INSERT INTO trips (name, place_name, latitude, longitude, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)",
        (name, place, body.place.latitude, body.place.longitude, body.start_date.isoformat(), body.end_date.isoformat()),
    )
    trip_id = int(cur.lastrowid)  # type: ignore[arg-type]
    db.execute("INSERT INTO trip_members (trip_id, user_id, role) VALUES (?, ?, 'owner')", (trip_id, user["id"]))
    for s in body.slots:
        _add_slot(db, trip_id, s, body.start_date, body.end_date)
    log(db, trip_id, user["display_name"], f"created the trip to {place}")
    return {"id": trip_id}


def _add_slot(db: sqlite3.Connection, trip_id: int, s: SlotIn, start: date, end: date) -> int:
    if not start <= s.day <= end:
        raise HTTPException(status_code=422, detail="That day isn't within the trip dates.")
    label = clean_name(s.label, 60)
    if not label:
        raise HTTPException(status_code=422, detail="Slot label can't be blank.")
    return int(db.execute("INSERT INTO trip_slots (trip_id, day, label) VALUES (?, ?, ?)", (trip_id, s.day.isoformat(), label)).lastrowid)  # type: ignore[arg-type]


@router.get("/trips")
def my_trips(db: Db, user: UserDep) -> list[dict]:
    rows = db.execute(
        "SELECT t.id, t.name, t.place_name, t.start_date, t.end_date, m.role FROM trips t JOIN trip_members m ON m.trip_id = t.id WHERE m.user_id = ? ORDER BY t.start_date",
        (user["id"],),
    )
    return [dict(r) for r in rows]


@router.get("/trips/{trip_id}")
def trip_detail(trip_id: int, db: Db, user: UserDep, fetch: FetchDep, embedder: EmbedderDep) -> dict:
    role = require_role(db, trip_id, user, "viewer")
    trip = _trip(db, trip_id)
    names = _names(db, trip_id)
    members = [
        {"user_id": r["user_id"], "name": names.get(r["user_id"], "?"), "role": r["role"], "is_you": r["user_id"] == user["id"]}
        for r in db.execute("SELECT user_id, role FROM trip_members WHERE trip_id = ? ORDER BY role, user_id", (trip_id,))
    ]
    taste, colors, n_images = _taste(db, trip_id)
    bank = bank_for(embedder)
    return {
        "id": trip_id,
        "name": trip["name"],
        "place": trip["place_name"],
        "start_date": trip["start_date"],
        "end_date": trip["end_date"],
        "coordinate": bool(trip["coordinate"]),
        "public_slug": trip["public_slug"] if role == "owner" else None,
        "published": trip["public_slug"] is not None,
        "your_role": role,
        "members": members,
        "slots": [dict(r) for r in db.execute("SELECT id, day, label FROM trip_slots WHERE trip_id = ? ORDER BY day, id", (trip_id,))],
        "weather": weather_for(trip, fetch),
        "taste": {
            "inspiration_count": n_images,
            "group_style": [w for w, _ in style_tags(taste.blended, bank)] if taste.blended is not None else [],
            "members": [{"user_id": u, "name": names.get(u, "?"), "style": [w for w, _ in style_tags(c, bank)]} for u, c in taste.member_centroids.items()],
            "overlap": [{"a": names.get(a, "?"), "b": names.get(b, "?"), "similarity": s, "reading": overlap_word(s)} for a, b, s in taste.overlap],
        },
        "palette": group_palette(colors) if trip["coordinate"] else [],
    }


@router.patch("/trips/{trip_id}")
def update_trip(trip_id: int, db: Db, user: UserDep, coordinate: bool) -> dict:
    require_role(db, trip_id, user, "editor")
    db.execute("UPDATE trips SET coordinate = ? WHERE id = ?", (int(coordinate), trip_id))
    log(db, trip_id, user["display_name"], f"turned {'on' if coordinate else 'off'} coordinate-for-photos")
    return {"coordinate": coordinate}


@router.post("/trips/{trip_id}/slots", status_code=201)
def add_slot(trip_id: int, body: SlotIn, db: Db, user: UserDep) -> dict:
    require_role(db, trip_id, user, "editor")
    trip = _trip(db, trip_id)
    slot_id = _add_slot(db, trip_id, body, date.fromisoformat(trip["start_date"]), date.fromisoformat(trip["end_date"]))
    log(db, trip_id, user["display_name"], f"added “{clean_name(body.label, 60)}” on {body.day.isoformat()}")
    return {"id": slot_id}


@router.post("/trips/{trip_id}/invites", status_code=201)
def create_invite(trip_id: int, body: InviteIn, db: Db, user: UserDep) -> dict:
    """Owner-only. The token is returned once; only its hash is stored."""
    require_role(db, trip_id, user, "owner")
    rate_limit("invite", user["id"], limit=10)
    token = secrets.token_urlsafe(24)  # 192 bits
    expires = (datetime.now(timezone.utc) + timedelta(days=body.days_valid)).isoformat()
    cur = db.execute("INSERT INTO trip_invites (trip_id, token_sha256, role, expires_at) VALUES (?, ?, ?, ?)", (trip_id, _hash(token), body.role, expires))
    return {"id": cur.lastrowid, "token": token, "role": body.role, "expires_at": expires}


@router.get("/trips/{trip_id}/invites")
def list_invites(trip_id: int, db: Db, user: UserDep) -> list[dict]:
    require_role(db, trip_id, user, "owner")
    return [dict(r) for r in db.execute("SELECT id, role, expires_at, revoked FROM trip_invites WHERE trip_id = ? ORDER BY id DESC", (trip_id,))]


@router.delete("/trips/{trip_id}/invites/{invite_id}", status_code=204)
def revoke_invite(trip_id: int, invite_id: int, db: Db, user: UserDep) -> None:
    require_role(db, trip_id, user, "owner")
    db.execute("UPDATE trip_invites SET revoked = 1 WHERE id = ? AND trip_id = ?", (invite_id, trip_id))


@router.post("/join/{token}")
def join(token: str, db: Db, user: UserDep) -> dict:
    rate_limit("join", user["id"], limit=20)
    invite = db.execute("SELECT * FROM trip_invites WHERE token_sha256 = ?", (_hash(token),)).fetchone()
    if invite is None or invite["revoked"] or datetime.fromisoformat(invite["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="This invite link is invalid, expired, or was revoked.")
    existing = role_of(db, invite["trip_id"], user["id"])
    if existing is None:
        db.execute("INSERT INTO trip_members (trip_id, user_id, role) VALUES (?, ?, ?)", (invite["trip_id"], user["id"], invite["role"]))
        log(db, invite["trip_id"], user["display_name"], f"joined as {invite['role']}")
    return {"trip_id": invite["trip_id"], "role": existing or invite["role"]}


@router.post("/trips/{trip_id}/inspiration", status_code=201)
async def add_inspiration(
    trip_id: int,
    db: Db,
    user: UserDep,
    embedder: EmbedderDep,
    images: Annotated[list[UploadFile], File(description="Up to 10 inspiration photos")],
) -> dict:
    """Members add inspiration photos. Each goes through the upload pipeline (GPS stripped) and only
    its embedding and colors are stored, not the photo."""
    require_role(db, trip_id, user, "editor")
    if not 1 <= len(images) <= MAX_INSPIRATION_PER_UPLOAD:
        raise HTTPException(status_code=422, detail=f"Add 1–{MAX_INSPIRATION_PER_UPLOAD} photos at a time.")
    processed = [process_upload((await read_image(u))[0], u.content_type or "image/jpeg").image for u in images]
    vectors = embedder.embed_images(processed)
    for img, vec in zip(processed, vectors):
        db.execute(
            "INSERT INTO trip_inspiration (trip_id, user_id, vector, colors) VALUES (?, ?, ?, ?)",
            (trip_id, user["id"], np.asarray(vec, dtype=np.float32).tobytes(), json.dumps(dominant_colors(img))),
        )
    log(db, trip_id, user["display_name"], f"added {len(images)} inspiration photo{'s' if len(images) > 1 else ''}")
    return {"added": len(images)}


@router.get("/trips/{trip_id}/slots/{slot_id}/suggestions")
def slot_suggestions(
    trip_id: int,
    slot_id: int,
    db: Db,
    user: UserDep,
    catalog: CatalogDep,
    embedder: EmbedderDep,
    fetch: FetchDep,
    sort: Literal["relevance", "votes"] = "relevance",
) -> dict:
    """Outfit pieces for one day/event (the plan_trip_outfits logic), with everyone's votes."""
    require_role(db, trip_id, user, "viewer")
    trip = _trip(db, trip_id)
    slot = db.execute("SELECT * FROM trip_slots WHERE id = ? AND trip_id = ?", (slot_id, trip_id)).fetchone()
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found.")
    weather = weather_for(trip, fetch)
    day = next((d for d in weather["days"] if d["date"] == slot["day"]), {})
    taste, colors, _ = _taste(db, trip_id)
    palette = group_palette(colors) if trip["coordinate"] else None
    suggestions = plan_slot(catalog, embedder, taste.blended, slot["label"], day.get("high_c"), day.get("rain_chance"), palette)
    votes: dict[str, dict] = defaultdict(lambda: {"up": 0, "down": 0, "mine": 0})
    for v in db.execute("SELECT item_id, user_id, value FROM trip_votes WHERE slot_id = ?", (slot_id,)):
        entry = votes[v["item_id"]]
        entry["up" if v["value"] > 0 else "down"] += 1
        if v["user_id"] == user["id"]:
            entry["mine"] = v["value"]
    items = [
        {"role": s.role, "item": Item.from_meta(s.hit.item).model_dump(), "votes": dict(votes[s.hit.item["id"]])}
        for s in suggestions
    ]
    if sort == "votes":
        items.sort(key=lambda x: -(x["votes"]["up"] - x["votes"]["down"]))
    return {"slot": dict(slot), "weather": day, "weather_source": weather["source"], "items": items}


@router.post("/trips/{trip_id}/slots/{slot_id}/votes")
def vote(trip_id: int, slot_id: int, body: VoteIn, db: Db, user: UserDep, catalog: CatalogDep) -> dict:
    require_role(db, trip_id, user, "editor")
    slot = db.execute("SELECT label FROM trip_slots WHERE id = ? AND trip_id = ?", (slot_id, trip_id)).fetchone()
    if slot is None or catalog.get(body.item_id) is None:
        raise HTTPException(status_code=404, detail="Slot or item not found.")
    if body.value == 0:
        db.execute("DELETE FROM trip_votes WHERE slot_id = ? AND item_id = ? AND user_id = ?", (slot_id, body.item_id, user["id"]))
    else:
        db.execute(
            "INSERT INTO trip_votes (slot_id, item_id, user_id, value) VALUES (?, ?, ?, ?) ON CONFLICT(slot_id, item_id, user_id) DO UPDATE SET value = excluded.value",
            (slot_id, body.item_id, user["id"], body.value),
        )
        log(db, trip_id, user["display_name"], f"{'liked' if body.value > 0 else 'passed on'} a {catalog.get(body.item_id)['category'].lower()} for “{slot['label']}”")  # type: ignore[index]
    return {"ok": True}


@router.get("/trips/{trip_id}/packing")
def my_packing_list(trip_id: int, db: Db, user: UserDep, catalog: CatalogDep, fetch: FetchDep) -> dict:
    """Your checklist: pieces you liked across the trip's slots, plus weather essentials."""
    require_role(db, trip_id, user, "viewer")
    trip = _trip(db, trip_id)
    rows = db.execute(
        "SELECT s.id AS slot_id, v.item_id FROM trip_votes v JOIN trip_slots s ON s.id = v.slot_id WHERE s.trip_id = ? AND v.user_id = ? AND v.value > 0 ORDER BY s.day",
        (trip_id, user["id"]),
    )
    by_slot: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        meta = catalog.get(r["item_id"])
        if meta:
            by_slot[r["slot_id"]].append(meta)
    weather = weather_for(trip, fetch)
    return {"items": packing_list(list(by_slot.values()), weather["days"]), "weather_source": weather["source"]}


@router.get("/trips/{trip_id}/notes")
def list_notes(trip_id: int, db: Db, user: UserDep) -> list[dict]:
    require_role(db, trip_id, user, "viewer")
    rows = db.execute(
        "SELECT n.id, n.day, n.text, n.ai_suggestion, n.created_at, COALESCE(u.display_name, 'former member') AS author FROM trip_notes n LEFT JOIN users u ON u.id = n.user_id WHERE n.trip_id = ? ORDER BY n.day, n.id",
        (trip_id,),
    )
    return [dict(r) for r in rows]


@router.post("/trips/{trip_id}/notes", status_code=201)
def add_note(trip_id: int, body: NoteIn, db: Db, user: UserDep) -> dict:
    require_role(db, trip_id, user, "editor")
    text = " ".join(body.text.split())[:1000]  # rendered as text by React (no HTML), see THREAT_MODEL.md
    db.execute("INSERT INTO trip_notes (trip_id, user_id, day, text) VALUES (?, ?, ?, ?)", (trip_id, user["id"], body.day.isoformat(), text))
    log(db, trip_id, user["display_name"], f"added a note for {body.day.isoformat()}")
    return {"ok": True}


DRAFT_PROMPT = """Write 2-3 short packing and outfit tips for a day of a group trip.
Destination: {place}. Date: {day}. Plans: {plans}. Weather: {weather}.
Rules: talk only about clothing, layers and what to bring. Do NOT mention prices, opening hours,
bookings, reservations, specific businesses, or anything you can't know. Plain sentences, no lists."""


@router.post("/trips/{trip_id}/notes/draft", status_code=201)
def draft_note(trip_id: int, day: date, db: Db, user: UserDep, fetch: FetchDep, llm=Depends(get_llm)) -> dict:  # type: ignore[no-untyped-def]
    """The assistant drafts a note, saved and always labeled "AI suggestion"."""
    require_role(db, trip_id, user, "editor")
    trip = _trip(db, trip_id)
    plans = ", ".join(r["label"] for r in db.execute("SELECT label FROM trip_slots WHERE trip_id = ? AND day = ?", (trip_id, day.isoformat()))) or "no plans yet"
    w = next((d for d in weather_for(trip, fetch)["days"] if d["date"] == day.isoformat()), None)
    weather = f"high {w['high_c']}°C, low {w['low_c']}°C, rain chance {w['rain_chance']}" if w else "unknown"
    try:
        text = str(llm.invoke(DRAFT_PROMPT.format(place=trip["place_name"], day=day.isoformat(), plans=plans, weather=weather)).content).strip()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The assistant model isn't reachable. Is Ollama running with the model pulled?") from exc
    text = " ".join(text.split())[:1000]
    db.execute("INSERT INTO trip_notes (trip_id, user_id, day, text, ai_suggestion) VALUES (?, ?, ?, ?, 1)", (trip_id, user["id"], day.isoformat(), text))
    log(db, trip_id, user["display_name"], f"added an AI suggestion for {day.isoformat()}")
    return {"text": text, "ai_suggestion": True}


@router.get("/trips/{trip_id}/activity")
def activity(trip_id: int, db: Db, user: UserDep, after: int = 0) -> list[dict]:
    require_role(db, trip_id, user, "viewer")
    return [dict(r) for r in db.execute("SELECT id, actor, text, created_at FROM trip_activity WHERE trip_id = ? AND id > ? ORDER BY id DESC LIMIT 50", (trip_id, after))]


@router.get("/trips/{trip_id}/events")
async def activity_stream(trip_id: int, request: Request, db: Db, user: UserDep, poll_s: float = 1.0, once: bool = False) -> StreamingResponse:
    """Live activity feed as Server-Sent Events (polls the activity table; fine at this scale)."""
    require_role(db, trip_id, user, "viewer")
    last = db.execute("SELECT COALESCE(MAX(id), 0) FROM trip_activity WHERE trip_id = ?", (trip_id,)).fetchone()[0]
    path = get_db_path()

    async def stream():  # type: ignore[no-untyped-def]
        nonlocal last
        yield ": connected\n\n"
        while not await request.is_disconnected():
            conn = connect(path)
            try:
                rows = conn.execute("SELECT id, actor, text, created_at FROM trip_activity WHERE trip_id = ? AND id > ? ORDER BY id", (trip_id, last)).fetchall()
            finally:
                conn.close()
            for r in rows:
                last = r["id"]
                yield f"event: activity\ndata: {json.dumps(dict(r))}\n\n"
            if once:
                return
            await asyncio.sleep(poll_s)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/trips/{trip_id}/publish")
def publish(trip_id: int, db: Db, user: UserDep) -> dict:
    require_role(db, trip_id, user, "owner")
    rate_limit("publish", user["id"], limit=5)
    trip = _trip(db, trip_id)
    slug = trip["public_slug"] or secrets.token_urlsafe(12)
    db.execute("UPDATE trips SET public_slug = ? WHERE id = ?", (slug, trip_id))
    log(db, trip_id, user["display_name"], "published the trip page")
    return {"slug": slug}


@router.delete("/trips/{trip_id}/publish", status_code=204)
def unpublish(trip_id: int, db: Db, user: UserDep) -> None:
    require_role(db, trip_id, user, "owner")
    db.execute("UPDATE trips SET public_slug = NULL WHERE id = ?", (trip_id,))
    log(db, trip_id, user["display_name"], "unpublished the trip page")


@router.get("/public/trips/{slug}")
def public_trip(slug: str, db: Db, catalog: CatalogDep, fetch: FetchDep) -> dict:
    """Read-only, no login. No names, emails, or personal info: only the plan."""
    trip = db.execute("SELECT * FROM trips WHERE public_slug = ?", (slug,)).fetchone()
    if trip is None:
        raise HTTPException(status_code=404, detail="This trip page isn't published.")
    slots = db.execute("SELECT id, day, label FROM trip_slots WHERE trip_id = ? ORDER BY day, id", (trip["id"],)).fetchall()
    lineup = []
    for s in slots:
        liked = db.execute(
            "SELECT item_id, SUM(value) AS score FROM trip_votes WHERE slot_id = ? GROUP BY item_id HAVING score > 0 ORDER BY score DESC LIMIT 6", (s["id"],)
        ).fetchall()
        lineup.append({"day": s["day"], "label": s["label"], "items": [Item.from_meta(catalog.get(r["item_id"])).model_dump() for r in liked if catalog.get(r["item_id"])]})  # type: ignore[arg-type]
    notes = [dict(r) for r in db.execute("SELECT day, text, ai_suggestion FROM trip_notes WHERE trip_id = ? ORDER BY day, id", (trip["id"],))]
    member_count = db.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip["id"],)).fetchone()[0]
    return {
        "name": trip["name"],
        "place": trip["place_name"],
        "start_date": trip["start_date"],
        "end_date": trip["end_date"],
        "travelers": member_count,
        "weather": weather_for(trip, fetch),
        "lineup": lineup,
        "notes": notes,
    }
