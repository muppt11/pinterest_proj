import { act, fireEvent, render, screen } from "@testing-library/react";
import { BoardAnalyzer } from "../components/BoardAnalyzer";

const photo = (name: string, type = "image/jpeg") => new File(["x"], name, { type });
const item = (id: string, category: string) => ({ id, category, image_url: `/images/${id}.jpg`, kids: false, width: 400, height: 500, score: 0.8 });

beforeEach(() => {
  localStorage.clear();
  URL.createObjectURL = vi.fn((f: Blob) => `blob:${(f as File).name}`);
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

function choose(files: File[]) {
  fireEvent.change(screen.getByLabelText(/drop 3–20 outfit photos/i), { target: { files } });
}

describe("BoardAnalyzer", () => {
  it("needs at least 3 images and skips unsupported types", () => {
    render(<BoardAnalyzer onOpen={() => {}} />);
    choose([photo("a.jpg"), photo("b.gif", "image/gif")]);
    expect(screen.getByRole("alert")).toHaveTextContent("Skipped 1 file");
    expect(screen.getByText(/add at least 2 more/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze board" })).toBeDisabled();
  });

  it("uploads the board and shows each aesthetic with its images, tags, and matches", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          k: 2,
          silhouette: 0.42,
          silhouette_by_k: { "2": 0.42 },
          aesthetics: [
            { index: 0, image_indices: [0, 1], style_tags: [{ word: "minimalist", score: 0.3 }], results: [item("a", "Shirt")] },
            { index: 1, image_indices: [2], style_tags: [{ word: "streetwear", score: 0.3 }], results: [item("b", "Hoodie")] },
          ],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<BoardAnalyzer onOpen={() => {}} />);
    choose([photo("a.jpg"), photo("b.jpg"), photo("c.png", "image/png")]);
    fireEvent.click(screen.getByRole("button", { name: "Analyze board" }));

    expect(await screen.findByText(/2 distinct aesthetics/)).toBeInTheDocument();
    expect(screen.getByText("minimalist")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Your images in aesthetic 1" }).children).toHaveLength(2);
    expect(screen.getByRole("img", { name: "Photo of hoodie" })).toBeInTheDocument();

    const body = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as FormData;
    expect(body.getAll("images")).toHaveLength(3);
  });

  it("can remove an image before analyzing", () => {
    render(<BoardAnalyzer onOpen={() => {}} />);
    choose([photo("a.jpg"), photo("b.jpg"), photo("c.jpg")]);
    fireEvent.click(screen.getByRole("button", { name: "Remove b.jpg" }));
    expect(screen.getByRole("list", { name: "Your board" }).children).toHaveLength(2);
  });

  it("discards an analysis when the photo selection changes during the request", async () => {
    let finish!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; })));
    const onAnalyzed = vi.fn();
    render(<BoardAnalyzer onOpen={() => {}} onAnalyzed={onAnalyzed} />);
    choose([photo("a.jpg"), photo("b.jpg"), photo("c.jpg")]);
    fireEvent.click(screen.getByRole("button", { name: "Analyze board" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove c.jpg" }));
    await act(async () => { finish(new Response(JSON.stringify({ k: 1, aesthetics: [] }))); });
    expect(screen.queryByRole("region", { name: "Board analysis" })).not.toBeInTheDocument();
    expect(onAnalyzed).toHaveBeenLastCalledWith(null);
    expect(screen.getByRole("button", { name: "Analyze board" })).toBeDisabled();
  });
});
