"""Color search, the mood picker (color + aesthetic), and outbound Shop similar links."""

from typing import Annotated
from urllib.parse import quote_plus

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_catalog, get_embedder
from app.models import ColorMatchItem, ColorResults, Item, ShopLinks
from app.services.board import STYLE_WORDS
from app.services.catalog import Catalog
from app.services.color_search import ColorHit, ColorIndex, color_name, color_search
from app.services.embedder import Embedder

router = APIRouter(tags=["color"])

CatalogDep = Annotated[Catalog, Depends(get_catalog)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
HexColor = Annotated[str, Query(pattern=r"^#?[0-9a-fA-F]{6}$", description="picked color, e.g. #9caf88")]
Weight = Annotated[float, Query(ge=0, le=1, description="1 = color only, 0 = text/style only")]
K = Annotated[int, Query(ge=1, le=100)]

# Dataset labels -> words a shopping search understands.
SHOP_TERMS = {
    "Outwear": "jacket",
    "Longsleeve": "long sleeve top",
    "Body": "bodysuit",
    "Other": "clothing",
    "T-Shirt": "t-shirt",
}


def color_index(catalog: Catalog) -> ColorIndex:
    """Built once per loaded catalog and cached on it."""
    cached = getattr(catalog, "_color_index", None)
    if cached is None:
        cached = ColorIndex(catalog)
        catalog._color_index = cached  # type: ignore[attr-defined]
    return cached


def _results(catalog: Catalog, hits: list[ColorHit]) -> list[ColorMatchItem]:
    return [
        ColorMatchItem(
            **Item.from_meta(catalog.items[h.row]).model_dump(),
            score=round(h.combined, 4),
            color_score=round(h.color_score, 4),
            delta_e=round(h.delta_e, 2),
            matched_color=h.matched_hex,
            text_score=None if h.text_score is None else round(h.text_score, 4),
        )
        for h in hits
    ]


def _hex(value: str) -> str:
    return "#" + value.lstrip("#").lower()


@router.get("/search/color", response_model=ColorResults)
def search_color(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    hex: HexColor,
    q: Annotated[str | None, Query(max_length=200)] = None,
    k: K = 30,
    color_weight: Weight = 0.6,
) -> ColorResults:
    """Items whose dominant colors are perceptually closest to `hex` (CIEDE2000), optionally blended
    with a text query through the CLIP text encoder, e.g. hex=#9caf88 & q=linen."""
    query = q.strip() if q else None
    text_vector = embedder.embed_texts([query])[0] if query else None
    hits = color_search(catalog, color_index(catalog), hex, k, text_vector, color_weight if query else 1.0)
    return ColorResults(color=_hex(hex), query=query, color_weight=color_weight if query else 1.0, results=_results(catalog, hits))


@router.get("/styles", response_model=list[str])
def styles() -> list[str]:
    """The aesthetic vocabulary used by the mood picker and board analysis."""
    return STYLE_WORDS


@router.get("/mood", response_model=ColorResults)
def mood(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    hex: HexColor,
    style: str,
    k: K = 30,
    color_weight: Weight = 0.5,
) -> ColorResults:
    """Mood picker: a color from the wheel plus an aesthetic -> items matching both."""
    if style not in STYLE_WORDS:
        raise HTTPException(status_code=422, detail=f"Unknown style. Choose from: {', '.join(STYLE_WORDS)}")
    prompt = f"a {style} outfit"
    text_vector = embedder.embed_texts([prompt])[0]
    hits = color_search(catalog, color_index(catalog), hex, k, text_vector, color_weight)
    return ColorResults(color=_hex(hex), query=style, color_weight=color_weight, results=_results(catalog, hits))


@router.get("/items/{item_id}/shop-links", response_model=ShopLinks)
def shop_links(item_id: str, catalog: CatalogDep) -> ShopLinks:
    """Google Shopping / Lens links for finding something similar to buy. Built only from the item's
    real category, kids flag, and extracted main color; MoodBoards shows no prices or stores itself."""
    meta = catalog.get(item_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    name = color_name(np.array(meta["colors"][0]["lab"])) if meta.get("colors") else None
    words = [w for w in ("kids" if meta["kids"] else None, name, SHOP_TERMS.get(meta["category"], meta["category"].lower())) if w]
    query = " ".join(words)
    return ShopLinks(
        query=query,
        color_name=name,
        google_shopping=f"https://www.google.com/search?tbm=shop&q={quote_plus(query)}",
        google_lens="https://lens.google.com/",
    )
