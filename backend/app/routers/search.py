"""Catalog browsing and visual / text search."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.deps import get_catalog, get_embedder
from app.models import Item, ItemPage, ScoredItem, SearchResults
from app.services.catalog import Catalog, Hit
from app.services.embedder import Embedder
from app.uploads import read_image

router = APIRouter(tags=["search"])

CatalogDep = Annotated[Catalog, Depends(get_catalog)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
K = Annotated[int, Query(ge=1, le=100)]


def _scored(hits: list[Hit]) -> list[ScoredItem]:
    return [ScoredItem(**Item.from_meta(h.item).model_dump(), score=round(h.score, 4)) for h in hits]


def _check_category(catalog: Catalog, category: str | None) -> None:
    if category is not None and category not in catalog.categories:
        raise HTTPException(status_code=422, detail=f"Unknown category. Choose from: {', '.join(catalog.categories)}")


@router.get("/items", response_model=ItemPage)
def list_items(
    catalog: CatalogDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    category: str | None = None,
) -> ItemPage:
    """Browse the catalog in a stable order (the home grid)."""
    _check_category(catalog, category)
    pool = [i for i in catalog.items if category is None or i["category"] == category]
    return ItemPage(items=[Item.from_meta(i) for i in pool[offset : offset + limit]], total=len(pool), offset=offset)


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str, catalog: CatalogDep) -> Item:
    """One catalog item, for the close-up view."""
    meta = catalog.get(item_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return Item.from_meta(meta)


@router.get("/items/{item_id}/similar", response_model=SearchResults)
def similar_items(item_id: str, catalog: CatalogDep, k: K = 20, category: str | None = None) -> SearchResults:
    """'More like this': nearest neighbours of a catalog item, excluding itself."""
    if catalog.get(item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    _check_category(catalog, category)
    hits = catalog.search(catalog.vector(item_id), k=k, category=category, exclude_ids={item_id})
    return SearchResults(results=_scored(hits))


@router.get("/search/text", response_model=SearchResults)
def search_text(
    catalog: CatalogDep,
    embedder: EmbedderDep,
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
    return SearchResults(query=query, results=_scored(catalog.search(vector, k=k, category=category)))


@router.post("/search/image", response_model=SearchResults)
async def search_image(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    image: Annotated[UploadFile, File(description="JPEG, PNG, or WebP up to 10 MB")],
    k: K = 20,
    category: str | None = None,
) -> SearchResults:
    """Search by example photo. The upload is embedded in memory and not stored."""
    _check_category(catalog, category)
    _, decoded = await read_image(image)
    vector = embedder.embed_images([decoded])[0]
    return SearchResults(results=_scored(catalog.search(vector, k=k, category=category)))
