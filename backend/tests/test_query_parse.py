"""Query understanding: garment words -> categories, color words -> color target."""

import pytest

from app.services.query_parse import parse_query


def test_garment_and_color_words() -> None:
    q = parse_query("Black leather boots")
    assert q.categories == {"Shoes"} and q.color == "black" and q.family is None
    assert q.summary == ["Shoes", "black"]


def test_multiword_colors_win_over_single_words() -> None:
    assert parse_query("sage green linen shirt").color == "sage green"
    assert parse_query("hot pink mini skirt").color == "hot pink"


def test_families_and_no_matches() -> None:
    q = parse_query("pastel cardigan")
    assert q.family == "pastels" and q.categories == {"Longsleeve"}
    none = parse_query("cozy fall vibes")
    assert none.categories is None and none.color is None and none.family is None


def test_word_boundaries() -> None:
    # "capri" must not trigger "cap"; "tanned" must not trigger "tan"
    assert parse_query("capri").categories is None
    assert parse_query("tanned look").color is None


@pytest.mark.parametrize(("query", "categories"), [
    ("jackets", {"Outwear"}), ("dresses", {"Dress"}),
    ("skirts", {"Skirt"}), ("hoodies", {"Hoodie"}),
    ("T shirts", {"T-Shirt"}), ("t-shirts", {"T-Shirt"}),
])
def test_common_plural_and_spaced_garment_names(query: str, categories: set[str]) -> None:
    assert parse_query(query).categories == categories


def test_british_color_spelling() -> None:
    assert parse_query("light grey sweaters").color == "light gray"


@pytest.mark.parametrize(("query", "categories"), [
    ("white dress shirt", {"Shirt"}), ("shirt dresses", {"Dress"}),
    ("polo shirts", {"Polo"}), ("long-sleeve shirts", {"Longsleeve"}),
    ("cropped top", {"Top"}), ("button down shirt", {"Shirt"}),
    ("black jackets and blazers", {"Outwear", "Blazer"}),
])
def test_compound_garments_do_not_expand_to_unrelated_categories(query: str, categories: set[str]) -> None:
    assert parse_query(query).categories == categories


def test_kids_and_earth_tone_queries() -> None:
    parsed = parse_query("children's earth tone jackets")
    assert parsed.kids is True and parsed.family == "earth tones" and parsed.categories == {"Outwear"}
