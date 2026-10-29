import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ItemGrid } from "../components/ItemGrid";
import { SavesProvider } from "../saves";
import { SaveMenu } from "../components/SaveMenu";

const item = { id: "a", category: "Dress", image_url: "/images/a.jpg", kids: false, width: 4, height: 5 };

/** Tiny in-memory fake of the boards API. */
function fakeApi() {
  const boards = [
    { id: 1, name: "Wedding", parent_id: null, item_count: 0, cover: null },
    { id: 2, name: "Guests", parent_id: 1, item_count: 0, cover: null },
  ];
  const saved = new Map<number, Set<string>>();
  const calls: { url: string; body?: unknown }[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    calls.push({ url, body });
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/boards") return ok(boards);
    if (url.endsWith("/saved-in")) return ok([...saved].filter(([, s]) => s.has("a")).map(([b]) => b));
    if (url === "/api/saves") {
      const added = body.board_ids.filter((b: number) => !saved.get(b)?.has(body.item_id));
      added.forEach((b: number) => saved.set(b, new Set([...(saved.get(b) ?? []), body.item_id])));
      return ok({ item_id: body.item_id, added_to: added, already_in: [] });
    }
    if (url === "/api/saves/remove") {
      body.board_ids.forEach((b: number) => saved.get(b)?.delete(body.item_id));
      return ok({ item_id: body.item_id, added_to: [], already_in: body.board_ids });
    }
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, saved };
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderGrid() {
  return render(
    <SavesProvider>
      <ItemGrid items={[item]} label="Grid" onOpen={() => {}} />
    </SavesProvider>,
  );
}

describe("saving", () => {
  it("fits the whole save menu above a low anchor and adjusts to a shorter viewport", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("[]")));
    const anchor = document.createElement("button");
    document.body.append(anchor);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return this === anchor ? new DOMRect(950, 700, 30, 40) : new DOMRect(0, 0, 320, 400);
    });
    await act(async () => {
      render(<SaveMenu item={item} anchor={anchor} boards={[]} onCreateBoard={vi.fn()} onApply={vi.fn()} onClose={vi.fn()} />);
    });
    const menu = screen.getByRole("dialog", { name: "Save to boards" });
    expect(menu.parentElement).toBe(document.body);
    expect(menu).toHaveStyle({ top: "292px", left: "688px" });
    vi.stubGlobal("innerHeight", 320);
    fireEvent.resize(window);
    expect(menu).toHaveStyle({ top: "16px", maxHeight: "288px" });
    anchor.remove();
  });

  it("saves to several boards (including a sub-board) from the checklist, then undoes", async () => {
    const api = fakeApi();
    renderGrid();
    await waitFor(() => expect(api.calls.some((c) => c.url === "/api/boards")).toBe(true));

    // No last board yet, so Save opens the picker.
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    const menu = await screen.findByRole("dialog", { name: "Save to boards" });
    expect(menu).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Wedding" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Guests" }));
    fireEvent.click(screen.getByRole("button", { name: "Save to 2 boards" }));

    expect(await screen.findByText("Saved to Wedding, Guests")).toBeInTheDocument();
    expect([...api.saved.keys()].sort()).toEqual([1, 2]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); // no modal after saving

    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("Undone")).toBeInTheDocument();
    expect(api.saved.get(1)?.size).toBe(0);
    expect(api.saved.get(2)?.size).toBe(0);
  });

  it("quick-saves to the last board and the toast disappears after 5 seconds", async () => {
    localStorage.setItem("mb-last-board", "1");
    const api = fakeApi();
    renderGrid();
    expect(await screen.findByRole("button", { name: "Save to Wedding" })).toBeInTheDocument();

    vi.useFakeTimers({ shouldAdvanceTime: true });
    fireEvent.click(screen.getByRole("button", { name: "Save to Wedding" }));
    expect(await screen.findByText("Saved to Wedding")).toBeInTheDocument();
    expect(api.calls.find((c) => c.url === "/api/saves")?.body).toEqual({ item_id: "a", board_ids: [1] });

    await act(async () => {
      vi.advanceTimersByTime(5100);
    });
    expect(screen.queryByText("Saved to Wedding")).not.toBeInTheDocument();
  });
});
