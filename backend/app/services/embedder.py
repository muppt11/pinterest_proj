"""Image and text embeddings from Marqo-FashionCLIP (open_clip)."""

from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

HUB_MODEL = "hf-hub:Marqo/marqo-fashionCLIP"
WEIGHTS_FILE = "open_clip_model.safetensors"


def model_name(local_dir: Path | None) -> str:
    """Prefer the verified local copy from scripts/download_model.sh; fall back to the Hugging Face Hub."""
    if local_dir is not None and (local_dir / WEIGHTS_FILE).exists():
        return f"local-dir:{local_dir}"
    return HUB_MODEL


class Embedder(Protocol):
    """Anything that maps images or text into the same L2-normalized vector space."""

    dim: int

    def embed_images(self, images: list[Image.Image]) -> np.ndarray: ...

    def embed_texts(self, texts: list[str]) -> np.ndarray: ...


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize rows so inner product equals cosine similarity."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.clip(norms, 1e-12, None)).astype(np.float32)


class FashionClipEmbedder:
    """Loads Marqo-FashionCLIP once and embeds batches on Apple GPU (MPS) when available."""

    def __init__(self, local_dir: Path | None = None) -> None:
        import open_clip
        import torch

        self._torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        name = model_name(local_dir)
        model, _, preprocess = open_clip.create_model_and_transforms(name)
        self.model = model.to(self.device).eval()
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(name)
        self.dim = int(self.model.text_projection.shape[1])

    def embed_images(self, images: list[Image.Image]) -> np.ndarray:
        """Embed RGB images; returns an (n, dim) float32 array of unit vectors."""
        batch = self._torch.stack([self.preprocess(img.convert("RGB")) for img in images]).to(self.device)
        with self._torch.no_grad():
            features = self.model.encode_image(batch)
        return _normalize(features.float().cpu().numpy())

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed text queries; returns an (n, dim) float32 array of unit vectors."""
        tokens = self.tokenizer(texts).to(self.device)
        with self._torch.no_grad():
            features = self.model.encode_text(tokens)
        return _normalize(features.float().cpu().numpy())


# --- Out-of-process embedding ------------------------------------------------------------------
# On macOS, faiss-cpu and torch each bundle their own OpenMP runtime (libomp). Once both are
# initialized in one process, OpenMP aborts ("OMP: Error #15"); its only escape hatch is an
# officially unsafe flag that may silently produce wrong results. So the model runs in a separate
# worker process: the API process holds FAISS, the worker holds torch, and they never share a runtime.
# This module must not import faiss, because the worker imports it.

_worker: FashionClipEmbedder | None = None


def _exit_when_orphaned(parent_pid: int, interval_s: float = 2.0) -> None:
    """Background thread: if the API process dies (e.g. a dev-server reload), exit too instead of
    lingering with a copy of the model in memory."""
    import os
    import threading
    import time

    def watch() -> None:
        while True:
            time.sleep(interval_s)
            if os.getppid() != parent_pid:
                os._exit(0)

    threading.Thread(target=watch, daemon=True, name="orphan-watch").start()


def _init_worker(local_dir: Path | None, parent_pid: int | None = None) -> None:
    global _worker
    if parent_pid is not None:
        _exit_when_orphaned(parent_pid)
    _worker = FashionClipEmbedder(local_dir)


def _worker_dim() -> int:
    assert _worker is not None
    return _worker.dim


def _worker_embed_images(images: list[Image.Image]) -> np.ndarray:
    assert _worker is not None
    return _worker.embed_images(images)


def _worker_embed_texts(texts: list[str]) -> np.ndarray:
    assert _worker is not None
    return _worker.embed_texts(texts)


class ProcessEmbedder:
    """FashionCLIP running in one dedicated worker process (spawned, so it starts clean)."""

    def __init__(self, local_dir: Path | None = None) -> None:
        import multiprocessing
        import os
        from concurrent.futures import ProcessPoolExecutor

        self._pool = ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_init_worker,
            initargs=(local_dir, os.getpid()),
        )
        self.dim: int = self._pool.submit(_worker_dim).result()  # waits for the model to load

    def embed_images(self, images: list[Image.Image]) -> np.ndarray:
        return self._pool.submit(_worker_embed_images, [img.convert("RGB") for img in images]).result()

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return self._pool.submit(_worker_embed_texts, texts).result()

    def close(self) -> None:
        self._pool.shutdown()
