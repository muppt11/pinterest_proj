"""FastAPI dependencies. Tests swap these via app.dependency_overrides."""

from functools import lru_cache

from fastapi import HTTPException

from app.config import get_settings
from app.services.catalog import Catalog
from app.services.embedder import Embedder, FashionClipEmbedder


@lru_cache
def _load_catalog() -> Catalog:
    return Catalog.load(get_settings().index_dir)


def get_catalog() -> Catalog:
    """The loaded catalog, or a 503 telling the developer to build the index."""
    try:
        return _load_catalog()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Catalog index not built yet. Run `make index`.") from exc


@lru_cache
def get_embedder() -> Embedder:
    """The FashionCLIP model, loaded once on first use (takes a few seconds)."""
    return FashionClipEmbedder()
