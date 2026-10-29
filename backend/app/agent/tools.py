"""Assistant tools. Every item ID a tool returns is recorded in the turn's ledger, and the final
answer may only cite IDs from that ledger (see validate.py)."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from langchain_core.tools import BaseTool, tool

from app.services.catalog import Catalog
from app.services.complete_look import complete_look as complete_look_service
from app.services.embedder import Embedder
from app.services.text_search import text_search

MAX_COMPARE = 4


@dataclass
class TurnLedger:
    """What the tools did during one assistant turn."""

    item_ids: set[str] = field(default_factory=set)
    tools_used: list[str] = field(default_factory=list)
    ordered_ids: list[str] = field(default_factory=list)  # results in the order tools returned them


@dataclass
class BoardSummary:
    """A board analysis the user ran earlier, passed in by the client."""

    aesthetics: list[dict[str, Any]]  # [{label, style_tags: [str], centroid: [float]}]


def _brief(item: dict[str, Any], score: float | None = None) -> dict[str, Any]:
    """Compact, factual item info for the model. Only real dataset fields and derived colors."""
    out = {"id": item["id"], "category": item["category"], "kids": item["kids"]}
    if item.get("colors"):
        out["main_colors"] = [c["hex"] for c in item["colors"][:2]]
    if score is not None:
        out["similarity"] = round(score, 3)
    return out


def build_tools(
    catalog: Catalog,
    embedder: Embedder,
    ledger: TurnLedger,
    board: BoardSummary | None = None,
    describe_image: Callable[[dict[str, Any]], str | None] | None = None,
    exclude_ids: set[str] | None = None,
    bias: np.ndarray | None = None,
) -> list[BaseTool]:
    """Tools bound to this request's catalog, model, board, and ledger."""

    def record(name: str, items: list[dict[str, Any]]) -> None:
        ledger.tools_used.append(name)
        ledger.item_ids.update(i["id"] for i in items)
        ledger.ordered_ids.extend(i["id"] for i in items if i["id"] not in ledger.ordered_ids)

    @tool
    def search_similar(query: str, category: str | None = None, kids: bool | None = None, k: int = 6) -> str:
        """Find catalog items matching a description, e.g. 'black ankle boots' or 'pastel cardigan'.
        Garment and color words in the query are understood automatically. Optionally restrict to one
        category name, or set kids=true for children's clothing (kids=false for adults only)."""
        k = max(1, min(k, 12))
        if category is not None and category not in catalog.categories:
            ledger.tools_used.append("search_similar")
            return json.dumps({"error": f"unknown category; choose from {catalog.categories}"})
        result = text_search(catalog, embedder, query, k, category=category, kids=kids, exclude_ids=exclude_ids, bias=bias)
        if result.low_relevance or not result.hits:
            ledger.tools_used.append("search_similar")
            return json.dumps({"results": [], "note": "no good matches; the catalog is clothing only"})
        record("search_similar", [h.item for h in result.hits])
        return json.dumps({"understood": result.understood, "results": [_brief(h.item, h.score) for h in result.hits]})

    @tool
    def complete_look(item_id: str, per_group: int = 3) -> str:
        """Suggest complementary pieces (bottoms, shoes, outerwear, hats, ...) for one catalog item.
        Uses the board aesthetic closest to this item as a taste signal when a board has been analyzed."""
        per_group = max(1, min(per_group, 6))
        centroid = None
        try:
            anchor = catalog.vector(item_id)
            if board and board.aesthetics:
                centroids = [np.asarray(a["centroid"], dtype=np.float32) for a in board.aesthetics]
                centroid = max(centroids, key=lambda c: float(anchor @ (c / np.linalg.norm(c))))
            group, groups = complete_look_service(catalog, item_id, per_group, centroid, exclude_ids=exclude_ids, bias=bias)
        except KeyError:
            ledger.tools_used.append("complete_look")
            return json.dumps({"error": f"no catalog item with id {item_id}"})
        items = [h.item for g in groups for h in g.hits]
        record("complete_look", items)
        return json.dumps(
            {
                "anchor": _brief(catalog.get(item_id)),  # type: ignore[arg-type]
                "anchor_role": group,
                "used_board": centroid is not None,
                "groups": {g.group: [_brief(h.item, h.score) for h in g.hits] for g in groups},
            }
        )

    @tool
    def compare_items(item_ids: list[str]) -> str:
        """Compare 2-4 catalog items: category, colors, a short visual description, and how visually
        similar each pair is (cosine similarity, 1.0 = identical)."""
        ids = list(dict.fromkeys(item_ids))[:MAX_COMPARE]
        found = [catalog.get(i) for i in ids]
        missing = [i for i, m in zip(ids, found, strict=False) if m is None]
        items = [m for m in found if m is not None]
        if len(items) < 2:
            ledger.tools_used.append("compare_items")
            return json.dumps({"error": "need at least 2 valid catalog item ids", "unknown_ids": missing})
        vectors = {m["id"]: catalog.vector(m["id"]) for m in items}
        pairs = [
            {"a": a["id"], "b": b["id"], "similarity": round(float(vectors[a["id"]] @ vectors[b["id"]]), 3)}
            for i, a in enumerate(items)
            for b in items[i + 1 :]
        ]
        described = []
        for m in items:
            entry = _brief(m)
            if describe_image is not None:
                entry["visual_description"] = describe_image(m) or "unavailable"
            described.append(entry)
        record("compare_items", items)
        return json.dumps({"items": described, "pairs": pairs, "unknown_ids": missing})

    @tool
    def describe_board() -> str:
        """Summarize the user's analyzed board: its distinct aesthetics, their style words, and a few
        catalog items closest to each aesthetic."""
        if board is None or not board.aesthetics:
            ledger.tools_used.append("describe_board")
            return json.dumps({"error": "no board analyzed yet; ask the user to use Analyze board first"})
        out = []
        found: list[dict[str, Any]] = []
        for a in board.aesthetics:
            hits = catalog.search(np.asarray(a["centroid"], dtype=np.float32), k=3, exclude_ids=exclude_ids, bias=bias)
            found.extend(h.item for h in hits)
            out.append({"label": a["label"], "style_words": a["style_tags"], "closest_items": [_brief(h.item, h.score) for h in hits]})
        record("describe_board", found)
        return json.dumps({"aesthetics": out})

    return [search_similar, complete_look, compare_items, describe_board]
