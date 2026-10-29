"""Repost detection: known duplicate pairs (resized, cropped, recompressed, color-shifted) and credit rules."""

import io

import numpy as np
import pytest
from PIL import Image, ImageEnhance

from app.services.reposts import (
    REPOST_THRESHOLD,
    credit,
    exif_datetime_original,
    hamming,
    hashes_to_uint64,
    near_duplicate_groups,
    phash_hex,
)


def textured(seed: int, size: int = 256) -> Image.Image:
    """A synthetic 'photo' with structure at several scales so pHash has something to see."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size] / size
    base = np.zeros((size, size, 3))
    for c in range(3):
        for _ in range(6):
            fx, fy, ph = rng.uniform(1, 6), rng.uniform(1, 6), rng.uniform(0, 6.28)
            base[..., c] += np.sin(2 * np.pi * (fx * x + fy * y) + ph)
    base = (base - base.min()) / (base.max() - base.min())
    return Image.fromarray((base * 255).astype(np.uint8))


def jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


TRANSFORMS = {
    "resized": lambda im: im.resize((im.width // 2, im.height // 2)),
    "cropped": lambda im: im.crop((int(im.width * 0.02), int(im.height * 0.02), int(im.width * 0.98), int(im.height * 0.98))),
    "recompressed": lambda im: jpeg(im, 20),
    "color-shifted": lambda im: ImageEnhance.Color(ImageEnhance.Brightness(im).enhance(1.25)).enhance(0.6),
}


def distance(a: Image.Image, b: Image.Image) -> int:
    ha, hb = hashes_to_uint64([phash_hex(a), phash_hex(b)])
    return int(hamming(ha, hb))


@pytest.mark.parametrize("name", list(TRANSFORMS))
def test_known_duplicate_pairs_are_within_threshold(name: str) -> None:
    for seed in range(5):
        original = textured(seed)
        assert distance(original, TRANSFORMS[name](original)) <= REPOST_THRESHOLD, f"{name} seed {seed}"


def test_heavier_crops_need_the_clip_signal() -> None:
    """pHash is fragile to cropping (documented): a 10% crop drifts past the threshold, which is why
    near-duplicates also accept CLIP agreement rather than relying on pHash alone."""
    original = textured(1)
    cropped = original.crop((25, 25, 231, 231))
    assert distance(original, cropped) > REPOST_THRESHOLD // 2


def test_different_images_are_beyond_threshold() -> None:
    images = [textured(seed) for seed in range(8)]
    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            assert distance(images[i], images[j]) > REPOST_THRESHOLD


def test_hamming_and_grouping() -> None:
    assert int(hamming(np.uint64(0), np.uint64(0xFF))) == 8
    hashes = ["0000000000000000", "0000000000000003", "000000000000000f", "ffffffffffffffff", "fffffffffffffff0"]
    assert near_duplicate_groups(hashes, threshold=4) == [[0, 1, 2], [3, 4]]
    assert near_duplicate_groups(hashes, threshold=0) == []
    # With vectors, a pHash match also needs CLIP agreement: items 0 and 1 hash alike but look different.
    vecs = np.array([[1, 0], [0, 1], [1, 0], [0, 1], [0, 1]], dtype=np.float32)
    assert near_duplicate_groups(hashes, threshold=4, vectors=vecs) == [[0, 2], [3, 4]]


def test_exif_datetime_original_is_read() -> None:
    img = Image.new("RGB", (8, 8))
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = "2021:06:01 10:30:00"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    buf.seek(0)
    assert exif_datetime_original(Image.open(buf)) == "2021-06-01T10:30:00"
    assert exif_datetime_original(Image.new("RGB", (8, 8))) is None


ING = "2026-10-28T18:00:00"


def test_credit_earliest_exif_wins() -> None:
    c = credit([
        {"id": "a", "ingested_at": ING, "exif_datetime_original": "2020-01-01T00:00:00"},
        {"id": "b", "ingested_at": ING, "exif_datetime_original": "2022-01-01T00:00:00"},
    ])
    assert (c.status, c.original_id, c.date_source) == ("original", "a", "EXIF DateTimeOriginal")


def test_credit_unclear_when_only_ingestion_times() -> None:
    c = credit([{"id": "a", "ingested_at": ING}, {"id": "b", "ingested_at": ING}])
    assert c.status == "unclear" and c.original_id is None and "ingestion" in c.reason


def test_credit_unclear_on_tied_earliest() -> None:
    same = "2020-01-01T00:00:00"
    c = credit([
        {"id": "a", "ingested_at": ING, "exif_datetime_original": same},
        {"id": "b", "ingested_at": ING, "exif_datetime_original": same},
        {"id": "c", "ingested_at": ING, "exif_datetime_original": "2023-01-01T00:00:00"},
    ])
    assert c.status == "unclear" and "share the earliest" in c.reason


def test_upload_never_takes_credit_from_catalog() -> None:
    # Even with an older EXIF date, the upload loses to the catalog copy.
    c = credit([
        {"id": "catalog", "ingested_at": ING},
        {"id": "upload", "ingested_at": "2026-10-29T00:00:00", "exif_datetime_original": "2019-01-01T00:00:00", "is_upload": True},
    ])
    assert (c.status, c.original_id, c.date_source) == ("original", "catalog", "ingestion time")
    assert "uploads are always newer" in c.reason


def test_catalog_collapses_reposts_and_credits_the_original() -> None:
    from app.services.catalog import Catalog

    def meta(id_: str, phash: str, exif: str | None = None) -> dict:
        m = {"id": id_, "category": "Dress", "image_file": f"{id_}.jpg", "kids": False, "width": 1, "height": 1,
             "phash": phash, "ingested_at": ING}
        if exif:
            m["exif_datetime_original"] = exif
        return m

    items = [
        meta("repost-new", "00000000000000ff", "2023-05-01T00:00:00"),
        meta("original", "00000000000000fe", "2020-05-01T00:00:00"),  # 1 bit away, earlier capture
        meta("twin-a", "ff00000000000000"),
        meta("twin-b", "ff00000000000001"),  # ingestion-only pair -> unclear
        meta("solo", "0f0f0f0f0f0f0f0f"),
    ]
    vecs = np.eye(5, dtype=np.float32)
    vecs[1] = vecs[0] * 0.9 + vecs[1] * 0.1  # the repost looks like the original (cosine ~0.99)
    vecs[3] = vecs[2] * 0.95 + vecs[3] * 0.05  # the twins look alike too
    catalog = Catalog.from_vectors(vecs / np.linalg.norm(vecs, axis=1, keepdims=True), items)

    # Searching near the repost returns one card: the credited original, with the repost hidden.
    hits = catalog.search(vecs[0], k=5)
    ids = [h.item["id"] for h in hits]
    assert ids.count("original") == 1 and "repost-new" not in ids
    info = catalog.get("original")["repost"]  # type: ignore[index]
    assert info["status"] == "original" and info["original_id"] == "original" and info["hidden"] == 1
    assert info["date_source"] == "EXIF DateTimeOriginal" and info["first_seen"] == "2020-05-01T00:00:00"

    twin = catalog.get("twin-a")["repost"]  # type: ignore[index]
    assert twin["status"] == "unclear" and twin["original_id"] is None
    assert len([i for i in ids if i.startswith("twin")]) <= 1
    assert catalog.get("solo")["repost"] is None  # type: ignore[index]
    assert catalog.search(vecs[0], k=5, collapse_reposts=False)[0].item["id"] == "repost-new"


def test_photo_search_flags_reposts_of_catalog_images() -> None:
    from fastapi.testclient import TestClient

    from app.deps import get_catalog, get_embedder
    from app.main import app
    from app.services.catalog import Catalog

    from .conftest import FakeEmbedder

    photo = textured(7)
    items = [
        {"id": "cat-original", "category": "Dress", "image_file": "o.jpg", "kids": False, "width": 1, "height": 1,
         "phash": phash_hex(photo), "ingested_at": ING},
        {"id": "other", "category": "Dress", "image_file": "x.jpg", "kids": False, "width": 1, "height": 1,
         "phash": phash_hex(textured(8)), "ingested_at": ING},
    ]
    # FakeEmbedder maps every image to axis 0; put the original there so CLIP agrees too.
    vecs = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
    catalog = Catalog.from_vectors(vecs, items)
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_embedder] = FakeEmbedder
    try:
        buf = io.BytesIO()
        jpeg(photo, 40).save(buf, format="JPEG")  # a recompressed repost
        body = TestClient(app).post("/search/image", files={"image": ("r.jpg", buf.getvalue(), "image/jpeg")}).json()
        assert body["repost_of"]["original"]["id"] == "cat-original"
        assert "uploads are always newer" in body["repost_of"]["reason"]

        buf = io.BytesIO()
        textured(9).save(buf, format="JPEG")  # unrelated photo
        body = TestClient(app).post("/search/image", files={"image": ("n.jpg", buf.getvalue(), "image/jpeg")}).json()
        assert body["repost_of"] is None
    finally:
        app.dependency_overrides.clear()
