import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { categoryLabel, DEFAULT_FILTERS } from "../categories";
import { FilterBar } from "../components/FilterBar";
import { SaveLookButton } from "../components/SaveLookButton";
import { SavesProvider } from "../saves";

afterEach(() => vi.unstubAllGlobals());

describe("categoryLabel", () => {
  it("fixes the dataset's awkward labels and leaves the rest", () => {
    expect(categoryLabel("Outwear")).toBe("Outerwear");
    expect(categoryLabel("Longsleeve")).toBe("Long-sleeve top");
    expect(categoryLabel("Dress")).toBe("Dress");
  });
});

describe("FilterBar", () => {
  it("changes garment type and aesthetic", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(["minimalist", "streetwear"]))));
    const onChange = vi.fn();
    render(<FilterBar value={{ ...DEFAULT_FILTERS }} showStyle onChange={onChange} />);
    fireEvent.click(screen.getByRole("radio", { name: "Shoes" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, group: "shoes" });
    await screen.findByRole("option", { name: "streetwear" });
    fireEvent.change(screen.getByRole("combobox", { name: "Aesthetic" }), { target: { value: "streetwear" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, style: "streetwear" });
  });

  it("shows counted subcategories, preserves other filters, and resets conflicting categories", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/filters") ? {
      categories: [
        { value: "T-Shirt", label: "T-shirt", group: "tops", count: 2 },
        { value: "Hoodie", label: "Hoodie", group: "tops", count: 0 },
        { value: "Pants", label: "Pants", group: "bottoms", count: 3 },
      ], total: 5,
    } : ["minimalist"]))));
    const onChange = vi.fn();
    const value = { ...DEFAULT_FILTERS, group: "tops" as const, audience: "kids" as const, colorFamily: "pastels" };
    const { rerender } = render(<FilterBar value={value} showStyle onChange={onChange} />);
    expect(await screen.findByRole("option", { name: "T-shirt (2)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Hoodie (0)" })).toBeDisabled();
    expect(screen.queryByRole("option", { name: "Pants (3)" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Category" }), { target: { value: "T-Shirt" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...value, category: "T-Shirt" });
    rerender(<FilterBar value={{ ...value, category: "T-Shirt" }} showStyle onChange={onChange} />);
    fireEvent.click(screen.getByRole("radio", { name: "Bottoms" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...value, group: "bottoms", category: null });
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onChange).toHaveBeenLastCalledWith(DEFAULT_FILTERS);
  });
});

describe("SaveLookButton", () => {
  it("creates a board from the look, with undo", async () => {
    const calls: { url: string; method: string; body?: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(init.body as string) : undefined });
        if (url === "/api/boards/from-items") return new Response(JSON.stringify({ id: 9, name: "Cher · The yellow plaid suit", parent_id: null, item_count: 2, cover: null }), { status: 201 });
        return new Response(JSON.stringify([]));
      }),
    );
    const items = ["a", "b"].map((id) => ({ id, category: "Blazer", image_url: `/images/${id}.jpg`, kids: false, width: 1, height: 1 }));
    render(
      <SavesProvider>
        <SaveLookButton name="Cher · The yellow plaid suit" items={items} />
      </SavesProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save as board" }));
    expect(await screen.findByText("Saved 2 items to “Cher · The yellow plaid suit”")).toBeInTheDocument();
    expect(calls.find((c) => c.url === "/api/boards/from-items")?.body).toEqual({ name: "Cher · The yellow plaid suit", item_ids: ["a", "b"] });
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/boards/9" && c.method === "DELETE")).toBe(true));
  });
});
