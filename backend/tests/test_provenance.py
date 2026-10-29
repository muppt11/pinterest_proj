"""Evidence-based AI labels and the upload pipeline (provenance first, then GPS stripping)."""

import io

from PIL import Image

from app.services.provenance import assess
from app.services.upload_pipeline import GPS_IFD, process_upload

from .c2pa_fixtures import iptc_xmp, jpeg_bytes, sign_jpeg


def test_signed_ai_image_is_labeled_ai_with_evidence() -> None:
    p = assess(sign_jpeg(jpeg_bytes(), "trainedAlgorithmicMedia"), "image/jpeg")
    assert p.label == "ai_generated"
    assert p.evidence[0].source == "C2PA" and p.evidence[0].value == "trainedAlgorithmicMedia"
    assert "not on a trust list" in p.evidence[0].note  # honest about the test signer


def test_signed_camera_capture_is_human_verified() -> None:
    p = assess(sign_jpeg(jpeg_bytes(), "digitalCapture"), "image/jpeg")
    assert p.label == "human_verified" and "camera" in p.explanation


def test_tampered_manifest_is_unknown() -> None:
    signed = bytearray(sign_jpeg(jpeg_bytes(), "trainedAlgorithmicMedia"))
    signed[-200] ^= 0xFF  # flip bits in the image data after signing
    p = assess(bytes(signed), "image/jpeg")
    assert p.label == "unknown" and "failed validation" in p.explanation


def test_iptc_ai_tag_counts_but_unsigned_capture_claim_does_not() -> None:
    assert assess(jpeg_bytes(xmp=iptc_xmp("trainedAlgorithmicMedia")), "image/jpeg").label == "ai_generated"
    capture = assess(jpeg_bytes(xmp=iptc_xmp("digitalCapture")), "image/jpeg")
    assert capture.label == "unknown" and "isn't signed" in capture.explanation


def test_no_metadata_defaults_to_unknown() -> None:
    p = assess(jpeg_bytes(), "image/jpeg")
    assert p.label == "unknown" and "never guesses from pixels" in p.explanation and p.evidence == []


def _exif_with_gps_and_date() -> Image.Exif:
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = "2024:07:04 18:30:00"
    exif.get_ifd(GPS_IFD).update({1: "N", 2: (40.0, 26.0, 46.0), 3: "W", 4: (79.0, 58.0, 56.0)})
    return exif


def test_c2pa_signed_upload_keeps_its_label_after_gps_stripping() -> None:
    """The required order: provenance is read before stripping, which also removes the manifest."""
    signed = sign_jpeg(jpeg_bytes(exif=_exif_with_gps_and_date()), "trainedAlgorithmicMedia")
    result = process_upload(signed, "image/jpeg")
    assert result.provenance.label == "ai_generated"  # decided from the original bytes
    assert assess(result.jpeg, "image/jpeg").label == "unknown"  # the stripped copy no longer carries it
    assert result.had_gps


def test_pipeline_strips_gps_but_keeps_capture_date() -> None:
    result = process_upload(jpeg_bytes(exif=_exif_with_gps_and_date()), "image/jpeg")
    cleaned = Image.open(io.BytesIO(result.jpeg)).getexif()
    assert not cleaned.get_ifd(GPS_IFD)
    assert result.exif_datetime_original == "2024-07-04T18:30:00"
    assert cleaned.get_ifd(0x8769).get(36867) == "2024:07:04 18:30:00"


def test_pipeline_applies_phone_rotation_without_rotating_twice() -> None:
    image = Image.new("RGB", (30, 20), "red")
    exif = _exif_with_gps_and_date()
    exif[274] = 6  # display rotated 90 degrees clockwise
    data = io.BytesIO()
    image.save(data, format="JPEG", exif=exif)
    result = process_upload(data.getvalue(), "image/jpeg")
    assert result.image.size == (20, 30)
    saved = Image.open(io.BytesIO(result.jpeg))
    assert saved.size == (20, 30) and saved.getexif().get(274) is None
    assert result.exif_datetime_original == "2024-07-04T18:30:00" and result.had_gps
    assert not saved.getexif().get_ifd(GPS_IFD)


def test_photo_search_reports_the_upload_label_and_catalog_items_are_unknown(client) -> None:  # type: ignore[no-untyped-def]
    signed = sign_jpeg(jpeg_bytes(), "trainedAlgorithmicMedia")
    body = client.post("/search/image", files={"image": ("ai.jpg", signed, "image/jpeg")}).json()
    assert body["upload_provenance"]["label"] == "ai_generated"
    assert all(r["provenance"]["label"] == "unknown" for r in body["results"])
    assert "doesn't guess" in body["results"][0]["provenance"]["explanation"]
