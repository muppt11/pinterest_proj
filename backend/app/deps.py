"""FastAPI dependencies. Tests swap these via app.dependency_overrides."""

from functools import lru_cache

from fastapi import HTTPException
from langchain_core.language_models import BaseChatModel

from app.agent.vision import VisionDescriber
from app.config import get_settings
from app.services.catalog import Catalog
from app.services.embedder import Embedder, ProcessEmbedder


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
