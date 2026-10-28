import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../App";
import { StyleQuiz } from "../components/StyleQuiz";
import { resetFocus } from "../focus";

const quiz = {
  aesthetics: ["minimalist", "y2k"],
  colors: { neutrals: ["#f5f5f0"], pastels: ["#f6c6d0"] },
  eras: ["90s", "2000s"],
  focus: ["all", "women", "men"],
  max_picks: 6,
};

function api() {
  const calls: { url: string; method: string; body?: unknown }[] = [];
  let me: unknown = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(init.body as string) : undefined;
      calls.push({ url, method, body });
      const ok = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status });
      if (url.startsWith("/api/quiz")) return ok(quiz);
      if (url.startsWith("/api/me/prefs")) return ok((me = { display_name: "Tanvi", prefs: body }));
      if (url.startsWith("/api/me") && method === "POST") return ok((me = { display_name: body.display_name, prefs: { aesthetics: [], colors: [], eras: [], focus: "all" } }), 201);
      if (url.startsWith("/api/me")) return me ? ok(me) : ok({ detail: "Not signed up." }, 404);
      if (url.startsWith("/api/for-you")) return ok({ personalized: true, items: [] });
      if (url.startsWith("/api/items")) return ok({ items: [], total: 0, offset: 0 });
      return ok([]);
    }),
  );
  return calls;
}

beforeEach(() => {
  localStorage.clear();
  resetFocus();
  window.history.pushState(null, "", "/");
});
afterEach(() => vi.unstubAllGlobals());

describe("StyleQuiz", () => {
  it("walks through the steps, allows skipping one, and saves the answers", async () => {
    const calls = api();
    const onDone = vi.fn();
    render(<StyleQuiz mode="onboarding" me={null} onDone={onDone} />);
    fireEvent.change(await screen.findByPlaceholderText("Your first name"), { target: { value: "Tanvi" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "minimalist" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: /pastels/ }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Skip this question" })); // eras skipped
    fireEvent.click(screen.getByRole("radio", { name: "Womenswear" }));
    fireEvent.click(screen.getByRole("button", { name: "Finish" }));

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(calls.find((c) => c.url === "/api/me" && c.method === "POST")?.body).toEqual({ display_name: "Tanvi" });
    expect(calls.find((c) => c.url.startsWith("/api/me/prefs"))?.body).toEqual({ aesthetics: ["minimalist"], colors: ["pastels"], eras: [], focus: "women" });
    expect(localStorage.getItem("mb-focus")).toBe("women");
  });

  it("can skip setup entirely and won't ask again", async () => {
    api();
    const onDone = vi.fn();
    render(<StyleQuiz mode="onboarding" me={null} onDone={onDone} />);
    fireEvent.click(await screen.findByRole("button", { name: "Skip setup for now" }));
    expect(onDone).toHaveBeenCalledWith(null);
    expect(localStorage.getItem("mb-onboarding-skipped")).toBe("1");
  });

  it("first visit opens onboarding; after the quiz, Discover becomes For you", async () => {
    const calls = api();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "What should we call you?" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/welcome");
    fireEvent.change(screen.getByPlaceholderText("Your first name"), { target: { value: "Tanvi" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "y2k" }));
    for (let i = 0; i < 4; i++) fireEvent.click(screen.getByRole("button", { name: /Next|Finish/ }));
    expect(await screen.findByRole("heading", { name: "For you, Tanvi" })).toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.url.startsWith("/api/for-you"))).toBe(true));
    expect(screen.getByRole("radio", { name: "Everything" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Your style (Tanvi)" })).toBeInTheDocument();
  });
});
