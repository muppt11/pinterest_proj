import { useEffect, useState, type ReactNode } from "react";
import { dismissTip, getDismissedTips, getTip } from "../featureTips";
import "./FeatureTip.css";

interface FeatureTipProps {
  tipId: string;
  children: ReactNode;
}

/**
 * Wraps a feature's UI and shows a small, non-blocking popover the first time it appears.
 * It never steals focus or blocks the page; Escape or "Got it" dismisses it for good.
 */
export function FeatureTip({ tipId, children }: FeatureTipProps) {
  const tip = getTip(tipId);
  const [open, setOpen] = useState(() => !getDismissedTips().has(tipId));

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function close() {
    dismissTip(tipId);
    setOpen(false);
  }

  return (
    <div className="mb-tip-anchor">
      {children}
      {open && (
        <div className="mb-tip" role="dialog" aria-modal="false" aria-labelledby={`tip-${tipId}`}>
          <p className="mb-tip-title" id={`tip-${tipId}`}>{tip.title}</p>
          <p><strong>How:</strong> {tip.how}</p>
          <p><strong>Why:</strong> {tip.why}</p>
          <button type="button" className="mb-tip-ok" onClick={close}>
            Got it
          </button>
        </div>
      )}
    </div>
  );
}
