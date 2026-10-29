import { fireEvent, render, screen } from "@testing-library/react";
import App from "../App";
import { hslToHex, MoodPage, wheelPoint } from "../components/MoodPage";
import { searchLensWithImage, ShopSimilar } from "../components/ShopSimilar";

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
  localStorage.setItem("mb-onboarding-skipped", "1");
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

describe("searchLensWithImage", () => {
  it("opens a tab inside the click and POSTs the image file itself to Lens", async () => {
    const tab = { opener: {} };
    const open = vi.spyOn(window, "open").mockReturnValue(tab as unknown as Window);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new Blob(["jpegbytes"], { type: "image/jpeg" }))));
    class FakeDataTransfer {
      private list: File[] = [];
      items = { add: (f: File) => this.list.push(f) };
      get files() {
        return this.list as unknown as FileList;
      }
    }
    vi.stubGlobal("DataTransfer", FakeDataTransfer);
    let submitted: HTMLFormElement | null = null;
    let fileName = "";
    vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(function (this: HTMLFormElement) {
      submitted = this;
      fileName = (this.querySelector("input") as HTMLInputElement & { files: File[] }).files[0].name;
    });
    Object.defineProperty(HTMLInputElement.prototype, "files", { configurable: true, writable: true, value: null });

    await searchLensWithImage("/api/images/a.jpg");
    expect(open).toHaveBeenCalledWith("", "mb-lens");
    expect(tab.opener).toBeNull();
    const form = submitted as unknown as HTMLFormElement;
    expect(form.method.toLowerCase()).toBe("post");
    expect(form.enctype).toBe("multipart/form-data");
    expect(form.action).toMatch(/^https:\/\/lens\.google\.com\/v3\/upload\?/);
    expect(form.target).toBe("mb-lens");
    expect(fileName).toBe("item.jpg");
    open.mockRestore();
  });
});

describe("ShopSimilar", () => {
  it("searches by the photo first (Lens), with a keyword search as the fallback", async () => {
    routes({
      "/api/items/a/shop-links?detailed=false": {
        query: "sage green shirt",
        query_source: "color + category",
        color_name: "sage green",
        google_shopping: "https://www.google.com/search?tbm=shop&q=sage+green+shirt",
        google_lens: "https://lens.google.com/",
        google_images: "https://www.google.com/imghp",
      },
    });
    render(<ShopSimilar itemId="a" imageUrl="/api/images/a.jpg" />);
    expect(screen.getByRole("button", { name: /Shop this exact look with Google Lens/ })).toBeInTheDocument();
    expect(screen.getByText(/Sends this photo itself to Google Lens/)).toBeInTheDocument();
    const words = await screen.findByRole("link", { name: /Or search by words: “sage green shirt”/ });
    expect(words).toHaveAttribute("target", "_blank");
    expect(words).toHaveAttribute("rel", "noopener noreferrer");
  });

});
