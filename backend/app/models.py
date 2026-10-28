"""Pydantic response schemas shared across routers."""

from typing import Any

from pydantic import BaseModel, Field


class Item(BaseModel):
    """A catalog item. Only fields the dataset actually has, plus image size for layout."""

    id: str
    category: str
    image_url: str
    kids: bool
    width: int
    height: int

    @classmethod
    def from_meta(cls, meta: dict[str, Any]) -> "Item":
        return cls(
            id=meta["id"],
            category=meta["category"],
            image_url=f"/images/{meta['image_file']}",
            kids=meta["kids"],
            width=meta["width"],
            height=meta["height"],
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
