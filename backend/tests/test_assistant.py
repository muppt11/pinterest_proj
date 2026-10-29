"""Assistant: grounding validator, tools, and the SSE endpoint driven by a scripted chat model."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agent.tools import BoardSummary, TurnLedger, build_tools
from app.agent.validate import validate_answer
from app.deps import get_catalog, get_describer, get_embedder, get_llm
from app.main import app
from app.services.catalog import Catalog

from .conftest import FakeEmbedder

# --- validator -----------------------------------------------------------------------------------


def test_validator_keeps_tool_ids_and_strips_invented_ones() -> None:
    text = "Try [item:a] with [item:FAKE] and again [item:a], plus [item:b]."
    result = validate_answer(text, allowed_ids={"a", "b"})
    assert result.item_ids == ["a", "b"]
    assert result.removed_ids == ["FAKE"]
    assert "[item:FAKE]" not in result.text and result.text.count("[item:a]") == 2


def test_validator_with_no_citations() -> None:
    result = validate_answer("I can only help with outfits.", allowed_ids=set())
    assert result.item_ids == [] and result.removed_ids == [] and result.text == "I can only help with outfits."


# --- tools ---------------------------------------------------------------------------------------


@pytest.fixture
def ledger() -> TurnLedger:
    return TurnLedger()


def call(tools: list, name: str, **args: Any) -> dict:  # type: ignore[type-arg]
    return json.loads(next(t for t in tools if t.name == name).invoke(args))


def test_search_tool_records_ids(catalog: Catalog, ledger: TurnLedger) -> None:
    tools = build_tools(catalog, FakeEmbedder(), ledger)
    out = call(tools, "search_similar", query="red shirt", k=2)
    assert [r["id"] for r in out["results"]] == ["tshirt-red", "tshirt-pink"]
    assert ledger.item_ids == {"tshirt-red", "tshirt-pink"} and ledger.tools_used == ["search_similar"]


def test_search_tool_reports_no_match_without_recording(catalog: Catalog, ledger: TurnLedger) -> None:
    out = call(build_tools(catalog, FakeEmbedder(), ledger), "search_similar", query="birthday cake")
    assert out["results"] == [] and "clothing only" in out["note"]
    assert ledger.item_ids == set()


def test_search_tool_rejects_unknown_category(catalog: Catalog, ledger: TurnLedger) -> None:
    out = call(build_tools(catalog, FakeEmbedder(), ledger), "search_similar", query="shirt", category="Capes")
    assert "unknown category" in out["error"]


def test_compare_tool_uses_vision_and_similarity(catalog: Catalog, ledger: TurnLedger) -> None:
    tools = build_tools(catalog, FakeEmbedder(), ledger, describe_image=lambda m: f"a {m['category'].lower()}")
    out = call(tools, "compare_items", item_ids=["tshirt-red", "tshirt-pink", "nope"])
    assert out["unknown_ids"] == ["nope"]
    assert out["items"][0]["visual_description"] == "a t-shirt"
    assert out["pairs"][0]["similarity"] > 0.9
    assert ledger.item_ids == {"tshirt-red", "tshirt-pink"}


def test_compare_tool_needs_two_items(catalog: Catalog, ledger: TurnLedger) -> None:
    out = call(build_tools(catalog, FakeEmbedder(), ledger), "compare_items", item_ids=["tshirt-red"])
    assert "at least 2" in out["error"]


def test_complete_look_and_describe_board_tools(catalog: Catalog, ledger: TurnLedger) -> None:
    board = BoardSummary([{"label": "Aesthetic 1", "style_tags": ["minimalist"], "centroid": [1, 0, 0, 0]}])
    tools = build_tools(catalog, FakeEmbedder(), ledger, board)
    look = call(tools, "complete_look", item_id="tshirt-red")
    assert look["anchor_role"] == "tops" and look["used_board"] is True
    assert "pants-jeans" in {i["id"] for i in look["groups"]["bottoms"]}
    desc = call(tools, "describe_board")
    assert desc["aesthetics"][0]["style_words"] == ["minimalist"]
    assert call(tools, "complete_look", item_id="nope")["error"]


def test_describe_board_without_board(catalog: Catalog, ledger: TurnLedger) -> None:
    assert "no board" in call(build_tools(catalog, FakeEmbedder(), ledger), "describe_board")["error"]


# --- endpoint with a scripted model --------------------------------------------------------------


class ScriptedChatModel(BaseChatModel):
    """Returns pre-written messages in order: tool calls first, then a final answer."""

    script: list[AIMessage]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":  # type: ignore[override]
        return self

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        message = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call(name: str, args: dict, call_id: str = "c1") -> AIMessage:  # type: ignore[type-arg]
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


def events(response) -> list[tuple[str, dict]]:  # type: ignore[no-untyped-def, type-arg]
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture
def chat(catalog: Catalog) -> Iterator:  # type: ignore[type-arg]
    def make(script: list[AIMessage]) -> TestClient:
        model = ScriptedChatModel(script=script)
        app.dependency_overrides[get_catalog] = lambda: catalog
        app.dependency_overrides[get_embedder] = FakeEmbedder
        app.dependency_overrides[get_llm] = lambda: model
        app.dependency_overrides[get_describer] = lambda: (lambda item: None)
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def test_chat_streams_tools_and_validated_answer(chat) -> None:  # type: ignore[no-untyped-def]
    client = chat(
        [
            tool_call("search_similar", {"query": "red shirt", "k": 2}),
            AIMessage(content="These work: [item:tshirt-red] and [item:tshirt-pink]. Also [item:made-up-123]."),
        ]
    )
    response = client.post("/assistant/chat", json={"message": "red tops?"})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    evs = events(response)
    names = [e for e, _ in evs]
    assert names[0] == "tool" and evs[0][1]["name"] == "search_similar"
    assert ("tool_result", {"name": "search_similar", "item_ids": ["tshirt-pink", "tshirt-red"]}) in evs
    done = evs[-1][1]
    assert names[-1] == "done"
    assert [i["id"] for i in done["items"]] == ["tshirt-red", "tshirt-pink"]
    assert done["removed_ids"] == ["made-up-123"] and "made-up-123" not in done["text"]
    assert done["tools_used"] == ["search_similar"]


def test_chat_strips_real_ids_not_returned_this_turn(chat) -> None:  # type: ignore[no-untyped-def]
    # pants-jeans exists in the catalog, but no tool returned it, so it must not be shown.
    client = chat([AIMessage(content="Wear it with [item:pants-jeans].")])
    done = events(client.post("/assistant/chat", json={"message": "what goes with this?"}))[-1][1]
    assert done["items"] == [] and done["removed_ids"] == ["pants-jeans"]


def test_chat_off_topic_answers_without_tools(chat) -> None:  # type: ignore[no-untyped-def]
    client = chat([AIMessage(content="I can only help with outfits from this catalog.")])
    evs = events(client.post("/assistant/chat", json={"message": "what's the capital of France?"}))
    assert [e for e, _ in evs if e in ("tool", "tool_result")] == []
    assert evs[-1][1]["tools_used"] == [] and evs[-1][1]["items"] == []


def test_chat_handles_empty_results(chat) -> None:  # type: ignore[no-untyped-def]
    client = chat(
        [tool_call("search_similar", {"query": "birthday cake"}), AIMessage(content="I couldn't find anything like that.")]
    )
    evs = events(client.post("/assistant/chat", json={"message": "birthday cake outfit"}))
    assert ("tool_result", {"name": "search_similar", "item_ids": []}) in evs
    assert evs[-1][1]["items"] == []


def test_chat_reports_model_errors(chat) -> None:  # type: ignore[no-untyped-def]
    class Broken(ScriptedChatModel):
        def _generate(self, *a: Any, **k: Any) -> ChatResult:
            raise ConnectionError("Failed to connect to Ollama")

    model = Broken(script=[])
    client = chat([])
    app.dependency_overrides[get_llm] = lambda: model
    evs = events(client.post("/assistant/chat", json={"message": "hi"}))
    assert evs == [("error", {"message": "The assistant model isn't reachable. Is Ollama running with the model pulled?"})]


def test_chat_validates_request(chat) -> None:  # type: ignore[no-untyped-def]
    client = chat([AIMessage(content="ok")])
    assert client.post("/assistant/chat", json={"message": ""}).status_code == 422
    assert client.post("/assistant/chat", json={"message": "x", "history": [{"role": "system", "content": "x"}]}).status_code == 422


def test_status_reports_missing_ollama(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import urllib.request

    def down(*a, **k):  # type: ignore[no-untyped-def]
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    body = TestClient(app).get("/assistant/status").json()
    assert body == {"available": False, "model": "qwen3:8b", "reason": "ollama_not_running"}


def test_endless_searching_gets_a_forced_answer_not_an_error(chat) -> None:  # type: ignore[no-untyped-def]
    """Regression: a model that kept re-searching hit LangGraph's recursion limit and errored."""
    from app.agent.graph import MAX_TOOL_ROUNDS

    loops = [tool_call("search_similar", {"query": "red shirt"}, call_id=f"c{i}") for i in range(MAX_TOOL_ROUNDS + 1)]
    client = chat([*loops, AIMessage(content="Best pick: [item:tshirt-red].")])
    evs = events(client.post("/assistant/chat", json={"message": "something cozy for a rainy day"}))
    assert [e for e, _ in evs if e == "error"] == []
    done = evs[-1][1]
    assert done["items_source"] == "cited" and [i["id"] for i in done["items"]] == ["tshirt-red"]


def test_uncited_results_fall_back_to_tool_items(chat) -> None:  # type: ignore[no-untyped-def]
    client = chat([tool_call("search_similar", {"query": "red shirt", "k": 2}), AIMessage(content="I found a couple of red tops for you.")])
    done = events(client.post("/assistant/chat", json={"message": "red tops?"}))[-1][1]
    assert done["items_source"] == "tool results"
    assert [i["id"] for i in done["items"]] == ["tshirt-red", "tshirt-pink"]


def test_search_tool_kids_filter(catalog: Catalog, ledger: TurnLedger) -> None:
    out = call(build_tools(catalog, FakeEmbedder(), ledger), "search_similar", query="boot", kids=True)
    assert [r["id"] for r in out["results"]] == ["shoes-boot"]
    adults = call(build_tools(catalog, FakeEmbedder(), TurnLedger()), "search_similar", query="boot", kids=False)
    assert "shoes-boot" not in [r["id"] for r in adults["results"]]
