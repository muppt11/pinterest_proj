import { useState } from "react";
import { FEATURE_TIPS } from "../featureTips";
import "./FeatureTip.css";

/** Floating "?" button that lists every feature tip, so dismissed tips are never lost. */
export function HelpMenu() {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-help">
      {open && (
        <section className="mb-help-panel" aria-label="How MoodBoards works">
          <h2>How MoodBoards works</h2>
          <ul>
            {FEATURE_TIPS.map((tip) => (
              <li key={tip.id}>
                <p className="mb-tip-title">{tip.title}</p>
                <p><strong>How:</strong> {tip.how}</p>
                <p><strong>Why:</strong> {tip.why}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
      <button
        type="button"
        className="mb-help-button"
        aria-expanded={open}
        aria-label={open ? "Close help" : "Open help"}
        onClick={() => setOpen(!open)}
      >
        {open ? "×" : "?"}
      </button>
    </div>
  );
}
