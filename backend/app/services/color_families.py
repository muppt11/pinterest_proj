"""Color families defined by perceptual rules in CIE Lab (lightness L*, chroma C*, hue angle h).

An item belongs to a family when its *main* color (the largest area of its center crop) does.
Rules, not nearest-swatch matching: "pastel" means light and softly colored, whatever the hue.
"""

import numpy as np

FAMILY_SWATCHES: dict[str, list[str]] = {
    "neutrals": ["#f5f5f0", "#d8c8b0", "#8a8a8a", "#1a1a1a", "#c3a27a"],
    "brights": ["#e60023", "#ff7a00", "#f5d000", "#00a651", "#0072ce", "#e5007e"],
    "pastels": ["#f6c6d0", "#cfe3f5", "#d9f0d3", "#e6dcf5", "#fff2b3"],
    "darks": ["#1b2a4a", "#4a1020", "#1f3d2b", "#2b2b2b", "#3d2a1e"],
    "earth tones": ["#a0522d", "#8b7d3a", "#c19a6b", "#6b4f2a", "#b5651d"],
}


def lch(lab: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    L, a, b = np.moveaxis(np.asarray(lab, dtype=np.float64), -1, 0)
    return L, np.hypot(a, b), np.degrees(np.arctan2(b, a)) % 360


def family_masks(lab: np.ndarray) -> dict[str, np.ndarray]:
    """Boolean membership per family for an array of Lab colors (families can overlap)."""
    L, C, h = lch(lab)
    warm = (h >= 30) & (h <= 100)  # oranges, browns, yellows, olives
    return {
        "darks": L < 30,
        "neutrals": (C < 10) | (warm & (C < 28) & (L >= 55)),  # greys/black/white, plus beige and camel
        # light and visibly tinted; warm low-chroma tones (beige, cream) count as neutrals instead
        "pastels": (L >= 74) & (C >= 12) & (C <= 45) & ~(warm & (C < 22)),
        "brights": (C >= 45) & (L >= 35) & (L <= 85),
        "earth tones": warm & (C >= 15) & (C <= 55) & (L >= 25) & (L < 68),
    }


def main_lab(items: list[dict]) -> np.ndarray:
    """(n, 3) Lab of each item's heaviest color; NaN when an item has no colors."""
    out = np.full((len(items), 3), np.nan)
    for i, item in enumerate(items):
        colors = item.get("colors") or []
        if colors:
            out[i] = max(colors, key=lambda c: c["weight"])["lab"]
    return out


def items_in_families(items: list[dict], families: list[str]) -> np.ndarray:
    """(n,) True where the item's main color is in any of `families`."""
    lab = main_lab(items)
    known = ~np.isnan(lab[:, 0])
    masks = family_masks(np.nan_to_num(lab))
    hit = np.zeros(len(items), dtype=bool)
    for f in families:
        hit |= masks[f]
    return hit & known
