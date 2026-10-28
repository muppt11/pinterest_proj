import { useState } from "react";
import { dismissTip, FEATURE_TIPS, getDismissedTips, INTRO, WELCOME_ID } from "../featureTips";
import "./FeatureTip.css";

function Intro({ headingId }: { headingId: string }) {
  return (
    <>
      <h2 id={headingId}>Welcome to MoodBoards</h2>
      <p>{INTRO.sentence}</p>
      <ul className="mb-intro-list">
        {INTRO.bullets.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>
    </>
  );
}

/**
 * Floating "?" button. On first visit a small welcome card sits above it (non-blocking);
 * afterwards the same intro and every feature tip live in the help panel.
 */
export function HelpMenu({ suppressWelcome = false }: { suppressWelcome?: boolean }) {
  const [open, setOpen] = useState(false);
  const [welcome, setWelcome] = useState(() => !getDismissedTips().has(WELCOME_ID));

  function closeWelcome() {
    dismissTip(WELCOME_ID);
    setWelcome(false);
  }

  return (
    <div className="mb-help">
      {welcome && !open && !suppressWelcome && (
        <section className="mb-help-panel mb-welcome" aria-labelledby="welcome-heading">
          <Intro headingId="welcome-heading" />
          <div className="mb-welcome-actions">
            <button type="button" className="mb-tip-ok" onClick={closeWelcome}>
              Got it
            </button>
            <span>Tap ? any time to see this again.</span>
          </div>
        </section>
      )}
      {open && (
        <section className="mb-help-panel" aria-label="How MoodBoards works">
          <Intro headingId="help-intro" />
          <h2 className="mb-help-features">Features</h2>
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
        onClick={() => {
          if (welcome) closeWelcome();
          setOpen(!open);
        }}
      >
        {open ? "×" : "?"}
      </button>
    </div>
  );
}
