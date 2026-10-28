"""Character style boards: written style profiles of iconic film/TV looks, matched against the catalog.

Profiles are short editorial descriptions of each character's signature costume *style* in general
terms. They are not claims about specific garments, brands, or prices, and no film stills or actor
photos are used anywhere.
"""

from dataclasses import dataclass

import numpy as np

from app.services.catalog import Catalog, Hit
from app.services.embedder import Embedder


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    source: str  # film or show, with year
    summary: str
    phrases: tuple[str, ...]


CHARACTERS: tuple[Character, ...] = (
    Character(
        "cher-horowitz", "Cher Horowitz", "Clueless (1995)",
        "Coordinated 90s preppy: matching plaid sets, knee socks, and crisp collars.",
        ("yellow plaid blazer and matching mini skirt", "knee-high socks with mary jane shoes", "white collared shirt", "preppy coordinated two-piece set"),
    ),
    Character(
        "rachel-green", "Rachel Green", "Friends (1994–2004)",
        "Easy 90s staples: slip dresses, mini skirts, fitted knits, and knee boots.",
        ("plaid mini skirt", "satin slip dress", "fitted cropped cardigan", "knee-high boots", "straight-leg jeans with a fitted top"),
    ),
    Character(
        "carrie-bradshaw", "Carrie Bradshaw", "Sex and the City (1998–2004)",
        "Playful, maximal city dressing: tulle, mixed prints, and statement heels.",
        ("tulle tutu skirt", "mixed bold prints", "statement high heels", "fitted tank top with a full skirt", "printed slip dress"),
    ),
    Character(
        "blair-waldorf", "Blair Waldorf", "Gossip Girl (2007–2012)",
        "Polished preppy: headbands, pleats, tights, and tailored blazers.",
        ("pleated skirt with tights", "tailored blazer", "peter pan collar dress", "fitted coat in a bold color", "preppy schoolgirl outfit"),
    ),
    Character(
        "elle-woods", "Elle Woods", "Legally Blonde (2001)",
        "Unapologetically pink: pink suits, pink dresses, and polished accessories.",
        ("hot pink skirt suit", "pink fitted dress", "pink cardigan", "feminine pastel outfit"),
    ),
    Character(
        "wednesday-addams", "Wednesday Addams", "Wednesday (2022)",
        "Strict monochrome gothic: black dresses, white collars, and pleats.",
        ("black dress with a white collar", "black pleated skirt", "black and white striped top", "chunky black platform boots", "all black gothic outfit"),
    ),
    Character(
        "indiana-jones", "Indiana Jones", "Raiders of the Lost Ark (1981)",
        "Rugged adventurer: leather jacket, khaki shirt, fedora, and boots.",
        ("brown leather jacket", "khaki button-up shirt", "brown fedora hat", "rugged canvas trousers", "leather work boots"),
    ),
    Character(
        "the-dude", "The Dude", "The Big Lebowski (1998)",
        "Relaxed and rumpled: patterned cardigans, baggy shorts, and loose tees.",
        ("chunky patterned knit cardigan", "loose baggy shorts", "faded loose t-shirt", "casual sandals"),
    ),
    Character(
        "ted-lasso", "Ted Lasso", "Ted Lasso (2020–2023)",
        "Coach-casual: quarter-zips, polos, khakis, and sneakers.",
        ("quarter-zip pullover", "polo shirt", "khaki chino pants", "casual sneakers", "track jacket"),
    ),
)

BY_ID = {c.id: c for c in CHARACTERS}


@dataclass
class CharacterMatch:
    hit: Hit
    matched_phrase: str
    phrase_score: float


class CharacterBoards:
    """Embeds each character's phrases once and ranks the catalog against their mean."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._phrases: dict[str, np.ndarray] = {}

    def phrase_vectors(self, character: Character) -> np.ndarray:
        if character.id not in self._phrases:
            self._phrases[character.id] = self._embedder.embed_texts(list(character.phrases))
        return self._phrases[character.id]

    def board(
        self, catalog: Catalog, character: Character, k: int = 24, kids: bool | None = False, exclude_ids: set[str] | None = None
    ) -> list[CharacterMatch]:
        """Top-k items for the character's style (adult items by default), each with its best phrase."""
        vectors = self.phrase_vectors(character)
        centroid = vectors.mean(0)
        centroid /= np.linalg.norm(centroid)
        matches = []
        for hit in catalog.search(centroid, k=k, kids=kids, exclude_ids=exclude_ids):
            scores = vectors @ catalog.vector(hit.item["id"])
            best = int(np.argmax(scores))
            matches.append(CharacterMatch(hit, character.phrases[best], float(scores[best])))
        return matches
