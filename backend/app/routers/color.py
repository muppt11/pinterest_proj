"""Color search, the mood picker (color + aesthetic), and outbound Shop similar links."""

from typing import Annotated
from urllib.parse import quote_plus

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import CatalogFilters, FocusFilter, get_catalog, get_describer, get_embedder, get_filters, get_focus
from app.models import ColorMatchItem, ColorResults, Item, ShopLinks
from app.services.aesthetics import STYLE_WORDS, bank_for, phrases_for
from app.services.catalog import Catalog
from app.services.color_search import ColorHit, color_index, color_name, color_search
from app.services.embedder import Embedder
from app.services.query_parse import parse_query

router = APIRouter(tags=["color"])

CatalogDep = Annotated[Catalog, Depends(get_catalog)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
FocusDep = Annotated[FocusFilter, Depends(get_focus)]
FiltersDep = Annotated[CatalogFilters, Depends(get_filters)]
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


def _results(catalog: Catalog, hits: list[ColorHit]) -> list[ColorMatchItem]:
    return [
        ColorMatchItem(
            **Item.from_meta(catalog.items[h.row]).model_dump(),
            score=round(h.combined, 4),
            color_score=round(h.color_score, 4),
            delta_e=round(h.delta_e, 2),
            matched_color=h.matched_hex,
            text_score=None if h.text_score is None else round(h.text_score, 4),
            matched_phrase=h.phrase,
        )
        for h in hits
    ]


def _hex(value: str) -> str:
    return "#" + value.lstrip("#").lower()


def _boost(focus: FocusFilter) -> np.ndarray | None:
    return None if focus.bias is None else focus.bias / 0.03  # -1..1


@router.get("/search/color", response_model=ColorResults)
def search_color(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    focus: FocusDep,
    filters: FiltersDep,
    hex: HexColor,
    q: Annotated[str | None, Query(max_length=200)] = None,
    k: K = 30,
    color_weight: Weight = 0.6,
) -> ColorResults:
    """Items whose dominant colors are perceptually closest to `hex` (CIEDE2000), optionally blended
    with a text query through the CLIP text encoder, e.g. hex=#9caf88 & q=linen."""
    query = (q or "").strip() or None
    text_vector = embedder.embed_texts([query])[0] if query else None
    allowed = filters.mask.copy()
    if query:
        parsed = parse_query(query)
        if filters.category is None:
            categories = parsed.categories
            if filters.categories is not None:
                categories = (categories & filters.categories) or filters.categories if categories else filters.categories
            if categories is not None:
                allowed &= np.array([item["category"] in categories for item in catalog.items], dtype=bool)
        if filters.kids is None and parsed.kids:
            allowed &= np.array([item["kids"] for item in catalog.items], dtype=bool)
    hits = color_search(catalog, color_index(catalog), hex, k, text_vector, color_weight if query else 1.0, allowed=allowed, focus_boost=_boost(focus))
    return ColorResults(color=_hex(hex), query=query, color_weight=color_weight if query else 1.0, results=_results(catalog, hits))


@router.get("/styles", response_model=list[str])
def styles() -> list[str]:
    """The aesthetic vocabulary used by the mood picker and board analysis."""
    return STYLE_WORDS


@router.get("/mood", response_model=ColorResults)
def mood(
    catalog: CatalogDep,
    embedder: EmbedderDep,
    focus: FocusDep,
    filters: FiltersDep,
    hex: HexColor,
    style: str,
    k: K = 30,
    color_weight: Weight = 0.5,
) -> ColorResults:
    """Mood picker: a color from the wheel plus an aesthetic -> items matching both."""
    if style not in STYLE_WORDS:
        raise HTTPException(status_code=422, detail=f"Unknown style. Choose from: {', '.join(STYLE_WORDS)}")
    scores = bank_for(embedder).score(catalog.matrix, phrases_for([style]))
    hits = color_search(catalog, color_index(catalog), hex, k, None, color_weight, allowed=filters.mask, style=scores, focus_boost=_boost(focus))
    return ColorResults(color=_hex(hex), query=style, color_weight=color_weight, results=_results(catalog, hits))


@router.get("/items/{item_id}/shop-links", response_model=ShopLinks)
def shop_links(
    item_id: str,
    catalog: CatalogDep,
    describer: Annotated[object, Depends(get_describer)],
    detailed: bool = True,
) -> ShopLinks:
    """Links for finding something similar to buy. With `detailed`, the local vision model writes a
    specific query from the photo (pattern, material, cut); otherwise, or if the model is unavailable,
    the query is the item's extracted main color + category. MoodBoards shows no prices or stores."""
    meta = catalog.get(item_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    name = color_name(np.array(meta["colors"][0]["lab"])) if meta.get("colors") else None
    vision_query = describer.shopping_query(meta) if detailed and hasattr(describer, "shopping_query") else None
    if vision_query:
        query = f"kids {vision_query}" if meta["kids"] and "kid" not in vision_query.lower() else vision_query
        source = "vision model"
    else:
        words = [w for w in ("kids" if meta["kids"] else None, name, SHOP_TERMS.get(meta["category"], meta["category"].lower())) if w]
        query = " ".join(words)
        source = "color + category"
    return ShopLinks(
        query=query,
        query_source=source,
        color_name=name,
        google_shopping=f"https://www.google.com/search?tbm=shop&q={quote_plus(query)}",
        google_lens="https://lens.google.com/",
        google_images="https://www.google.com/imghp",
    )
