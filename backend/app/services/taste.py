"""Style-quiz options and the personalized "For you" ranking built from a user's answers.

Taste = mean CLIP text embedding of the chosen aesthetics and eras; color fit = how close an item's
dominant colors are (CIEDE2000) to the chosen color families. Both are explainable per item.
"""

from dataclasses import dataclass

import numpy as np

from app.services.aesthetics import ERA_PHRASES, STYLE_WORDS, bank_for, diversified_order, phrases_for
from app.services.catalog import Catalog
from app.services.color_families import FAMILY_SWATCHES as COLOR_FAMILIES
from app.services.color_families import items_in_families
from app.services.color import delta_e_2000, hex_to_rgb, rgb_to_lab
from app.services.color_search import ColorIndex
from app.services.embedder import Embedder


ERAS = ERA_PHRASES  # quiz era keys -> signature garments

MAX_PICKS = 6
TEXT_WEIGHT = 0.7  # vs. color fit, when both are set (after the color-family filter)
MIN_FAMILY_ITEMS = 24  # below this, fall back to blending instead of filtering
DE_ZERO = 40.0


@dataclass
class Prefs:
    aesthetics: list[str]
    colors: list[str]
    eras: list[str]
    focus: str = "all"

    @property
    def is_empty(self) -> bool:
        return not (self.aesthetics or self.colors or self.eras)


@dataclass
class TasteHit:
    row: int
    score: float
    text_score: float | None
    color_score: float | None
    phrase: str | None = None  # signature garment of the chosen aesthetics/eras this item matched


def for_you(
    catalog: Catalog,
    color_index: ColorIndex,
    embedder: Embedder,
    prefs: Prefs,
    k: int = 50,
    offset: int = 0,
    allowed: np.ndarray | None = None,
) -> list[TasteHit]:
    """Catalog ranked by the user's quiz answers. Kids' items are excluded."""
    n = catalog.index.ntotal
    text_score = color_score = None
    parts: list[tuple[float, np.ndarray]] = []

    phrases = phrases_for(prefs.aesthetics, prefs.eras)
    style = None
    if phrases:
        style = bank_for(embedder).score(catalog.matrix, phrases)
        text_score = style.normalized()
        parts.append((TEXT_WEIGHT if prefs.colors else 1.0, text_score))

    if prefs.colors:
        palette = [rgb_to_lab(np.array(hex_to_rgb(h))) for fam in prefs.colors for h in COLOR_FAMILIES[fam]]
        best = np.full(n, np.inf)
        for target in palette:
            de = delta_e_2000(color_index.labs, np.broadcast_to(target, color_index.labs.shape))
            weighted = np.where(color_index.weights > 0, de + 10 * (1 - color_index.weights), np.inf)
            best = np.minimum(best, weighted.min(1))
        color_score = np.clip(1 - best / DE_ZERO, 0, 1)
        parts.append((1 - TEXT_WEIGHT if phrases else 1.0, color_score))

    combined = sum(w * s for w, s in parts) if parts else np.zeros(n)
    mask = np.array([not item["kids"] for item in catalog.items])
    if allowed is not None:
        mask &= allowed
    if prefs.colors:
        # Color families are a filter: an item qualifies when its *main* color is in a chosen family
        # (Lab rules, services/color_families.py). Blending alone let dark items through on style.
        in_family = items_in_families(catalog.items, prefs.colors)
        if (mask & in_family).sum() >= MIN_FAMILY_ITEMS:
            mask &= in_family
    combined = np.where(mask, combined, -1.0)
    if style is not None:
        ranked = diversified_order(combined, style.phrase_of, eligible=combined >= 0, pool=max(400, (offset + k) * 3))
    else:
        ranked = [int(r) for r in np.argsort(-combined, kind="stable")[: (offset + k) * 3]]
    order = catalog.reposts.dedupe_rows(ranked, [i["id"] for i in catalog.items])[offset : offset + k]
    return [
        TasteHit(
            int(r),
            float(combined[r]),
            None if text_score is None else float(text_score[r]),
            None if color_score is None else float(color_score[r]),
            None if style is None else style.phrases[int(style.phrase_of[r])],
        )
        for r in order
        if combined[r] >= 0
    ]


def quiz_options() -> dict:
    return {
        "aesthetics": STYLE_WORDS,
        "colors": COLOR_FAMILIES,
        "eras": list(ERAS),
        "focus": ["all", "women", "men"],
        "max_picks": MAX_PICKS,
    }
