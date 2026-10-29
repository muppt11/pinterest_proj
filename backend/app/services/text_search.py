"""Text search shared by the search bar and the assistant's search tool.

FashionCLIP text→image similarity, plus light query understanding: garment words narrow the
categories and color words re-rank by perceived color (CIEDE2000).
"""

from dataclasses import dataclass

import numpy as np

from app.services.catalog import Catalog, Hit
from app.services.color import rgb_to_lab
from app.services.color_families import items_in_families
from app.services.color_search import COLOR_NAMES, color_index
from app.services.embedder import Embedder
from app.services.query_parse import ParsedQuery, parse_query
from app.services.relevance import MIN_TEXT_RELEVANCE, RELEVANCE_WINDOW


@dataclass
class TextSearchResult:
    hits: list[Hit]
    low_relevance: bool  # even the best matches are weak (e.g. a non-clothing query)
    understood: list[str]  # categories and colors the query was understood as


def rerank_by_color(catalog: Catalog, hits: list[Hit], parsed: ParsedQuery) -> list[Hit]:
    """Blend each hit's text score (rescaled within the pool) with how well its main colors match."""
    if not hits:
        return hits
    rows = [catalog._row_by_id[h.item["id"]] for h in hits]
    text = np.array([h.score for h in hits])
    text = (text - text.min()) / max(float(text.max() - text.min()), 1e-6)
    color_parts = []
    if parsed.color:
        de, _ = color_index(catalog).distances(rgb_to_lab(np.array(COLOR_NAMES[parsed.color])))
        color_parts.append(np.clip(1 - de[rows] / 40.0, 0, 1))
    if parsed.family:
        color_parts.append(items_in_families([catalog.items[r] for r in rows], [parsed.family]).astype(float))
    if not color_parts:
        return hits
    color = np.mean(color_parts, axis=0)
    combined = 0.5 * text + 0.5 * color
    return [hits[i] for i in np.argsort(-combined, kind="stable")]


def text_search(
    catalog: Catalog,
    embedder: Embedder,
    query: str,
    k: int = 20,
    *,
    category: str | None = None,
    group_categories: set[str] | None = None,
    exclude_ids: set[str] | None = None,
    bias: np.ndarray | None = None,
    kids: bool | None = None,
) -> TextSearchResult:
    vector = embedder.embed_texts([query])[0]
    parsed = parse_query(query)
    if kids is None:
        kids = parsed.kids

    window = catalog.search(vector, k=RELEVANCE_WINDOW, category=category, exclude_ids=exclude_ids)
    relevance = sum(h.score for h in window) / len(window) if window else 0.0
    # A query that names a garment ("pastel cardigan") is about clothing even when CLIP scores run low.
    low_relevance = relevance < MIN_TEXT_RELEVANCE and parsed.categories is None

    categories = parsed.categories if category is None else None
    if group_categories is not None:  # explicit filters take priority over inferred garment words
        categories = (group_categories & categories) or group_categories if categories else group_categories
    pool_size = catalog.index.ntotal if parsed.color or parsed.family else max(k * 4, 200)
    pool = catalog.search(vector, k=pool_size, category=category, categories=categories, exclude_ids=exclude_ids, bias=bias, kids=kids)
    if parsed.color or parsed.family:
        pool = rerank_by_color(catalog, pool, parsed)
    understood = (sorted(categories) if categories else []) + [w for w in (parsed.color, parsed.family) if w]
    if kids is not None:
        understood.append("Kids" if kids else "Adults")
    return TextSearchResult(pool[:k], low_relevance, understood)
