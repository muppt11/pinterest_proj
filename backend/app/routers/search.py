"""Catalog browsing and visual / text search."""

from collections import deque
from collections.abc import Callable
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.deps import CatalogFilters, FocusFilter, get_catalog, get_embedder, get_embedder_factory, get_filters, get_focus
from app.models import Item, ItemPage, ProvenanceLabel, ScoredItem, SearchResults, UploadRepost
from app.services.aesthetics import STYLE_WORDS, bank_for, diversified_order, phrases_for
from app.services.catalog import Catalog, Hit
from app.services.color import dominant_colors
from app.services.complete_look import group_of
from app.services.embedder import Embedder
from app.services.reposts import credit, phash_hex
from app.services.text_search import text_search
from app.services.upload_pipeline import process_upload
from app.uploads import read_image

router = APIRouter(tags=["search"])

CatalogDep = Annotated[Catalog, Depends(get_catalog)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
FocusDep = Annotated[FocusFilter, Depends(get_focus)]
FiltersDep = Annotated[CatalogFilters, Depends(get_filters)]
K = Annotated[int, Query(ge=1, le=100)]

def _scored(hits: list[Hit]) -> list[ScoredItem]:
    return [ScoredItem(**Item.from_meta(h.item).model_dump(), score=round(h.score, 4)) for h in hits]


def _check_category(catalog: Catalog, category: str | None) -> None:
    if category is not None and category not in catalog.categories:
        raise HTTPException(status_code=422, detail=f"Unknown category. Choose from: {', '.join(catalog.categories)}")


@router.get("/items", response_model=ItemPage)
def list_items(
    catalog: CatalogDep,
    focus: FocusDep,
    filters: FiltersDep,
    embedder_factory: Annotated[Callable[[], Embedder], Depends(get_embedder_factory)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    style: Annotated[str | None, Query(description="an aesthetic; ranks the feed by its signature garments")] = None,
) -> ItemPage:
    """Browse the catalog (the home grid), optionally narrowed to a garment type and ranked by an aesthetic."""
    if style is not None and style not in STYLE_WORDS:
        raise HTTPException(status_code=422, detail=f"Unknown style. Choose from: {', '.join(STYLE_WORDS)}")
    rows = np.flatnonzero(filters.mask).tolist()
    ids = [i["id"] for i in catalog.items]
    if style:
        # Rank by the aesthetic's garment phrases (max-match, rotating across phrases), nudged by focus.
        scores = bank_for(embedder_factory()).score(catalog.matrix, phrases_for([style]))
        ranking = scores.normalized() + (0.0 if focus.bias is None else focus.bias / 0.03 * 0.15)
        eligible = np.zeros(len(ids), dtype=bool)
        eligible[rows] = True
        # Rank the same eligible catalog on every page, so totals and page boundaries stay stable.
        ordered = diversified_order(ranking, scores.phrase_of, eligible=eligible, pool=None)
    else:
        ordered = focus.order(rows)
        if focus.focus != "all" and filters.category is None:
            ordered = _interleave_by_category(ordered, catalog)
    pool = [catalog.items[r] for r in catalog.reposts.dedupe_rows(ordered, ids)]
    return ItemPage(items=[Item.from_meta(i) for i in pool[offset : offset + limit]], total=len(pool), offset=offset)


@router.get("/filters")
def filter_options(catalog: CatalogDep, filters: FiltersDep) -> dict:
    """Available recorded categories and duplicate-aware counts under the current filters."""
    labels = {"Outwear": "Outerwear", "Longsleeve": "Long-sleeve top", "Body": "Bodysuit", "Undershirt": "Tank top", "T-Shirt": "T-shirt"}
    ids = [item["id"] for item in catalog.items]
    rows = catalog.reposts.dedupe_rows(np.flatnonzero(filters.mask).tolist(), ids)
    categories = [
        {"value": category, "label": labels.get(category, category), "group": group_of(category),
         "count": sum(catalog.items[r]["category"] == category for r in rows)}
        for category in catalog.categories
    ]
    return {"categories": categories, "total": len(rows)}


def _interleave_by_category(rows: list[int], catalog: Catalog) -> list[int]:
    """Round-robin across categories, keeping each category's internal order (strongest first)."""
    buckets: dict[str, deque[int]] = {}
    for r in rows:
        buckets.setdefault(catalog.items[r]["category"], deque()).append(r)
    queues = list(buckets.values())
    out: list[int] = []
    while queues:
        for q in list(queues):
            out.append(q.popleft())
            if not q:
                queues.remove(q)
    return out


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str, catalog: CatalogDep) -> Item:
    """One catalog item, for the close-up view."""
    meta = catalog.get(item_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return Item.from_meta(meta)


@router.get("/items/{item_id}/similar", response_model=SearchResults)
def similar_items(
    item_id: str, catalog: CatalogDep, focus: FocusDep, k: K = 20, category: str | None = None, same_category: bool = True,
) -> SearchResults:
    """'More like this': nearest neighbours of a catalog item, excluding itself."""
    anchor = catalog.get(item_id)
    if anchor is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    _check_category(catalog, category)
    # Exclude the item's own duplicate group too, so "More like this" never shows a copy of itself.
    exclude = catalog.reposts.group_members(item_id) | focus.excluded
    target_category = category or (anchor["category"] if same_category else None)
    hits = catalog.search(catalog.vector(item_id), k=k, category=target_category, kids=anchor["kids"], exclude_ids=exclude, bias=focus.bias)
    return SearchResults(results=_scored(hits))


@router.get("/search/text", response_model=SearchResults)
def search_text(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    focus: FocusDep,
    filters: FiltersDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    k: K = 20,
) -> SearchResults:
    """Search by description, e.g. 'sage green linen shirt', via the CLIP text encoder."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query can't be blank.")
    result = text_search(
        catalog,
        embedder,
        query,
        k,
        category=filters.category,
        group_categories=filters.categories if filters.group else None,
        exclude_ids=filters.excluded,
        bias=focus.bias,
        kids=filters.kids,
    )
    return SearchResults(query=query, results=_scored(result.hits), low_relevance=result.low_relevance, understood=result.understood)


@router.post("/search/image", response_model=SearchResults)
async def search_image(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    focus: FocusDep,
    filters: FiltersDep,
    image: Annotated[UploadFile, File(description="JPEG, PNG, or WebP up to 10 MB")],
    k: K = 20,
) -> SearchResults:
    """Search by example photo. The upload is embedded in memory and not stored."""
    data, _ = await read_image(image)
    upload = process_upload(data, image.content_type or "image/jpeg")  # label first, then strip GPS
    decoded = upload.image
    vector = embedder.embed_images([decoded])[0]
    results = _scored(catalog.search(vector, k=k, exclude_ids=filters.excluded, bias=focus.bias))
    repost = None
    colors = dominant_colors(decoded)
    main = np.array(max(colors, key=lambda c: c["weight"])["lab"]) if colors else None
    matches = catalog.reposts.match_upload(catalog.items, catalog.matrix, phash_hex(decoded), vector, main)
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
    return SearchResults(
        results=results, repost_of=repost, upload_provenance=ProvenanceLabel(**upload.provenance.to_dict())
    )
