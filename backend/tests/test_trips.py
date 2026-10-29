"""Group trips: permissions, invites, weather source, planner rules, votes, packing, publish."""

import io
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, timedelta
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import connect, get_db
from app.deps import get_catalog, get_embedder
from app.main import app
from app.routers import trips as trips_router
from app.services.catalog import Catalog
from app.services.trip_planner import COLD_C, HOT_C, allowed_categories, group_taste, packing_list, roles_for
from app.services.weather import trip_weather

from .conftest import FakeEmbedder

TODAY = date.today()


def fake_fetch(url: str, params: dict) -> dict:  # type: ignore[type-arg]
    """Open-Meteo stand-in: geocoding, a 3-day forecast, or a hot, dry archive year."""
    if "geocoding" in url:
        return {"results": [{"name": "Lisbon", "country": "Portugal", "admin1": "Lisbon", "latitude": 38.7, "longitude": -9.1, "timezone": "Europe/Lisbon"}]}
    start, end = date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
    days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    if "archive" in url:
        return {"daily": {"time": days, "temperature_2m_max": [30.0] * len(days), "temperature_2m_min": [20.0] * len(days), "precipitation_sum": [0.0] * len(days)}}
    return {"daily": {"time": days, "temperature_2m_max": [10.0] * len(days), "temperature_2m_min": [4.0] * len(days), "precipitation_probability_max": [80] * len(days)}}


# --- weather -----------------------------------------------------------------------------------


def test_weather_uses_forecast_inside_the_window() -> None:
    w = trip_weather(0, 0, TODAY + timedelta(days=2), TODAY + timedelta(days=4), today=TODAY, fetch=fake_fetch)
    assert w.source == "forecast" and len(w.days) == 3 and w.days[0].rain_chance == 0.8
    assert "Open-Meteo" in w.attribution


def test_weather_uses_historical_averages_outside_the_window() -> None:
    w = trip_weather(0, 0, TODAY + timedelta(days=60), TODAY + timedelta(days=61), today=TODAY, fetch=fake_fetch)
    assert w.source == "historical average" and w.days[0].high_c == 30.0 and w.days[0].rain_chance == 0.0
    assert "Average of the same dates" in w.source_detail


# --- planner rules -----------------------------------------------------------------------------


def test_weather_rules() -> None:
    assert "outerwear" in roles_for(COLD_C - 1) and "outerwear" not in roles_for(HOT_C)
    assert "Shorts" not in allowed_categories("bottoms", COLD_C - 1)
    assert allowed_categories("bottoms", HOT_C) == {"Shorts", "Skirt"}
    assert "Dress" in allowed_categories("tops", HOT_C)


def test_group_taste_counts_each_member_equally() -> None:
    a = [np.array([1, 0], dtype=np.float32)] * 9
    b = [np.array([0, 1], dtype=np.float32)]
    t = group_taste({1: a, 2: b})
    np.testing.assert_allclose(t.blended, [0.7071, 0.7071], atol=1e-3)  # not dominated by 9 photos
    assert t.overlap == [(1, 2, 0.0)]


def test_packing_list_adds_weather_essentials() -> None:
    items = packing_list([[{"id": "a", "category": "Dress"}], [{"id": "a", "category": "Dress"}]], [{"high_c": 31, "low_c": 8, "rain_chance": 0.6}])
    labels = [i["label"] for i in items]
    assert labels.count("Dress") == 1  # deduplicated across slots
    assert {"Umbrella or rain jacket", "Warm layer for evenings", "Sun hat and sunscreen"} <= set(labels)


# --- API ---------------------------------------------------------------------------------------


@pytest.fixture
def make_client(catalog: Catalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator:  # type: ignore[type-arg]
    db_path = tmp_path / "trips.db"

    def db() -> Iterator[sqlite3.Connection]:
        conn = connect(db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[trips_router.get_weather_fetch] = lambda: fake_fetch
    trips_router._hits.clear()
    trips_router._weather_cache.clear()
    monkeypatch.setattr(trips_router, "get_db_path", lambda: db_path)  # the SSE stream opens its own connection

    def make(name: str) -> TestClient:
        c = TestClient(app)
        assert c.post("/me", json={"display_name": name}).status_code == 201
        return c

    yield make
    app.dependency_overrides.clear()


def new_trip(c: TestClient) -> int:
    start = TODAY + timedelta(days=3)
    body = {
        "name": "Girls trip",
        "place": {"name": "Lisbon", "country": "Portugal", "latitude": 38.7, "longitude": -9.1},
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=2)).isoformat(),
        "slots": [{"day": start.isoformat(), "label": "beach dinner"}],
    }
    r = c.post("/trips", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (220, 30, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def test_trip_flow_with_invites_roles_votes_packing_and_publish(make_client) -> None:  # type: ignore[no-untyped-def]
    owner, editor, viewer, stranger = make_client("Ana"), make_client("Bea"), make_client("Cy"), make_client("Dee")
    trip_id = new_trip(owner)

    # Invite links (one-time token shown to the owner; only a hash is stored).
    edit_link = owner.post(f"/trips/{trip_id}/invites", json={"role": "editor"}).json()["token"]
    view_link = owner.post(f"/trips/{trip_id}/invites", json={"role": "viewer"}).json()["token"]
    assert len(edit_link) >= 32
    assert editor.post(f"/join/{edit_link}").json()["role"] == "editor"
    assert viewer.post(f"/join/{view_link}").json()["role"] == "viewer"

    # Strangers can't even tell the trip exists.
    assert stranger.get(f"/trips/{trip_id}").status_code == 404

    detail = owner.get(f"/trips/{trip_id}").json()
    assert detail["weather"]["source"] == "forecast" and len(detail["members"]) == 3
    slot_id = detail["slots"][0]["id"]

    # Inspiration -> group taste.
    files = [("images", ("a.jpg", jpeg(), "image/jpeg"))]
    assert editor.post(f"/trips/{trip_id}/inspiration", files=files).status_code == 201
    assert owner.get(f"/trips/{trip_id}").json()["taste"]["inspiration_count"] == 1

    # Cold (10°C) and rainy forecast: outerwear role present, no shorts suggested.
    sug = owner.get(f"/trips/{trip_id}/slots/{slot_id}/suggestions").json()
    assert sug["weather_source"] == "forecast" and sug["weather"]["high_c"] == 10.0
    assert all(i["item"]["category"] != "Shorts" for i in sug["items"])
    first = sug["items"][0]["item"]["id"]

    # Votes, sorted by votes, then the packing list reflects what I liked.
    assert owner.post(f"/trips/{trip_id}/slots/{slot_id}/votes", json={"item_id": first, "value": 1}).status_code == 200
    by_votes = owner.get(f"/trips/{trip_id}/slots/{slot_id}/suggestions", params={"sort": "votes"}).json()
    assert by_votes["items"][0]["item"]["id"] == first and by_votes["items"][0]["votes"] == {"up": 1, "down": 0, "mine": 1}
    packing = owner.get(f"/trips/{trip_id}/packing").json()["items"]
    assert any(i.get("item_id") == first for i in packing) and any(i["label"] == "Umbrella or rain jacket" for i in packing)

    # Notes are plain text; activity records everything; SSE replays new events.
    assert editor.post(f"/trips/{trip_id}/notes", json={"day": detail["start_date"], "text": "<b>bring</b> layers"}).status_code == 201
    assert owner.get(f"/trips/{trip_id}/notes").json()[0]["text"] == "<b>bring</b> layers"  # stored as text; React escapes it
    feed = [a["text"] for a in owner.get(f"/trips/{trip_id}/activity").json()]
    assert any("joined as editor" in t for t in feed) and any("liked" in t for t in feed)

    # Publish -> public read-only page without names; unpublish -> 404.
    slug = owner.post(f"/trips/{trip_id}/publish").json()["slug"]
    public = TestClient(app).get(f"/public/trips/{slug}").json()
    assert public["travelers"] == 3 and public["lineup"][0]["items"][0]["id"] == first
    assert "Ana" not in str(public) and "Bea" not in str(public)
    assert owner.delete(f"/trips/{trip_id}/publish").status_code == 204
    assert TestClient(app).get(f"/public/trips/{slug}").status_code == 404


def test_viewer_cannot_edit(make_client) -> None:  # type: ignore[no-untyped-def]
    owner, viewer = make_client("Ana"), make_client("Cy")
    trip_id = new_trip(owner)
    viewer.post(f"/join/{owner.post(f'/trips/{trip_id}/invites', json={'role': 'viewer'}).json()['token']}")
    slot_id = owner.get(f"/trips/{trip_id}").json()["slots"][0]["id"]
    assert viewer.get(f"/trips/{trip_id}").status_code == 200  # can read
    assert viewer.post(f"/trips/{trip_id}/slots/{slot_id}/votes", json={"item_id": "tshirt-red", "value": 1}).status_code == 403
    assert viewer.post(f"/trips/{trip_id}/slots", json={"day": owner.get(f"/trips/{trip_id}").json()["start_date"], "label": "x"}).status_code == 403
    assert viewer.post(f"/trips/{trip_id}/notes", json={"day": TODAY.isoformat(), "text": "x"}).status_code == 403
    assert viewer.post(f"/trips/{trip_id}/invites", json={"role": "editor"}).status_code == 403
    assert viewer.post(f"/trips/{trip_id}/publish").status_code == 403


def test_revoked_and_expired_links_fail(make_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    owner, guest = make_client("Ana"), make_client("Bea")
    trip_id = new_trip(owner)
    invite = owner.post(f"/trips/{trip_id}/invites", json={"role": "editor"}).json()
    assert owner.delete(f"/trips/{trip_id}/invites/{invite['id']}").status_code == 204
    assert guest.post(f"/join/{invite['token']}").status_code == 404

    expiring = owner.post(f"/trips/{trip_id}/invites", json={"role": "editor", "days_valid": 1}).json()
    from datetime import datetime

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def, override]
            return datetime.now(UTC) + timedelta(days=2)

    monkeypatch.setattr(trips_router, "datetime", Later)
    assert guest.post(f"/join/{expiring['token']}").status_code == 404
    assert guest.post("/join/not-a-real-token").status_code == 404


def test_unpublished_page_404s_and_rate_limits(make_client) -> None:  # type: ignore[no-untyped-def]
    owner = make_client("Ana")
    trip_id = new_trip(owner)
    assert TestClient(app).get("/public/trips/never-published").status_code == 404
    codes = [owner.post(f"/trips/{trip_id}/invites", json={"role": "viewer"}).status_code for _ in range(12)]
    assert codes[:10] == [201] * 10 and codes[-1] == 429


def test_requires_sign_up_and_validates_dates(make_client) -> None:  # type: ignore[no-untyped-def]
    assert TestClient(app).get("/trips").status_code == 401
    owner = make_client("Ana")
    bad = {"name": "x", "place": {"name": "Lisbon", "latitude": 0, "longitude": 0}, "start_date": "2026-12-05", "end_date": "2026-12-01"}
    assert owner.post("/trips", json=bad).status_code == 422
    too_long = dict(bad, end_date="2027-01-30")
    assert owner.post("/trips", json=too_long).status_code == 422


def test_activity_stream_sends_events(make_client) -> None:  # type: ignore[no-untyped-def]
    owner = make_client("Ana")
    trip_id = new_trip(owner)
    with owner.stream("GET", f"/trips/{trip_id}/events", params={"once": True}) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert ": connected" in body


def test_geocode_proxy(make_client) -> None:  # type: ignore[no-untyped-def]
    c = make_client("Ana")
    places = c.get("/geocode", params={"q": "Lisbon"}).json()
    assert places[0]["name"] == "Lisbon" and places[0]["country"] == "Portugal"
