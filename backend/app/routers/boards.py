"""Boards (nestable to any depth) and saves, including saving one item to several boards at once."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.db import get_db
from app.deps import get_catalog
from app.models import Item
from app.services.catalog import Catalog
from app.text import clean_name

router = APIRouter(tags=["boards"])

Db = Annotated[sqlite3.Connection, Depends(get_db)]
CatalogDep = Annotated[Catalog, Depends(get_catalog)]


class BoardIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None


class BoardSummary(BaseModel):
    id: int
    name: str
    parent_id: int | None
    item_count: int  # items saved directly on this board
    cover: Item | None  # most recently saved item, for the board tile


class BoardDetail(BoardSummary):
    breadcrumb: list[BoardSummary]  # root ... parent (excludes this board)
    children: list[BoardSummary]
    items: list[Item]


class SaveIn(BaseModel):
    item_id: str
    board_ids: list[int] = Field(min_length=1, max_length=50)


class SaveResult(BaseModel):
    item_id: str
    added_to: list[int]  # boards that newly got the item (undo removes from exactly these)
    already_in: list[int]


def _summary(db: sqlite3.Connection, catalog: Catalog, row: sqlite3.Row) -> BoardSummary:
    count = db.execute("SELECT COUNT(*) FROM saves WHERE board_id = ?", (row["id"],)).fetchone()[0]
    latest = db.execute(
        "SELECT item_id FROM saves WHERE board_id = ? ORDER BY saved_at DESC, rowid DESC LIMIT 1", (row["id"],)
    ).fetchone()
    cover_meta = catalog.get(latest["item_id"]) if latest else None
    return BoardSummary(
        id=row["id"],
        name=row["name"],
        parent_id=row["parent_id"],
        item_count=count,
        cover=Item.from_meta(cover_meta) if cover_meta else None,
    )


def _board(db: sqlite3.Connection, board_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Board not found.")
    return row


@router.get("/boards", response_model=list[BoardSummary])
def list_boards(db: Db, catalog: CatalogDep) -> list[BoardSummary]:
    """Every board, flat, ordered so parents come before children (the client builds the tree)."""
    rows = db.execute(
        """
        WITH RECURSIVE tree(id, path) AS (
            SELECT id, printf('%08d', id) FROM boards WHERE parent_id IS NULL
            UNION ALL
            SELECT b.id, tree.path || '/' || printf('%08d', b.id) FROM boards b JOIN tree ON b.parent_id = tree.id
        )
        SELECT boards.* FROM boards JOIN tree USING (id) ORDER BY tree.path
        """
    ).fetchall()
    return [_summary(db, catalog, r) for r in rows]


@router.post("/boards", response_model=BoardSummary, status_code=201)
def create_board(body: BoardIn, db: Db, catalog: CatalogDep) -> BoardSummary:
    """Create a board, or a sub-board inside `parent_id` (no depth limit)."""
    name = clean_name(body.name)
    if not name:
        raise HTTPException(status_code=422, detail="Board name can't be blank.")
    if body.parent_id is not None:
        _board(db, body.parent_id)
    cur = db.execute("INSERT INTO boards (name, parent_id) VALUES (?, ?)", (name, body.parent_id))
    return _summary(db, catalog, _board(db, cur.lastrowid))  # type: ignore[arg-type]


@router.get("/boards/{board_id}", response_model=BoardDetail)
def get_board(board_id: int, db: Db, catalog: CatalogDep) -> BoardDetail:
    """A board with its breadcrumb, direct sub-boards, and saved items (newest first)."""
    row = _board(db, board_id)
    crumbs: list[BoardSummary] = []
    parent = row["parent_id"]
    while parent is not None:
        p = _board(db, parent)
        crumbs.insert(0, _summary(db, catalog, p))
        parent = p["parent_id"]
    children = db.execute("SELECT * FROM boards WHERE parent_id = ? ORDER BY id", (board_id,)).fetchall()
    saved = db.execute(
        "SELECT item_id FROM saves WHERE board_id = ? ORDER BY saved_at DESC, rowid DESC", (board_id,)
    ).fetchall()
    items = [Item.from_meta(m) for m in (catalog.get(s["item_id"]) for s in saved) if m is not None]
    return BoardDetail(
        **_summary(db, catalog, row).model_dump(),
        breadcrumb=crumbs,
        children=[_summary(db, catalog, c) for c in children],
        items=items,
    )


@router.delete("/boards/{board_id}", status_code=204)
def delete_board(board_id: int, db: Db) -> Response:
    """Delete a board and, recursively, its sub-boards and saves."""
    _board(db, board_id)
    db.execute("DELETE FROM boards WHERE id = ?", (board_id,))
    return Response(status_code=204)


@router.post("/saves", response_model=SaveResult)
def save_item(body: SaveIn, db: Db, catalog: CatalogDep) -> SaveResult:
    """Save one item to one or more boards in a single action."""
    if catalog.get(body.item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    board_ids = list(dict.fromkeys(body.board_ids))
    for b in board_ids:
        _board(db, b)
    added, already = [], []
    for b in board_ids:
        cur = db.execute("INSERT OR IGNORE INTO saves (board_id, item_id) VALUES (?, ?)", (b, body.item_id))
        (added if cur.rowcount else already).append(b)
    return SaveResult(item_id=body.item_id, added_to=added, already_in=already)


@router.post("/saves/remove", response_model=SaveResult)
def unsave_item(body: SaveIn, db: Db) -> SaveResult:
    """Remove an item from the given boards (used by Undo and by unchecking a board)."""
    removed = []
    for b in dict.fromkeys(body.board_ids):
        cur = db.execute("DELETE FROM saves WHERE board_id = ? AND item_id = ?", (b, body.item_id))
        if cur.rowcount:
            removed.append(b)
    return SaveResult(item_id=body.item_id, added_to=[], already_in=removed)


@router.get("/items/{item_id}/saved-in", response_model=list[int])
def saved_in(item_id: str, db: Db) -> list[int]:
    """IDs of boards that contain this item (to pre-check the save checklist)."""
    return [r["board_id"] for r in db.execute("SELECT board_id FROM saves WHERE item_id = ?", (item_id,))]
