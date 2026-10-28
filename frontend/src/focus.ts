import { useSyncExternalStore } from "react";

/** Estimated style focus. The dataset has no gender field, so the backend estimates it per item. */
export type Focus = "all" | "women" | "men";

export const FOCUS_LABELS: Record<Focus, string> = { all: "All styles", women: "Womenswear", men: "Menswear" };

const KEY = "mb-focus";
const listeners = new Set<() => void>();

function read(): Focus {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "women" || v === "men") return v;
  } catch {
    // ignore
  }
  return "all";
}

let current: Focus = read();

export function getFocus(): Focus {
  return current;
}

export function setFocus(next: Focus): void {
  current = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    // ignore
  }
  listeners.forEach((l) => l());
}

export function useFocus(): Focus {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    getFocus,
  );
}

/** Test helper. */
export function resetFocus(): void {
  current = read();
  listeners.forEach((l) => l());
}
