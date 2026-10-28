"""Pydantic response schemas shared across routers."""

from typing import Any

from pydantic import BaseModel


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
