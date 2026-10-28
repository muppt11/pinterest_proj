"""Short garment descriptions from the local vision model (qwen2.5vl via Ollama), cached per item."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROMPT = (
    "Describe this clothing item in one short sentence: type, color, pattern, and apparent material or "
    "texture. Describe only what is visible. Do not guess brand, price, or size."
)


class VisionDescriber:
    """Calls Ollama's vision model; returns None (never raises) if it's unavailable."""

    def __init__(self, host: str, model: str, images_dir: Path, timeout_s: float = 60) -> None:
        import ollama

        self._client = ollama.Client(host=host, timeout=timeout_s)
        self._model = model
        self._images_dir = images_dir
        self._cache: dict[str, str] = {}

    def __call__(self, item: dict[str, Any]) -> str | None:
        if item["id"] in self._cache:
            return self._cache[item["id"]]
        try:
            response = self._client.chat(
                model=self._model,
                messages=[{"role": "user", "content": PROMPT, "images": [str(self._images_dir / item["image_file"])]}],
                options={"temperature": 0},
            )
            text = response["message"]["content"].strip()
        except Exception as exc:  # model not pulled, Ollama not running, timeout...
            logger.warning("vision description failed for %s: %s", item["id"], exc)
            return None
        self._cache[item["id"]] = text
        return text
