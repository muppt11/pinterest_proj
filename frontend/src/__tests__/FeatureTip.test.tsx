import { fireEvent, render, screen } from "@testing-library/react";
import { FeatureTip } from "../components/FeatureTip";
import { HelpMenu } from "../components/HelpMenu";
import { INTRO, tipStore } from "../featureTips";

const dismissWelcome = () => localStorage.setItem("mb-dismissed-tips", JSON.stringify(["welcome"]));

beforeEach(() => {
  localStorage.clear();
  tipStore.resetSession();
});

describe("FeatureTip", () => {
  it("waits for the welcome card, then shows how/why and stays dismissed after 'Got it'", () => {
    const { unmount } = render(
      <FeatureTip tipId="search">
        <input aria-label="search" />
      </FeatureTip>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); // welcome not dismissed yet
    unmount();

    dismissWelcome();
    const second = render(
      <FeatureTip tipId="search">
        <input aria-label="search" />
      </FeatureTip>,
    );
    expect(screen.getByRole("dialog", { name: "Search outfits" })).toBeInTheDocument();
    expect(screen.getByText(/Why:/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    second.unmount();

    render(
      <FeatureTip tipId="search">
        <input aria-label="search" />
      </FeatureTip>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows only one tip at a time, in order, and Escape advances the queue", () => {
    dismissWelcome();
    render(
      <>
        <FeatureTip tipId="theme">
          <button>theme</button>
        </FeatureTip>
        <FeatureTip tipId="search">
          <input aria-label="search" />
        </FeatureTip>
      </>,
    );
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: "Search outfits" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Light or dark mode" })).toBeInTheDocument();
  });
});

describe("HelpMenu", () => {
  it("shows a one-time welcome with a one-sentence intro and feature bullets", () => {
    const { unmount } = render(<HelpMenu />);
    const welcome = screen.getByRole("region", { name: "Welcome to MoodBoards" });
    expect(welcome).toHaveTextContent(INTRO.sentence);
    expect(screen.getAllByRole("listitem")).toHaveLength(INTRO.bullets.length);
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("region", { name: "Welcome to MoodBoards" })).not.toBeInTheDocument();
    unmount();
    render(<HelpMenu />);
    expect(screen.queryByRole("region", { name: "Welcome to MoodBoards" })).not.toBeInTheDocument();
  });

  it("lists the intro and every feature tip when opened", () => {
    dismissWelcome();
    render(<HelpMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Open help" }));
    const panel = screen.getByRole("region", { name: "How MoodBoards works" });
    expect(panel).toHaveTextContent(INTRO.bullets[0]);
    expect(screen.getByText("Search outfits")).toBeInTheDocument();
    expect(screen.getByText("Mood picker")).toBeInTheDocument();
  });
});
