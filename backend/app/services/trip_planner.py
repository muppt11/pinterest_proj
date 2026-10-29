"""Trip taste, weather-aware outfit suggestions, photo palettes, and packing lists.

Weather rules (also checked by feature 10's evals):
- Cold (high < COLD_C): every outfit includes outerwear and never shorts.
- Hot (high >= HOT_C): no outerwear; prefer shorts, skirts, and dresses.
- Rain likely (chance >= RAIN_LIKELY): shoes that look like open-toe sandals are excluded.
"""

from dataclasses import dataclass

import numpy as np

from app.services.board import kmeans
from app.services.catalog import Catalog, Hit
from app.services.color import delta_e_2000
from app.services.complete_look import GROUPS
from app.services.embedder import Embedder

COLD_C = 15.0
HOT_C = 27.0
RAIN_LIKELY = 0.5
# FashionCLIP similarity to "open-toe sandals" above which a shoe counts as open-toe. Chosen by viewing
# the 431 catalog shoes ranked by this score: ranks 1-97 (score >= ~0.185) are almost all sandals, slides
# and flip-flops (one closed slip-on at 0.189). My first guess, 0.24, caught only 1 shoe.
SANDAL_SIMILARITY = 0.19
SLOT_TEXT_WEIGHT = 0.35  # how much the slot label ("beach dinner") steers vs. the group taste
PER_ROLE = 3


def _unit(v: np.ndarray) -> np.ndarray:
    return v / max(float(np.linalg.norm(v)), 1e-12)


@dataclass
class GroupTaste:
    member_centroids: dict[int, np.ndarray]  # user_id -> unit vector
    blended: np.ndarray | None  # unit vector (mean of member centroids, so each person counts equally)
    overlap: list[tuple[int, int, float]]  # (user a, user b, cosine) for each pair


def group_taste(vectors_by_user: dict[int, list[np.ndarray]]) -> GroupTaste:
    centroids = {u: _unit(np.mean(vs, axis=0)) for u, vs in vectors_by_user.items() if vs}
    blended = _unit(np.mean(list(centroids.values()), axis=0)) if centroids else None
    users = sorted(centroids)
    overlap = [(a, b, round(float(centroids[a] @ centroids[b]), 3)) for i, a in enumerate(users) for b in users[i + 1 :]]
    return GroupTaste(centroids, blended, overlap)


def overlap_word(cosine: float) -> str:
    """Plain-language reading of how similar two members' tastes are (FashionCLIP image space)."""
    return "very close" if cosine >= 0.85 else "overlapping" if cosine >= 0.7 else "different" if cosine >= 0.55 else "clashing"


def group_palette(color_lists: list[list[dict]], k: int = 3) -> list[dict]:
    """Shared photo palette: k-means over everyone's inspiration colors in Lab, weighted by area."""
    labs, hexes, weights = [], [], []
    for colors in color_lists:
        for c in colors:
            labs.append(c["lab"])
            hexes.append(c["hex"])
            weights.append(c["weight"])
    if not labs:
        return []
    x = np.array(labs)
    k = min(k, len(np.unique(x, axis=0)))
    labels = np.zeros(len(x), dtype=int) if k <= 1 else kmeans(x, k, restarts=3)[0]
    w = np.array(weights)
    palette = []
    for j in np.unique(labels):
        m = labels == j
        center = (x[m] * w[m, None]).sum(0) / w[m].sum()
        nearest = int(np.argmin(((x - center) ** 2).sum(1) + (~m) * 1e9))
        palette.append({"hex": hexes[nearest], "lab": [round(float(v), 2) for v in center], "weight": round(float(w[m].sum() / w.sum()), 3)})
    return sorted(palette, key=lambda p: -p["weight"])


def roles_for(high_c: float | None) -> list[str]:
    if high_c is not None and high_c < COLD_C:
        return ["tops", "bottoms", "outerwear", "shoes"]
    if high_c is not None and high_c >= HOT_C:
        return ["tops", "bottoms", "shoes"]
    return ["tops", "bottoms", "shoes"]


def allowed_categories(role: str, high_c: float | None) -> set[str]:
    cats = set(GROUPS[role])
    if role == "bottoms":
        if high_c is not None and high_c < COLD_C:
            cats -= {"Shorts"}
        if high_c is not None and high_c >= HOT_C:
            cats = {"Shorts", "Skirt"}
    if role == "tops" and high_c is not None and high_c >= HOT_C:
        cats |= GROUPS["one-piece"]
    if role == "tops" and high_c is not None and high_c < COLD_C:
        cats -= {"Undershirt", "Body", "Top"}
    return cats


@dataclass
class Suggestion:
    role: str
    hit: Hit


def plan_slot(
    catalog: Catalog,
    embedder: Embedder,
    taste: np.ndarray | None,
    slot_label: str,
    high_c: float | None,
    rain_chance: float | None,
    palette: list[dict] | None = None,
    exclude_ids: set[str] | None = None,
) -> list[Suggestion]:
    """Outfit pieces for one day/event: group taste + slot description + weather rules (+ palette)."""
    label_vec = embedder.embed_texts([f"an outfit for {slot_label}"])[0]
    query = label_vec if taste is None else _unit((1 - SLOT_TEXT_WEIGHT) * taste + SLOT_TEXT_WEIGHT * label_vec)
    exclude = set(exclude_ids or set())
    if rain_chance is not None and rain_chance >= RAIN_LIKELY:
        sandal = embedder.embed_texts(["open-toe sandals"])[0]
        exclude |= {i["id"] for r, i in enumerate(catalog.items) if i["category"] == "Shoes" and float(catalog.matrix[r] @ sandal) >= SANDAL_SIMILARITY}

    out: list[Suggestion] = []
    for role in roles_for(high_c):
        hits = catalog.search(query, k=40, categories=allowed_categories(role, high_c), kids=False, exclude_ids=exclude)
        if palette:
            hits = _rank_by_palette(catalog, hits, palette)
        for h in hits[:PER_ROLE]:
            out.append(Suggestion(role, h))
            exclude.add(h.item["id"])
    return out


def _rank_by_palette(catalog: Catalog, hits: list[Hit], palette: list[dict]) -> list[Hit]:
    """Coordinate for photos: favor items whose main color is close to the group palette."""
    targets = np.array([p["lab"] for p in palette])

    def palette_fit(item: dict) -> float:
        colors = item.get("colors") or []
        if not colors:
            return 0.0
        main = np.array(max(colors, key=lambda c: c["weight"])["lab"])
        de = delta_e_2000(np.broadcast_to(main, targets.shape), targets).min()
        return float(np.clip(1 - de / 40.0, 0, 1))

    scores = np.array([h.score for h in hits])
    scores = (scores - scores.min()) / max(float(scores.max() - scores.min()), 1e-6) if len(hits) else scores
    combined = [0.5 * s + 0.5 * palette_fit(h.item) for s, h in zip(scores, hits, strict=False)]
    return [hits[i] for i in np.argsort(-np.array(combined), kind="stable")]


def packing_list(chosen_by_slot: list[list[dict]], weather_days: list[dict]) -> list[dict]:
    """Per-person checklist: the distinct pieces they upvoted, then weather essentials.
    Items reference real catalog entries; extras are generic categories, never products or prices."""
    seen: dict[str, dict] = {}
    for items in chosen_by_slot:
        for item in items:
            seen.setdefault(item["id"], {"kind": "item", "label": item["category"], "item_id": item["id"]})
    extras = []
    highs = [d["high_c"] for d in weather_days if d.get("high_c") is not None]
    lows = [d["low_c"] for d in weather_days if d.get("low_c") is not None]
    rain = [d["rain_chance"] for d in weather_days if d.get("rain_chance") is not None]
    if rain and max(rain) >= RAIN_LIKELY:
        extras.append({"kind": "essential", "label": "Umbrella or rain jacket", "why": f"up to {max(rain):.0%} chance of rain"})
    if lows and min(lows) < 10:
        extras.append({"kind": "essential", "label": "Warm layer for evenings", "why": f"lows down to {min(lows):.0f}°C"})
    if highs and max(highs) >= HOT_C:
        extras.append({"kind": "essential", "label": "Sun hat and sunscreen", "why": f"highs up to {max(highs):.0f}°C"})
    return list(seen.values()) + extras
