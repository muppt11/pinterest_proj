import { useEffect, useState } from "react";
import { api, type ShopLinks } from "../api/client";
import { FeatureTip } from "./FeatureTip";

/** Copy an image to the clipboard as PNG (the format browsers accept for image paste). */
async function copyImage(url: string): Promise<void> {
  const blob = await (await fetch(url)).blob();
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0);
  const png = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("couldn't encode image"))), "image/png"),
  );
  await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
}

/** Outbound links to find something similar to buy. MoodBoards shows no prices or stores itself. */
export function ShopSimilar({ itemId, imageUrl }: { itemId: string; imageUrl: string }) {
  const [links, setLinks] = useState<ShopLinks | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    let cancelled = false;
    setLinks(null);
    setCopyState("idle");
    // Instant query from color + category, then a sharper one from the vision model if it's running.
    api
      .shopLinks(itemId, false)
      .then((l) => !cancelled && setLinks(l))
      .catch(() => {});
    api
      .shopLinks(itemId, true)
      .then((l) => !cancelled && l.query_source === "vision model" && setLinks(l))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [itemId]);

  if (!links) return null;

  async function copyAndSearch() {
    // Open the tab synchronously (inside the click) so pop-up blockers allow it.
    const tab = window.open(links!.google_images, "_blank", "noopener");
    try {
      await copyImage(imageUrl);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    tab?.focus();
  }

  return (
    <div className="mb-shop">
      <FeatureTip tipId="shop">
        <a className="mb-shop-primary" href={links.google_shopping} target="_blank" rel="noopener noreferrer">
          Shop similar: “{links.query}”
          <span className="visually-hidden"> (opens Google Shopping in a new tab)</span>
        </a>
      </FeatureTip>
      <button type="button" className="mb-shop-secondary" onClick={copyAndSearch}>
        Copy image + search Google by photo
      </button>
      <p className="mb-shop-note" aria-live="polite">
        {copyState === "copied"
          ? "Image copied. Press ⌘V (Ctrl+V) in the Google search box for visually identical results."
          : copyState === "failed"
            ? "Your browser blocked copying images. Right-click the photo, choose Copy Image, then paste it into Google."
            : `Query ${links.query_source === "vision model" ? "written from the photo by the local vision model" : "built from the item's color and type"}. Results on Google aren't checked by MoodBoards.`}
      </p>
    </div>
  );
}
