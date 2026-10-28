"""Color search, mood picker, and Shop similar links."""

from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.deps import get_catalog, get_describer, get_embedder
from app.main import app
from app.services.catalog import Catalog
from app.services.color import rgb_to_lab
from app.services.color_search import ColorIndex, color_name, color_search

from .conftest import DIM, FakeEmbedder


def colors(*rgbs_weights: tuple[tuple[int, int, int], float]) -> list[dict]:
    return [
        {"hex": "#{:02x}{:02x}{:02x}".format(*rgb), "lab": [float(v) for v in rgb_to_lab(np.array(rgb))], "weight": w}
        for rgb, w in rgbs_weights
    ]


SAGE, NAVY, YELLOW, BLACK = (156, 175, 136), (25, 35, 75), (245, 215, 50), (20, 20, 20)

ITEMS = [
    {"id": "sage-shirt", "category": "Shirt", "kids": False, "colors": colors((SAGE, 0.8), (BLACK, 0.2))},
    {"id": "navy-yellow-trim", "category": "T-Shirt", "kids": False, "colors": colors((NAVY, 0.9), (YELLOW, 0.1))},
    {"id": "yellow-dress", "category": "Dress", "kids": False, "colors": colors((YELLOW, 0.85), (NAVY, 0.15))},
    {"id": "kids-sage", "category": "Hoodie", "kids": True, "colors": colors((SAGE, 1.0))},
    {"id": "no-colors", "category": "Other", "kids": False, "colors": []},
]
# Text axis: "shirt" -> axis 0. sage-shirt points mostly at axis 0, yellow-dress away from it.
VECS = np.array([[1, 0, 0, 0], [0.7, 0.7, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1], [0, 1, 0, 0]], dtype=np.float32)


@pytest.fixture
def color_catalog() -> Catalog:
    items = [dict(i, image_file=f"{i['id']}.jpg", width=1, height=1, sender_id="x") for i in ITEMS]
    v = VECS / np.linalg.norm(VECS, axis=1, keepdims=True)
    return Catalog.from_vectors(v, items)


def ids(hits, catalog: Catalog) -> list[str]:  # type: ignore[no-untyped-def]
    return [catalog.items[h.row]["id"] for h in hits]


def test_color_only_ranks_by_perceptual_distance(color_catalog: Catalog) -> None:
    hits = color_search(color_catalog, ColorIndex(color_catalog), "#9caf88", k=10)
    assert ids(hits, color_catalog)[:2] in (["kids-sage", "sage-shirt"], ["sage-shirt", "kids-sage"])
    assert "no-colors" not in ids(hits, color_catalog)
    assert hits[0].delta_e < 5 and hits[0].matched_hex in ("#9caf88",)


def test_small_trim_loses_to_main_color(color_catalog: Catalog) -> None:
    hits = color_search(color_catalog, ColorIndex(color_catalog), "#f5d732", k=10)
    order = ids(hits, color_catalog)
    assert order.index("yellow-dress") < order.index("navy-yellow-trim")


def test_text_blend_and_kids_filter(color_catalog: Catalog) -> None:
    shirt = np.array([1, 0, 0, 0], dtype=np.float32)
    hits = color_search(color_catalog, ColorIndex(color_catalog), "#9caf88", k=10, text_vector=shirt, color_weight=0.5, kids=False)
    assert ids(hits, color_catalog)[0] == "sage-shirt"
    assert "kids-sage" not in ids(hits, color_catalog)
    assert hits[0].text_score is not None


def test_color_names() -> None:
    assert color_name(rgb_to_lab(np.array(SAGE))) == "sage green"
    assert color_name(rgb_to_lab(np.array(NAVY))) == "navy"
    assert color_name(rgb_to_lab(np.array((112, 22, 42)))) == "burgundy"


@pytest.fixture
def client(color_catalog: Catalog) -> Iterator[TestClient]:
    class TextEmbedder(FakeEmbedder):
        def embed_texts(self, texts: list[str]) -> np.ndarray:
            return np.stack([np.eye(DIM, dtype=np.float32)[0] for _ in texts])

    app.dependency_overrides[get_catalog] = lambda: color_catalog
    app.dependency_overrides[get_embedder] = TextEmbedder
    app.dependency_overrides[get_describer] = lambda: object()  # no vision model: fallback queries
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_color_endpoint(client: TestClient) -> None:
    body = client.get("/search/color", params={"hex": "9CAF88", "k": 2}).json()
    assert body["color"] == "#9caf88" and body["color_weight"] == 1.0 and body["query"] is None
    assert {r["id"] for r in body["results"]} == {"sage-shirt", "kids-sage"}
    assert body["results"][0]["colors"] and body["results"][0]["delta_e"] < 5

    blended = client.get("/search/color", params={"hex": "#9caf88", "q": "linen shirt"}).json()
    assert blended["query"] == "linen shirt" and blended["results"][0]["text_score"] is not None
    assert client.get("/search/color", params={"hex": "#zzz"}).status_code == 422


def test_mood_endpoint(client: TestClient) -> None:
    assert "minimalist" in client.get("/styles").json()
    body = client.get("/mood", params={"hex": "#9caf88", "style": "minimalist", "k": 3}).json()
    assert body["query"] == "minimalist" and len(body["results"]) == 3
    assert client.get("/mood", params={"hex": "#9caf88", "style": "goblincore"}).status_code == 422


def test_shop_links_use_only_real_attributes(client: TestClient) -> None:
    body = client.get("/items/sage-shirt/shop-links").json()
    assert body["query"] == "sage green shirt" and body["color_name"] == "sage green"
    assert body["query_source"] == "color + category" and body["google_images"].startswith("https://www.google.com/")
    url = urlparse(body["google_shopping"])
    assert url.netloc == "www.google.com" and parse_qs(url.query) == {"tbm": ["shop"], "q": ["sage green shirt"]}
    assert client.get("/items/kids-sage/shop-links").json()["query"] == "kids sage green hoodie"
    assert client.get("/items/no-colors/shop-links").json()["query"] == "clothing"
    assert client.get("/items/nope/shop-links").status_code == 404


def test_shop_links_prefer_vision_query(client: TestClient) -> None:
    class Describer:
        def shopping_query(self, item: dict) -> str:  # type: ignore[type-arg]
            return "sage green linen relaxed button-up shirt"

    app.dependency_overrides[get_describer] = Describer
    body = client.get("/items/sage-shirt/shop-links").json()
    assert body["query"] == "sage green linen relaxed button-up shirt" and body["query_source"] == "vision model"
    assert client.get("/items/kids-sage/shop-links").json()["query"].startswith("kids ")
    fallback = client.get("/items/sage-shirt/shop-links", params={"detailed": False}).json()
    assert fallback["query_source"] == "color + category"


def test_clean_query() -> None:
    from app.agent.vision import clean_query

    assert clean_query('Query: "Burgundy ribbed knit top $25"\nextra') == "Burgundy ribbed knit top"
    assert clean_query("   ") is None
    assert len(clean_query("a " * 30).split()) == 10  # type: ignore[union-attr]
