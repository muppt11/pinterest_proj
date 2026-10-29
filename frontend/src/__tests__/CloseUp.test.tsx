import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CloseUp } from "../components/CloseUp";

const item = { id: "a", category: "Shoes", image_url: "/images/a.jpg", kids: false, width: 1, height: 1 };
const props = { itemId: "a", board: null, onBack: () => {}, onOpen: () => {} };

afterEach(() => vi.unstubAllGlobals());

describe("CloseUp", () => {
  it("shows item details even when similar-item retrieval fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/similar?")) return new Response(JSON.stringify({ detail: "Search unavailable" }), { status: 503 });
      if (url === "/api/items/a") return new Response(JSON.stringify(item));
      return new Response("{}", { status: 404 });
    }));
    render(<CloseUp {...props} />);
    expect(await screen.findByRole("heading", { level: 1, name: "Shoes" })).toBeInTheDocument();
    expect(await screen.findByText("Couldn't load similar items: Search unavailable")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Photo of shoes" })).toBeInTheDocument();
  });

  it("lets people broaden an empty same-category search", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("same_category=true")) return new Response(JSON.stringify({ results: [] }));
      if (url.includes("same_category=false")) return new Response(JSON.stringify({ results: [{ ...item, id: "b", category: "Pants" }] }));
      if (url === "/api/items/a") return new Response(JSON.stringify(item));
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CloseUp {...props} />);
    expect(await screen.findByText(/No more items in this category/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Similar styles" }));
    expect(await screen.findByRole("img", { name: "Photo of pants" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => u.includes("same_category=false"))).toBe(true));
  });
});
