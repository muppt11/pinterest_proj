"""Application settings loaded from environment variables (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Every field can be overridden with a MOODBOARDS_* env var."""

    model_config = SettingsConfigDict(
        env_prefix="MOODBOARDS_",
        env_file=REPO_ROOT / ".env",
        extra="ignore",
    )

    data_dir: Path = REPO_ROOT / "data"
    frontend_origin: str = "http://localhost:5173"
    ollama_host: str = "http://localhost:11434"
    agent_model: str = "qwen3:8b"
    vision_model: str = "qwen2.5vl:7b"
    secure_cookies: bool = False  # set MOODBOARDS_SECURE_COOKIES=1 when served over HTTPS (e.g. Hugging Face Spaces)

    @property
    def index_dir(self) -> Path:
        """Where scripts/build_index.py writes the FAISS index and metadata."""
        return self.data_dir / "index"

    @property
    def model_dir(self) -> Path:
        """Local Marqo-FashionCLIP copy written by scripts/download_model.sh."""
        return self.data_dir / "models" / "marqo-fashionCLIP"

    @property
    def images_dir(self) -> Path:
        """Catalog images from the clothing-dataset download."""
        return self.data_dir / "raw" / "clothing-dataset" / "images"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
