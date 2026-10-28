"""Board analysis: cluster selection unit tests and the /board/analyze endpoint."""

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.deps import get_catalog, get_embedder
from app.main import app
from app.services.board import STYLE_WORDS, choose_clusters, silhouette
from app.services.catalog import Catalog

from .conftest import DIM, FakeEmbedder

RNG = np.random.default_rng(42)


def blob(center: list[float], n: int, spread: float = 0.05) -> np.ndarray:
    c = np.array(center, dtype=np.float64)
    pts = c + RNG.normal(0, spread, size=(n, len(c)))
    return pts / np.linalg.norm(pts, axis=1, keepdims=True)


class TestChooseClusters:
    def test_one_tight_group_stays_one_aesthetic(self) -> None:
        # Regression: silhouette alone scored an arbitrary split of this tight group at 0.67.
        result = choose_clusters(blob([1, 0, 0, 0], 8, spread=0.01))
        assert result.k == 1
        assert result.silhouette is None
        assert result.candidates == {}  # both splits rejected by the centroid-gap check
        assert np.allclose(np.linalg.norm(result.centroids, axis=1), 1, atol=1e-5)

    def test_two_separated_groups_split_in_two(self) -> None:
        x = np.vstack([blob([1, 0, 0, 0], 6), blob([0, 1, 0, 0], 4)])
        result = choose_clusters(x)
        assert result.k == 2
        assert result.silhouette is not None and result.silhouette > 0.5
        # Largest cluster first, and every image in a group shares a label.
        assert list(result.labels) == [0] * 6 + [1] * 4

    def test_three_groups_split_in_three(self) -> None:
        x = np.vstack([blob([1, 0, 0, 0], 5), blob([0, 1, 0, 0], 5), blob([0, 0, 1, 0], 5)])
        result = choose_clusters(x)
        assert result.k == 3
        assert set(result.candidates) == {2, 3}
        assert result.candidates[3] > result.candidates[2]

    def test_three_images_can_only_try_k2(self) -> None:
        result = choose_clusters(blob([1, 0, 0, 0], 3))
        assert set(result.candidates) <= {2}

    def test_weak_split_falls_back_to_one(self) -> None:
        # Uniformly scattered points have no real structure.
        x = blob([0, 0, 0, 0], 12, spread=1.0)
        result = choose_clusters(x, min_silhouette=0.5)
        assert result.k == 1


def test_silhouette_matches_hand_computed_value() -> None:
    # Two points per cluster on orthogonal axes: a = 0 within, b = 1 across, so s = 1 for everyone.
    x = np.array([[1, 0], [1, 0], [0, 1], [0, 1]], dtype=np.float64)
    assert silhouette(x, np.array([0, 0, 1, 1])) == pytest.approx(1.0)


class ColorEmbedder(FakeEmbedder):
    """Embeds an image by its dominant RGB channel so test boards have known structure."""

    def embed_images(self, images: list[Image.Image]) -> np.ndarray:
        out = []
        for img in images:
            r, g, b = np.asarray(img.convert("RGB"), dtype=np.float64).reshape(-1, 3).mean(0)
            v = np.array([r, g, b, 1.0])
            out.append(v / np.linalg.norm(v))
        return np.stack(out).astype(np.float32)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        # Deterministic pseudo-random directions for the style vocabulary.
        rng = np.random.default_rng(0)
        v = rng.normal(size=(len(texts), DIM))
        return (v / np.linalg.norm(v, axis=1, keepdims=True)).astype(np.float32)


def png(color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def board_client(catalog: Catalog) -> TestClient:
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_embedder] = ColorEmbedder
    yield TestClient(app)  # type: ignore[misc]
    app.dependency_overrides.clear()


def upload(colors: list[tuple[int, int, int]]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("images", (f"{i}.png", png(c), "image/png")) for i, c in enumerate(colors)]


def test_analyze_finds_two_aesthetics_and_matches_catalog(board_client: TestClient) -> None:
    red, blue = (230, 20, 20), (20, 20, 230)
    response = board_client.post("/board/analyze", files=upload([red, red, red, blue, blue]), params={"k": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["k"] == 2
    assert body["silhouette"] > 0.1
    first, second = body["aesthetics"]
    assert first["image_indices"] == [0, 1, 2] and second["image_indices"] == [3, 4]
    # Red aesthetic matches the red/pink t-shirts (catalog axis 0); blue matches the jeans (axis 2).
    assert {r["id"] for r in first["results"]} == {"tshirt-red", "tshirt-pink"}
    assert second["results"][0]["id"] == "pants-jeans"
    assert all(t["word"] in STYLE_WORDS for t in first["style_tags"]) and len(first["style_tags"]) == 3


def test_analyze_single_look_board(board_client: TestClient) -> None:
    response = board_client.post("/board/analyze", files=upload([(230, 20, 20)] * 4))
    body = response.json()
    assert body["k"] == 1 and body["silhouette"] is None
    assert body["aesthetics"][0]["image_indices"] == [0, 1, 2, 3]


@pytest.mark.parametrize("count", [2, 21])
def test_analyze_rejects_wrong_image_count(board_client: TestClient, count: int) -> None:
    response = board_client.post("/board/analyze", files=upload([(1, 2, 3)] * count))
    assert response.status_code == 422


def test_analyze_rejects_non_image(board_client: TestClient) -> None:
    files = upload([(230, 20, 20)] * 2) + [("images", ("x.txt", b"hello", "text/plain"))]
    assert board_client.post("/board/analyze", files=files).status_code == 415
