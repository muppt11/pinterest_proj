"""Aesthetics described as concrete garments, matched by max-similarity and diversified.

Why: catalog photos show single garments, so an abstract prompt like "a streetwear outfit" barely
separates a hoodie from a plain tee. Each aesthetic is a handful of concrete garment phrases; an item
belongs to the aesthetic if it strongly matches *any* of them (max, not mean: averaging collapsed
everything toward generic shirts in testing), and results rotate across the phrases so one garment
doesn't take the whole board. Each match carries the phrase it matched, so results explain themselves.
"""

from dataclasses import dataclass

import numpy as np

from app.services.embedder import Embedder

AESTHETIC_PHRASES: dict[str, tuple[str, ...]] = {
    "minimalist": ("plain white t-shirt", "clean black trousers", "simple beige knit sweater", "plain grey crewneck", "tailored neutral coat"),
    "streetwear": ("oversized graphic hoodie", "baggy cargo pants", "chunky sneakers", "graphic print t-shirt", "bomber jacket", "baseball cap"),
    "bohemian": ("flowy floral maxi dress", "embroidered peasant blouse", "fringe suede jacket", "paisley print skirt"),
    "preppy": ("navy blazer", "white polo shirt", "cable knit sweater", "pleated chino shorts", "oxford button-down shirt"),
    "athleisure": ("sporty zip-up track jacket", "athletic leggings", "running sneakers", "performance t-shirt", "sweatpants"),
    "vintage": ("retro patterned blouse", "high-waisted mom jeans", "vintage wool cardigan", "retro print dress"),
    "business formal": ("tailored suit blazer", "crisp white dress shirt", "formal trousers", "leather dress shoes", "pencil skirt"),
    "y2k": ("baby tee crop top", "low-rise flared jeans", "pastel velour tracksuit", "butterfly print top", "mini skirt"),
    "grunge": ("oversized flannel plaid shirt", "ripped black jeans", "band t-shirt", "combat boots", "distressed denim jacket"),
    "romantic": ("lace blouse", "floral midi dress", "ruffled pastel top", "soft pink cardigan"),
    "western": ("cowboy boots", "denim western shirt", "suede fringe jacket", "plaid flannel shirt", "cowboy hat"),
    "coastal": ("linen shirt", "white linen trousers", "striped breton top", "light blue denim shorts", "straw sun hat"),
    "cozy knitwear": ("chunky knit sweater", "knitted cardigan", "wool turtleneck", "cable knit jumper"),
    "monochrome black": ("all black t-shirt", "black skinny jeans", "black leather jacket", "black dress"),
    "colorful maximalist": ("bright multicolor print shirt", "bold patterned dress", "neon colored top", "clashing prints outfit"),
    "classic denim": ("blue denim jacket", "straight leg blue jeans", "denim shirt", "denim shorts"),
}

ERA_PHRASES: dict[str, tuple[str, ...]] = {
    "70s": ("flared corduroy trousers", "suede fringe jacket", "earth-tone patterned blouse", "wide collar shirt"),
    "80s": ("bold shoulder pad blazer", "neon windbreaker", "acid wash jeans", "oversized bright sweater"),
    "90s": ("satin slip dress", "oversized flannel shirt", "mom jeans", "plain baby tee"),
    "2000s": ("low-rise flared jeans", "velour tracksuit", "baby tee crop top", "denim mini skirt"),
    "2010s": ("skinny jeans", "statement print top", "athleisure leggings", "chambray shirt"),
    "2020s": ("oversized blazer", "wide leg trousers", "quiet luxury knit sweater", "chunky dad sneakers"),
}

STYLE_WORDS = list(AESTHETIC_PHRASES)

# Only items in the top POOL by best-phrase score are eligible; then results rotate across phrases.
POOL = 400


@dataclass
class PhraseScores:
    best: np.ndarray  # (n,) max cosine over the phrases
    phrase_of: np.ndarray  # (n,) index of the matching phrase
    phrases: list[str]

    def normalized(self) -> np.ndarray:
        """0..1 per query: the median item maps to 0, the 99th percentile to 1 (robust to prompt scale)."""
        lo, hi = np.percentile(self.best, [50, 99])
        return np.clip((self.best - lo) / max(hi - lo, 1e-6), 0, 1)


class PhraseBank:
    """Caches phrase embeddings (a few dozen texts, embedded once each)."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._cache: dict[str, np.ndarray] = {}

    def vectors(self, phrases: list[str]) -> np.ndarray:
        missing = [p for p in phrases if p not in self._cache]
        if missing:
            for p, v in zip(missing, self._embedder.embed_texts(missing)):
                self._cache[p] = v
        return np.stack([self._cache[p] for p in phrases])

    def score(self, item_vectors: np.ndarray, phrases: list[str]) -> PhraseScores:
        sims = item_vectors @ self.vectors(phrases).T
        return PhraseScores(sims.max(1), sims.argmax(1), phrases)


_BANKS: dict[int, PhraseBank] = {}


def bank_for(embedder: Embedder) -> PhraseBank:
    """One phrase cache per embedder instance."""
    key = id(embedder)
    if key not in _BANKS or _BANKS[key]._embedder is not embedder:
        _BANKS[key] = PhraseBank(embedder)
    return _BANKS[key]


def phrases_for(aesthetics: list[str] = (), eras: list[str] = ()) -> list[str]:  # type: ignore[assignment]
    out: list[str] = []
    for a in aesthetics:
        out.extend(AESTHETIC_PHRASES[a])
    for e in eras:
        out.extend(ERA_PHRASES[e])
    return list(dict.fromkeys(out))


def diversified_order(scores: np.ndarray, phrase_of: np.ndarray, eligible: np.ndarray | None = None, pool: int = POOL) -> list[int]:
    """Rows ranked by `scores`, then interleaved round-robin across matched phrases.

    `scores` is the final ranking score (may already blend color); `phrase_of` groups rows by garment.
    """
    s = np.where(eligible, scores, -np.inf) if eligible is not None else scores
    top = [int(r) for r in np.argsort(-s, kind="stable")[:pool] if np.isfinite(s[r])]
    buckets: dict[int, list[int]] = {}
    for r in top:
        buckets.setdefault(int(phrase_of[r]), []).append(r)
    queues = sorted(buckets.values(), key=lambda b: -s[b[0]])
    out: list[int] = []
    while queues:
        for q in list(queues):
            out.append(q.pop(0))
            if not q:
                queues.remove(q)
    return out


def style_tags(centroid: np.ndarray, bank: PhraseBank, top: int = 3) -> list[tuple[str, float]]:
    """Aesthetics closest to a board centroid: each scored by its best-matching garment phrase."""
    scored = []
    for style, phrases in AESTHETIC_PHRASES.items():
        sims = bank.vectors(list(phrases)) @ centroid
        scored.append((style, float(sims.max())))
    scored.sort(key=lambda t: -t[1])
    return scored[:top]
