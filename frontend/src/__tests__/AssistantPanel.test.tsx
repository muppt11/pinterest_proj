import { fireEvent, render, screen } from "@testing-library/react";
import { parseSse } from "../api/sse";
import { AssistantPanel, suggestionsFor } from "../components/AssistantPanel";

const item = (id: string, category: string) => ({ id, category, image_url: `/images/${id}.jpg`, kids: false, width: 4, height: 5 });

const READY = { available: true, model: "qwen3:8b", reason: null };

/** fetch mock: status first (when asked), then the SSE chat response. */
function withStatus(status: unknown, chat: () => Response) {
  return vi.fn(async (url: string) => (url.includes("/assistant/status") ? new Response(JSON.stringify(status)) : chat()));
}

function sseResponse(events: [string, unknown][]) {
  const body = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");
  return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("parseSse", () => {
  it("parses complete events and keeps partial ones for later", () => {
    const { events, rest } = parseSse('event: token\ndata: {"text":"Hi"}\n\nevent: done\ndata: {"te');
    expect(events).toEqual([{ event: "token", data: { text: "Hi" } }]);
    expect(rest).toBe('event: done\ndata: {"te');
  });
});

describe("AssistantPanel", () => {
  const props = { open: true, onClose: () => {}, onOpenItem: () => {}, contextItemIds: ["a"], board: null };

  it("streams, shows tool activity, and renders only validated items with numbered citations", async () => {
    const fetchMock = withStatus(READY, () =>
      sseResponse([
        ["tool", { name: "search_similar", args: { query: "boots" } }],
        ["tool_result", { name: "search_similar", item_ids: ["b1"] }],
        ["token", { text: "Try " }],
        ["done", { text: "Try [item:b1].", items: [item("b1", "Shoes")], removed_ids: ["fake"], tools_used: ["search_similar"] }],
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<AssistantPanel {...props} />);
    fireEvent.change(screen.getByLabelText("Ask the style assistant"), { target: { value: "boots for this?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Try (1).")).toBeInTheDocument();
    expect(screen.getByText("Searching the catalog…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open item 1: Shoes" })).toBeInTheDocument();

    const chatCall = fetchMock.mock.calls.find((c) => String(c[0]).includes("/assistant/chat")) as unknown as [string, RequestInit];
    const body = JSON.parse(chatCall[1].body as string);
    expect(body).toMatchObject({ message: "boots for this?", context_item_ids: ["a"], history: [] });
  });

  it("shows the model error message", async () => {
    vi.stubGlobal("fetch", withStatus(READY, () => sseResponse([["error", { message: "The assistant model isn't reachable." }]])));
    render(<AssistantPanel {...props} />);
    fireEvent.click(await screen.findByRole("button", { name: "What shoes would finish this look?" }));
    expect(await screen.findByText("The assistant model isn't reachable.")).toBeInTheDocument();
  });

  it("explains setup up front when the local model isn't available", async () => {
    vi.stubGlobal("fetch", withStatus({ available: false, model: "qwen3:8b", reason: "model_not_pulled" }, () => new Response("")));
    render(<AssistantPanel {...props} />);
    expect(await screen.findByText(/isn't set up on this computer yet/)).toBeInTheDocument();
    expect(screen.getByText(/ollama pull qwen3:8b/)).toBeInTheDocument();
    expect(screen.getByLabelText("Ask the style assistant")).toBeDisabled();
  });

  it("renders nothing when closed", () => {
    const { container } = render(<AssistantPanel {...props} open={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("suggestionsFor", () => {
  it("leads with item and board questions when there's context", () => {
    expect(suggestionsFor(true, false)[0]).toBe("What shoes would finish this look?");
    expect(suggestionsFor(false, true)[0]).toBe("Describe my board's style");
    const general = suggestionsFor(false, false);
    expect(general).toContain("Find a black leather jacket");
    expect(general).not.toContain("What shoes would finish this look?");
    expect(suggestionsFor(true, true)).toHaveLength(5);
  });
});
