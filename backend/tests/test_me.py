"""Sign-up (cookie identity), the style quiz, and the For you feed."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.db import connect, get_db
from app.deps import get_catalog, get_embedder
from app.main import app
from app.services.catalog import Catalog
from app.services.color import rgb_to_lab

from .conftest import ITEMS, VECTORS, FakeEmbedder


def colors(rgb: tuple[int, int, int]) -> list[dict]:
    return [{"hex": "#000000", "lab": [float(v) for v in rgb_to_lab(np.array(rgb))], "weight": 1.0}]


@pytest.fixture
def colored_catalog() -> Catalog:
    palette = {"tshirt-red": (230, 0, 35), "tshirt-pink": (246, 198, 208), "shoes-boot": (26, 26, 26), "pants-jeans": (27, 42, 74)}
    items = [dict(i, colors=colors(palette[i["id"]])) for i in ITEMS]
    return Catalog.from_vectors(VECTORS, items)


@pytest.fixture
def client(colored_catalog: Catalog, tmp_path: Path) -> Iterator[TestClient]:
    db_path = tmp_path / "me.db"

    def db() -> Iterator[sqlite3.Connection]:
        conn = connect(db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    app.dependency_overrides[get_catalog] = lambda: colored_catalog
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_db] = db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_signup_sets_httponly_cookie_and_stores_only_a_hash(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/me").status_code == 404
    response = client.post("/me", json={"display_name": "  Tanvi <3 "})
    assert response.status_code == 201 and response.json()["display_name"] == "Tanvi 3"
    cookie = response.headers["set-cookie"]
    assert "mb_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    token = client.cookies.get("mb_session")
    assert token and len(token) >= 40
    stored = sqlite3.connect(tmp_path / "me.db").execute("SELECT token_sha256 FROM users").fetchone()[0]
    assert token not in stored and len(stored) == 64
    assert client.get("/me").json()["display_name"] == "Tanvi 3"


def test_prefs_save_update_and_validate(client: TestClient) -> None:
    assert client.put("/me/prefs", json={}).status_code == 401
    client.post("/me", json={"display_name": "A"})
    saved = client.put("/me/prefs", json={"aesthetics": ["minimalist", "minimalist"], "colors": ["pastels"], "eras": ["2000s"], "focus": "women"})
    assert saved.json()["prefs"] == {"aesthetics": ["minimalist"], "colors": ["pastels"], "eras": ["2000s"], "focus": "women"}
    updated = client.put("/me/prefs", json={"colors": ["darks"]}).json()["prefs"]
    assert updated["colors"] == ["darks"] and client.get("/me").json()["prefs"]["colors"] == ["darks"]
    assert client.put("/me/prefs", json={"aesthetics": ["goblincore"]}).status_code == 422
    assert client.put("/me/prefs", json={"eras": ["1800s"]}).status_code == 422
    assert client.put("/me/prefs", json={"colors": ["neon"]}).status_code == 422


def test_quiz_options(client: TestClient) -> None:
    q = client.get("/quiz").json()
    assert "minimalist" in q["aesthetics"] and "neutrals" in q["colors"] and "2000s" in q["eras"]
    assert all(h.startswith("#") for h in q["colors"]["pastels"])


def test_for_you_uses_colors_and_excludes_kids(client: TestClient) -> None:
    assert client.get("/for-you").json() == {"personalized": False, "items": []}
    client.post("/me", json={"display_name": "A"})
    client.put("/me/prefs", json={"colors": ["pastels"]})
    feed = client.get("/for-you").json()
    assert feed["personalized"] is True
    ids = [i["id"] for i in feed["items"]]
    assert ids[0] == "tshirt-pink"  # the pastel item
    assert "shoes-boot" not in ids  # kids item
    assert feed["items"][0]["color_match"] > feed["items"][-1]["color_match"]


def test_sign_out_clears_cookie(client: TestClient) -> None:
    client.post("/me", json={"display_name": "A"})
    response = client.delete("/me")
    assert response.status_code == 204 and 'mb_session=""' in response.headers["set-cookie"]
