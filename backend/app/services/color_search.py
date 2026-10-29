"""Rank the catalog by perceptual color match (CIEDE2000), optionally blended with a CLIP text score."""

from dataclasses import dataclass

import numpy as np

from app.services.aesthetics import PhraseScores, diversified_order
from app.services.catalog import Catalog
from app.services.color import delta_e_2000, hex_to_rgb, rgb_to_lab

MAX_COLORS = 5
# Small-coverage colors (a button, a stripe) get a penalty so they don't win on their own.
COVERAGE_PENALTY = 10.0
# Delta E at which the color score reaches 0. ~25 is "clearly a different color".
DE_ZERO = 40.0
# Cosine range FashionCLIP text scores actually occupy on this catalog (see README, feature 1).
TEXT_LOW, TEXT_HIGH = 0.15, 0.30

# Named colors for building human-readable queries ("burgundy t-shirt"). Approximate sRGB values.
COLOR_NAMES: dict[str, tuple[int, int, int]] = {
    "black": (20, 20, 20), "charcoal": (60, 60, 64), "gray": (128, 128, 128), "light gray": (200, 200, 200),
    "white": (245, 245, 245), "cream": (240, 230, 205), "beige": (215, 195, 160), "tan": (190, 155, 110),
    "camel": (195, 150, 95), "brown": (110, 70, 40), "chocolate brown": (75, 45, 30), "khaki": (170, 160, 115),
    "olive": (110, 110, 50), "sage green": (155, 175, 135), "green": (40, 140, 60), "forest green": (35, 80, 45),
    "mint": (170, 225, 195), "teal": (0, 120, 120), "turquoise": (60, 200, 200), "light blue": (160, 200, 230),
    "denim blue": (75, 105, 150), "blue": (40, 80, 190), "navy": (25, 35, 75), "lavender": (190, 170, 220),
    "purple": (110, 50, 140), "plum": (95, 40, 75), "pink": (240, 160, 185), "hot pink": (230, 50, 140),
    "blush": (230, 190, 185), "red": (200, 30, 40), "burgundy": (110, 20, 40), "coral": (245, 120, 100),
    "orange": (240, 130, 30), "rust": (170, 75, 35), "mustard": (210, 165, 40), "yellow": (245, 215, 50),
}
_NAME_LABS = {name: rgb_to_lab(rgb) for name, rgb in COLOR_NAMES.items()}


def color_name(lab: np.ndarray) -> str:
    """Closest named color by CIEDE2000."""
    return min(_NAME_LABS, key=lambda n: float(delta_e_2000(lab, _NAME_LABS[n])))


@dataclass
class ColorHit:
    row: int
    combined: float  # 0..1
    color_score: float  # 0..1
    delta_e: float  # best (penalized) Delta E to the target
    matched_hex: str  # the item's dominant color that matched
    text_score: float | None  # 0..1 when a text/style query was given
    phrase: str | None = None  # garment phrase matched, for aesthetic queries


class ColorIndex:
    """Every item's dominant colors as padded arrays, so one vectorized CIEDE2000 call scores the catalog."""

    def __init__(self, catalog: Catalog) -> None:
        n = len(catalog.items)
        self.labs = np.zeros((n, MAX_COLORS, 3))
        self.weights = np.zeros((n, MAX_COLORS))
        self.hexes: list[list[str]] = []
        for i, item in enumerate(catalog.items):
            colors = item.get("colors", [])[:MAX_COLORS]
            for j, c in enumerate(colors):
                self.labs[i, j] = c["lab"]
                self.weights[i, j] = c["weight"]
            self.hexes.append([c["hex"] for c in colors])
        self.has_color = self.weights.sum(1) > 0

    def distances(self, target_lab: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(n,) best penalized Delta E per item and (n,) index of the matching color."""
        de = delta_e_2000(self.labs, np.broadcast_to(target_lab, self.labs.shape))
        penalized = np.where(self.weights > 0, de + COVERAGE_PENALTY * (1 - self.weights), np.inf)
        best = penalized.argmin(1)
        return penalized[np.arange(len(best)), best], best


def color_index(catalog: Catalog) -> ColorIndex:
    """Built once per loaded catalog and cached on it."""
    cached = getattr(catalog, "_color_index", None)
    if cached is None:
        cached = ColorIndex(catalog)
        catalog._color_index = cached  # type: ignore[attr-defined]
    return cached


def color_search(
    catalog: Catalog,
    index: ColorIndex,
    hex_color: str,
    k: int = 30,
    text_vector: np.ndarray | None = None,
    color_weight: float = 0.6,
    kids: bool | None = None,
    allowed: np.ndarray | None = None,
    style: PhraseScores | None = None,
    focus_boost: np.ndarray | None = None,
) -> list[ColorHit]:
    """Top-k items by color, blended with free text (`text_vector`) or an aesthetic's garment phrases
    (`style`, results rotate across the phrases). Raises ValueError for a malformed hex."""
    target = rgb_to_lab(np.array(hex_to_rgb(hex_color)))
    de, which = index.distances(target)
    color_score = np.clip(1 - de / DE_ZERO, 0, 1)

    text_score = None
    combined = color_score
    if style is not None:
        text_score = style.normalized()
        combined = color_weight * color_score + (1 - color_weight) * text_score
    elif text_vector is not None:
        cos = catalog.matrix @ text_vector
        text_score = np.clip((cos - TEXT_LOW) / (TEXT_HIGH - TEXT_LOW), 0, 1)
        combined = color_weight * color_score + (1 - color_weight) * text_score

    if focus_boost is not None:
        combined = combined + 0.15 * focus_boost  # lean toward the chosen style focus
    mask = index.has_color.copy()
    if allowed is not None:
        mask &= allowed
    if kids is not None:
        mask &= np.array([item["kids"] == kids for item in catalog.items])
    combined = np.where(mask, combined, -1)
    if style is not None:
        ranked = diversified_order(combined, style.phrase_of, eligible=combined >= 0)[: k * 3]
    else:
        ranked = [int(r) for r in np.argsort(-combined, kind="stable")[: k * 3]]
    order = catalog.reposts.dedupe_rows(ranked, [i["id"] for i in catalog.items])[:k]
    return [
        ColorHit(
            row=int(r),
            combined=float(combined[r]),
            color_score=float(color_score[r]),
            delta_e=float(de[r]),
            matched_hex=index.hexes[r][which[r]],
            text_score=None if text_score is None else float(text_score[r]),
            phrase=None if style is None else style.phrases[int(style.phrase_of[r])],
        )
        for r in order
        if combined[r] >= 0
    ]
