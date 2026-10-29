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

/** Google can only fetch images from a public address, not from localhost or a private network. */
export function isPublicOrigin(hostname: string): boolean {
  return !/^(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[?::1\]?$)/.test(hostname);
}

/** Google Lens's public "search by image URL" link: Lens fetches the image and runs the search. */
export function lensUrlFor(absoluteImageUrl: string): string {
  return `https://lens.google.com/uploadbyurl?url=${encodeURIComponent(absoluteImageUrl)}`;
}

/**
 * Shop similar, image first, using only Google's public entry points:
 * - on a public deployment, Lens's search-by-image-URL link (fully automatic);
 * - locally (Google can't reach localhost), copy the photo and open Lens for a one-key paste.
 * A keyword search is offered too. MoodBoards shows no prices or stores itself.
 */
export function ShopSimilar({ itemId, imageUrl }: { itemId: string; imageUrl: string }) {
  const [links, setLinks] = useState<ShopLinks | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const absolute = new URL(imageUrl, window.location.href).href;
  const direct = isPublicOrigin(window.location.hostname);

  useEffect(() => {
    let cancelled = false;
    setLinks(null);
    setCopyState("idle");
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

  async function copyAndOpenLens() {
    window.open("https://lens.google.com/", "_blank", "noopener"); // inside the click, so it isn't blocked
    try {
      await copyImage(imageUrl);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (
    <div className="mb-shop">
      <FeatureTip tipId="shop">
        {direct ? (
          <a className="mb-shop-primary" href={lensUrlFor(absolute)} target="_blank" rel="noopener noreferrer">
            Shop this exact look with Google Lens
            <span className="visually-hidden"> (searches with the photo, opens in a new tab)</span>
          </a>
        ) : (
          <button type="button" className="mb-shop-primary" onClick={copyAndOpenLens}>
            Shop this exact look with Google Lens
          </button>
        )}
      </FeatureTip>
      <p className="mb-shop-note" aria-live="polite">
        {direct
          ? "Searches Google Lens with this photo itself, not keywords, for the closest visual matches."
          : copyState === "copied"
            ? "Photo copied. In the Google Lens tab, press ⌘V (Ctrl+V) to search with it."
            : copyState === "failed"
              ? "Your browser blocked copying. Right-click the photo, choose Copy Image, then paste it into Google Lens."
              : "Running locally, Google can't fetch the photo, so this copies it for a one-key paste into Lens. On the hosted site it's automatic."}
      </p>
      {links && (
        <a className="mb-shop-secondary" href={links.google_shopping} target="_blank" rel="noopener noreferrer">
          Or search by words: “{links.query}”
        </a>
      )}
      <p className="mb-shop-note">Results on Google aren't checked by MoodBoards.</p>
    </div>
  );
}
