"""Unit tests for the FAISS-backed catalog."""

from pathlib import Path

import numpy as np
import pytest

from app.services.catalog import Catalog

from .conftest import ITEMS, VECTORS


def test_search_ranks_by_cosine_similarity(catalog: Catalog) -> None:
    hits = catalog.search(VECTORS[0], k=2)
    assert [h.item["id"] for h in hits] == ["tshirt-red", "tshirt-pink"]
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].score > hits[1].score


def test_category_filter_and_exclusion(catalog: Catalog) -> None:
    hits = catalog.search(VECTORS[0], k=10, category="T-Shirt", exclude_ids={"tshirt-red"})
    assert [h.item["id"] for h in hits] == ["tshirt-pink"]


def test_save_and_load_round_trip(catalog: Catalog, tmp_path: Path) -> None:
    catalog.save(tmp_path)
    loaded = Catalog.load(tmp_path)
    assert loaded.items == catalog.items
    np.testing.assert_allclose(loaded.vector("shoes-boot"), VECTORS[2], atol=1e-6)


def test_mismatched_index_and_metadata_is_rejected() -> None:
    with pytest.raises(ValueError):
        Catalog.from_vectors(VECTORS, ITEMS[:2])


def test_zero_results_requested_with_bias(catalog: Catalog) -> None:
    assert catalog.search(VECTORS[0], k=0, bias=np.zeros(4)) == []


@pytest.mark.parametrize("field,value", [("category", "Pants"), ("kids", True)])
def test_repost_representative_must_respect_filters(field: str, value: object) -> None:
    items = [dict(ITEMS[0]), dict(ITEMS[1])]
    for i, item in enumerate(items):
        item.update(phash="0000000000000000", ingested_at="2026-01-01", exif_datetime_original=f"202{i}-01-01")
    items[1][field] = value
    catalog = Catalog.from_vectors(VECTORS[:2], items)
    hits = catalog.search(VECTORS[1], **{field: value})
    assert [h.item["id"] for h in hits] == ["tshirt-pink"]
