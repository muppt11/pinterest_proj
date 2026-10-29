"""Endpoint tests for browsing, text search, image search, and 'More like this'."""

from fastapi.testclient import TestClient

from app.deps import get_catalog
from app.main import app

from .conftest import image_bytes


def ids(response) -> list[str]:  # type: ignore[no-untyped-def]
    return [r["id"] for r in response.json()["results"]]


def test_list_items_paginates_and_filters(client: TestClient) -> None:
    page = client.get("/items", params={"limit": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2
    assert page["items"][0]["image_url"] == "/images/tshirt-red.jpg"

    shoes = client.get("/items", params={"category": "Shoes"}).json()
    assert [i["id"] for i in shoes["items"]] == ["shoes-boot"]


def test_get_item_and_404(client: TestClient) -> None:
    assert client.get("/items/pants-jeans").json()["category"] == "Pants"
    assert client.get("/items/nope").status_code == 404


def test_similar_excludes_the_item_itself(client: TestClient) -> None:
    response = client.get("/items/tshirt-red/similar", params={"k": 2})
    # Pink is nearly parallel to red; boot and jeans are orthogonal (tied), so only check the top hit.
    assert ids(response)[0] == "tshirt-pink"
    assert "tshirt-red" not in ids(response) and len(ids(response)) == 2
    assert client.get("/items/nope/similar").status_code == 404


def test_text_search_ranks_matching_items_first(client: TestClient) -> None:
    response = client.get("/search/text", params={"q": "red shirt", "k": 2})
    assert response.status_code == 200
    assert response.json()["query"] == "red shirt"
    assert ids(response) == ["tshirt-red", "tshirt-pink"]


def test_off_topic_query_is_flagged_low_relevance(client: TestClient) -> None:
    # The fake embedder maps unknown words to an axis no catalog item points along (cosine 0).
    response = client.get("/search/text", params={"q": "birthday cake"}).json()
    assert response["low_relevance"] is True
    assert len(response["results"]) == 4  # closest items still returned for "show anyway"


def test_matching_query_is_not_flagged(client: TestClient, catalog) -> None:  # type: ignore[no-untyped-def]
    from app.services import relevance as search

    # Mean of the 4 fixture scores for "shirt" is ~0.5, well above the cutoff.
    response = client.get("/search/text", params={"q": "red shirt"}).json()
    assert response["low_relevance"] is False
    assert search.MIN_TEXT_RELEVANCE < 0.5


def test_text_search_with_category_filter(client: TestClient) -> None:
    response = client.get("/search/text", params={"q": "boot", "category": "Pants"})
    assert ids(response) == ["pants-jeans"]


def test_text_search_rejects_blank_and_unknown_category(client: TestClient) -> None:
    assert client.get("/search/text", params={"q": "   "}).status_code == 422
    assert client.get("/search/text", params={"q": ""}).status_code == 422
    assert client.get("/search/text", params={"q": "shirt", "category": "Hats?"}).status_code == 422


def test_image_search_returns_nearest_items(client: TestClient) -> None:
    files = {"image": ("look.jpg", image_bytes(), "image/jpeg")}
    response = client.post("/search/image", files=files, params={"k": 1})
    assert response.status_code == 200
    assert ids(response) == ["tshirt-red"]


def test_image_search_rejects_wrong_type_and_bad_bytes(client: TestClient) -> None:
    gif = {"image": ("x.gif", image_bytes("GIF"), "image/gif")}
    assert client.post("/search/image", files=gif).status_code == 415

    junk = {"image": ("x.jpg", b"not an image", "image/jpeg")}
    assert client.post("/search/image", files=junk).status_code == 400


def test_image_search_rejects_oversized_upload(client: TestClient) -> None:
    big = {"image": ("big.jpg", b"0" * (10 * 1024 * 1024 + 1), "image/jpeg")}
    assert client.post("/search/image", files=big).status_code == 413


def test_missing_index_returns_503() -> None:
    def missing():  # type: ignore[no-untyped-def]
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Catalog index not built yet. Run `make index`.")

    app.dependency_overrides[get_catalog] = missing
    try:
        assert TestClient(app).get("/items").status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_text_search_understands_garment_and_color_words(client: TestClient) -> None:
    body = client.get("/search/text", params={"q": "boot", "k": 4}).json()
    # "boot" -> Shoes only, even though other items exist
    assert {r["category"] for r in body["results"]} == {"Shoes"}
    assert body["understood"] == ["Shoes"]


def test_garment_type_filter_on_browse_and_search(client: TestClient) -> None:
    bottoms = client.get("/items", params={"group": "bottoms"}).json()
    assert [i["id"] for i in bottoms["items"]] == ["pants-jeans"] and bottoms["total"] == 1
    shoes = client.get("/search/text", params={"q": "red shirt", "group": "shoes"}).json()
    assert {r["category"] for r in shoes["results"]} == {"Shoes"} and shoes["understood"] == ["Shoes", "red"]
    assert client.get("/items", params={"group": "capes"}).status_code == 422


def test_aesthetic_ranking_on_browse(client: TestClient) -> None:
    body = client.get("/items", params={"style": "minimalist", "limit": 4}).json()
    assert body["total"] == 4 and len(body["items"]) == 4
    assert client.get("/items", params={"style": "goblincore"}).status_code == 422
