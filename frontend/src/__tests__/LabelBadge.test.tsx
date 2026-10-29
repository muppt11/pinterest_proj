import { fireEvent, render, screen } from "@testing-library/react";
import { LabelBadge } from "../components/LabelBadge";

describe("LabelBadge", () => {
  it("shows the AI label and explains which metadata field was found", () => {
    render(
      <LabelBadge
        provenance={{
          label: "ai_generated",
          explanation: "Its Content Credentials (C2PA) say it was made with generative AI.",
          evidence: [{ source: "C2PA", field: "c2pa.actions → digitalSourceType", value: "trainedAlgorithmicMedia" }],
        }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "AI-generated: why?" }));
    expect(screen.getByRole("dialog", { name: "Why this label" })).toHaveTextContent("trainedAlgorithmicMedia");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps Unknown quiet on cards but still explainable", () => {
    render(<LabelBadge compact provenance={{ label: "unknown", explanation: "No provenance metadata.", evidence: [] }} />);
    const button = screen.getByRole("button", { name: "No provenance: why?" });
    expect(button).toHaveTextContent("ⓘ");
    fireEvent.click(button);
    expect(screen.getByText("No provenance metadata.")).toBeInTheDocument();
  });
});
