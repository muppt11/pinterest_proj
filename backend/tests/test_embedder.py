"""Model-source selection (the model itself isn't loaded in unit tests)."""

from pathlib import Path

from app.services.embedder import HUB_MODEL, WEIGHTS_FILE, model_name


def test_prefers_verified_local_copy(tmp_path: Path) -> None:
    (tmp_path / WEIGHTS_FILE).write_bytes(b"")
    assert model_name(tmp_path) == f"local-dir:{tmp_path}"


def test_falls_back_to_hub_without_local_weights(tmp_path: Path) -> None:
    assert model_name(tmp_path) == HUB_MODEL
    assert model_name(None) == HUB_MODEL
