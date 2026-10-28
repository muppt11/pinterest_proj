"""Complete the look: group mapping, kids filter, board blending, and the endpoint."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.deps import get_catalog
from app.main import app
from app.services.catalog import Catalog
from app.services.complete_look import COMPLEMENTS, GROUPS, complete_look, group_of


def unit(*v: float) -> np.ndarray:
    a = np.array(v, dtype=np.float32)
    return a / np.linalg.norm(a)


def meta(id_: str, category: str, kids: bool = False) -> dict:
    return {"id": id_, "category": category, "image_file": f"{id_}.jpg", "kids": kids, "width": 1, "height": 1, "sender_id": "x"}


# Axis 0 ≈ the anchor's style, axis 2 ≈ a different board aesthetic.
ROWS = [
    (meta("top", "T-Shirt"), unit(1, 0, 0, 0)),
    (meta("pants-near", "Pants"), unit(0.95, 0, 0.3, 0)),  # close to the top
    (meta("pants-board", "Pants"), unit(0.3, 0, 0.95, 0)),  # close to the board
    (meta("shoes-adult", "Shoes"), unit(0.5, 0.8, 0, 0)),
    (meta("shoes-kids", "Shoes", kids=True), unit(1, 0, 0, 0.05)),  # most similar, but kids
    (meta("dress", "Dress"), unit(0, 1, 0, 0)),
    (meta("misc", "Other"), unit(0, 0, 0, 1)),
]


@pytest.fixture
def look_catalog() -> Catalog:
    return Catalog.from_vectors(np.stack([v for _, v in ROWS]), [m for m, _ in ROWS])


def test_every_dataset_label_except_other_has_a_group() -> None:
    labels = {"T-Shirt", "Longsleeve", "Pants", "Shoes", "Shirt", "Dress", "Outwear", "Shorts", "Hat", "Skirt",
              "Polo", "Undershirt", "Blazer", "Hoodie", "Body", "Top", "Blouse"}
    assert all(group_of(label) for label in labels)
    assert group_of("Other") is None
    assert set(COMPLEMENTS) == set(GROUPS)


def test_top_gets_bottoms_shoes_outerwear_hats(look_catalog: Catalog) -> None:
    group, groups = complete_look(look_catalog, "top")
    assert group == "tops"
    assert [g.group for g in groups] == ["bottoms", "shoes", "outerwear", "hats"]
    by = {g.group: [h.item["id"] for h in g.hits] for g in groups}
    assert by["bottoms"] == ["pants-near", "pants-board"]
    assert by["shoes"] == ["shoes-adult"]  # the kids' shoe is filtered out despite scoring highest
    assert by["outerwear"] == [] and by["hats"] == []


def test_board_centroid_shifts_ranking_toward_the_board(look_catalog: Catalog) -> None:
    _, groups = complete_look(look_catalog, "top", centroid=unit(0, 0, 1, 0), item_weight=0.3)
    assert [h.item["id"] for h in groups[0].hits][0] == "pants-board"


def test_other_category_has_no_suggestions(look_catalog: Catalog) -> None:
    assert complete_look(look_catalog, "misc") == (None, [])


def test_unknown_item_raises(look_catalog: Catalog) -> None:
    with pytest.raises(KeyError):
        complete_look(look_catalog, "nope")


@pytest.fixture
def look_client(look_catalog: Catalog) -> TestClient:
    app.dependency_overrides[get_catalog] = lambda: look_catalog
    yield TestClient(app)  # type: ignore[misc]
    app.dependency_overrides.clear()


def test_endpoint_without_and_with_board(look_client: TestClient) -> None:
    plain = look_client.post("/complete-look", json={"item_id": "top"}).json()
    assert plain["anchor_group"] == "tops" and plain["used_board"] is False
    assert plain["groups"][0]["results"][0]["id"] == "pants-near"

    tuned = look_client.post(
        "/complete-look", json={"item_id": "top", "centroid": [0, 0, 1, 0], "item_weight": 0.3}
    ).json()
    assert tuned["used_board"] is True
    assert tuned["groups"][0]["results"][0]["id"] == "pants-board"


def test_endpoint_validation(look_client: TestClient) -> None:
    assert look_client.post("/complete-look", json={"item_id": "nope"}).status_code == 404
    assert look_client.post("/complete-look", json={"item_id": "top", "centroid": [1, 0]}).status_code == 422
    assert look_client.post("/complete-look", json={"item_id": "top", "centroid": [0, 0, 0, 0]}).status_code == 422
    assert look_client.post("/complete-look", json={"item_id": "top", "item_weight": 2}).status_code == 422
