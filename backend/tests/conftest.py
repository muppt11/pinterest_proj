"""Shared fixtures: a tiny in-memory catalog and a deterministic fake embedder.

Tests never load the real FashionCLIP model or the real index, so they run in under a second.
"""

import io
from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.deps import get_catalog, get_embedder
from app.main import app
from app.services.catalog import Catalog

DIM = 4


def _unit(*values: float) -> np.ndarray:
    v = np.array(values, dtype=np.float32)
    return v / np.linalg.norm(v)


# Four items on known directions so expected rankings are easy to reason about.
VECTORS = np.stack(
    [
        _unit(1, 0, 0, 0),  # tshirt-red
        _unit(0.9, 0.1, 0, 0),  # tshirt-pink (close to red)
        _unit(0, 1, 0, 0),  # shoes-boot
        _unit(0, 0, 1, 0),  # pants-jeans
    ]
)
ITEMS = [
    {"id": "tshirt-red", "category": "T-Shirt", "image_file": "tshirt-red.jpg", "kids": False, "width": 400, "height": 533, "sender_id": "1"},
    {"id": "tshirt-pink", "category": "T-Shirt", "image_file": "tshirt-pink.jpg", "kids": False, "width": 400, "height": 533, "sender_id": "2"},
    {"id": "shoes-boot", "category": "Shoes", "image_file": "shoes-boot.jpg", "kids": True, "width": 400, "height": 400, "sender_id": "1"},
    {"id": "pants-jeans", "category": "Pants", "image_file": "pants-jeans.jpg", "kids": False, "width": 400, "height": 600, "sender_id": "3"},
]


class FakeEmbedder:
    """Maps known words to fixed directions; every image embeds like a red t-shirt."""

    dim = DIM
    WORDS = {"shirt": _unit(1, 0, 0, 0), "boot": _unit(0, 1, 0, 0), "jeans": _unit(0, 0, 1, 0)}

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return np.stack([self.WORDS.get(t.split()[-1], _unit(0, 0, 0, 1)) for t in texts])

    def embed_images(self, images: list[Image.Image]) -> np.ndarray:
        return np.stack([_unit(1, 0, 0, 0) for _ in images])


@pytest.fixture
def catalog() -> Catalog:
    return Catalog.from_vectors(VECTORS, [dict(i) for i in ITEMS])


@pytest.fixture
def client(catalog: Catalog) -> Iterator[TestClient]:
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_embedder] = FakeEmbedder
    yield TestClient(app)
    app.dependency_overrides.clear()


def image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format=fmt)
    return buf.getvalue()
