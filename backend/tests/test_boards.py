"""Boards, nested sub-boards, multi-board save, and undo."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import connect, get_db
from app.deps import get_catalog
from app.main import app
from app.services.catalog import Catalog
from app.text import clean_name


@pytest.fixture
def client(catalog: Catalog, tmp_path: Path) -> Iterator[TestClient]:
    db_path = tmp_path / "test.db"

    def db() -> Iterator:  # type: ignore[type-arg]
        conn = connect(db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_db] = db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make(client: TestClient, name: str, parent: int | None = None) -> int:
    response = client.post("/boards", json={"name": name, "parent_id": parent})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_clean_name() -> None:
    assert clean_name("  Summer\t\n<b>Looks</b>  ") == "Summer bLooks/b"
    assert clean_name("\x00\x07") == ""
    assert len(clean_name("x" * 80)) == 50


def test_create_and_list_nested_boards_in_tree_order(client: TestClient) -> None:
    wedding = make(client, "Wedding")
    guests = make(client, "Guest outfits", wedding)
    shoes = make(client, "Shoes", guests)  # three levels deep
    travel = make(client, "Travel")
    boards = client.get("/boards").json()
    assert [b["id"] for b in boards] == [wedding, guests, shoes, travel]
    assert boards[2]["parent_id"] == guests


def test_board_detail_has_breadcrumb_children_and_items(client: TestClient) -> None:
    wedding = make(client, "Wedding")
    guests = make(client, "Guest outfits", wedding)
    shoes = make(client, "Shoes", guests)
    client.post("/saves", json={"item_id": "shoes-boot", "board_ids": [shoes]})
    detail = client.get(f"/boards/{shoes}").json()
    assert [c["name"] for c in detail["breadcrumb"]] == ["Wedding", "Guest outfits"]
    assert [i["id"] for i in detail["items"]] == ["shoes-boot"]
    assert detail["cover"]["id"] == "shoes-boot" and detail["item_count"] == 1
    assert [c["id"] for c in client.get(f"/boards/{guests}").json()["children"]] == [shoes]


def test_save_to_multiple_boards_then_undo(client: TestClient) -> None:
    a, b, c = make(client, "A"), make(client, "B"), make(client, "C")
    client.post("/saves", json={"item_id": "tshirt-red", "board_ids": [a]})
    result = client.post("/saves", json={"item_id": "tshirt-red", "board_ids": [a, b, c, b]}).json()
    assert result == {"item_id": "tshirt-red", "added_to": [b, c], "already_in": [a]}
    assert sorted(client.get("/items/tshirt-red/saved-in").json()) == [a, b, c]

    # Undo removes exactly the boards this save added; the earlier save to A stays.
    client.post("/saves/remove", json={"item_id": "tshirt-red", "board_ids": result["added_to"]})
    assert client.get("/items/tshirt-red/saved-in").json() == [a]


def test_save_validation(client: TestClient) -> None:
    a = make(client, "A")
    assert client.post("/saves", json={"item_id": "nope", "board_ids": [a]}).status_code == 404
    assert client.post("/saves", json={"item_id": "tshirt-red", "board_ids": [999]}).status_code == 404
    assert client.post("/saves", json={"item_id": "tshirt-red", "board_ids": []}).status_code == 422


def test_board_validation_and_delete_cascades(client: TestClient) -> None:
    assert client.post("/boards", json={"name": "   "}).status_code == 422
    assert client.post("/boards", json={"name": "x", "parent_id": 999}).status_code == 404
    parent = make(client, "Parent")
    child = make(client, "Child", parent)
    client.post("/saves", json={"item_id": "tshirt-red", "board_ids": [child]})
    assert client.delete(f"/boards/{parent}").status_code == 204
    assert client.get(f"/boards/{child}").status_code == 404
    assert client.get("/items/tshirt-red/saved-in").json() == []
