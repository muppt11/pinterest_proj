"""Image and text embeddings from Marqo-FashionCLIP (open_clip)."""

from typing import Protocol

import numpy as np
from PIL import Image

MODEL_NAME = "hf-hub:Marqo/marqo-fashionCLIP"


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

    def __init__(self) -> None:
        import open_clip
        import torch

        self._torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME)
        self.model = model.to(self.device).eval()
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(MODEL_NAME)
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
