"""Complete the look: complementary categories ranked by the item (and optionally a board's taste).

This approximates compatibility with *shared style in embedding space*: within a complementary
category, items closest to the anchor tend to share its color, formality, and vibe. Pinterest's
Complete the Look learns compatibility from scene images; we have no scene data, so we don't.
"""

from dataclasses import dataclass

import numpy as np

from app.services.catalog import Catalog, Hit

# Groups built only from the clothing-dataset's real labels. "Other" has no defined role.
GROUPS: dict[str, set[str]] = {
    "tops": {"T-Shirt", "Longsleeve", "Shirt", "Polo", "Top", "Blouse", "Undershirt", "Hoodie", "Body"},
    "bottoms": {"Pants", "Shorts", "Skirt"},
    "one-piece": {"Dress"},
    "outerwear": {"Outwear", "Blazer"},
    "shoes": {"Shoes"},
    "hats": {"Hat"},
}

COMPLEMENTS: dict[str, list[str]] = {
    "tops": ["bottoms", "shoes", "outerwear", "hats"],
    "bottoms": ["tops", "shoes", "outerwear", "hats"],
    "one-piece": ["shoes", "outerwear", "hats"],
    "outerwear": ["tops", "bottoms", "shoes"],
    "shoes": ["tops", "bottoms", "outerwear"],
    "hats": ["tops", "bottoms", "shoes"],
}

# Weight on the item itself vs. the board centroid when a board is given.
DEFAULT_ITEM_WEIGHT = 0.7


@dataclass
class LookGroup:
    group: str
    hits: list[Hit]


def group_of(category: str) -> str | None:
    return next((g for g, cats in GROUPS.items() if category in cats), None)


def blended_query(item_vec: np.ndarray, centroid: np.ndarray | None, item_weight: float) -> np.ndarray:
    """item_weight * item + (1 - item_weight) * board centroid, re-normalized."""
    if centroid is None:
        return item_vec
    c = centroid / np.linalg.norm(centroid)
    q = item_weight * item_vec + (1 - item_weight) * c
    return (q / np.linalg.norm(q)).astype(np.float32)


def complete_look(
    catalog: Catalog,
    item_id: str,
    per_group: int = 6,
    centroid: np.ndarray | None = None,
    item_weight: float = DEFAULT_ITEM_WEIGHT,
) -> tuple[str | None, list[LookGroup]]:
    """Return the anchor's group and, for each complementary group, the best-matching items.

    Suggestions match the anchor's kids flag, so adult outfits don't get kids' items and vice versa.
    Raises KeyError for an unknown item.
    """
    item = catalog.get(item_id)
    if item is None:
        raise KeyError(item_id)
    group = group_of(item["category"])
    if group is None:
        return None, []
    query = blended_query(catalog.vector(item_id), centroid, item_weight)
    return group, [
        LookGroup(g, catalog.search(query, k=per_group, categories=GROUPS[g], kids=item["kids"], exclude_ids={item_id}))
        for g in COMPLEMENTS[group]
    ]
