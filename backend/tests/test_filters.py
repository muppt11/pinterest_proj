"""Narrow recorded categories, audience and palette combine consistently in every search mode."""

from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.deps import get_catalog, get_embedder, get_embedder_factory
from app.main import app
from app.services.catalog import Catalog
from app.services.color import rgb_to_lab

from .conftest import FakeEmbedder, image_bytes


@pytest.fixture
def refined_client() -> Iterator[TestClient]:
    rows = [
        ("adult-tee", "T-Shirt", False, (246, 198, 208)),
        ("kids-tee", "T-Shirt", True, (246, 198, 208)),
        ("adult-pants", "Pants", False, (20, 20, 20)),
        ("kids-pants", "Pants", True, (20, 20, 20)),
        ("jacket", "Outwear", False, (20, 20, 20)),
        ("blazer", "Blazer", False, (20, 20, 20)),
        ("dress-shirt", "Shirt", False, (246, 198, 208)),
        ("dress", "Dress", False, (246, 198, 208)),
    ]
    items = [
        {"id": id_, "category": category, "kids": kids, "image_file": id_ + ".jpg", "width": 1, "height": 1,
         "colors": [{"hex": "#{:02x}{:02x}{:02x}".format(*rgb), "lab": rgb_to_lab(rgb).tolist(), "weight": 1.0}]}
        for id_, category, kids, rgb in rows
    ]
    catalog = Catalog.from_vectors(np.tile(np.array([[1, 0, 0, 0]], dtype=np.float32), (len(items), 1)), items)
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_embedder_factory] = lambda: FakeEmbedder
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("mode", ["browse", "text", "image", "color", "mood"])
def test_combined_filters_are_strict_in_every_search(refined_client: TestClient, mode: str) -> None:
    params = {"group": "tops", "category": "T-Shirt", "audience": "kids", "color_family": "pastels"}
    if mode == "browse":
        response = refined_client.get("/items", params=params)
    elif mode == "text":
        response = refined_client.get("/search/text", params={**params, "q": "pink shirt"})
    elif mode == "image":
        response = refined_client.post("/search/image", params=params, files={"image": ("x.jpg", image_bytes(), "image/jpeg")})
    elif mode == "color":
        response = refined_client.get("/search/color", params={**params, "hex": "#f6c6d0", "q": "shirt"})
    else:
        response = refined_client.get("/mood", params={**params, "hex": "#f6c6d0", "style": "minimalist"})
    assert response.status_code == 200
    body = response.json()
    assert [i["id"] for i in body.get("items", body.get("results", []))] == ["kids-tee"]


def test_facets_expose_recorded_categories_and_filtered_counts(refined_client: TestClient) -> None:
    body = refined_client.get("/filters", params={"audience": "adults", "color_family": "pastels"}).json()
    by_category = {c["value"]: c for c in body["categories"]}
    assert body["total"] == 3
    assert by_category["T-Shirt"] == {"value": "T-Shirt", "label": "T-shirt", "group": "tops", "count": 1}
    assert by_category["Outwear"]["count"] == 0


@pytest.mark.parametrize("params", [{"audience": "pets"}, {"color_family": "rainbow"}, {"category": "Boots"}])
def test_unrecorded_filters_are_rejected(refined_client: TestClient, params: dict) -> None:
    assert refined_client.get("/items", params=params).status_code == 422


def test_missing_inferred_category_does_not_fall_back_to_unrelated_items(client: TestClient) -> None:
    body = client.get("/search/text", params={"q": "floral dress"}).json()
    assert body["results"] == [] and body["understood"] == ["Dress"]


def test_kids_query_and_compound_garments_narrow_results(refined_client: TestClient) -> None:
    kids = refined_client.get("/search/text", params={"q": "kids shirt"}).json()
    assert [i["id"] for i in kids["results"]] == ["kids-tee"]
    dress_shirt = refined_client.get("/search/text", params={"q": "white dress shirt"}).json()
    assert [i["id"] for i in dress_shirt["results"]] == ["dress-shirt"]
    jackets = refined_client.get("/search/color", params={"q": "black jackets", "hex": "#141414"}).json()
    assert [i["id"] for i in jackets["results"]] == ["jacket"]
