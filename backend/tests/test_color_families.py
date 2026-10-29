"""Color family rules (Lab lightness/chroma/hue)."""

import numpy as np
import pytest

from app.services.color import rgb_to_lab
from app.services.color_families import family_masks, items_in_families


def families_of(hex_color: str) -> set[str]:
    rgb = np.array([int(hex_color[i : i + 2], 16) for i in (1, 3, 5)])
    masks = family_masks(rgb_to_lab(rgb)[None])
    return {f for f, m in masks.items() if m[0]}


@pytest.mark.parametrize(
    "hex_color,expected,never",
    [
        ("#111111", {"darks", "neutrals"}, {"pastels", "brights"}),
        ("#d9c0e9", {"pastels"}, {"darks", "neutrals"}),  # lilac
        ("#a7d4c0", {"pastels"}, {"darks"}),  # mint
        ("#d5c5b4", {"neutrals"}, {"pastels"}),  # beige is neutral, not pastel
        ("#e60023", {"brights"}, {"pastels", "neutrals"}),
        ("#6c452c", {"earth tones"}, {"pastels", "brights"}),  # brown
        ("#1b2a4a", {"darks"}, {"pastels", "brights"}),  # navy
    ],
)
def test_family_rules(hex_color: str, expected: set[str], never: set[str]) -> None:
    got = families_of(hex_color)
    assert expected <= got, (hex_color, got)
    assert not (never & got), (hex_color, got)


def test_items_use_their_main_color() -> None:
    def item(*colors):  # type: ignore[no-untyped-def]
        return {"colors": [{"lab": list(rgb_to_lab(np.array(rgb))), "weight": w} for rgb, w in colors]}

    pastel_with_black_trim = item(((217, 192, 233), 0.8), ((17, 17, 17), 0.2))
    black_with_pastel_trim = item(((17, 17, 17), 0.8), ((217, 192, 233), 0.2))
    assert list(items_in_families([pastel_with_black_trim, black_with_pastel_trim, {"colors": []}], ["pastels"])) == [True, False, False]
