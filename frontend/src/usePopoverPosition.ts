import { useLayoutEffect, useState, type CSSProperties, type RefObject } from "react";

/** Keep a portaled, fixed-position panel beside its anchor and inside the visible viewport. */
export function usePopoverPosition(
  open: boolean,
  anchor: HTMLElement | RefObject<HTMLElement>,
  panel: RefObject<HTMLElement>,
  { align = "start", side = "bottom", gap = 8, margin = 12 }: {
    align?: "start" | "end";
    side?: "top" | "bottom";
    gap?: number;
    margin?: number;
  } = {},
): CSSProperties {
  const [position, setPosition] = useState<{ top: number; left: number; maxHeight: number; maxWidth: number } | null>(null);

  useLayoutEffect(() => {
    if (!open) return;
    const anchorElement = anchor instanceof HTMLElement ? anchor : anchor.current;
    const panelElement = panel.current;
    if (!anchorElement || !panelElement) return;
    const update = () => {
      const rect = anchorElement.getBoundingClientRect();
      const bounds = panelElement.getBoundingClientRect();
      const viewport = window.visualViewport;
      const maxWidth = Math.max(0, (viewport?.width ?? window.innerWidth) - margin * 2);
      const maxHeight = Math.max(0, (viewport?.height ?? window.innerHeight) - margin * 2);
      const leftEdge = (viewport?.offsetLeft ?? 0) + margin;
      const topEdge = (viewport?.offsetTop ?? 0) + margin;
      const width = Math.min(bounds.width, maxWidth);
      const height = Math.min(bounds.height, maxHeight);
      const below = topEdge + maxHeight - rect.bottom - gap;
      const above = rect.top - topEdge - gap;
      const placeBelow = side === "bottom" ? height <= below || below >= above : height > above && below > above;
      const preferredTop = placeBelow ? rect.bottom + gap : rect.top - gap - height;
      const preferredLeft = align === "end" ? rect.right - width : rect.left;
      const next = {
        top: Math.max(topEdge, Math.min(preferredTop, topEdge + maxHeight - height)),
        left: Math.max(leftEdge, Math.min(preferredLeft, leftEdge + maxWidth - width)),
        maxHeight,
        maxWidth,
      };
      setPosition((previous) => previous?.top === next.top && previous.left === next.left && previous.maxHeight === maxHeight && previous.maxWidth === maxWidth ? previous : next);
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    window.visualViewport?.addEventListener("resize", update);
    window.visualViewport?.addEventListener("scroll", update);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(anchorElement);
    observer?.observe(panelElement);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
      window.visualViewport?.removeEventListener("resize", update);
      window.visualViewport?.removeEventListener("scroll", update);
      observer?.disconnect();
    };
  }, [open, anchor, panel, align, side, gap, margin]);

  return { ...position, visibility: position ? "visible" : "hidden" };
}
