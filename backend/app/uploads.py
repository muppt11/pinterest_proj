"""Validation for user-uploaded images (type, size, and decompression-bomb limits)."""

import io

from fastapi import HTTPException, UploadFile
from PIL import Image

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000

# Pillow raises DecompressionBombError above 2x this value; keep it well below memory limits.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


async def read_image(upload: UploadFile) -> tuple[bytes, Image.Image]:
    """Return the raw bytes (kept for provenance checks later) and a decoded image.

    Raises 415 for unsupported types and 413 for oversized files.
    """
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")
    data = await upload.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Images must be 10 MB or smaller.")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise HTTPException(status_code=400, detail="That file isn't a readable image.") from exc
    return data, image
