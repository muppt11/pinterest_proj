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

export const LENS_UPLOAD_URL = "https://lens.google.com/v3/upload";

/**
 * Search Google Lens with the image file itself (works on localhost too): open a named tab inside the
 * click so it isn't blocked as a pop-up, then POST the image there as a multipart form, the same way
 * the browser's own "Search image with Google" does. Google answers with its visual search results.
 * This upload endpoint isn't officially documented, so callers keep a copy-and-paste fallback.
 */
export async function searchLensWithImage(imageUrl: string): Promise<void> {
  const tab = window.open("", "mb-lens");
  if (tab) tab.opener = null;
  const blob = await (await fetch(imageUrl)).blob();
  const file = new File([blob], "item.jpg", { type: blob.type || "image/jpeg" });
  const form = document.createElement("form");
  form.method = "POST";
  form.enctype = "multipart/form-data";
  form.action = `${LENS_UPLOAD_URL}?ep=gsbubb&st=${Date.now()}`;
  form.target = "mb-lens";
  form.style.display = "none";
  const input = document.createElement("input");
  input.type = "file";
  input.name = "encoded_image";
  const files = new DataTransfer();
  files.items.add(file);
  input.files = files.files;
  form.appendChild(input);
  document.body.appendChild(form);
  form.submit();
  form.remove();
}

/**
 * Shop similar, image first: Google Lens searches with the photo itself, so results look as close as
 * possible; a keyword search is offered as the fallback. MoodBoards shows no prices or stores itself.
 */
export function ShopSimilar({ itemId, imageUrl }: { itemId: string; imageUrl: string }) {
  const [links, setLinks] = useState<ShopLinks | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

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

  async function openLens() {
    try {
      await searchLensWithImage(imageUrl);
      setCopyState("idle");
    } catch {
      // Fallback: copy the photo so it can be pasted into Lens by hand.
      window.open("https://lens.google.com/", "_blank", "noopener");
      try {
        await copyImage(imageUrl);
        setCopyState("copied");
      } catch {
        setCopyState("failed");
      }
    }
  }

  return (
    <div className="mb-shop">
      <FeatureTip tipId="shop">
        <button type="button" className="mb-shop-primary" onClick={openLens}>
          Shop this exact look with Google Lens
          <span className="visually-hidden"> (searches Google with this photo, opens in a new tab)</span>
        </button>
      </FeatureTip>
      <p className="mb-shop-note" aria-live="polite">
        {copyState === "copied"
          ? "Couldn't send the photo automatically, so it's copied: press ⌘V (Ctrl+V) in the Google Lens tab."
          : copyState === "failed"
            ? "Your browser blocked it. Right-click the photo, choose Copy Image, then paste it into Google Lens."
            : "Sends this photo itself to Google Lens (not keywords) for the closest visual matches."}
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
