import { fireEvent, render, screen } from "@testing-library/react";
import { FeatureTip } from "../components/FeatureTip";
import { HelpMenu } from "../components/HelpMenu";

beforeEach(() => localStorage.clear());

describe("FeatureTip", () => {
  it("shows how and why on first view, and stays dismissed after 'Got it'", () => {
    const { unmount } = render(
      <FeatureTip tipId="search">
        <input aria-label="search" />
      </FeatureTip>,
    );
    expect(screen.getByRole("dialog", { name: "Search outfits" })).toBeInTheDocument();
    expect(screen.getByText(/Why:/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    unmount();
    render(
      <FeatureTip tipId="search">
        <input aria-label="search" />
      </FeatureTip>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape", () => {
    render(
      <FeatureTip tipId="search">
        <input aria-label="search" />
      </FeatureTip>,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("HelpMenu", () => {
  it("lists every feature tip when opened", () => {
    render(<HelpMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Open help" }));
    expect(screen.getByRole("region", { name: "How MoodBoards works" })).toBeInTheDocument();
    expect(screen.getByText("Search outfits")).toBeInTheDocument();
  });
});
