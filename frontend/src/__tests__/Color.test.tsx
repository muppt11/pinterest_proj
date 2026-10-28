import { fireEvent, render, screen } from "@testing-library/react";
import App from "../App";
import { hslToHex, MoodPage, wheelPoint } from "../components/MoodPage";
import { ShopSimilar } from "../components/ShopSimilar";

const item = (id: string, category: string) => ({ id, category, image_url: `/images/${id}.jpg`, kids: false, width: 4, height: 5, colors: ["#9caf88"] });
const match = (id: string, category: string) => ({ ...item(id, category), score: 0.8, color_score: 0.8, delta_e: 7.8, matched_color: "#a1b18c", text_score: null });

function routes(map: Record<string, unknown>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const key = Object.keys(map).find((p) => url.startsWith(p));
      return key ? new Response(JSON.stringify(map[key])) : new Response("{}", { status: 404 });
    }),
  );
  return calls;
}

beforeEach(() => {
  localStorage.clear();
  window.history.pushState(null, "", "/");
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("color wheel math", () => {
  it("converts HSL to hex", () => {
    expect(hslToHex(0, 100, 50)).toBe("#ff0000");
    expect(hslToHex(120, 100, 25)).toBe("#008000");
    expect(hslToHex(0, 0, 100)).toBe("#ffffff");
  });

  it("maps wheel points to hue (0° at top, clockwise) and saturation (center 0, edge 100)", () => {
    expect(wheelPoint(100, 0, 200)).toEqual({ h: 0, s: 100 });
    expect(wheelPoint(200, 100, 200)).toEqual({ h: 90, s: 100 });
    expect(wheelPoint(100, 100, 200).s).toBe(0);
  });
});

describe("color search", () => {
  it("searches by the picked color, blended with typed words", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = routes({
      "/api/items?": { items: [], total: 0, offset: 0 },
      "/api/search/color": { color: "#9caf88", query: "linen", color_weight: 0.6, results: [match("s", "Shirt")] },
    });
    const { container } = render(<App />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "linen" } });
    fireEvent.change(container.querySelector('input[type="color"]')!, { target: { value: "#d72638" } });
    await vi.advanceTimersByTimeAsync(350);
    expect(await screen.findByRole("heading", { name: "Color #d72638 + “linen”" })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Photo of shirt" })).toBeInTheDocument();
    expect(calls.filter((c) => c.startsWith("/api/search/color"))).toEqual(["/api/search/color?hex=%23d72638&k=50&q=linen"]);
  });
});

describe("MoodPage", () => {
  it("curates items once an aesthetic is picked", async () => {
    const calls = routes({
      "/api/styles": ["minimalist", "streetwear"],
      "/api/mood": { color: "#9caf88", query: "minimalist", color_weight: 0.5, results: [match("m", "Dress")] },
    });
    render(<MoodPage onOpen={() => {}} />);
    expect(screen.getByText(/Pick a color on the wheel/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("radio", { name: "minimalist" }));
    expect(await screen.findByRole("img", { name: "Photo of dress" })).toBeInTheDocument();
    expect(calls.some((c) => c.startsWith("/api/mood?hex=%23") && c.includes("style=minimalist"))).toBe(true);
    expect(screen.getByRole("slider", { name: /Color wheel/ })).toBeInTheDocument();
  });
});

describe("ShopSimilar", () => {
  it("links out to Google Shopping in a new tab with a truthful query", async () => {
    routes({
      "/api/items/a/shop-links": {
        query: "sage green shirt",
        color_name: "sage green",
        google_shopping: "https://www.google.com/search?tbm=shop&q=sage+green+shirt",
        google_lens: "https://lens.google.com/",
      },
    });
    render(<ShopSimilar itemId="a" />);
    const link = await screen.findByRole("link", { name: /Shop similar: “sage green shirt”/ });
    expect(link).toHaveAttribute("href", "https://www.google.com/search?tbm=shop&q=sage+green+shirt");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/aren't checked by MoodBoards/)).toBeInTheDocument();
  });
});
