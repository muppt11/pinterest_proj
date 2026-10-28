import { fireEvent, render, screen } from "@testing-library/react";
import { parseSse } from "../api/sse";
import { AssistantPanel } from "../components/AssistantPanel";

const item = (id: string, category: string) => ({ id, category, image_url: `/images/${id}.jpg`, kids: false, width: 4, height: 5 });

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
    const fetchMock = vi.fn(async () =>
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

    const body = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body).toMatchObject({ message: "boots for this?", context_item_ids: ["a"], history: [] });
  });

  it("shows the model error message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse([["error", { message: "The assistant model isn't reachable." }]])));
    render(<AssistantPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "What shoes would finish this look?" }));
    expect(await screen.findByText("The assistant model isn't reachable.")).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    const { container } = render(<AssistantPanel {...props} open={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
