"""The indexed clothing catalog: FAISS vectors plus per-item metadata."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np

INDEX_FILE = "catalog.faiss"
METADATA_FILE = "metadata.json"


@dataclass
class Hit:
    """One search result: the item's metadata and its cosine similarity to the query."""

    item: dict[str, Any]
    score: float


class Catalog:
    """Exact cosine search over the catalog (IndexFlatIP on unit vectors)."""

    def __init__(self, index: faiss.Index, items: list[dict[str, Any]]) -> None:
        if index.ntotal != len(items):
            raise ValueError(f"index has {index.ntotal} vectors but metadata has {len(items)} items")
        self.index = index
        self.items = items
        self._row_by_id = {item["id"]: row for row, item in enumerate(items)}

    @classmethod
    def from_vectors(cls, vectors: np.ndarray, items: list[dict[str, Any]]) -> "Catalog":
        """Build an in-memory catalog (used by the index script and tests)."""
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        return cls(index, items)

    @classmethod
    def load(cls, index_dir: Path) -> "Catalog":
        """Load the index and metadata written by scripts/build_index.py."""
        index = faiss.read_index(str(index_dir / INDEX_FILE))
        items = json.loads((index_dir / METADATA_FILE).read_text())
        return cls(index, items)

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_dir / INDEX_FILE))
        (index_dir / METADATA_FILE).write_text(json.dumps(self.items, indent=1))

    @property
    def categories(self) -> list[str]:
        return sorted({item["category"] for item in self.items})

    def get(self, item_id: str) -> dict[str, Any] | None:
        row = self._row_by_id.get(item_id)
        return None if row is None else self.items[row]

    def vector(self, item_id: str) -> np.ndarray:
        """The stored embedding for an item (raises KeyError if unknown)."""
        return self.index.reconstruct(self._row_by_id[item_id])

    def search(
        self,
        query: np.ndarray,
        k: int = 20,
        category: str | None = None,
        exclude_ids: set[str] | None = None,
    ) -> list[Hit]:
        """Top-k items by cosine similarity, optionally restricted to one category.

        With filters we score the whole catalog: at ~5k vectors an exact scan is ~1 ms,
        so there's no need for a pre-filtered index.
        """
        exclude_ids = exclude_ids or set()
        filtered = category is not None or bool(exclude_ids)
        fetch = self.index.ntotal if filtered else min(k, self.index.ntotal)
        scores, rows = self.index.search(query.reshape(1, -1).astype(np.float32), fetch)

        hits: list[Hit] = []
        for score, row in zip(scores[0], rows[0]):
            if row < 0:
                continue
            item = self.items[row]
            if category is not None and item["category"] != category:
                continue
            if item["id"] in exclude_ids:
                continue
            hits.append(Hit(item=item, score=float(score)))
            if len(hits) == k:
                break
        return hits
