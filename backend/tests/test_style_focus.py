"""Estimated style focus (menswear / womenswear / all) and its effect on endpoints."""

from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.deps import get_catalog, get_embedder, get_embedder_factory
from app.main import app
from app.services.catalog import Catalog
from app.services.style_focus import UNISEX_MARGIN, FocusIndex

from .conftest import FakeEmbedder


class GenderEmbedder(FakeEmbedder):
    """'women' prompts point at axis 0 (the t-shirts), 'men' prompts at axis 2 (the jeans)."""

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            v = np.zeros(4, dtype=np.float32)
            if "women" in t:
                v[0] = 1
            elif "men" in t:
                v[2] = 1
            else:
                v[0] = 1  # ordinary queries: "shirt" etc.
            out.append(v)
        return np.stack(out)


def test_lean_and_masks(catalog: Catalog) -> None:
    index = FocusIndex(catalog, GenderEmbedder())
    labels = {item["id"]: index.label(i) for i, item in enumerate(catalog.items)}
    assert labels == {"tshirt-red": "womenswear", "tshirt-pink": "womenswear", "shoes-boot": "unisex", "pants-jeans": "menswear"}
    assert index.excluded_ids("women") == {"pants-jeans"}
    assert index.excluded_ids("men") == {"tshirt-red", "tshirt-pink"}
    assert index.excluded_ids("all") == set()
    assert UNISEX_MARGIN > 0


@pytest.fixture
def client(catalog: Catalog) -> Iterator[TestClient]:
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_embedder] = GenderEmbedder
    app.dependency_overrides[get_embedder_factory] = lambda: (lambda: GenderEmbedder())
    yield TestClient(app)
    app.dependency_overrides.clear()


def ids(body: dict) -> set[str]:  # type: ignore[type-arg]
    return {i["id"] for i in body.get("items", body.get("results", []))}


def test_focus_filters_browse_and_search(client: TestClient) -> None:
    assert ids(client.get("/items").json()) == {"tshirt-red", "tshirt-pink", "shoes-boot", "pants-jeans"}
    assert ids(client.get("/items", params={"focus": "women"}).json()) == {"tshirt-red", "tshirt-pink", "shoes-boot"}
    assert ids(client.get("/items", params={"focus": "men"}).json()) == {"shoes-boot", "pants-jeans"}
    men = client.get("/search/text", params={"q": "shirt", "focus": "men"}).json()
    assert "tshirt-red" not in ids(men) and "tshirt-pink" not in ids(men)
    assert client.get("/items", params={"focus": "kids"}).status_code == 422


def test_focus_applies_to_similar_and_complete_look(client: TestClient) -> None:
    similar = client.get("/items/shoes-boot/similar", params={"focus": "men"}).json()
    assert ids(similar) == {"pants-jeans"}
    look = client.post("/complete-look?focus=women", json={"item_id": "tshirt-red"}).json()
    assert all(r["id"] != "pants-jeans" for g in look["groups"] for r in g["results"])


def test_browse_order_changes_with_focus(client: TestClient) -> None:
    """Regression: the first page looked identical under both focuses because unisex items led."""
    women = [i["id"] for i in client.get("/items", params={"focus": "women"}).json()["items"]]
    men = [i["id"] for i in client.get("/items", params={"focus": "men"}).json()["items"]]
    assert women[0] in ("tshirt-red", "tshirt-pink")  # most womenswear-leaning first
    assert men[0] == "pants-jeans"  # most menswear-leaning first
    assert women != men
