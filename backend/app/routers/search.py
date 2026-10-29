"""Catalog browsing and visual / text search."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.deps import FocusFilter, get_catalog, get_embedder, get_focus
from app.models import Item, ItemPage, ScoredItem, SearchResults, UploadRepost
from app.services.reposts import credit, phash_hex
from app.services.catalog import Catalog, Hit
from app.services.embedder import Embedder
from app.uploads import read_image

router = APIRouter(tags=["search"])

CatalogDep = Annotated[Catalog, Depends(get_catalog)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
FocusDep = Annotated[FocusFilter, Depends(get_focus)]
K = Annotated[int, Query(ge=1, le=100)]

# Text→image relevance cutoff on the mean cosine score of the top 10 results.
# Measured on the real index (2026-10-28): 13 clothing queries scored 0.232–0.269,
# 13 non-clothing/gibberish queries scored 0.069–0.211. 0.22 sits in the gap; feature 10 re-checks it.
MIN_TEXT_RELEVANCE = 0.22
RELEVANCE_WINDOW = 10


def _scored(hits: list[Hit]) -> list[ScoredItem]:
    return [ScoredItem(**Item.from_meta(h.item).model_dump(), score=round(h.score, 4)) for h in hits]


def _check_category(catalog: Catalog, category: str | None) -> None:
    if category is not None and category not in catalog.categories:
        raise HTTPException(status_code=422, detail=f"Unknown category. Choose from: {', '.join(catalog.categories)}")


@router.get("/items", response_model=ItemPage)
def list_items(
    catalog: CatalogDep,
    focus: FocusDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    category: str | None = None,
) -> ItemPage:
    """Browse the catalog in a stable order (the home grid)."""
    _check_category(catalog, category)
    rows = [r for r, i in enumerate(catalog.items) if (category is None or i["category"] == category) and i["id"] not in focus.excluded]
    ids = [i["id"] for i in catalog.items]
    pool = [catalog.items[r] for r in catalog.reposts.dedupe_rows(rows, ids)]
    return ItemPage(items=[Item.from_meta(i) for i in pool[offset : offset + limit]], total=len(pool), offset=offset)


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str, catalog: CatalogDep) -> Item:
    """One catalog item, for the close-up view."""
    meta = catalog.get(item_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return Item.from_meta(meta)


@router.get("/items/{item_id}/similar", response_model=SearchResults)
def similar_items(item_id: str, catalog: CatalogDep, focus: FocusDep, k: K = 20, category: str | None = None) -> SearchResults:
    """'More like this': nearest neighbours of a catalog item, excluding itself."""
    if catalog.get(item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    _check_category(catalog, category)
    # Exclude the item's own duplicate group too, so "More like this" never shows a copy of itself.
    exclude = catalog.reposts.group_members(item_id) | focus.excluded
    hits = catalog.search(catalog.vector(item_id), k=k, category=category, exclude_ids=exclude)
    return SearchResults(results=_scored(hits))


@router.get("/search/text", response_model=SearchResults)
def search_text(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    focus: FocusDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    k: K = 20,
    category: str | None = None,
) -> SearchResults:
    """Search by description, e.g. 'sage green linen shirt', via the CLIP text encoder."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query can't be blank.")
    _check_category(catalog, category)
    vector = embedder.embed_texts([query])[0]
    hits = catalog.search(vector, k=max(k, RELEVANCE_WINDOW), category=category, exclude_ids=focus.excluded)
    window = hits[:RELEVANCE_WINDOW]
    relevance = sum(h.score for h in window) / len(window) if window else 0.0
    return SearchResults(query=query, results=_scored(hits[:k]), low_relevance=relevance < MIN_TEXT_RELEVANCE)


@router.post("/search/image", response_model=SearchResults)
async def search_image(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    focus: FocusDep,
    image: Annotated[UploadFile, File(description="JPEG, PNG, or WebP up to 10 MB")],
    k: K = 20,
    category: str | None = None,
) -> SearchResults:
    """Search by example photo. The upload is embedded in memory and not stored."""
    _check_category(catalog, category)
    _, decoded = await read_image(image)
    vector = embedder.embed_images([decoded])[0]
    results = _scored(catalog.search(vector, k=k, category=category, exclude_ids=focus.excluded))
    repost = None
    matches = catalog.reposts.match_upload(catalog.items, catalog.matrix, phash_hex(decoded), vector)
    if matches:
        members = [catalog.items[r] for r in matches] + [{"id": "upload", "is_upload": True, "ingested_at": "9999"}]
        c = credit(members)
        original = catalog.get(c.original_id) if c.original_id else catalog.items[matches[0]]
        repost = UploadRepost(
            original=Item.from_meta(original),  # type: ignore[arg-type]
            reason="Your photo matches an image already in the catalog. " + c.reason,
            first_seen=c.first_seen,
            date_source=c.date_source,
        )
    return SearchResults(results=results, repost_of=repost)
