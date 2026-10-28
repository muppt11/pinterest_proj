import { render, screen } from "@testing-library/react";
import App from "../App";

describe("App shell", () => {
  it("shows the MoodBoards brand and a labeled search field", () => {
    render(<App />);
    expect(screen.getByRole("link", { name: "MoodBoards home" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /search outfits/i })).toBeInTheDocument();
  });
});
