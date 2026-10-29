"""Repost detection with credit to the original.

Two signals must agree (measured on the real catalog, see evals/reports/repost_threshold.md):
- pHash (64-bit) within REPOST_THRESHOLD bits. pHash shrugs off resizing, recompression and color
  shifts (0-2 bits) but cropping moves it a lot (5% crop: median 12 bits).
- FashionCLIP cosine >= MIN_CLIP_SIMILARITY. This dataset's photos share one flat-lay layout, so
  *different* garments can hash within 2-4 bits (cosine 0.58-0.89); true copies score >= 0.97, and
  a 5% crop still scores a median 0.97.
pHash alone at <= 12 bits flagged 3,847 catalog pairs; both signals together flag 3, all true copies.

Credit rules (decided with the project owner):
- Each image's timestamp is its EXIF DateTimeOriginal if present, else its ingestion time; the UI
  always says which one was used.
- The original is the member with the single earliest timestamp.
- If the earliest timestamps tie, or every member only has an ingestion time, the original is
  "unclear" and the card says so instead of crediting anyone.
- User uploads are always newer than catalog items, so an upload never takes credit from the catalog.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import numpy as np
from PIL import Image

# Max Hamming distance (of 64 bits) for two images to count as the same picture. Chosen from the
# measured distribution in evals/reports/repost_threshold.md; see README feature 6.
REPOST_THRESHOLD = 12
MIN_CLIP_SIMILARITY = 0.95
# Second tier for heavy recompression (JPEG quality ~20 drops CLIP to ~0.90-0.94 while pHash stays
# within 4 bits): near-identical structure + similar look + the same main color. The color check
# rejects look-alike catalog pairs this tier would otherwise admit: grey vs. navy trousers, and light vs.
# dark jeans on the same floor (main colors ~12 apart; a limit of 15 let them through, so it is 6).
STRICT_PHASH = 4
STRICT_TIER_CLIP = 0.88
MAX_MAIN_COLOR_DE = 6.0

DateSource = Literal["EXIF DateTimeOriginal", "ingestion time"]
EXIF_IFD, DATETIME_ORIGINAL = 0x8769, 36867


def phash_hex(image: Image.Image) -> str:
    """64-bit perceptual hash as 16 hex characters."""
    import imagehash

    return str(imagehash.phash(image.convert("RGB"), hash_size=8))


def exif_datetime_original(image: Image.Image) -> str | None:
    """EXIF DateTimeOriginal as ISO 8601, or None. Must be read before any re-encoding strips EXIF."""
    raw = image.getexif().get_ifd(EXIF_IFD).get(DATETIME_ORIGINAL)
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return None


def hashes_to_uint64(hashes: list[str]) -> np.ndarray:
    return np.array([int(h, 16) for h in hashes], dtype=np.uint64)


def hamming(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Bitwise Hamming distance between uint64 hash arrays (broadcasting)."""
    x = np.bitwise_xor(np.asarray(a, dtype=np.uint64), np.asarray(b, dtype=np.uint64))
    flat = np.atleast_1d(x)  # a 0-d array can't be re-viewed as bytes
    bits = np.unpackbits(flat.view(np.uint8).reshape(*flat.shape, 8), axis=-1).sum(-1)
    return bits.reshape(x.shape)


def is_duplicate(bits: np.ndarray, cosine: np.ndarray, main_de: np.ndarray | None) -> np.ndarray:
    """The two-tier rule, vectorized: (pHash <= 12 and CLIP >= 0.95) or
    (pHash <= 4 and CLIP >= 0.88 and main colors within Delta E 6)."""
    loose = (bits <= REPOST_THRESHOLD) & (cosine >= MIN_CLIP_SIMILARITY)
    if main_de is None:
        return loose
    strict = (bits <= STRICT_PHASH) & (cosine >= STRICT_TIER_CLIP) & (main_de <= MAX_MAIN_COLOR_DE)
    return loose | strict


def near_duplicate_groups(
    hashes: list[str],
    threshold: int = REPOST_THRESHOLD,
    vectors: np.ndarray | None = None,
    min_similarity: float = MIN_CLIP_SIMILARITY,
    main_labs: np.ndarray | None = None,
) -> list[list[int]]:
    """Connected components of the near-duplicate graph (union-find). Only groups of 2+.
    With `vectors` (and optionally each image's main color in Lab), edges use the two-tier rule."""
    h = hashes_to_uint64(hashes)
    parent = list(range(len(h)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(h) - 1):  # O(n^2 / 2) popcounts: ~13M for 5k images, well under a second
        bits = hamming(h[i], h[i + 1 :])
        close = np.flatnonzero(bits <= threshold) + i + 1
        if vectors is not None and len(close):
            cos = vectors[close] @ vectors[i]
            de = None
            if main_labs is not None:
                from app.services.color import delta_e_2000

                de = delta_e_2000(main_labs[close], np.broadcast_to(main_labs[i], main_labs[close].shape))
                de = np.where(np.isnan(de), np.inf, de)
            if threshold == REPOST_THRESHOLD and min_similarity == MIN_CLIP_SIMILARITY:
                close = close[is_duplicate(bits[close - i - 1], cos, de)]
            else:
                close = close[cos >= min_similarity]
        for j in close:
            a, b = find(i), find(int(j))
            if a != b:
                parent[b] = a
    groups: dict[int, list[int]] = {}
    for i in range(len(h)):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


@dataclass
class Credit:
    status: Literal["original", "unclear"]
    original_id: str | None
    first_seen: str | None  # ISO timestamp of the credited original
    date_source: DateSource | None
    reason: str  # human-readable why, shown in the UI


def timestamp_of(member: dict[str, Any]) -> tuple[str, DateSource]:
    if member.get("exif_datetime_original"):
        return member["exif_datetime_original"], "EXIF DateTimeOriginal"
    return member["ingested_at"], "ingestion time"


def credit(members: list[dict[str, Any]]) -> Credit:
    """Who gets credit in a duplicate group. `members` have id, ingested_at, optional
    exif_datetime_original, and optional is_upload."""
    catalog = [m for m in members if not m.get("is_upload")]
    pool = catalog or members  # uploads are always newer than catalog items
    stamps = [(timestamp_of(m), m) for m in pool]

    if all(src == "ingestion time" for (_, src), _ in stamps) and len(pool) > 1:
        return Credit("unclear", None, None, None, "Only ingestion times are known for these copies, so the original can't be determined.")

    earliest = min(ts for (ts, _), _ in stamps)
    first = [(src, m) for (ts, src), m in stamps if ts == earliest]
    if len(first) > 1:
        return Credit("unclear", None, None, None, "Two or more copies share the earliest timestamp.")
    src, original = first[0]
    reason = (
        "Earliest capture date in the photo's metadata."
        if src == "EXIF DateTimeOriginal"
        else "Catalog copy; uploads are always newer than the catalog."
        if catalog and len(catalog) == 1 and len(members) > 1
        else "Earliest time MoodBoards saw it."
    )
    return Credit("original", original["id"], earliest, src, reason)


class RepostIndex:
    """Duplicate groups for a catalog, with the credit decision for each group."""

    def __init__(self, items: list[dict[str, Any]], vectors: np.ndarray | None = None, threshold: int = REPOST_THRESHOLD) -> None:
        self.group_of: dict[str, int] = {}
        self.groups: list[list[str]] = []
        self.credits: list[Credit] = []
        if not items or any("phash" not in i for i in items):
            return  # index built before repost metadata existed
        from app.services.color_families import main_lab

        labs = main_lab(items) if vectors is not None else None
        for g in near_duplicate_groups([i["phash"] for i in items], threshold, vectors, main_labs=labs):
            members = [items[r] for r in g]
            gi = len(self.groups)
            self.groups.append([m["id"] for m in members])
            self.credits.append(credit(members))
            for m in members:
                self.group_of[m["id"]] = gi

    def info(self, item_id: str) -> dict[str, Any] | None:
        """What the UI shows on a collapsed card, or None if the item has no duplicates."""
        gi = self.group_of.get(item_id)
        if gi is None:
            return None
        c = self.credits[gi]
        return {
            "status": c.status,
            "original_id": c.original_id,
            "first_seen": c.first_seen,
            "date_source": c.date_source,
            "reason": c.reason,
            "hidden": len(self.groups[gi]) - 1,
            "member_ids": self.groups[gi],
        }

    def representative(self, item_id: str) -> str:
        """The card to show for this item's group: the credited original, else the item itself."""
        gi = self.group_of.get(item_id)
        if gi is None:
            return item_id
        return self.credits[gi].original_id or item_id

    def collapse(self, item_ids: list[str]) -> list[str]:
        """Keep the first appearance of each duplicate group (as its representative), drop the rest."""
        seen: set[int] = set()
        out: list[str] = []
        for i in item_ids:
            gi = self.group_of.get(i)
            if gi is None:
                out.append(i)
            elif gi not in seen:
                seen.add(gi)
                out.append(self.representative(i))
        return out

    def dedupe_rows(self, rows: list[int], ids: list[str]) -> list[int]:
        """Keep only the first row of each duplicate group, preserving order (no swapping)."""
        seen: set[int] = set()
        out = []
        for r in rows:
            gi = self.group_of.get(ids[r])
            if gi is None or gi not in seen:
                if gi is not None:
                    seen.add(gi)
                out.append(r)
        return out

    def group_members(self, item_id: str) -> set[str]:
        gi = self.group_of.get(item_id)
        return set(self.groups[gi]) if gi is not None else {item_id}

    def match_upload(
        self, items: list[dict[str, Any]], vectors: np.ndarray, phash: str, vector: np.ndarray, main_lab: np.ndarray | None = None
    ) -> list[int]:
        """Catalog rows that an uploaded image is a near-duplicate of (two-tier rule)."""
        if not items or "phash" not in items[0]:
            return []
        from app.services.color import delta_e_2000
        from app.services.color_families import main_lab as main_labs_of

        h = hashes_to_uint64([i["phash"] for i in items])
        bits = hamming(hashes_to_uint64([phash])[0], h)
        close = np.flatnonzero(bits <= REPOST_THRESHOLD)
        if not len(close):
            return []
        cos = vectors[close] @ vector
        de = None
        if main_lab is not None:
            labs = main_labs_of([items[r] for r in close])
            de = np.where(np.isnan(labs[:, 0]), np.inf, delta_e_2000(np.nan_to_num(labs), np.broadcast_to(main_lab, labs.shape)))
        return [int(r) for r in close[is_duplicate(bits[close], cos, de)]]
