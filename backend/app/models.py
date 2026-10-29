"""Pydantic response schemas shared across routers."""

from typing import Any

from pydantic import BaseModel, Field


class RepostInfo(BaseModel):
    """Credit for a group of near-duplicate images (feature 6)."""

    status: str  # "original" (credited) or "unclear"
    original_id: str | None
    first_seen: str | None  # ISO timestamp of the credited original
    date_source: str | None  # "EXIF DateTimeOriginal" or "ingestion time"
    reason: str
    hidden: int  # how many other copies were collapsed into this card
    member_ids: list[str]


class ProvenanceLabel(BaseModel):
    """Evidence-based AI label (feature 5). Never guessed from pixels."""

    label: str  # "ai_generated" | "human_verified" | "unknown"
    explanation: str
    evidence: list[dict] = []


CATALOG_PROVENANCE = ProvenanceLabel(
    label="unknown",
    explanation="No provenance metadata: the catalog's photos carry no Content Credentials, IPTC tags, or EXIF at all, so MoodBoards doesn't guess.",
)


class Item(BaseModel):
    """A catalog item. Only fields the dataset actually has, plus image size for layout."""

    id: str
    category: str
    image_url: str
    kids: bool
    width: int
    height: int
    colors: list[str] = []  # dominant colors (hex), heaviest first, extracted from the image at index time
    repost: RepostInfo | None = None  # set when near-duplicate copies of this image exist
    provenance: ProvenanceLabel = CATALOG_PROVENANCE

    @classmethod
    def from_meta(cls, meta: dict[str, Any]) -> "Item":
        return cls(
            id=meta["id"],
            category=meta["category"],
            image_url=f"/images/{meta['image_file']}",
            kids=meta["kids"],
            width=meta["width"],
            height=meta["height"],
            colors=[c["hex"] for c in meta.get("colors", [])[:3]],
            repost=meta.get("repost"),
            provenance=meta.get("provenance") or CATALOG_PROVENANCE,
        )


class ScoredItem(Item):
    """An item returned by a search, with its cosine similarity to the query (-1..1)."""

    score: float


class ItemPage(BaseModel):
    items: list[Item]
    total: int
    offset: int


class SearchResults(BaseModel):
    query: str | None = None
    results: list[ScoredItem]
    # True when even the best matches are weak, e.g. a non-clothing query against a clothing-only catalog.
    # Results are still returned (closest items) so the UI can offer them behind an explanation.
    low_relevance: bool = False
    # Text searches: what the query was understood as (categories and color), shown as chips in the UI.
    understood: list[str] = []
    # For photo searches: set when the uploaded photo is a repost of a catalog image (credit goes to the catalog).
    repost_of: "UploadRepost | None" = None
    # For photo searches: the uploaded photo's own label, read from its original bytes.
    upload_provenance: "ProvenanceLabel | None" = None


class UploadRepost(BaseModel):
    original: "Item"
    reason: str
    first_seen: str | None
    date_source: str | None


class ColorMatchItem(Item):
    """A color/mood search result, with the evidence for its rank."""

    score: float  # combined 0..1
    color_score: float  # 0..1
    delta_e: float  # CIEDE2000 to the picked color (lower = closer), incl. small-coverage penalty
    matched_color: str  # which of the item's dominant colors matched
    text_score: float | None = None  # 0..1, when a text or style was given
    matched_phrase: str | None = None  # for aesthetics: which signature garment this item matched


class ColorResults(BaseModel):
    color: str
    query: str | None
    color_weight: float
    results: list[ColorMatchItem]


class ShopLinks(BaseModel):
    """Outbound search links built from the item's photo or real attributes. MoodBoards verifies nothing there."""

    query: str
    query_source: str  # "vision model" (described from the photo) or "color + category" (fallback)
    color_name: str | None
    google_shopping: str
    google_lens: str
    google_images: str  # paste the copied photo here for a visual match


class StyleTag(BaseModel):
    """A style word close to an aesthetic in CLIP space. A hint for humans, not a classification."""

    word: str
    score: float


class Aesthetic(BaseModel):
    """One distinct look within a board."""

    index: int
    image_indices: list[int]  # positions of the uploaded images in this aesthetic
    style_tags: list[StyleTag]
    results: list[ScoredItem]
    centroid: list[float]  # unit vector; pass to /complete-look to tune suggestions to this aesthetic


class CompleteLookRequest(BaseModel):
    item_id: str
    centroid: list[float] | None = Field(default=None, description="a board aesthetic's centroid from /board/analyze")
    item_weight: float = Field(default=0.7, ge=0, le=1, description="weight on the item vs. the board centroid")
    per_group: int = Field(default=6, ge=1, le=24)


class LookGroupOut(BaseModel):
    group: str  # e.g. "bottoms", "shoes"
    results: list[ScoredItem]


class CompleteLook(BaseModel):
    item_id: str
    anchor_group: str | None  # None for categories without a defined outfit role ("Other")
    used_board: bool
    groups: list[LookGroupOut]


class BoardAnalysis(BaseModel):
    k: int
    silhouette: float | None  # None when the board is one aesthetic (k = 1)
    silhouette_by_k: dict[int, float]  # every split that was tried, for transparency
    aesthetics: list[Aesthetic]
