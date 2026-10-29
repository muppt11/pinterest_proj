import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  localStorage.setItem("mb-onboarding-skipped", "1");
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

  it("explains weak matches for off-topic searches and can show them anyway", async () => {
    mockFetch({
      "/api/items?": { items: [], total: 0, offset: 0 },
      "/api/search/text": { query: "birthday cake", results: [{ ...item("t", "T-Shirt"), score: 0.15 }], low_relevance: true },
    });
    render(<App />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "birthday cake" } });
    fireEvent.submit(screen.getByRole("search"));
    expect(await screen.findByText(/catalog is clothing only/)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Photo of t-shirt" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show closest items anyway" }));
    expect(await screen.findByRole("img", { name: "Photo of t-shirt" })).toBeInTheDocument();
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

  it("keeps newer search results when an older request finishes late", async () => {
    let finishOld!: (response: Response) => void;
    const oldResponse = new Promise<Response>((resolve) => { finishOld = resolve; });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.startsWith("/api/search/text?q=old")) return oldResponse;
      if (url.startsWith("/api/search/text?q=new")) return new Response(JSON.stringify({ results: [item("new", "Dress")] }));
      if (url.startsWith("/api/items?")) return new Response(JSON.stringify({ items: [], total: 0 }));
      return new Response("{}", { status: 404 });
    }));
    render(<App />);
    const search = screen.getByRole("searchbox");
    fireEvent.change(search, { target: { value: "old" } });
    fireEvent.submit(screen.getByRole("search"));
    fireEvent.change(search, { target: { value: "new" } });
    fireEvent.submit(screen.getByRole("search"));
    expect(await screen.findByRole("img", { name: "Photo of dress" })).toBeInTheDocument();
    await act(async () => { finishOld(new Response(JSON.stringify({ results: [item("old", "Shoes")] }))); });
    expect(screen.getByRole("img", { name: "Photo of dress" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Photo of shoes" })).not.toBeInTheDocument();
  });

  it("discards an old browse page after a garment filter changes", async () => {
    let finishPage!: (response: Response) => void;
    const oldPage = new Promise<Response>((resolve) => { finishPage = resolve; });
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/api/items?") && url.includes("group=shoes")) return new Response(JSON.stringify({ items: [item("filtered")], total: 1 }));
      if (url.startsWith("/api/items?offset=1")) return oldPage;
      if (url.startsWith("/api/items?")) return new Response(JSON.stringify({ items: [item("first", "Dress")], total: 2 }));
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Load more" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => u.includes("offset=1"))).toBe(true));
    fireEvent.click(screen.getByRole("radio", { name: "Shoes" }));
    expect(await screen.findByRole("img", { name: "Photo of shoes" })).toBeInTheDocument();
    await act(async () => { finishPage(new Response(JSON.stringify({ items: [item("stale", "Hat")], total: 2 }))); });
    expect(screen.queryByRole("img", { name: "Photo of hat" })).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Photo of shoes" })).toBeInTheDocument();
  });

  it("carries specific category, audience and palette into photo search", async () => {
    const calls = mockFetch({
      "/api/items?": { items: [], total: 0, offset: 0 },
      "/api/search/image": { results: [item("match", "T-Shirt")] },
    });
    render(<App />);
    fireEvent.change(screen.getByRole("combobox", { name: "Category" }), { target: { value: "T-Shirt" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Audience" }), { target: { value: "adults" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Color family" }), { target: { value: "pastels" } });
    fireEvent.change(screen.getByTestId("photo-input"), { target: { files: [new File(["image"], "shirt.jpg", { type: "image/jpeg" })] } });
    expect(await screen.findByRole("img", { name: "Photo of t-shirt" })).toBeInTheDocument();
    const url = calls.find((c) => c.startsWith("/api/search/image"))!;
    expect(url).toContain("category=T-Shirt");
    expect(url).toContain("audience=adults");
    expect(url).toContain("color_family=pastels");
    expect(screen.getByRole("combobox", { name: "Category" })).toHaveValue("T-Shirt");
  });

  it("handles a malformed encoded item URL without crashing", async () => {
    window.history.pushState(null, "", "/item/%E0%A4%A");
    mockFetch({ "/api/items?": { items: [], total: 0 } });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load this item");
  });
});
