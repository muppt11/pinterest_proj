import { useEffect, useRef, useState } from "react";
import type { ProvenanceLabel } from "../api/client";
import "./LabelBadge.css";

const TEXT: Record<ProvenanceLabel["label"], string> = {
  ai_generated: "AI-generated",
  human_verified: "Human-made ✓",
  unknown: "No provenance",
};

/**
 * The AI label, always visible on cards. Clicking explains which metadata field was found (or that
 * none was). "Unknown" is shown as a small, quiet marker so it doesn't crowd the grid.
 */
export function LabelBadge({ provenance, compact = false }: { provenance: ProvenanceLabel; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", close);
    };
  }, [open]);

  const quiet = compact && provenance.label === "unknown";
  return (
    <span ref={ref} className="mb-label-wrap">
      <button
        type="button"
        className={`mb-label mb-label-${provenance.label}${quiet ? " is-quiet" : ""}`}
        aria-expanded={open}
        aria-label={`${TEXT[provenance.label]}: why?`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
      >
        {quiet ? "ⓘ" : TEXT[provenance.label]}
      </button>
      {open && (
        <span className="mb-label-pop" role="dialog" aria-modal="false" aria-label="Why this label">
          <strong>{TEXT[provenance.label]}</strong>
          <span>{provenance.explanation}</span>
          {provenance.evidence.length > 0 && (
            <span className="mb-label-evidence">
              {provenance.evidence.map((e, i) => (
                <span key={i}>
                  {e.source}: {e.field} = <code>{e.value}</code>
                  {e.note ? ` (${e.note})` : ""}
                </span>
              ))}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
