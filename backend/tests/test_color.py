"""Color conversion, CIEDE2000 against published reference values, and dominant-color extraction."""

import numpy as np
import pytest
from PIL import Image

from app.services.color import color_distance, delta_e_2000, dominant_colors, hex_to_rgb, rgb_to_lab

# A subset of the test pairs published with Sharma, Wu & Dalal (2005), "The CIEDE2000 Color-Difference
# Formula: Implementation Notes, Supplementary Test Data, and Mathematical Observations".
SHARMA_PAIRS = [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
    ((50.0, 2.8361, -74.0200), (50.0, 0.0, -82.7485), 3.4412),
    ((50.0, -1.3802, -84.2814), (50.0, 0.0, -82.7485), 1.0000),
    ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
    ((50.0, 2.5, 0.0), (50.0, 0.0, -2.5), 4.3065),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((50.0, 2.5, 0.0), (61.0, -5.0, 29.0), 22.8977),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


@pytest.mark.parametrize("lab1,lab2,expected", SHARMA_PAIRS)
def test_ciede2000_matches_reference(lab1, lab2, expected) -> None:  # type: ignore[no-untyped-def]
    assert delta_e_2000(np.array(lab1), np.array(lab2)) == pytest.approx(expected, abs=1e-4)
    assert delta_e_2000(np.array(lab2), np.array(lab1)) == pytest.approx(expected, abs=1e-4)  # symmetric


def test_rgb_to_lab_known_values() -> None:
    np.testing.assert_allclose(rgb_to_lab([255, 255, 255]), [100, 0, 0], atol=0.01)
    np.testing.assert_allclose(rgb_to_lab([0, 0, 0]), [0, 0, 0], atol=0.01)
    np.testing.assert_allclose(rgb_to_lab([255, 0, 0]), [53.24, 80.09, 67.20], atol=0.05)


def test_hex_parsing() -> None:
    assert hex_to_rgb("#9CAF88") == (156, 175, 136)
    assert hex_to_rgb("000000") == (0, 0, 0)
    for bad in ["#fff", "zzzzzz", "#12345678", ""]:
        with pytest.raises(ValueError):
            hex_to_rgb(bad)


def two_tone(main: tuple[int, int, int], accent: tuple[int, int, int]) -> Image.Image:
    """100x100 image: background border (ignored by the center crop), a main color, and an accent stripe."""
    img = Image.new("RGB", (100, 100), (240, 240, 240))
    img.paste(Image.new("RGB", (60, 60), main), (20, 20))
    img.paste(Image.new("RGB", (60, 12), accent), (20, 60))
    return img


def test_dominant_colors_ignore_border_and_rank_by_area() -> None:
    colors = dominant_colors(two_tone((20, 60, 160), (230, 200, 30)))
    assert 1 <= len(colors) <= 5
    top = colors[0]
    assert delta_e_2000(np.array(top["lab"]), rgb_to_lab([20, 60, 160])) < 3
    assert top["weight"] > 0.6
    assert sum(c["weight"] for c in colors) == pytest.approx(1.0, abs=0.06)
    assert all(delta_e_2000(np.array(c["lab"]), rgb_to_lab([240, 240, 240])) > 5 for c in colors[:2])


def test_color_distance_prefers_main_color_over_small_accent() -> None:
    navy_with_yellow = dominant_colors(two_tone((20, 60, 160), (230, 200, 30)))
    yellow_with_navy = dominant_colors(two_tone((230, 200, 30), (20, 60, 160)))
    yellow = rgb_to_lab([230, 200, 30])
    assert color_distance(yellow, yellow_with_navy) < color_distance(yellow, navy_with_yellow)
