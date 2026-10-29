import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { JoinPage } from "../components/JoinPage";
import { PublicTripPage } from "../components/PublicTripPage";
import { TripPage } from "../components/TripPage";

const item = { id: "i1", category: "Outwear", image_url: "/images/i1.jpg", kids: false, width: 4, height: 5 };
const weather = {
  source: "historical average",
  source_detail: "Average of the same dates in 2021–2025 (Open-Meteo archive)",
  attribution: "Weather data by Open-Meteo.com (CC BY 4.0)",
  days: [{ date: "2026-12-01", high_c: 12, low_c: 6, rain_chance: 0.6 }],
};
const trip = (role: string) => ({
  id: 7, name: "Lisbon", place: "Lisbon, Portugal", start_date: "2026-12-01", end_date: "2026-12-02",
  coordinate: false, public_slug: null, published: false, your_role: role,
  members: [{ user_id: 1, name: "Ana", role: "owner", is_you: role === "owner" }, { user_id: 2, name: "Bea", role: "editor", is_you: false }],
  slots: [{ id: 3, day: "2026-12-01", label: "beach dinner" }],
  weather,
  taste: { inspiration_count: 4, group_style: ["minimalist"], members: [], overlap: [{ a: "Ana", b: "Bea", similarity: 0.5, reading: "clashing" }] },
  palette: [],
});

function api(role: string) {
  const calls: { url: string; method: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(init.body as string) : undefined });
      const ok = (d: unknown) => new Response(JSON.stringify(d));
      if (url === "/api/trips/7") return ok(trip(role));
      if (url.includes("/suggestions")) return ok({ slot: trip(role).slots[0], weather: weather.days[0], weather_source: "historical average", items: [{ role: "outerwear", item, votes: { up: 1, down: 0, mine: 0 } }] });
      if (url.includes("/votes")) return ok({ ok: true });
      if (url.includes("/packing")) return ok({ items: [{ kind: "essential", label: "Umbrella or rain jacket", why: "up to 60% chance of rain" }], weather_source: "historical average" });
      if (url.includes("/notes")) return ok([{ id: 1, day: "2026-12-01", text: "Bring a light layer.", ai_suggestion: 1, author: "Ana" }]);
      if (url.includes("/activity")) return ok([{ id: 1, actor: "Bea", text: "joined as editor" }]);
      if (url.includes("/invites")) return ok([]);
      return ok({});
    }),
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("TripPage", () => {
  it("labels the weather source, shows taste overlap, AI-labeled notes, activity, and packing", async () => {
    api("owner");
    render(<TripPage tripId={7} onOpen={() => {}} onNavigate={() => {}} />);
    expect(await screen.findByText("Historical average")).toBeInTheDocument();
    expect(screen.getByText(/Weather data by Open-Meteo/)).toBeInTheDocument();
    expect(screen.getByText("clashing")).toBeInTheDocument();
    expect(await screen.findByText("AI suggestion")).toBeInTheDocument();
    expect(await screen.findByText("joined as editor")).toBeInTheDocument();
    expect(await screen.findByText("Umbrella or rain jacket")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Invite (can edit)" })).toBeInTheDocument();
  });

  it("lets editors vote but viewers only look", async () => {
    const calls = api("editor");
    const { unmount } = render(<TripPage tripId={7} onOpen={() => {}} onNavigate={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /beach dinner/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Like this outwear" }));
    await waitFor(() => expect(calls.find((c) => c.url.includes("/votes"))?.body).toEqual({ item_id: "i1", value: 1 }));
    expect(screen.queryByRole("button", { name: "Invite (can edit)" })).not.toBeInTheDocument();
    unmount();

    api("viewer");
    render(<TripPage tripId={7} onOpen={() => {}} onNavigate={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /beach dinner/ }));
    expect(await screen.findByRole("button", { name: "Like this outwear" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Draft with AI" })).not.toBeInTheDocument();
  });
});

describe("PublicTripPage", () => {
  it("shows the plan without names", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      name: "Lisbon", place: "Lisbon, Portugal", start_date: "2026-12-01", end_date: "2026-12-02", travelers: 3, weather,
      lineup: [{ day: "2026-12-01", label: "beach dinner", items: [item] }], notes: [],
    }))));
    render(<PublicTripPage slug="abc" />);
    expect(await screen.findByRole("heading", { name: "Lisbon" })).toBeInTheDocument();
    expect(screen.getByText(/3 travelers/)).toBeInTheDocument();
    expect(screen.queryByText(/Ana|Bea/)).not.toBeInTheDocument();
  });
});

describe("JoinPage", () => {
  it("asks you to sign up first, then joins and goes to the trip", async () => {
    const onNavigate = vi.fn();
    const { rerender } = render(<JoinPage token="tok" signedIn={false} onNavigate={onNavigate} />);
    expect(screen.getByText(/invited to a trip/)).toBeInTheDocument();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ trip_id: 7, role: "editor" }))));
    rerender(<JoinPage token="tok" signedIn onNavigate={onNavigate} />);
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/trips/7"));
  });
});
