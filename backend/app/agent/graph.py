"""The assistant as an explicit LangGraph: agent ⇄ tools loop, then a grounding check.

    START → agent ──(tool calls?)──→ tools → agent …
                 └─(final answer)──→ END   (validate_answer runs on the final text)
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
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
- Keep answers short: a sentence or two of reasoning, then the cited items.
{context}"""


def build_graph(llm: BaseChatModel, tools: list[BaseTool], categories: list[str], context: str = "") -> CompiledStateGraph:
    """Compile the agent graph for one request (tools are bound to that request's ledger)."""
    model = llm.bind_tools(tools)
    system = SystemMessage(SYSTEM_PROMPT.format(categories=", ".join(categories), context=context))

    def agent(state: MessagesState) -> dict:
        return {"messages": [model.invoke([system, *state["messages"]])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


def recursion_limit() -> int:
    """LangGraph counts each node visit; agent + tools per round, plus the final agent step."""
    return 2 * MAX_TOOL_ROUNDS + 1
