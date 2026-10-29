"""Catalog browsing and visual / text search."""

from typing import Annotated

import numpy as np

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.deps import FocusFilter, get_catalog, get_embedder, get_focus
from app.models import Item, ItemPage, ProvenanceLabel, ScoredItem, SearchResults, UploadRepost
from app.services.upload_pipeline import process_upload
from app.services.color import rgb_to_lab
from app.services.color_families import items_in_families
from app.services.color_search import COLOR_NAMES, color_index
from app.services.query_parse import ParsedQuery, parse_query
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
    ordered = focus.order(rows)
    if focus.focus != "all" and category is None:
        ordered = _interleave_by_category(ordered, catalog)
    pool = [catalog.items[r] for r in catalog.reposts.dedupe_rows(ordered, ids)]
    return ItemPage(items=[Item.from_meta(i) for i in pool[offset : offset + limit]], total=len(pool), offset=offset)


def _interleave_by_category(rows: list[int], catalog: Catalog) -> list[int]:
    """Round-robin across categories, keeping each category's internal order (strongest first)."""
    buckets: dict[str, list[int]] = {}
    for r in rows:
        buckets.setdefault(catalog.items[r]["category"], []).append(r)
    queues = list(buckets.values())
    out: list[int] = []
    while queues:
        for q in list(queues):
            out.append(q.pop(0))
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
    window = catalog.search(vector, k=RELEVANCE_WINDOW, category=category, exclude_ids=focus.excluded)
    relevance = sum(h.score for h in window) / len(window) if window else 0.0

    # Query understanding: garment words narrow the categories, color words re-rank by perceived color.
    parsed = parse_query(query)
    categories = parsed.categories if category is None else None
    pool = catalog.search(vector, k=max(k * 4, 200), category=category, categories=categories, exclude_ids=focus.excluded)
    if not pool:  # e.g. the garment word matched no category in this focus; fall back to text only
        pool = catalog.search(vector, k=max(k * 4, 200), category=category, exclude_ids=focus.excluded)
        categories = None
    if parsed.color or parsed.family:
        pool = _rerank_by_color(catalog, pool, parsed)
    return SearchResults(
        query=query,
        results=_scored(pool[:k]),
        low_relevance=relevance < MIN_TEXT_RELEVANCE,
        understood=(sorted(categories) if categories else []) + [w for w in (parsed.color, parsed.family) if w],
    )


def _rerank_by_color(catalog: Catalog, hits: list[Hit], parsed: ParsedQuery) -> list[Hit]:
    """Blend each hit's text score (rescaled within the pool) with how well its main colors match."""
    rows = [catalog._row_by_id[h.item["id"]] for h in hits]
    text = np.array([h.score for h in hits])
    text = (text - text.min()) / max(float(text.max() - text.min()), 1e-6)
    if parsed.color:
        de, _ = color_index(catalog).distances(rgb_to_lab(np.array(COLOR_NAMES[parsed.color])))
        color = np.clip(1 - de[rows] / 40.0, 0, 1)
    else:
        color = items_in_families([catalog.items[r] for r in rows], [parsed.family]).astype(float)  # type: ignore[list-item]
    combined = 0.5 * text + 0.5 * color
    return [hits[i] for i in np.argsort(-combined, kind="stable")]


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
    data, _ = await read_image(image)
    upload = process_upload(data, image.content_type or "image/jpeg")  # label first, then strip GPS
    decoded = upload.image
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
    return SearchResults(
        results=results, repost_of=repost, upload_provenance=ProvenanceLabel(**upload.provenance.to_dict())
    )
