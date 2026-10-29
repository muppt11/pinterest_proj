"""Light query understanding for text search: garment words -> catalog categories, color words -> a
target color or color family. The rest of the query still goes through FashionCLIP as-is.

"black leather boots" -> categories {Shoes}, color "black", so a black t-shirt can't outrank boots.
"""

import re
from dataclasses import dataclass

from app.services.color_search import COLOR_NAMES

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
    "jacket": {"Outwear", "Blazer"}, "coat": {"Outwear"}, "parka": {"Outwear"}, "bomber": {"Outwear"},
    "puffer": {"Outwear"}, "windbreaker": {"Outwear"}, "outerwear": {"Outwear"},
    "hoodie": {"Hoodie"}, "sweatshirt": {"Hoodie", "Longsleeve"},
    "polo": {"Polo"},
    "tee": {"T-Shirt"}, "t-shirt": {"T-Shirt"}, "tshirt": {"T-Shirt"},
    "shirt": {"Shirt"}, "button-up": {"Shirt"}, "button-down": {"Shirt"}, "blouse": {"Blouse", "Shirt"},
    "sweater": {"Longsleeve"}, "cardigan": {"Longsleeve"}, "turtleneck": {"Longsleeve"}, "jumper": {"Longsleeve"},
    "knit": {"Longsleeve"},
    "top": {"Top", "T-Shirt", "Undershirt", "Body", "Blouse"}, "tank": {"Undershirt", "Top"},
    "cami": {"Top", "Undershirt"}, "bodysuit": {"Body"},
}

FAMILY_WORDS = {
    "pastel": "pastels", "pastels": "pastels",
    "neon": "brights", "bright": "brights", "vibrant": "brights",
    "neutral": "neutrals", "neutrals": "neutrals",
    "earthy": "earth tones",
}

_COLOR_PATTERN = re.compile(
    r"\b(" + "|".join(sorted((re.escape(c) for c in COLOR_NAMES), key=len, reverse=True)) + r")\b"
)


@dataclass
class ParsedQuery:
    text: str
    categories: set[str] | None  # None = no garment word found
    color: str | None  # a named color from COLOR_NAMES
    family: str | None  # a color family word ("pastel" etc.)

    @property
    def summary(self) -> list[str]:
        out = sorted(self.categories) if self.categories else []
        if self.color:
            out.append(self.color)
        if self.family:
            out.append(self.family)
        return out


def parse_query(query: str) -> ParsedQuery:
    q = query.lower()
    categories: set[str] = set()
    for word in re.findall(r"[a-z]+(?:-[a-z]+)?", q):
        categories |= CATEGORY_WORDS.get(word, set())
    color_match = _COLOR_PATTERN.search(q)
    family = next((FAMILY_WORDS[w] for w in re.findall(r"[a-z]+", q) if w in FAMILY_WORDS), None)
    return ParsedQuery(query, categories or None, color_match.group(1) if color_match else None, family)
