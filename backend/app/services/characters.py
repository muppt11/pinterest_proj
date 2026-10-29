"""Character style boards: iconic film/TV characters as named *signature looks*, matched to the catalog.

Each look is a few garment phrases written from widely reported costume descriptions. They describe
costume *style* in general terms: no brands, prices, film stills, or actor photos are used. Each phrase
is matched with query understanding (garment word -> category, color word -> CIEDE2000 re-rank), so
"yellow plaid blazer" only considers blazers and prefers yellow ones.
"""

from dataclasses import dataclass

import numpy as np

from app.services.catalog import Catalog, Hit
from app.services.color import delta_e_2000, rgb_to_lab
from app.services.color_families import items_in_families
from app.services.color_search import COLOR_NAMES, color_index
from app.services.embedder import Embedder
from app.services.query_parse import parse_query


@dataclass(frozen=True)
class Look:
    name: str
    phrases: tuple[str, ...]


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    source: str  # film or show, with year(s)
    summary: str
    looks: tuple[Look, ...]

    @property
    def phrases(self) -> tuple[str, ...]:
        return tuple(p for look in self.looks for p in look.phrases)


CHARACTERS: tuple[Character, ...] = (
    Character("cher-horowitz", "Cher Horowitz", "Clueless (1995)", "Coordinated 90s preppy with matching sets and knee socks.", (
        Look("The yellow plaid suit", ("yellow plaid blazer", "yellow plaid mini skirt", "white knee-high socks")),
        Look("The white slip dress", ("white slip mini dress",)),
        Look("Preppy school day", ("plaid mini skirt", "fitted cardigan", "white collared shirt")),
    )),
    Character("wednesday-addams", "Wednesday Addams", "Wednesday (2022)", "Strict monochrome gothic: stripes, pleats, collars, platforms.", (
        Look("Nevermore uniform", ("black and white striped blazer", "black pleated skirt", "white collared shirt")),
        Look("The Rave'N gown", ("black tulle dress",)),
        Look("Everyday black", ("black dress with a white collar", "black platform boots", "black and white striped top")),
    )),
    Character("rachel-green", "Rachel Green", "Friends (1994–2004)", "Easy 90s staples: slip dresses, mini skirts, fitted knits.", (
        Look("Plaid mini and turtleneck", ("plaid mini skirt", "fitted turtleneck sweater", "knee-high boots")),
        Look("The 90s slip dress", ("black slip dress",)),
        Look("Coffee-shop casual", ("straight-leg jeans", "fitted white t-shirt", "cropped cardigan")),
    )),
    Character("carrie-bradshaw", "Carrie Bradshaw", "Sex and the City (1998–2004)", "Playful city dressing: tulle, prints, and heels.", (
        Look("The opening-credits tutu", ("white tulle tutu skirt", "pink tank top")),
        Look("The newspaper-print dress", ("newspaper print dress",)),
        Look("Night out", ("satin slip dress", "strappy high heels", "fitted mini skirt")),
    )),
    Character("blair-waldorf", "Blair Waldorf", "Gossip Girl (2007–2012)", "Polished Upper East Side preppy.", (
        Look("The Constance uniform", ("navy blazer", "pleated skirt", "white collared shirt", "colorful tights")),
        Look("Statement coat", ("bright colored tailored coat",)),
        Look("Lady-like", ("peter pan collar dress", "fitted cardigan")),
    )),
    Character("rory-gilmore", "Rory Gilmore", "Gilmore Girls (2000–2007)", "Bookish New England layers.", (
        Look("Chilton uniform", ("plaid pleated skirt", "navy cardigan", "white collared shirt")),
        Look("Stars Hollow fall", ("cable knit sweater", "straight-leg jeans", "peacoat")),
    )),
    Character("emily-cooper", "Emily Cooper", "Emily in Paris (2020–)", "Bold, colorful, and pattern-mixed Paris looks.", (
        Look("Pattern mixing", ("checkered print blazer", "bold patterned top", "bright colored mini skirt")),
        Look("Statement colors", ("hot pink coat", "bright green dress", "red beret hat")),
    )),
    Character("elle-woods", "Elle Woods", "Legally Blonde (2001)", "Unapologetically pink and polished.", (
        Look("The pink skirt suit", ("hot pink blazer", "hot pink mini skirt")),
        Look("Harvard pink", ("pink fitted dress", "pink cardigan")),
    )),
    Character("indiana-jones", "Indiana Jones", "Raiders of the Lost Ark (1981)", "The rugged adventurer uniform.", (
        Look("The adventurer", ("brown leather jacket", "khaki button-up shirt", "brown fedora hat", "khaki canvas trousers", "brown leather boots")),
    )),
    Character("the-dude", "The Dude", "The Big Lebowski (1998)", "Relaxed and rumpled.", (
        Look("Bowling night", ("patterned knit cardigan", "loose baggy shorts", "faded loose t-shirt", "casual sandals")),
    )),
    Character("ted-lasso", "Ted Lasso", "Ted Lasso (2020–2023)", "Coach-casual.", (
        Look("Sideline coach", ("navy track jacket", "quarter-zip pullover", "khaki chino pants")),
        Look("Off duty", ("polo shirt", "casual sneakers")),
    )),
)

BY_ID = {c.id: c for c in CHARACTERS}
PER_PHRASE = 3


# A color-specific phrase ("yellow plaid blazer") whose item's main color is further than this
# (CIEDE2000) is flagged "closest available". Measured: true yellows 2.6-9.9 and hot pinks 10-19 from the
# target, while cream/beige score 22.7-24.8 against yellow (CIEDE2000 compresses chroma gaps at high
# chroma, so 25 let cream pass as yellow).
APPROX_COLOR_DE = 20.0


@dataclass
class CharacterMatch:
    hit: Hit
    matched_phrase: str
    phrase_score: float
    look: str = ""
    approximate: bool = False  # the catalog has nothing close; shown as "closest available"


class CharacterBoards:
    """Embeds each phrase once and matches it with category + color understanding."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._phrases: dict[str, np.ndarray] = {}

    def phrase_vectors(self, character: Character) -> np.ndarray:
        if character.id not in self._phrases:
            self._phrases[character.id] = self._embedder.embed_texts(list(character.phrases))
        return self._phrases[character.id]

    def _match_phrase(
        self, catalog: Catalog, phrase: str, vector: np.ndarray, n: int, kids: bool | None, exclude: set[str]
    ) -> list[tuple[Hit, bool]]:
        """Best hits for one garment phrase, each with an "approximate" flag."""
        parsed = parse_query(phrase)
        pool = catalog.search(vector, k=60, categories=parsed.categories, kids=kids, exclude_ids=exclude)
        category_fallback = False
        if not pool:
            pool = catalog.search(vector, k=60, kids=kids, exclude_ids=exclude)
            category_fallback = parsed.categories is not None
        if pool and (parsed.color or parsed.family):
            rows = [catalog._row_by_id[h.item["id"]] for h in pool]
            text = np.array([h.score for h in pool])
            text = (text - text.min()) / max(float(text.max() - text.min()), 1e-6)
            if parsed.color:
                de, _ = color_index(catalog).distances(rgb_to_lab(np.array(COLOR_NAMES[parsed.color])))
                color = np.clip(1 - de[rows] / 40.0, 0, 1)
            else:
                color = items_in_families([catalog.items[r] for r in rows], [parsed.family]).astype(float)  # type: ignore[list-item]
            pool = [pool[i] for i in np.argsort(-(0.5 * text + 0.5 * color), kind="stable")]
        target = rgb_to_lab(np.array(COLOR_NAMES[parsed.color])) if parsed.color else None
        out = []
        for hit in pool[: n * 4]:
            approx = category_fallback
            if target is not None:
                colors = hit.item.get("colors") or []
                main = max(colors, key=lambda c: c["weight"])["lab"] if colors else None
                approx = approx or main is None or float(delta_e_2000(np.array(main), target)) > APPROX_COLOR_DE
            out.append((hit, approx))
        out.sort(key=lambda pair: pair[1])  # close matches first; stable, so ranking is kept within each group
        return out[:n]

    def looks(
        self, catalog: Catalog, character: Character, per_phrase: int = PER_PHRASE, kids: bool | None = False, exclude_ids: set[str] | None = None
    ) -> list[tuple[Look, list[CharacterMatch]]]:
        """For each signature look, the best catalog matches for each of its garment phrases."""
        vectors = dict(zip(character.phrases, self.phrase_vectors(character), strict=False))
        used = set(exclude_ids or set())
        out = []
        for look in character.looks:
            matches = []
            for phrase in look.phrases:
                for hit, approx in self._match_phrase(catalog, phrase, vectors[phrase], per_phrase, kids, used):
                    used.add(hit.item["id"])
                    matches.append(CharacterMatch(hit, phrase, hit.score, look.name, approx))
            out.append((look, matches))
        return out

    def board(
        self, catalog: Catalog, character: Character, k: int = 24, kids: bool | None = False, exclude_ids: set[str] | None = None
    ) -> list[CharacterMatch]:
        """All looks' matches, interleaved across looks (for collages and the flat list)."""
        sections = [m for _, m in self.looks(catalog, character, kids=kids, exclude_ids=exclude_ids)]
        flat: list[CharacterMatch] = []
        while any(sections) and len(flat) < k:
            for s in sections:
                if s and len(flat) < k:
                    flat.append(s.pop(0))
        return flat
