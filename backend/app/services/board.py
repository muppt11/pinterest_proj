"""Board analysis: split a board's images into 1–3 aesthetics and describe each one.

All vectors are L2-normalized, so squared Euclidean distance = 2 - 2·cosine and plain
k-means on them groups images by cosine similarity.
"""

from dataclasses import dataclass

import numpy as np

MAX_K = 3
# Below this mean silhouette, a 2- or 3-way split isn't meaningfully better than one group.
MIN_SILHOUETTE = 0.15
# Silhouette is scale-free: it happily "splits" a very tight group because the noise inside it
# looks like structure at that scale. So a split also needs its aesthetics to be genuinely apart:
# every pair of centroids must be at least this far in cosine distance.
# Both thresholds were tuned on 240 synthetic catalog boards (seed 11; the eval report uses seed 7):
# the first guesses (0.1 / 0.1) split 90% of one-category boards; 0.15 / 0.35 keeps 69% of them whole
# while still splitting 83% of two-look boards.
MIN_CENTROID_DISTANCE = 0.35
RESTARTS = 10

# The aesthetic vocabulary lives with its garment phrases (services/aesthetics.py).
from app.services.aesthetics import STYLE_WORDS  # noqa: E402,F401


@dataclass
class Clustering:
    k: int
    labels: np.ndarray  # cluster index per image
    centroids: np.ndarray  # (k, dim), unit-normalized
    silhouette: float | None  # None when k == 1 (silhouette is undefined)
    candidates: dict[int, float]  # silhouette for every k that was tried


def _normalize(x: np.ndarray) -> np.ndarray:
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12, None)


def kmeans(
    x: np.ndarray, k: int, seed: int = 0, iterations: int = 50, restarts: int = RESTARTS
) -> tuple[np.ndarray, float]:
    """k-means++ init + Lloyd iterations, best of `restarts` by inertia. Returns (labels, inertia)."""
    rng = np.random.default_rng(seed)
    best_labels, best_inertia = np.zeros(len(x), dtype=int), np.inf
    for _ in range(restarts):
        centers = [x[rng.integers(len(x))]]
        for _ in range(1, k):
            d2 = np.min([((x - c) ** 2).sum(1) for c in centers], axis=0)
            probs = d2 / d2.sum() if d2.sum() > 0 else np.full(len(x), 1 / len(x))
            centers.append(x[rng.choice(len(x), p=probs)])
        c = np.stack(centers)
        for _ in range(iterations):
            labels = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
            new = np.stack([x[labels == j].mean(0) if np.any(labels == j) else c[j] for j in range(k)])
            if np.allclose(new, c):
                break
            c = new
        inertia = float(((x - c[labels]) ** 2).sum())
        if inertia < best_inertia and len(np.unique(labels)) == k:
            best_labels, best_inertia = labels, inertia
    return best_labels, best_inertia


def silhouette(x: np.ndarray, labels: np.ndarray) -> float:
    """Mean silhouette with cosine distance. Singleton clusters score 0, as in scikit-learn."""
    dist = 1 - x @ x.T
    scores = []
    for i, li in enumerate(labels):
        same = labels == li
        if same.sum() == 1:
            scores.append(0.0)
            continue
        a = dist[i, same].sum() / (same.sum() - 1)
        b = min(dist[i, labels == lj].mean() for lj in np.unique(labels) if lj != li)
        scores.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return float(np.mean(scores))


def min_centroid_distance(x: np.ndarray, labels: np.ndarray) -> float:
    """Smallest cosine distance between any two cluster centroids."""
    c = _normalize(np.stack([x[labels == j].mean(0) for j in np.unique(labels)]))
    sims = c @ c.T
    return float(1 - sims[~np.eye(len(c), dtype=bool)].max())


def choose_clusters(
    vectors: np.ndarray,
    max_k: int = MAX_K,
    min_silhouette: float = MIN_SILHOUETTE,
    min_gap: float = MIN_CENTROID_DISTANCE,
) -> Clustering:
    """Pick k in 1..max_k: the best-silhouette split whose aesthetics are at least `min_gap` apart
    and whose silhouette clears `min_silhouette`; otherwise the board is one aesthetic."""
    x = _normalize(np.asarray(vectors, dtype=np.float64))
    candidates: dict[int, float] = {}
    labelings: dict[int, np.ndarray] = {}
    for k in range(2, min(max_k, len(x) - 1) + 1):  # silhouette needs 2 <= k <= n - 1
        labels, _ = kmeans(x, k)
        if len(np.unique(labels)) < k or min_centroid_distance(x, labels) < min_gap:
            continue
        candidates[k] = silhouette(x, labels)
        labelings[k] = labels

    best_k = max(candidates, key=candidates.get, default=None)  # type: ignore[arg-type]
    if best_k is None or candidates[best_k] < min_silhouette:
        labels = np.zeros(len(x), dtype=int)
        return Clustering(1, labels, _normalize(x.mean(0, keepdims=True)).astype(np.float32), None, candidates)

    labels = labelings[best_k]
    # Order clusters largest-first so "Aesthetic 1" is the board's dominant look.
    order = np.argsort([-np.sum(labels == j) for j in range(best_k)], kind="stable")
    remap = np.empty(best_k, dtype=int)
    remap[order] = np.arange(best_k)
    labels = remap[labels]
    centroids = _normalize(np.stack([x[labels == j].mean(0) for j in range(best_k)])).astype(np.float32)
    return Clustering(best_k, labels, centroids, candidates[best_k], candidates)
