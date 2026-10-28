"""Dominant colors in CIE Lab and perceptual color distance (CIEDE2000)."""

import numpy as np
from PIL import Image

from app.services.board import kmeans

# Garments are usually centered; the outer border is mostly floor, wall, or hanger.
CENTER_CROP = 0.6
SAMPLE_SIZE = 40  # pixels per side after downsampling
N_CLUSTERS = 5
MIN_WEIGHT = 0.05  # drop clusters covering less than 5% of the crop
MIN_COLORS, MAX_COLORS = 3, 5

# sRGB (D65) -> XYZ matrix and D65 reference white.
_RGB_TO_XYZ = np.array(
    [[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]]
)
_WHITE = np.array([0.95047, 1.0, 1.08883])


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB values in 0..255, shape (..., 3) -> CIE Lab (D65), shape (..., 3)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = linear @ _RGB_TO_XYZ.T / _WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """'#a1b2c3' or 'a1b2c3' -> (161, 178, 195). Raises ValueError for anything else."""
    h = value.lstrip("#")
    if len(h) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in h):
        raise ValueError(f"not a 6-digit hex color: {value!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def delta_e_2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 color difference (Sharma, Wu & Dalal 2005), broadcasting over leading dims.

    Roughly: < 1 is imperceptible, 2–10 is similar at a glance, > 25 is a clearly different color.
    """
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, dtype=np.float64), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, dtype=np.float64), -1, 0)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    C_bar7 = ((C1 + C2) / 2) ** 7
    G = 0.5 * (1 - np.sqrt(C_bar7 / (C_bar7 + 25**7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360

    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))

    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    hsum = h1p + h2p
    hbp = np.where(
        C1p * C2p == 0,
        hsum,
        np.where(np.abs(h1p - h2p) <= 180, hsum / 2, np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)),
    )
    T = (
        1
        - 0.17 * np.cos(np.radians(hbp - 30))
        + 0.24 * np.cos(np.radians(2 * hbp))
        + 0.32 * np.cos(np.radians(3 * hbp + 6))
        - 0.20 * np.cos(np.radians(4 * hbp - 63))
    )
    d_theta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp**7 / (Cbp**7 + 25**7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * d_theta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def dominant_colors(image: Image.Image) -> list[dict]:
    """3–5 dominant colors of the image's center, heaviest first: [{hex, lab, weight}, ...]."""
    img = image.convert("RGB")
    w, h = img.size
    dx, dy = int(w * (1 - CENTER_CROP) / 2), int(h * (1 - CENTER_CROP) / 2)
    img = img.crop((dx, dy, w - dx, h - dy)).resize((SAMPLE_SIZE, SAMPLE_SIZE), Image.Resampling.BILINEAR)
    rgb = np.asarray(img, dtype=np.float64).reshape(-1, 3)
    lab = rgb_to_lab(rgb)

    k = min(N_CLUSTERS, len(np.unique(rgb, axis=0)))
    labels = np.zeros(len(lab), dtype=int) if k <= 1 else kmeans(lab, k, restarts=3, iterations=30)[0]
    clusters = []
    for j in np.unique(labels):
        members = labels == j
        mean_rgb = rgb[members].mean(0)
        clusters.append(
            {
                "hex": "#{:02x}{:02x}{:02x}".format(*np.clip(np.round(mean_rgb), 0, 255).astype(int)),
                "lab": [round(float(v), 2) for v in lab[members].mean(0)],
                "weight": round(float(members.mean()), 4),
            }
        )
    clusters.sort(key=lambda c: -c["weight"])
    kept = [c for c in clusters if c["weight"] >= MIN_WEIGHT]
    return (kept if len(kept) >= MIN_COLORS else clusters[:MIN_COLORS])[:MAX_COLORS]


def color_distance(target_lab: np.ndarray, colors: list[dict]) -> float:
    """How far an item is from a target color: the Delta E to its closest dominant color,
    lightly penalized when that color covers little of the item (so a tiny trim doesn't win)."""
    labs = np.array([c["lab"] for c in colors])
    weights = np.array([c["weight"] for c in colors])
    de = delta_e_2000(labs, np.broadcast_to(target_lab, labs.shape))
    return float(np.min(de + 10 * (1 - weights)))
