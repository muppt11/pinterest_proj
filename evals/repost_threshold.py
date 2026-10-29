"""Measure pHash distances for known duplicate pairs vs. unrelated pairs on real catalog photos,
and write evals/reports/repost_threshold.md. The REPOST_THRESHOLD in app/services/reposts.py is
chosen from this report.

Usage (from backend/): uv run python ../evals/repost_threshold.py [--n 300]
"""

import argparse
import io
import json
import random
import sys
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.reposts import REPOST_THRESHOLD, hamming, hashes_to_uint64, phash_hex  # noqa: E402


def jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def crop(img: Image.Image, frac: float) -> Image.Image:
    dx, dy = int(img.width * frac), int(img.height * frac)
    return img.crop((dx, dy, img.width - dx, img.height - dy))


TRANSFORMS = {
    "resized 50%": lambda im: im.resize((im.width // 2, im.height // 2)),
    "cropped 5% per side": lambda im: crop(im, 0.05),
    "cropped 10% per side": lambda im: crop(im, 0.10),
    "JPEG quality 20": lambda im: jpeg(im, 20),
    "color-shifted (+25% bright, -40% sat)": lambda im: ImageEnhance.Color(ImageEnhance.Brightness(im).enhance(1.25)).enhance(0.6),
    "all of the above": lambda im: jpeg(ImageEnhance.Brightness(crop(im.resize((im.width // 2, im.height // 2)), 0.05)).enhance(1.2), 30),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=300)
    args = parser.parse_args()

    settings = get_settings()
    items = json.loads((settings.index_dir / "metadata.json").read_text())
    rng = random.Random(0)
    sample = rng.sample(items, args.n)

    positives: dict[str, list[int]] = {name: [] for name in TRANSFORMS}
    base_hashes = []
    for item in sample:
        with Image.open(settings.images_dir / item["image_file"]) as im:
            im = im.convert("RGB")
            h0 = phash_hex(im)
            base_hashes.append(h0)
            for name, fn in TRANSFORMS.items():
                a, b = hashes_to_uint64([h0, phash_hex(fn(im))])
                positives[name].append(int(hamming(a, b)))

    h = hashes_to_uint64(base_hashes)
    negatives = [int(hamming(h[i], h[j])) for i in range(len(h)) for j in range(i + 1, len(h))]
    neg = np.array(negatives)
    all_pos = np.concatenate([np.array(v) for v in positives.values()])

    lines = [
        f"# Repost threshold report ({date.today().isoformat()})",
        "",
        f"{args.n} random catalog photos, each transformed {len(TRANSFORMS)} ways (known duplicates), "
        f"vs. {len(negatives):,} pairs of different photos. Distances are Hamming bits out of 64.",
        "",
        "| Pair type | median | 95th pct | max | within threshold |",
        "|---|---|---|---|---|",
    ]
    for name, d in positives.items():
        d = np.array(d)
        lines.append(f"| {name} | {np.median(d):.0f} | {np.percentile(d, 95):.0f} | {d.max()} | {(d <= REPOST_THRESHOLD).mean():.1%} |")
    lines.append(
        f"| **different photos** | {np.median(neg):.0f} | 5th pct {np.percentile(neg, 5):.0f} | min {neg.min()} | "
        f"{(neg <= REPOST_THRESHOLD).mean():.3%} (false matches) |"
    )
    lines += ["", "## Threshold sweep", "", "| threshold | recall (all transforms) | false-match rate (different photos) |", "|---|---|---|"]
    for t in range(4, 21, 2):
        lines.append(f"| {t} | {(all_pos <= t).mean():.1%} | {(neg <= t).mean():.3%} |")
    lines += ["", f"Current `REPOST_THRESHOLD` = **{REPOST_THRESHOLD}**."]

    out = REPO / "evals" / "reports" / "repost_threshold.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
