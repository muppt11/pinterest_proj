"""Query understanding: garment words -> categories, color words -> color target."""

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
