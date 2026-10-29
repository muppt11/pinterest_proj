"""The order uploads are processed in matters (see THREAT_MODEL.md):

1. Read provenance (C2PA / IPTC) and EXIF DateTimeOriginal from the ORIGINAL bytes.
2. Only then strip location data and re-encode. Re-encoding also drops the C2PA manifest, which is
   why the label must be decided first and carried alongside the processed image.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.services.provenance import Provenance, assess
from app.services.reposts import exif_datetime_original

GPS_IFD = 0x8825


@dataclass
class ProcessedUpload:
    image: Image.Image  # decoded, GPS-free
    jpeg: bytes  # re-encoded without GPS (keeps DateTimeOriginal for repost credit)
    provenance: Provenance
    exif_datetime_original: str | None
    had_gps: bool


def process_upload(data: bytes, mime: str) -> ProcessedUpload:
    provenance = assess(data, mime)  # 1. before anything touches the bytes
    original = Image.open(io.BytesIO(data))
    taken = exif_datetime_original(original)

    # Apply the camera's display rotation before embedding or saving, and remove the now-applied tag.
    upright = ImageOps.exif_transpose(original)
    exif = upright.getexif()  # 2. strip location, keep the capture date
    had_gps = GPS_IFD in exif and bool(exif.get_ifd(GPS_IFD))
    if GPS_IFD in exif:
        del exif[GPS_IFD]
    rgb = upright.convert("RGB")
    out = io.BytesIO()
    rgb.save(out, format="JPEG", quality=92, exif=exif.tobytes())
    return ProcessedUpload(rgb, out.getvalue(), provenance, taken, had_gps)
