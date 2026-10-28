import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../App";

const item = (id: string, category = "Shoes") => ({ id, category, image_url: `/images/${id}.jpg`, kids: false, width: 400, height: 500 });

function mockFetch(routes: Record<string, unknown>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const key = Object.keys(routes).find((prefix) => url.startsWith(prefix));
      if (!key) return new Response(JSON.stringify({ detail: "not mocked" }), { status: 404 });
      return new Response(JSON.stringify(routes[key]), { status: 200 });
    }),
  );
  return calls;
}

beforeEach(() => {
  localStorage.clear();
  window.history.pushState(null, "", "/");
});
afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("shows the brand, a labeled search field, and the catalog grid", async () => {
    mockFetch({ "/api/items?": { items: [item("a"), item("b", "Dress")], total: 2, offset: 0 } });
    render(<App />);
    expect(screen.getByRole("link", { name: "MoodBoards home" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /search outfits/i })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Photo of dress" })).toBeInTheDocument();
  });

  it("runs a text search and shows results", async () => {
    const calls = mockFetch({
      "/api/items?": { items: [], total: 0, offset: 0 },
      "/api/search/text": { query: "red boots", results: [{ ...item("boot"), score: 0.4 }] },
    });
    render(<App />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "red boots" } });
    fireEvent.submit(screen.getByRole("search"));
    expect(await screen.findByRole("heading", { name: "Results for “red boots”" })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Photo of shoes" })).toBeInTheDocument();
    expect(calls.some((c) => c.startsWith("/api/search/text?q=red%20boots"))).toBe(true);
  });

  it("shows a friendly error when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Catalog index not built yet. Run `make index`." }), { status: 503 })));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("make index");
  });

  it("opens a close-up with More like this", async () => {
    mockFetch({
      "/api/items?": { items: [item("a")], total: 1, offset: 0 },
      "/api/items/a/similar": { query: null, results: [{ ...item("b", "Dress"), score: 0.9 }] },
      "/api/items/a": item("a"),
      "/api/complete-look": {
        item_id: "a",
        anchor_group: "shoes",
        used_board: false,
        groups: [
          { group: "bottoms", results: [{ ...item("p", "Pants"), score: 0.7 }] },
          { group: "outerwear", results: [] },
        ],
      },
    });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Open Shoes" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Shoes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "More like this" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Complete the look" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Bottoms" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Outerwear" })).not.toBeInTheDocument(); // empty groups hidden
    await waitFor(() => expect(screen.getByRole("img", { name: "Photo of dress" })).toBeInTheDocument());
    expect(window.location.pathname).toBe("/item/a");
  });
});
