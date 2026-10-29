"""Light query understanding for text search: garment words -> catalog categories, color words -> a
target color or color family. The rest of the query still goes through FashionCLIP as-is.

"black leather boots" -> categories {Shoes}, color "black", so a black t-shirt can't outrank boots.
"""

import re
from dataclasses import dataclass

from app.services.color_search import COLOR_NAMES
from app.services.complete_look import GROUPS

# Garment words (singular and plural) -> dataset labels. Only labels that exist in the catalog.
CATEGORY_WORDS: dict[str, set[str]] = {
    "dress": {"Dress"}, "gown": {"Dress"}, "sundress": {"Dress"},
    "skirt": {"Skirt"}, "miniskirt": {"Skirt"},
    "jeans": {"Pants"}, "pants": {"Pants"}, "trousers": {"Pants"}, "chinos": {"Pants"}, "leggings": {"Pants"},
    "sweatpants": {"Pants"}, "joggers": {"Pants"}, "cargos": {"Pants"},
    "shorts": {"Shorts"},
    "boots": {"Shoes"}, "boot": {"Shoes"}, "sneakers": {"Shoes"}, "sneaker": {"Shoes"}, "shoes": {"Shoes"},
    "shoe": {"Shoes"}, "heels": {"Shoes"}, "sandals": {"Shoes"}, "loafers": {"Shoes"}, "trainers": {"Shoes"},
    "hat": {"Hat"}, "cap": {"Hat"}, "beanie": {"Hat"}, "fedora": {"Hat"},
    "blazer": {"Blazer"}, "suit": {"Blazer"},
    "jacket": {"Outwear"}, "coat": {"Outwear"}, "parka": {"Outwear"}, "bomber": {"Outwear"},
    "puffer": {"Outwear"}, "windbreaker": {"Outwear"}, "outerwear": {"Outwear"},
    "hoodie": {"Hoodie"}, "sweatshirt": {"Hoodie", "Longsleeve"},
    "polo": {"Polo"},
    "tee": {"T-Shirt"}, "t-shirt": {"T-Shirt"}, "tshirt": {"T-Shirt"},
    "shirt": {"Shirt", "T-Shirt"}, "button-up": {"Shirt"}, "button-down": {"Shirt"}, "blouse": {"Blouse"},
    "sweater": {"Longsleeve"}, "cardigan": {"Longsleeve"}, "turtleneck": {"Longsleeve"}, "jumper": {"Longsleeve"},
    "knit": {"Longsleeve"},
    "top": GROUPS["tops"], "tank": {"Undershirt", "Top"},
    "cami": {"Top", "Undershirt"}, "bodysuit": {"Body"},
}

FAMILY_WORDS = {
    "pastel": "pastels", "pastels": "pastels",
    "neon": "brights", "bright": "brights", "vibrant": "brights",
    "neutral": "neutrals", "neutrals": "neutrals",
    "earthy": "earth tones",
    "dark": "darks", "darks": "darks", "brights": "brights",
}

# Consume compound garments first: "dress shirt" is a shirt, "shirt dress" is a dress.
CATEGORY_PHRASES = [
    (re.compile(pattern), categories)
    for pattern, categories in [
        (r"\bdress shirts?\b", {"Shirt"}),
        (r"\bshirt dress(?:es)?\b", {"Dress"}),
        (r"\bpolo shirts?\b", {"Polo"}),
        (r"\btank tops?\b", {"Undershirt", "Top"}),
        (r"\bcrop(?:ped)? tops?\b", {"Top"}),
        (r"\blong[ -]?sleeve(?:d)? (?:tops?|shirts?)\b", {"Longsleeve"}),
        (r"\bbutton[ -](?:up|down)(?: shirts?)?\b", {"Shirt"}),
        (r"\b(?:t[ -]shirts?|tee shirts?)\b", {"T-Shirt"}),
    ]
]

# Generate only known regular plurals; don't stem arbitrary words (e.g. "dress" or "jeans").
for _word, _categories in list(CATEGORY_WORDS.items()):
    if not _word.endswith("s"):
        CATEGORY_WORDS.setdefault(_word + ("es" if _word.endswith(("ch", "sh")) else "s"), _categories)
CATEGORY_WORDS["dresses"] = {"Dress"}

_COLOR_PATTERN = re.compile(
    r"\b(" + "|".join(sorted((re.escape(c) for c in COLOR_NAMES), key=len, reverse=True)) + r")\b"
)


@dataclass
class ParsedQuery:
    text: str
    categories: set[str] | None  # None = no garment word found
    color: str | None  # a named color from COLOR_NAMES
    family: str | None  # a color family word ("pastel" etc.)
    kids: bool | None = None

    @property
    def summary(self) -> list[str]:
        out = sorted(self.categories) if self.categories else []
        if self.color:
            out.append(self.color)
        if self.family:
            out.append(self.family)
        return out


def parse_query(query: str) -> ParsedQuery:
    q = re.sub(r"\bgrey\b", "gray", query.lower())
    categories: set[str] = set()
    garments = q
    for pattern, matched_categories in CATEGORY_PHRASES:
        if pattern.search(garments):
            categories |= matched_categories
            garments = pattern.sub(" ", garments)
    for word in re.findall(r"[a-z]+(?:-[a-z]+)?", garments):
        categories |= CATEGORY_WORDS.get(word, set())
    color_match = _COLOR_PATTERN.search(q)
    family = next((FAMILY_WORDS[w] for w in re.findall(r"[a-z]+", q) if w in FAMILY_WORDS), None)
    if re.search(r"\b(?:earth[ -]tones?|earth[ -]toned)\b", q):
        family = "earth tones"
    kids = True if re.search(r"\b(?:kids?|children|child|toddlers?|boys?|girls?|baby|babies|infants?)\b", q) else None
    return ParsedQuery(query, categories or None, color_match.group(1) if color_match else None, family, kids)
