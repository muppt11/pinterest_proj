"""Add repost metadata (pHash, EXIF DateTimeOriginal, ingestion time) to an existing index's
metadata.json without re-embedding. New builds get these from build_index.py directly.

Usage (from backend/): uv run python ../scripts/add_repost_metadata.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.reposts import exif_datetime_original, phash_hex  # noqa: E402


def main() -> None:
    settings = get_settings()
    path = settings.index_dir / "metadata.json"
    items = json.loads(path.read_text())
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for n, item in enumerate(items, 1):
        with Image.open(settings.images_dir / item["image_file"]) as im:
            item["exif_datetime_original"] = exif_datetime_original(im)  # read before any conversion
            item["phash"] = phash_hex(im)
        item.setdefault("ingested_at", now)
        if n % 500 == 0:
            print(f"  {n}/{len(items)}", flush=True)
    path.write_text(json.dumps(items, indent=1))
    with_exif = sum(1 for i in items if i["exif_datetime_original"])
    print(f"Added pHash to {len(items)} items ({with_exif} with EXIF DateTimeOriginal).")


if __name__ == "__main__":
    main()
