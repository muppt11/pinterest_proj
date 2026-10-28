"""Assistant chat, streamed as Server-Sent Events.

Events (each `event: <name>` + `data: <json>`):
  tool         {"name", "args"}              a tool call started
  tool_result  {"name", "item_ids"}          IDs that tool returned
  token        {"text"}                      a chunk of the answer as it's generated (unvalidated)
  done         {"text", "items", "removed_ids", "tools_used"}   the validated final answer
  error        {"message"}
The client should replace the streamed text with `done.text`, and render only `done.items` as cards.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from app.agent.graph import build_graph, recursion_limit
from app.agent.tools import BoardSummary, TurnLedger, build_tools
from app.agent.validate import validate_answer
from app.deps import get_catalog, get_describer, get_embedder, get_llm
from app.models import Item
from app.services.catalog import Catalog
from app.services.embedder import Embedder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])

MAX_HISTORY = 10


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class BoardAesthetic(BaseModel):
    label: str
    style_tags: list[str]
    centroid: list[float]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list)
    context_item_ids: list[str] = Field(default_factory=list, max_length=4, description="items open in the UI")
    board: list[BoardAesthetic] | None = None


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _context_note(req: ChatRequest, catalog: Catalog) -> str:
    lines = []
    open_items = [catalog.get(i) for i in req.context_item_ids]
    open_items = [m for m in open_items if m is not None]
    if open_items:
        lines.append("Items the user is looking at (use these IDs with tools): " + ", ".join(f"{m['id']} ({m['category']})" for m in open_items))
    if req.board:
        lines.append(f"The user has analyzed a board with {len(req.board)} aesthetic(s); describe_board can summarize it.")
    return ("\nContext:\n- " + "\n- ".join(lines)) if lines else ""


async def _run(req: ChatRequest, catalog: Catalog, embedder: Embedder, llm: BaseChatModel, describer) -> AsyncIterator[str]:  # type: ignore[no-untyped-def]
    ledger = TurnLedger()
    board = BoardSummary([a.model_dump() for a in req.board]) if req.board else None
    tools = build_tools(catalog, embedder, ledger, board, describer)
    graph = build_graph(llm, tools, catalog.categories, _context_note(req, catalog))

    messages: list[BaseMessage] = [
        HumanMessage(t.content) if t.role == "user" else AIMessage(t.content) for t in req.history[-MAX_HISTORY:]
    ]
    messages.append(HumanMessage(req.message))

    final_text = ""
    try:
        async for mode, payload in graph.astream(
            {"messages": messages}, {"recursion_limit": recursion_limit()}, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                chunk, meta = payload
                if meta.get("langgraph_node") == "agent" and isinstance(chunk, (AIMessageChunk, AIMessage)):
                    if chunk.content and not getattr(chunk, "tool_calls", None):
                        yield _sse("token", {"text": chunk.content})
            elif mode == "updates":
                for node, update in payload.items():
                    for msg in (update or {}).get("messages", []):
                        if node == "agent" and isinstance(msg, AIMessage):
                            for call in msg.tool_calls:
                                yield _sse("tool", {"name": call["name"], "args": call["args"]})
                            if not msg.tool_calls:
                                final_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                        elif node == "tools" and isinstance(msg, ToolMessage):
                            ids = []
                            try:
                                ids = sorted(_ids_in(json.loads(msg.content)))
                            except (TypeError, ValueError):
                                pass
                            yield _sse("tool_result", {"name": msg.name, "item_ids": ids})
    except Exception as exc:
        logger.exception("assistant turn failed")
        message = "The assistant model isn't reachable. Is Ollama running with the model pulled?" if "connect" in str(exc).lower() else "The assistant hit an error. Please try again."
        yield _sse("error", {"message": message})
        return

    if not final_text.strip():
        final_text = "I couldn't finish that request. Try asking more specifically, e.g. “black boots for a denim skirt”."
    answer = validate_answer(final_text, ledger.item_ids)
    items = [Item.from_meta(catalog.get(i)).model_dump() for i in answer.item_ids]  # type: ignore[arg-type]
    yield _sse("done", {"text": answer.text, "items": items, "removed_ids": answer.removed_ids, "tools_used": ledger.tools_used})


def _ids_in(value: Any) -> set[str]:
    """All values under an "id" key anywhere in a tool's JSON output."""
    found: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "id" and isinstance(v, str):
                found.add(v)
            else:
                found |= _ids_in(v)
    elif isinstance(value, list):
        for v in value:
            found |= _ids_in(v)
    return found


@router.post("/chat")
async def chat(
    req: ChatRequest,
    catalog: Annotated[Catalog, Depends(get_catalog)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    llm: Annotated[BaseChatModel, Depends(get_llm)],
    describer: Annotated[object, Depends(get_describer)],
) -> StreamingResponse:
    """One assistant turn, streamed as SSE. Every product in the final answer comes from a tool call this turn."""
    return StreamingResponse(
        _run(req, catalog, embedder, llm, describer),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
