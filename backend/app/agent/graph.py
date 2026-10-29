"""The assistant as an explicit LangGraph: agent ⇄ tools loop, then a grounding check.

    START → agent ──(tool calls, under the round limit)──→ tools → agent …
                 ├─(tool calls, limit reached)──→ final → END
                 └─(final answer)───────────────→ END   (validate_answer runs on the final text)

"final" asks the model to answer from what the tools already returned, with no tools available, so a
model that keeps re-searching gets a real answer instead of a recursion error.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

# A turn may call tools at most this many rounds before it must answer.
MAX_TOOL_ROUNDS = 4

SYSTEM_PROMPT = """You are the MoodBoards style assistant. You help people put together outfits from a \
clothing catalog that has these categories: {categories}.

Rules:
- Recommend or mention specific products ONLY by calling a tool first, and cite each one exactly as \
[item:ID] using an ID the tool returned in this conversation turn. Never make up IDs or products.
- The catalog has no prices, brands, sizes, stores, or availability. Never state or guess any of these.
- If a tool returns no results or an error, say so plainly and suggest a different description.
- If the request isn't about clothing, outfits, or style, say briefly that you can only help with \
outfits from this catalog. Don't call tools for it.
- For any clothing request, call search_similar (or complete_look / compare_items) before answering.
  The catalog includes kids' clothing: pass kids=true when the user asks for kids' items.
- Search once or twice at most, then answer with what you found. Cite 3-6 items.
- Keep answers short: a sentence or two with inline [item:ID] citations where useful.
- The app displays cited products as picture cards. Never list or number products in the answer,
  write citation-only lines, or use category labels or bare IDs as citations.
{context}"""


def build_graph(llm: BaseChatModel, tools: list[BaseTool], categories: list[str], context: str = "") -> CompiledStateGraph:
    """Compile the agent graph for one request (tools are bound to that request's ledger)."""
    model = llm.bind_tools(tools)
    system = SystemMessage(SYSTEM_PROMPT.format(categories=", ".join(categories), context=context))

    def agent(state: MessagesState) -> dict:
        return {"messages": [model.invoke([system, *state["messages"]])]}

    def final(state: MessagesState) -> dict:
        # Drop the pending tool calls and answer from the results gathered so far, without tools.
        history = [m for m in state["messages"][:-1]]
        nudge = HumanMessage("Stop searching. Answer now using only the tool results above, citing items as [item:ID].")
        return {"messages": [llm.invoke([system, *history, nudge])]}

    def route(state: MessagesState) -> str:
        if tools_condition(state) != "tools":
            return END
        rounds = sum(1 for m in state["messages"] if isinstance(m, AIMessage) and m.tool_calls)
        return "tools" if rounds <= MAX_TOOL_ROUNDS else "final"

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_node("final", final)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", "final": "final", END: END})
    graph.add_edge("tools", "agent")
    graph.add_edge("final", END)
    return graph.compile()


def recursion_limit() -> int:
    """LangGraph counts each node visit: agent + tools per round, then agent and the forced final step."""
    return 2 * MAX_TOOL_ROUNDS + 4
