"""Style-quiz options and the personalized "For you" ranking built from a user's answers.

Taste = mean CLIP text embedding of the chosen aesthetics and eras; color fit = how close an item's
dominant colors are (CIEDE2000) to the chosen color families. Both are explainable per item.
"""

from dataclasses import dataclass

import numpy as np

from app.services.board import STYLE_WORDS
from app.services.catalog import Catalog
from app.services.color import delta_e_2000, hex_to_rgb, rgb_to_lab
from app.services.color_search import ColorIndex
from app.services.embedder import Embedder

COLOR_FAMILIES: dict[str, list[str]] = {
    "neutrals": ["#f5f5f0", "#d8c8b0", "#8a8a8a", "#1a1a1a", "#c3a27a"],
    "brights": ["#e60023", "#ff7a00", "#f5d000", "#00a651", "#0072ce", "#e5007e"],
    "pastels": ["#f6c6d0", "#cfe3f5", "#d9f0d3", "#e6dcf5", "#fff2b3"],
    "darks": ["#1b2a4a", "#4a1020", "#1f3d2b", "#2b2b2b", "#3d2a1e"],
    "earth tones": ["#a0522d", "#8b7d3a", "#c19a6b", "#6b4f2a", "#b5651d"],
}

ERAS: dict[str, str] = {
    "70s": "1970s fashion with flared trousers, suede, and earthy tones",
    "80s": "1980s fashion with bold shoulders and bright colors",
    "90s": "1990s fashion with slip dresses, grunge, and minimalism",
    "2000s": "2000s y2k fashion with low-rise jeans and baby tees",
    "2010s": "2010s fashion with skinny jeans, statement tops, and athleisure",
    "2020s": "2020s fashion with oversized fits and quiet luxury basics",
}

MAX_PICKS = 6
TEXT_WEIGHT = 0.7  # vs. color fit, when both are set
DE_ZERO = 40.0
TEXT_LOW, TEXT_HIGH = 0.15, 0.30


@dataclass
class Prefs:
    aesthetics: list[str]
    colors: list[str]
    eras: list[str]
    focus: str = "all"

    @property
    def is_empty(self) -> bool:
        return not (self.aesthetics or self.colors or self.eras)


def taste_prompts(prefs: Prefs) -> list[str]:
    return [f"a {a} outfit" for a in prefs.aesthetics] + [ERAS[e] for e in prefs.eras]


@dataclass
class TasteHit:
    row: int
    score: float
    text_score: float | None
    color_score: float | None


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

    prompts = taste_prompts(prefs)
    if prompts:
        taste = embedder.embed_texts(prompts).mean(0)
        taste /= np.linalg.norm(taste)
        cos = catalog.index.reconstruct_n(0, n) @ taste
        text_score = np.clip((cos - TEXT_LOW) / (TEXT_HIGH - TEXT_LOW), 0, 1)
        parts.append((TEXT_WEIGHT if prefs.colors else 1.0, text_score))

    if prefs.colors:
        palette = [rgb_to_lab(np.array(hex_to_rgb(h))) for fam in prefs.colors for h in COLOR_FAMILIES[fam]]
        best = np.full(n, np.inf)
        for target in palette:
            de = delta_e_2000(color_index.labs, np.broadcast_to(target, color_index.labs.shape))
            weighted = np.where(color_index.weights > 0, de + 10 * (1 - color_index.weights), np.inf)
            best = np.minimum(best, weighted.min(1))
        color_score = np.clip(1 - best / DE_ZERO, 0, 1)
        parts.append((1 - TEXT_WEIGHT if prompts else 1.0, color_score))

    combined = sum(w * s for w, s in parts) if parts else np.zeros(n)
    mask = np.array([not item["kids"] for item in catalog.items])
    if allowed is not None:
        mask &= allowed
    combined = np.where(mask, combined, -1.0)
    order = np.argsort(-combined, kind="stable")[offset : offset + k]
    return [
        TasteHit(
            int(r),
            float(combined[r]),
            None if text_score is None else float(text_score[r]),
            None if color_score is None else float(color_score[r]),
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
