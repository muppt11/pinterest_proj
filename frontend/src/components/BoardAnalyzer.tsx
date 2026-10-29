import { useEffect, useMemo, useState } from "react";
import { api, type BoardAnalysis, type BoardContext, type Item } from "../api/client";
import { FeatureTip } from "./FeatureTip";
import { ItemGrid } from "./ItemGrid";
import { PageTitle } from "./PageTitle";
import { SaveLookButton } from "./SaveLookButton";
import "./BoardAnalyzer.css";

const MIN_IMAGES = 3;
const MAX_IMAGES = 20;
const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

/** Upload a board (3–20 outfit photos) and see its distinct aesthetics with matching catalog items. */
interface BoardAnalyzerProps {
  onOpen: (item: Item, board: BoardContext) => void;
  /** Reports each new analysis so the assistant can use it as context. */
  onAnalyzed?: (analysis: BoardAnalysis) => void;
}

export function BoardAnalyzer({ onOpen, onAnalyzed }: BoardAnalyzerProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [analysis, setAnalysis] = useState<BoardAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  function add(list: FileList | null) {
    if (!list) return;
    const accepted = Array.from(list).filter((f) => ACCEPT.includes(f.type));
    const skipped = list.length - accepted.length;
    setFiles((prev) => [...prev, ...accepted].slice(0, MAX_IMAGES));
    setAnalysis(null);
    setError(skipped > 0 ? `Skipped ${skipped} file(s): only JPEG, PNG, and WebP are supported.` : null);
  }

  function remove(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setAnalysis(null);
  }

  async function analyze() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.analyzeBoard(files);
      setAnalysis(result);
      onAnalyzed?.(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = files.length >= MIN_IMAGES && files.length <= MAX_IMAGES;

  return (
    <div className="mb-board">
      <PageTitle>Analyze a board</PageTitle>
      <FeatureTip tipId="board">
        <label
          className={`mb-dropzone${dragging ? " is-dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            add(e.dataTransfer.files);
          }}
        >
          <input type="file" accept={ACCEPT.join(",")} multiple onChange={(e) => add(e.target.files)} />
          <strong>Drop {MIN_IMAGES}–{MAX_IMAGES} outfit photos here</strong>
          <span>or click to choose files · JPEG, PNG, WebP up to 10 MB each</span>
        </label>
      </FeatureTip>

      {files.length > 0 && (
        <ul className="mb-board-previews" aria-label="Your board">
          {files.map((file, i) => (
            <li key={`${file.name}-${i}`}>
              <img src={previews[i]} alt={`Board image ${i + 1}: ${file.name}`} />
              <button type="button" aria-label={`Remove ${file.name}`} onClick={() => remove(i)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mb-board-actions">
        <span aria-live="polite">
          {files.length} / {MAX_IMAGES} images{files.length < MIN_IMAGES && ` · add at least ${MIN_IMAGES - files.length} more`}
        </span>
        <button type="button" className="mb-button-primary" disabled={!ready || busy} onClick={analyze}>
          {busy ? "Analyzing…" : "Analyze board"}
        </button>
      </div>

      {error && (
        <p role="alert" className="mb-notice">
          {error}
        </p>
      )}

      {analysis && (
        <section aria-label="Board analysis" className="mb-board-results">
          <p className="mb-board-summary">
            {analysis.k === 1
              ? "Your board reads as one consistent aesthetic."
              : `Your board has ${analysis.k} distinct aesthetics (silhouette ${analysis.silhouette?.toFixed(2)}).`}
          </p>
          {analysis.aesthetics.map((a) => (
            <article key={a.index} className="mb-aesthetic">
              <header>
                <h2>Aesthetic {a.index + 1}</h2>
                <SaveLookButton
                  name={`Aesthetic ${a.index + 1} · ${a.style_tags.map((t) => t.word).slice(0, 2).join(", ")}`}
                  items={a.results}
                />
                <ul className="mb-tags" aria-label="Closest style words">
                  {a.style_tags.map((t) => (
                    <li key={t.word}>{t.word}</li>
                  ))}
                </ul>
                <ul className="mb-aesthetic-members" aria-label={`Your images in aesthetic ${a.index + 1}`}>
                  {a.image_indices.map((i) => (
                    <li key={i}>
                      <img src={previews[i]} alt={`Board image ${i + 1}`} />
                    </li>
                  ))}
                </ul>
              </header>
              <ItemGrid
                items={a.results}
                label={`Catalog matches for aesthetic ${a.index + 1}`}
                onOpen={(item) => onOpen(item, { label: `Aesthetic ${a.index + 1}`, centroid: a.centroid })}
              />
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
