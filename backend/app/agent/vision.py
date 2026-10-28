"""Short garment descriptions from the local vision model (qwen2.5vl via Ollama), cached per item."""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROMPT = (
    "Describe this clothing item in one short sentence: type, color, pattern, and apparent material or "
    "texture. Describe only what is visible. Do not guess brand, price, or size."
)

SHOPPING_PROMPT = (
    "Write a Google Shopping search query, at most 8 words, that would find this exact clothing item. "
    "Include color, pattern, material or texture, cut or fit, and item type, but only what is clearly visible. "
    "No brand names, no prices, no sizes. Reply with the query only."
)


class VisionDescriber:
    """Calls Ollama's vision model; returns None (never raises) if it's unavailable."""

    def __init__(self, host: str, model: str, images_dir: Path, timeout_s: float = 60) -> None:
        import ollama

        self._client = ollama.Client(host=host, timeout=timeout_s)
        self._model = model
        self._images_dir = images_dir
        self._cache: dict[tuple[str, str], str] = {}

    def _ask(self, item: dict[str, Any], prompt: str) -> str | None:
        key = (item["id"], prompt)
        if key in self._cache:
            return self._cache[key]
        try:
            response = self._client.chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt, "images": [str(self._images_dir / item["image_file"])]}],
                options={"temperature": 0},
            )
            text = response["message"]["content"].strip()
        except Exception as exc:  # model not pulled, Ollama not running, timeout...
            logger.warning("vision model call failed for %s: %s", item["id"], exc)
            return None
        self._cache[key] = text
        return text

    def __call__(self, item: dict[str, Any]) -> str | None:
        """One-sentence visual description (used by the assistant's compare_items)."""
        return self._ask(item, PROMPT)

    def shopping_query(self, item: dict[str, Any]) -> str | None:
        """A specific shopping query for this item's photo, or None if the model is unavailable."""
        text = self._ask(item, SHOPPING_PROMPT)
        return clean_query(text) if text else None


def clean_query(text: str, max_words: int = 10) -> str | None:
    """Keep the first line, drop quotes/markdown and anything that looks like a price, cap the length."""
    line = text.strip().splitlines()[0] if text.strip() else ""
    line = re.sub(r"[\"'`*#]|^query:\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"[$€£]\s?\d[\d.,]*", "", line)
    words = line.split()[:max_words]
    return " ".join(words) or None
