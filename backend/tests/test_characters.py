"""Character style boards."""

from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.deps import get_catalog, get_embedder
from app.main import app
from app.services.catalog import Catalog
from app.services.characters import BY_ID, CHARACTERS, CharacterBoards

from .conftest import DIM, FakeEmbedder


class PhraseEmbedder(FakeEmbedder):
    """'shirt'/'blazer'/'collar' phrases point at the t-shirt axis, 'boots' at the shoe axis, others at axis 3."""

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            if any(w in t for w in ("shirt", "blazer", "collar")):
                v[0] = 1
            elif "boots" in t or "shoes" in t:
                v[1] = 1
            else:
                v[3] = 1
            out.append(v)
        return np.stack(out)


def test_profiles_are_well_formed() -> None:
    assert len(CHARACTERS) >= 8 and len(BY_ID) == len(CHARACTERS)
    for c in CHARACTERS:
        assert c.looks and all(look.name and look.phrases for look in c.looks)
        assert 1 <= len(c.phrases) <= 12 and c.summary and "(" in c.source
        # Profiles describe style only: no prices, brands, or URLs.
        text = " ".join(c.phrases + (c.summary,)).lower()
        assert "$" not in text and "http" not in text


def test_board_excludes_kids_and_reports_matched_phrase(catalog: Catalog) -> None:
    boards = CharacterBoards(PhraseEmbedder())
    matches = boards.board(catalog, BY_ID["cher-horowitz"], k=3)
    ids = [m.hit.item["id"] for m in matches]
    assert "shoes-boot" not in ids  # kids item excluded by default
    assert ids and ids[0] in ("tshirt-red", "tshirt-pink", "pants-jeans")
    assert matches[0].matched_phrase in BY_ID["cher-horowitz"].phrases
    # Phrase vectors are cached after the first call.
    assert boards.phrase_vectors(BY_ID["cher-horowitz"]) is boards.phrase_vectors(BY_ID["cher-horowitz"])


@pytest.fixture
def client(catalog: Catalog) -> Iterator[TestClient]:
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_embedder] = PhraseEmbedder
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoints(client: TestClient) -> None:
    listed = client.get("/characters").json()
    assert [c["id"] for c in listed] == [c.id for c in CHARACTERS]
    assert all(1 <= len(c["covers"]) <= 4 for c in listed)
    assert all(not cover["kids"] for c in listed for cover in c["covers"])
    board = client.get("/characters/wednesday-addams", params={"k": 2}).json()
    assert board["name"] == "Wednesday Addams" and "not affiliated" in board["disclaimer"].lower()
    assert len(board["results"]) == 2 and board["results"][0]["matched_phrase"]
    assert [lo["name"] for lo in board["looks"]] == ["Nevermore uniform", "The Rave'N gown", "Everyday black"]
    assert all(r["matched_phrase"] in lo["phrases"] for lo in board["looks"] for r in lo["results"])
    assert client.get("/characters/nobody").status_code == 404
