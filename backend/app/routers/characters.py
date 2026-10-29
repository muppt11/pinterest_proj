"""Character style boards: iconic film/TV looks described in words and matched to the catalog."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import FocusFilter, get_catalog, get_embedder, get_focus
from app.models import Item, ScoredItem
from app.services.catalog import Catalog
from app.services.characters import BY_ID, CHARACTERS, CharacterBoards
from app.services.embedder import Embedder

router = APIRouter(prefix="/characters", tags=["characters"])

DISCLAIMER = (
    "An editorial interpretation of the character's costume style, matched to an open clothing catalog. "
    "Not affiliated with or endorsed by the studio or the actors; no film images are used."
)


class CharacterOut(BaseModel):
    id: str
    name: str
    source: str
    summary: str
    phrases: list[str]


class CharacterCard(CharacterOut):
    covers: list[Item]  # top catalog matches, shown as a collage (no film images)


class CharacterItem(ScoredItem):
    matched_phrase: str  # which part of the style profile this item matched best
    approximate: bool = False  # nothing close in the catalog; shown as "closest available"


class LookOut(BaseModel):
    name: str
    phrases: list[str]
    results: list[CharacterItem]


class CharacterBoard(CharacterOut):
    disclaimer: str
    looks: list[LookOut]
    results: list[CharacterItem]  # all looks, interleaved


@lru_cache(maxsize=4)
def _boards(embedder: Embedder) -> CharacterBoards:
    return CharacterBoards(embedder)


def _out(c) -> CharacterOut:  # type: ignore[no-untyped-def]
    return CharacterOut(id=c.id, name=c.name, source=c.source, summary=c.summary, phrases=list(c.phrases))


@router.get("", response_model=list[CharacterCard])
def list_characters(
    catalog: Annotated[Catalog, Depends(get_catalog)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    focus: Annotated[FocusFilter, Depends(get_focus)],
) -> list[CharacterCard]:
    """Every character with a 4-item collage of its closest catalog matches."""
    boards = _boards(embedder)
    return [
        CharacterCard(
            **_out(c).model_dump(),
            covers=[Item.from_meta(m.hit.item) for m in boards.board(catalog, c, k=4, exclude_ids=focus.excluded)],
        )
        for c in CHARACTERS
    ]


@router.get("/{character_id}", response_model=CharacterBoard)
def character_board(
    character_id: str,
    catalog: Annotated[Catalog, Depends(get_catalog)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    focus: Annotated[FocusFilter, Depends(get_focus)],
    k: Annotated[int, Query(ge=1, le=60)] = 24,
) -> CharacterBoard:
    """Catalog items in the character's signature style (adult clothing), each with the phrase it matched."""
    character = BY_ID.get(character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Unknown character.")
    def item(m) -> CharacterItem:  # type: ignore[no-untyped-def]
        return CharacterItem(
            **Item.from_meta(m.hit.item).model_dump(), score=round(m.hit.score, 4), matched_phrase=m.matched_phrase, approximate=m.approximate
        )

    sections = _boards(embedder).looks(catalog, character, exclude_ids=focus.excluded)
    looks = [LookOut(name=look.name, phrases=list(look.phrases), results=[item(m) for m in matches]) for look, matches in sections]
    flat: list[CharacterItem] = []
    queues = [list(lo.results) for lo in looks]
    while any(queues) and len(flat) < k:
        for q in queues:
            if q and len(flat) < k:
                flat.append(q.pop(0))
    return CharacterBoard(**_out(character).model_dump(), disclaimer=DISCLAIMER, looks=looks, results=flat)
