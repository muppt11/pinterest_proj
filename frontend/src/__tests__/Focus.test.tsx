import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../App";
import { withFocus } from "../api/client";
import { resetFocus, setFocus } from "../focus";

beforeEach(() => {
  localStorage.clear();
  resetFocus();
  window.history.pushState(null, "", "/");
});
afterEach(() => vi.unstubAllGlobals());

describe("style focus", () => {
  it("adds the focus to API URLs only when one is chosen", () => {
    expect(withFocus("/items?limit=5")).toBe("/items?limit=5");
    setFocus("women");
    expect(withFocus("/items?limit=5")).toBe("/items?limit=5&focus=women");
    expect(withFocus("/styles")).toBe("/styles?focus=women");
    expect(localStorage.getItem("mb-focus")).toBe("women");
  });

  it("re-runs the home feed with the new focus from the header", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        return new Response(JSON.stringify(url.startsWith("/api/items") ? { items: [], total: 0, offset: 0 } : []));
      }),
    );
    render(<App />);
    await waitFor(() => expect(calls.some((c) => c.startsWith("/api/items?offset=0"))).toBe(true));
    fireEvent.change(screen.getByRole("combobox", { name: "Show" }), { target: { value: "men" } });
    await waitFor(() => expect(calls.some((c) => c.startsWith("/api/items?") && c.endsWith("focus=men"))).toBe(true));
  });
});
