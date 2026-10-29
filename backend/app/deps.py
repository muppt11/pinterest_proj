"""FastAPI dependencies. Tests swap these via app.dependency_overrides."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import numpy as np
from fastapi import Depends, HTTPException, Query
from langchain_core.language_models import BaseChatModel

from app.agent.vision import VisionDescriber
from app.config import get_settings
from app.services.catalog import Catalog
from app.services.embedder import Embedder, ProcessEmbedder
from app.services.style_focus import Focus, FocusIndex


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
def get_llm() -> BaseChatModel:
    """The local tool-calling model (qwen3 via Ollama). Thinking mode off: faster, and answers stay short."""
    from langchain_ollama import ChatOllama

    s = get_settings()
    return ChatOllama(model=s.agent_model, base_url=s.ollama_host, reasoning=False, temperature=0.2, num_ctx=8192)


@lru_cache
def get_describer() -> VisionDescriber:
    """Garment descriptions from the local vision model, used by compare_items."""
    s = get_settings()
    return VisionDescriber(s.ollama_host, s.vision_model, s.images_dir)


@lru_cache
def get_embedder() -> Embedder:
    """The FashionCLIP model in its own worker process, started on first use (takes a few seconds)."""
    return ProcessEmbedder(get_settings().model_dir)


def get_embedder_factory() -> Callable[[], Embedder]:
    """Lazy access to the embedder, for dependencies that only sometimes need the model."""
    return get_embedder


@dataclass
class FocusFilter:
    """The request's style focus, resolved to the item IDs it hides (empty for "all")."""

    focus: Focus
    excluded: set[str]
    mask: np.ndarray | None  # per-row allowed mask, or None for "all"
    lean: np.ndarray | None = None  # per-row womenswear-minus-menswear lean, or None for "all"

    @property
    def bias(self) -> np.ndarray | None:
        """Additive cosine bias for similarity search: up to ±0.03 toward the chosen focus."""
        if self.lean is None or self.focus == "all":
            return None
        sign = 1.0 if self.focus == "women" else -1.0
        return 0.03 * np.clip(sign * self.lean / 0.08, -1, 1)

    def order(self, rows: list[int]) -> list[int]:
        """Rows with the most clearly on-focus items first (stable), so the feed visibly changes."""
        if self.lean is None or self.focus == "all":
            return rows
        sign = 1.0 if self.focus == "women" else -1.0
        return sorted(rows, key=lambda r: -sign * float(self.lean[r]))


def get_focus(
    catalog: Annotated[Catalog, Depends(get_catalog)],
    embedder_factory: Annotated[Callable[[], Embedder], Depends(get_embedder_factory)],
    focus: Annotated[Focus, Query(description="estimated style focus: all, women, or men")] = "all",
) -> FocusFilter:
    """Query param `focus`; the per-item estimate is computed once per catalog and cached on it.
    The model is only loaded when a focus other than "all" is requested."""
    if focus == "all":
        return FocusFilter("all", set(), None)
    index = getattr(catalog, "_focus_index", None)
    if index is None:
        index = FocusIndex(catalog, embedder_factory())
        catalog._focus_index = index  # type: ignore[attr-defined]
    return FocusFilter(focus, index.excluded_ids(focus), index.allowed(focus), index.lean)
