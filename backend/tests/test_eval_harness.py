"""Eval fixtures must reflect evidence-based labels and compare distinct products."""

import random
import runpy
from pathlib import Path

import pytest

from .c2pa_fixtures import jpeg_bytes, sign_jpeg


@pytest.fixture(scope="module")
def harness() -> dict:
    return runpy.run_path(str(Path(__file__).resolve().parents[2] / "evals" / "run_evals.py"))


def test_comparison_context_never_repeats_an_item(harness: dict) -> None:
    for seed in range(20):
        ids = harness["context_ids"]({"Shirt": ["a", "b"]}, ["Shirt", "Shirt"], random.Random(seed))
        assert set(ids) == {"a", "b"} and len(ids) == 2


def test_insufficient_comparison_items_are_reported(harness: dict) -> None:
    with pytest.raises(ValueError, match="not enough distinct items"):
        harness["context_ids"]({"Shirt": ["a"]}, ["Shirt", "Shirt"], random.Random(7))


def test_unsigned_human_photos_are_correctly_expected_to_be_unknown(harness: dict, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    photos = tmp_path / "evals" / "labels_handset"
    for name in ("human", "verified"):
        (photos / name).mkdir(parents=True)
    (photos / "human" / "unsigned.jpg").write_bytes(jpeg_bytes())
    (photos / "verified" / "signed.jpg").write_bytes(sign_jpeg(jpeg_bytes(), "digitalCapture"))
    evaluate = harness["eval_labels"]
    monkeypatch.setitem(evaluate.__globals__, "REPO", tmp_path)
    report = "\n".join(evaluate())
    assert "Hand-labeled set: 2 files. Accuracy **100.0%**" in report
