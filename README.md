# MoodBoards

> **Disclaimer:** This is a non-commercial concept project and portfolio sample. It is not affiliated with, endorsed by, or sponsored by Pinterest. See [Disclaimer](#13-disclaimer).

## 1. Pitch

_One-line pitch: written once features 1–2 work._

![Demo GIF placeholder](docs/demo.gif)

### Run it locally

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 20+, [Ollama](https://ollama.com).

```bash
make setup models index   # once: deps, local models, catalog index
make dev                  # API on :8000, web app on :5173
```

`make test` runs pytest and Vitest. `make help` lists every target.

## 2. User research and opportunities

_Problem | Evidence | My fix | Limits table: filled in as each feature lands._

## 3. Prior art and what's different

_To be written._ The five differentiators:

1. Board-level taste: many images become a taste profile with distinct aesthetics
2. An agent that makes real tool calls, plus an eval harness
3. AI labels users can see and trust: evidence-based, visible on the grid, with an appeal path
4. Repost detection that credits the original creator
5. Group trip outfit planning: a shared aesthetic plus real weather become coordinated outfits and packing lists

## 4. Features and why

| # | Feature | Status |
|---|---|---|
| 0 | Scaffolding (FastAPI, React + Vite, Makefile, tests) | done |
| 1 | Indexing + image/text search | planned |
| 2 | Board analysis (k-means, k by silhouette score) | planned |
| 3 | Complete the look | planned |
| 4 | Assistant (LangGraph + Ollama) | planned |
| 5 | AI labels, review queue, "Fewer AI images" toggle | planned |
| 6 | Repost detection + original credit | planned |
| 7 | Search by color (Lab k-means, Delta E 2000) | planned |
| 8 | Multi-board save, sections, undo toast | planned |
| 9 | Group trip outfit planning (stretch) | planned |
| 10 | Evals | planned |

Design rules decided up front:

- **Provenance before privacy stripping.** Uploads have their C2PA/IPTC provenance and EXIF `DateTimeOriginal` read and stored *before* any re-encoding or GPS removal. A test checks that a C2PA-signed upload keeps its label afterwards.
- **No guessing the original.** If duplicates share a timestamp, or only ingestion times are known, the card says "original unclear" instead of crediting one. Uploads always count as newer than catalog items.
- **Labels demo with real evidence.** A hand-labeled set (the author's phone photos and AI images carrying Content Credentials) is added in feature 5, so all three label states appear. Feature 10's eval reuses it.

### UI approach

The layout follows conventions shared by visual-discovery apps: a masonry grid of rounded cards with titles underneath, a Save button on hover, a close-up view with the image on one side and actions and "More like this" on the other, and a settings-style side nav. The color scheme (white canvas, neutral grey pills, red accent) is deliberately familiar to visual-discovery users. The name, logo, and wordmark are original, and no third-party logos, fonts, or screenshots appear in the app.

**In-app feature tips.** The first time a feature appears, a small popover explains how to use it and why it exists. It doesn't block the page: Escape or "Got it" dismisses it, and the floating "?" button lists every tip again. Tips never appear after saving or downloading. That avoids the kind of interruption users complained about (see section 2).

## 5. Architecture

_Mermaid diagram: added in feature 1 and kept current._

## 6. Eval results

_Feature 10._

## 7. Security and privacy

_Summary of [THREAT_MODEL.md](THREAT_MODEL.md): features 5 and 9._

## 8. How I used AI tools and how I validated their output

_To be written in my own words._

## 9. Learning curve

_Pulled from [LEARNING_LOG.md](LEARNING_LOG.md), in my own words._

## 10. Limitations and next steps

_To be written._

## 11. Sources

_Grouped list with one line each on what it informed. Short and mirror links will be replaced with canonical URLs. Dataset, model, API, and library licenses are recorded in [DATA.md](DATA.md)._

## 12. Where this fits in Pinterest

_Feature-to-surface mapping: written once features are built._

## 13. Disclaimer

This is a non-commercial concept project built as a portfolio sample. It is not affiliated with, endorsed by, or sponsored by Pinterest. "Pinterest" is a trademark of Pinterest, Inc. and is mentioned only to describe the problems this project explores. The UI is an original design inspired by visual-discovery apps in general.
