"""Ranking regressions: full-catalog colors and stable, complete recommendation pages."""

import numpy as np
from fastapi.testclient import TestClient

from app.services.aesthetics import diversified_order
from app.services.catalog import Catalog
from app.services.color import rgb_to_lab
from app.services.color_search import color_index
from app.services.taste import Prefs, for_you
from app.services.text_search import text_search

from .conftest import FakeEmbedder


def ranking_catalog(n: int = 450) -> Catalog:
    # A large pool of strong text matches and a smaller pool on another style direction.
    x = np.linspace(0.99, 0.5, n)
    vectors = np.stack([x, np.sqrt(1 - x * x), np.zeros(n), np.zeros(n)], axis=1).astype(np.float32)
    items = [
        {"id": f"item-{i}", "category": "T-Shirt", "kids": False, "image_file": f"{i}.jpg", "width": 1, "height": 1,
         "colors": [{"hex": "#1a1a1a", "lab": rgb_to_lab((26, 26, 26)).tolist(), "weight": 1.0}]}
        for i in range(n)
    ]
    return Catalog.from_vectors(vectors, items)


class StyleEmbedder(FakeEmbedder):
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return np.array([[1, 0, 0, 0] if "t-shirt" in t else [0, 1, 0, 0] for t in texts], dtype=np.float32)


def test_color_search_finds_matches_beyond_initial_text_pool() -> None:
    catalog = ranking_catalog()
    # This item is just outside the old 200-hit pool but is the only red garment.
    catalog.items[210]["colors"] = [{"hex": "#c81e28", "lab": rgb_to_lab((200, 30, 40)).tolist(), "weight": 1.0}]
    result = text_search(catalog, FakeEmbedder(), "red shirt", k=1)
    assert result.hits[0].item["id"] == "item-210"


def test_style_browse_has_stable_pages_and_complete_totals(client: TestClient) -> None:
    from app.deps import get_catalog, get_embedder_factory
    from app.main import app

    large = ranking_catalog()
    embedder = StyleEmbedder()
    app.dependency_overrides[get_catalog] = lambda: large
    app.dependency_overrides[get_embedder_factory] = lambda: (lambda: embedder)
    def page(offset: int, limit: int) -> dict:
        return client.get("/items", params={"style": "minimalist", "offset": offset, "limit": limit}).json()

    first, second, together = page(0, 50), page(50, 150), page(0, 200)
    assert first["total"] == second["total"] == together["total"] == 450
    assert first["items"] + second["items"] == together["items"]
    all_ids = [i["id"] for offset in (0, 200, 400) for i in page(offset, 200)["items"]]
    assert len(all_ids) == len(set(all_ids)) == 450


def test_personalized_ranking_has_stable_complete_pages() -> None:
    catalog = ranking_catalog()
    prefs = Prefs(["minimalist"], [], [])
    embedder = StyleEmbedder()
    index = color_index(catalog)
    first = for_you(catalog, index, embedder, prefs, k=50)
    second = for_you(catalog, index, embedder, prefs, k=150, offset=50)
    all_hits = for_you(catalog, index, embedder, prefs, k=450)
    assert [h.row for h in first + second] == [h.row for h in all_hits[:200]]
    assert len(all_hits) == 450


def test_empty_catalog_can_be_personalized() -> None:
    catalog = Catalog.from_vectors(np.zeros((0, 4), dtype=np.float32), [])
    assert for_you(catalog, color_index(catalog), StyleEmbedder(), Prefs(["minimalist"], [], [])) == []


def test_full_diversity_does_not_promote_a_weak_phrase_to_first_page() -> None:
    scores = np.linspace(1.0, 0.0, 450)
    phrases = np.zeros(450, dtype=int)
    phrases[420:] = 1
    order = diversified_order(scores, phrases, pool=None)
    assert set(order[:400]) == set(range(400))
    assert len(order) == 450
