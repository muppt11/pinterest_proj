"""Lightweight sign-up (display name + HTTP-only cookie, no passwords), the style quiz, and "For you".

Production would use real authentication; see README "Security and privacy".
"""

import hashlib
import json
import secrets
import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

from app.db import get_db
from app.deps import FocusFilter, get_catalog, get_embedder, get_focus
from app.models import Item
from app.services.color_search import color_index
from app.services.catalog import Catalog
from app.services.embedder import Embedder
from app.services.style_focus import FocusIndex
from app.services.taste import COLOR_FAMILIES, ERAS, MAX_PICKS, STYLE_WORDS, Prefs, for_you, quiz_options
from app.text import clean_name

router = APIRouter(tags=["profile"])

COOKIE = "mb_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
Db = Annotated[sqlite3.Connection, Depends(get_db)]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SignUp(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)


class PrefsIn(BaseModel):
    aesthetics: list[str] = Field(default_factory=list, max_length=MAX_PICKS)
    colors: list[str] = Field(default_factory=list, max_length=len(COLOR_FAMILIES))
    eras: list[str] = Field(default_factory=list, max_length=len(ERAS))
    focus: Literal["all", "women", "men"] = "all"

    @field_validator("aesthetics")
    @classmethod
    def _aesthetics(cls, v: list[str]) -> list[str]:
        bad = [a for a in v if a not in STYLE_WORDS]
        if bad:
            raise ValueError(f"unknown aesthetics: {bad}")
        return list(dict.fromkeys(v))

    @field_validator("colors")
    @classmethod
    def _colors(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in COLOR_FAMILIES]
        if bad:
            raise ValueError(f"unknown color families: {bad}")
        return list(dict.fromkeys(v))

    @field_validator("eras")
    @classmethod
    def _eras(cls, v: list[str]) -> list[str]:
        bad = [e for e in v if e not in ERAS]
        if bad:
            raise ValueError(f"unknown eras: {bad}")
        return list(dict.fromkeys(v))


class Me(BaseModel):
    display_name: str
    prefs: PrefsIn


class ForYouItem(Item):
    score: float
    style_match: float | None  # 0..1 from your aesthetics + eras
    color_match: float | None  # 0..1 from your color families
    matched_phrase: str | None = None  # which signature garment of your picks it matched


class ForYou(BaseModel):
    personalized: bool  # False when the quiz is empty (plain catalog order)
    items: list[ForYouItem]


def current_user(db: Db, mb_session: Annotated[str | None, Cookie()] = None) -> sqlite3.Row | None:
    if not mb_session:
        return None
    return db.execute("SELECT * FROM users WHERE token_sha256 = ?", (_hash(mb_session),)).fetchone()


UserDep = Annotated[sqlite3.Row | None, Depends(current_user)]


def _me(row: sqlite3.Row) -> Me:
    return Me(display_name=row["display_name"], prefs=PrefsIn(**json.loads(row["prefs_json"])))


@router.get("/quiz")
def quiz() -> dict:
    """Options for the style quiz."""
    return quiz_options()


@router.post("/me", response_model=Me, status_code=201)
def sign_up(body: SignUp, response: Response, db: Db, user: UserDep) -> Me:
    """Create a profile (or rename the current one). Sets an HTTP-only session cookie."""
    name = clean_name(body.display_name, 40)
    if not name:
        raise HTTPException(status_code=422, detail="Display name can't be blank.")
    if user is not None:
        db.execute("UPDATE users SET display_name = ? WHERE id = ?", (name, user["id"]))
        return _me(db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone())
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO users (token_sha256, display_name) VALUES (?, ?)", (_hash(token), name))
    response.set_cookie(COOKIE, token, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", path="/")
    return Me(display_name=name, prefs=PrefsIn())


@router.get("/me", response_model=Me)
def get_me(user: UserDep) -> Me:
    if user is None:
        raise HTTPException(status_code=404, detail="Not signed up.")
    return _me(user)


@router.put("/me/prefs", response_model=Me)
def save_prefs(body: PrefsIn, db: Db, user: UserDep) -> Me:
    """Save (or update) quiz answers."""
    if user is None:
        raise HTTPException(status_code=401, detail="Sign up first.")
    db.execute("UPDATE users SET prefs_json = ? WHERE id = ?", (body.model_dump_json(), user["id"]))
    return Me(display_name=user["display_name"], prefs=body)


@router.delete("/me", status_code=204)
def sign_out(response: Response) -> Response:
    """Forget this browser's session (the profile row stays; there's no password to recover it)."""
    response.delete_cookie(COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/for-you", response_model=ForYou)
def for_you_feed(
    user: UserDep,
    focus: Annotated[FocusFilter, Depends(get_focus)],
    catalog: Annotated[Catalog, Depends(get_catalog)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ForYou:
    """The catalog ranked by your quiz answers (aesthetics + eras via CLIP text, colors via CIEDE2000)."""
    prefs = Prefs(**_me(user).prefs.model_dump()) if user else Prefs([], [], [])
    if focus.focus != "all":  # the header's "Show" control overrides the quiz answer for this request
        prefs.focus = focus.focus
    allowed = boost = None
    if prefs.focus != "all":
        index = getattr(catalog, "_focus_index", None) or FocusIndex(catalog, embedder)
        catalog._focus_index = index  # type: ignore[attr-defined]
        allowed = index.allowed(prefs.focus)  # type: ignore[arg-type]
        boost = index.boost(prefs.focus)  # type: ignore[arg-type]
    if prefs.is_empty:
        return ForYou(personalized=False, items=[])
    hits = for_you(catalog, color_index(catalog), embedder, prefs, k=limit, offset=offset, allowed=allowed, focus_boost=boost)
    return ForYou(
        personalized=True,
        items=[
            ForYouItem(
                **Item.from_meta(catalog.items[h.row]).model_dump(),
                score=round(h.score, 4),
                style_match=None if h.text_score is None else round(h.text_score, 3),
                color_match=None if h.color_score is None else round(h.color_score, 3),
                matched_phrase=h.phrase,
            )
            for h in hits
        ],
    )
