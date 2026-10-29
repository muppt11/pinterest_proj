"""The indexed clothing catalog: FAISS vectors plus per-item metadata."""

import json
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Never import torch in a process that uses this module: see ProcessEmbedder in embedder.py.
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
        # Repost groups (feature 6). Each item dict gets a derived "repost" entry for the API to show.
        from app.services.reposts import RepostIndex

        self.reposts = RepostIndex(items, self.matrix if items and "phash" in items[0] else None)
        for item in items:
            item["repost"] = self.reposts.info(item["id"])

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
        stored = [{k: v for k, v in item.items() if k != "repost"} for item in self.items]  # derived at load
        (index_dir / METADATA_FILE).write_text(json.dumps(stored, indent=1))

    @property
    def matrix(self) -> np.ndarray:
        """All item vectors as one (n, dim) array, cached (for whole-catalog scoring)."""
        if getattr(self, "_matrix", None) is None:
            self._matrix = self.index.reconstruct_n(0, self.index.ntotal)
        return self._matrix

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
        categories: Collection[str] | None = None,
        kids: bool | None = None,
        collapse_reposts: bool = True,
        bias: np.ndarray | None = None,
    ) -> list[Hit]:
        """Top-k items by cosine similarity, optionally restricted by category (one or a set) and kids flag.
        Near-duplicate reposts collapse into one hit for their group's credited original.

        With filters we score the whole catalog: at ~5k vectors an exact scan is ~1 ms,
        so there's no need for a pre-filtered index.
        """
        exclude_ids = exclude_ids or set()
        allowed = set(categories) if categories is not None else None
        if category is not None:
            allowed = {category} if allowed is None else allowed & {category}
        filtered = allowed is not None or bool(exclude_ids) or kids is not None or bool(self.reposts.groups)
        fetch = self.index.ntotal if filtered else min(k, self.index.ntotal)
        if bias is not None:
            # Whole-catalog scoring with a per-item bias (e.g. a style-focus boost); ~1 ms at this size.
            all_scores = self.matrix @ query.astype(np.float32) + bias
            order = np.argsort(-all_scores, kind="stable")
            scores, rows = all_scores[order][None, :], order[None, :]
        else:
            scores, rows = self.index.search(query.reshape(1, -1).astype(np.float32), fetch)

        hits: list[Hit] = []
        seen_groups: set[int] = set()
        for score, row in zip(scores[0], rows[0]):
            if row < 0:
                continue
            item = self.items[row]
            if allowed is not None and item["category"] not in allowed:
                continue
            if kids is not None and item["kids"] != kids:
                continue
            if item["id"] in exclude_ids:
                continue
            if collapse_reposts and (group := self.reposts.group_of.get(item["id"])) is not None:
                if group in seen_groups:
                    continue
                seen_groups.add(group)
                rep = self.get(self.reposts.representative(item["id"]))
                if rep is not None and rep["id"] not in exclude_ids:
                    item = rep
            hits.append(Hit(item=item, score=float(score)))
            if len(hits) == k:
                break
        return hits
