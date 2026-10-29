import { fireEvent, render, screen } from "@testing-library/react";
import { CharactersPage } from "../components/CharactersPage";

const info = { id: "wednesday-addams", name: "Wednesday Addams", source: "Wednesday (2022)", summary: "Strict monochrome gothic.", phrases: ["black pleated skirt", "black dress with a white collar"] };
const result = { id: "d", category: "Dress", image_url: "/images/d.jpg", kids: false, width: 4, height: 5, score: 0.3, matched_phrase: "black pleated skirt" };

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      new Response(
        JSON.stringify(
          url === "/api/characters" ? [{ ...info, covers: [result] }] : { ...info, disclaimer: "Not affiliated with or endorsed by the studio.", results: [result], looks: [{ name: "Nevermore uniform", phrases: ["black pleated skirt"], results: [result] }] },
        ),
      ),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe("CharactersPage", () => {
  it("lists characters and navigates to one", async () => {
    const onNavigate = vi.fn();
    render(<CharactersPage characterId={null} onNavigate={onNavigate} onOpen={() => {}} />);
    const card = await screen.findByRole("button", { name: /Wednesday Addams/ });
    expect(card.querySelectorAll("img")).toHaveLength(1); // catalog collage, not a film still
    fireEvent.click(card);
    expect(onNavigate).toHaveBeenCalledWith("/characters/wednesday-addams");
  });

  it("shows a character board with its style phrases, disclaimer, and items (no film images)", async () => {
    render(<CharactersPage characterId="wednesday-addams" onNavigate={() => {}} onOpen={() => {}} />);
    expect(await screen.findByRole("heading", { name: "Wednesday Addams" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Nevermore uniform" })).toBeInTheDocument();
    expect(screen.getByText("black pleated skirt")).toBeInTheDocument();
    expect(screen.getByText(/Not affiliated/)).toBeInTheDocument();
    expect(screen.getAllByRole("img").map((i) => i.getAttribute("src"))).toEqual(["/api/images/d.jpg"]);
  });
});
