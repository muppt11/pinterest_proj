"""Build the catalog: FashionCLIP embeddings, a FAISS index, and metadata.json.

Metadata holds only fields the dataset actually has (id, label, sender_id, kids)
plus the image file name and pixel size, which the masonry grid needs for layout.

Usage (from backend/): uv run python ../scripts/build_index.py [--limit N]
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.catalog import Catalog  # noqa: E402
from app.services.embedder import FashionClipEmbedder  # noqa: E402

# Dataset labels that mean "not a usable clothing photo", per the dataset's own annotation scheme.
EXCLUDED_LABELS = {"Skip", "Not sure"}
BATCH = 64


def load_rows(dataset_dir: Path) -> list[dict[str, str]]:
    with (dataset_dir / "images.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    usable = [r for r in rows if r["label"] not in EXCLUDED_LABELS and (dataset_dir / "images" / f"{r['image']}.jpg").exists()]
    print(f"{len(rows)} rows in images.csv, {len(usable)} usable after dropping {sorted(EXCLUDED_LABELS)} and missing files")
    return usable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="index only the first N images (quick smoke test)")
    args = parser.parse_args()

    settings = get_settings()
    dataset_dir = settings.images_dir.parent
    if not (dataset_dir / "images.csv").exists():
        sys.exit("Dataset not found. Run: python scripts/download_dataset.py")

    rows = load_rows(dataset_dir)[: args.limit]
    embedder = FashionClipEmbedder()
    print(f"Embedding {len(rows)} images on {embedder.device} (dim={embedder.dim})")

    items: list[dict] = []
    vectors: list[np.ndarray] = []
    start = time.time()
    for i in range(0, len(rows), BATCH):
        batch_rows = rows[i : i + BATCH]
        images = []
        for row in batch_rows:
            with Image.open(dataset_dir / "images" / f"{row['image']}.jpg") as img:
                images.append(img.convert("RGB"))
                items.append(
                    {
                        "id": row["image"],
                        "category": row["label"],
                        "image_file": f"{row['image']}.jpg",
                        "sender_id": row["sender_id"],
                        "kids": row["kids"] == "True",
                        "width": img.width,
                        "height": img.height,
                    }
                )
        vectors.append(embedder.embed_images(images))
        done = min(i + BATCH, len(rows))
        print(f"\r  {done}/{len(rows)}  ({done / (time.time() - start):.0f} img/s)", end="", flush=True)
    print()

    catalog = Catalog.from_vectors(np.concatenate(vectors), items)
    catalog.save(settings.index_dir)
    print(f"Wrote {catalog.index.ntotal} vectors to {settings.index_dir} ({len(catalog.categories)} categories)")


if __name__ == "__main__":
    main()
