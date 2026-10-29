"""Build the catalog: FashionCLIP embeddings, a FAISS index, and metadata.json.

Metadata holds only fields the dataset actually has (id, label, sender_id, kids)
plus values derived from each image: file name, pixel size (for masonry layout), and
3–5 dominant colors in CIE Lab (for color search).

Usage (from backend/): uv run python ../scripts/build_index.py [--limit N]
"""

import argparse
from datetime import datetime, timezone
import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.color import dominant_colors  # noqa: E402
from app.services.reposts import exif_datetime_original, phash_hex  # noqa: E402
from app.services.embedder import ProcessEmbedder  # noqa: E402

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
    embedder = ProcessEmbedder(settings.model_dir)  # torch in a worker; this process uses faiss
    print(f"Embedding {len(rows)} images (dim={embedder.dim})")

    ingested_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    items: list[dict] = []
    vectors: list[np.ndarray] = []
    start = time.time()
    for i in range(0, len(rows), BATCH):
        batch_rows = rows[i : i + BATCH]
        images = []
        for row in batch_rows:
            with Image.open(dataset_dir / "images" / f"{row['image']}.jpg") as img:
                exif_date = exif_datetime_original(img)  # read before converting, which drops EXIF
                rgb = img.convert("RGB")
                images.append(rgb)
                items.append(
                    {
                        "id": row["image"],
                        "category": row["label"],
                        "image_file": f"{row['image']}.jpg",
                        "sender_id": row["sender_id"],
                        "kids": row["kids"] == "True",
                        "width": img.width,
                        "height": img.height,
                        "colors": dominant_colors(rgb),
                        "phash": phash_hex(rgb),
                        "exif_datetime_original": exif_date,
                        "ingested_at": ingested_at,
                    }
                )
        vectors.append(embedder.embed_images(images))
        done = min(i + BATCH, len(rows))
        print(f"\r  {done}/{len(rows)}  ({done / (time.time() - start):.0f} img/s)", end="", flush=True)
    print()

    embedder.close()
    # Imported here, not at the top: the spawned embedding worker re-imports this script,
    # and faiss must never load in the torch process (see ProcessEmbedder).
    from app.services.catalog import Catalog

    catalog = Catalog.from_vectors(np.concatenate(vectors), items)
    catalog.save(settings.index_dir)
    print(f"Wrote {catalog.index.ntotal} vectors to {settings.index_dir} ({len(catalog.categories)} categories)")


if __name__ == "__main__":
    main()
