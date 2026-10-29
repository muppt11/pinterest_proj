"""Menswear / womenswear / all: an *estimated* style focus, since the dataset has no gender field.

Each item gets lean = cos(image, "womenswear" prompts) - cos(image, "menswear" prompts).
Items within ±UNISEX_MARGIN are treated as unisex and shown under every focus. Measured on the
real index (2026-10-28): dresses, skirts, blouses and tops lean women in 91–100% of cases; polos,
shirts and hats lean men in 63–72%; t-shirts, pants, shoes and hoodies straddle zero.
The margin was 0.03 at first, which shared 1,666 items between the two views and made them look
alike (user feedback); 0.01 shares 539. Rankings also get a small boost toward the chosen focus.
"""

from typing import Literal

import numpy as np

from app.services.catalog import Catalog
from app.services.embedder import Embedder

Focus = Literal["all", "women", "men"]

UNISEX_MARGIN = 0.01
LEAN_SCALE = 0.08  # ~95th percentile of |lean|; used to normalize the ranking boost
PROMPTS = {
    "women": ["womenswear", "a women's clothing item", "clothing for women"],
    "men": ["menswear", "a men's clothing item", "clothing for men"],
}


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


class FocusIndex:
    """Per-item lean, computed once from the catalog vectors and two averaged text prompts."""

    def __init__(self, catalog: Catalog, embedder: Embedder) -> None:
        women = _unit(embedder.embed_texts(PROMPTS["women"]).mean(0))
        men = _unit(embedder.embed_texts(PROMPTS["men"]).mean(0))
        vectors = catalog.index.reconstruct_n(0, catalog.index.ntotal)
        self.lean = vectors @ women - vectors @ men
        self.ids = [item["id"] for item in catalog.items]

    def allowed(self, focus: Focus) -> np.ndarray:
        """Boolean mask of items shown under this focus (unisex items are always shown)."""
        if focus == "women":
            return self.lean >= -UNISEX_MARGIN
        if focus == "men":
            return self.lean <= UNISEX_MARGIN
        return np.ones(len(self.lean), dtype=bool)

    def excluded_ids(self, focus: Focus) -> set[str]:
        mask = self.allowed(focus)
        return {i for i, ok in zip(self.ids, mask, strict=False) if not ok}

    def boost(self, focus: Focus) -> np.ndarray | None:
        """Per-row -1..1 score: how strongly each item leans toward `focus` (None for "all")."""
        if focus == "all":
            return None
        sign = 1.0 if focus == "women" else -1.0
        return np.clip(sign * self.lean / LEAN_SCALE, -1, 1)

    def label(self, row: int) -> str:
        lean = self.lean[row]
        return "womenswear" if lean > UNISEX_MARGIN else "menswear" if lean < -UNISEX_MARGIN else "unisex"
