import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { dismissTip, getTip, tipStore } from "../featureTips";
import "./FeatureTip.css";

interface FeatureTipProps {
  tipId: string;
  children: ReactNode;
  /** Which edge of the anchor the popover lines up with; use "end" near the right side of the screen. */
  align?: "start" | "end";
}

/**
 * Wraps a feature's UI and shows a small, non-blocking popover the first time it appears.
 * Tips queue up so only one shows at a time; Escape or "Got it" dismisses it for good.
 */
export function FeatureTip({ tipId, children, align = "start" }: FeatureTipProps) {
  const tip = getTip(tipId);
  useEffect(() => tipStore.register(tipId), [tipId]);
  useSyncExternalStore(tipStore.subscribe, tipStore.getVersion);
  const open = tipStore.active() === tipId;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && dismissTip(tipId);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, tipId]);

  return (
    <div className="mb-tip-anchor">
      {children}
      {open && (
        <div className={`mb-tip mb-tip-${align}`} role="dialog" aria-modal="false" aria-labelledby={`tip-${tipId}`}>
          <p className="mb-tip-title" id={`tip-${tipId}`}>{tip.title}</p>
          <p><strong>How:</strong> {tip.how}</p>
          <p><strong>Why:</strong> {tip.why}</p>
          <button type="button" className="mb-tip-ok" onClick={() => dismissTip(tipId)}>
            Got it
          </button>
        </div>
      )}
    </div>
  );
}
