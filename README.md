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

_The full Problem | Evidence | My fix | Limits table is filled in as each feature lands._

### User wishes (anecdotal)

From an r/Pinterest thread where users listed their dream features ([link](https://www.reddit.com/r/Pinterest/comments/1tp1tkh/what_are_your_dream_features_on_pinterest/)). It's a handful of comments, not a survey, so I treat it as a signal, not proof.

| Wish (paraphrased) | Why it matters | My fix | Limits |
|---|---|---|---|
| Unlimited sub-boards inside boards | Big boards turn into a wall of images; one level of sections isn't enough for "Wedding → Guest outfits → Shoes" | Feature 8: nested sub-boards with no fixed depth limit, plus breadcrumbs | Deep nesting can get hard to navigate; the UI shows breadcrumbs and item counts per level |
| A color picker | People often remember an outfit by its color, not by a word for it | Feature 7: color picker in the search bar, ranked by perceptual color distance | Dominant colors come from the whole photo, so backgrounds can skew results |
| Seeing when a pin was made | Without a date, users can't tell old trends from new ones, or originals from reposts | Feature 6: a "first seen" date on the close-up, labeled with its source (photo metadata or ingestion time) | The catalog has no capture dates, so it shows ingestion time and says so |
| Saving one pin to several boards at once, like a checklist (a commenter said this used to exist) | Re-opening the save menu for each board is slow and breaks flow | Feature 8: checklist save to multiple boards in one action, with an undo toast | None beyond scope: it's a local demo with no accounts |

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
| 6 | Repost detection + original credit, "first seen" date on every item | planned |
| 7 | Search by color (Lab k-means, Delta E 2000) | planned |
| 7b | Mood picker: color wheel + aesthetic → curated items | planned |
| 8 | Checklist save to multiple boards, nested sub-boards, undo toast | planned |
| 9 | Group trip outfit planning (stretch) | planned |
| 10 | Evals | planned |

### Mood picker (7b)

**What it does.** Pick a color on a color wheel, then pick an aesthetic (for example minimalist, streetwear, or coastal). The app returns a curated grid of items that match both.

**Why it's here.** It's my own idea for when you know the *feeling* you want but not the words for it. Text search needs vocabulary like "sage linen co-ord", and browsing needs patience. Two taps on a wheel and a chip turn a vague mood into a concrete starting board. It also builds on the color-picker wish from the user thread in section 2.

**How it works.**
- Each item's dominant colors (feature 7) are scored against the picked color with Delta E 2000.
- The aesthetic is scored with the CLIP text encoder ("a minimalist outfit"), using the same style vocabulary that names board aesthetics in feature 2.
- The two scores are normalized and blended. A "color ↔ style" slider sets the weight, so you can lean toward one or the other.
- Each result shows its color match and its style match, so the curation can be explained, not just trusted.

**Alternatives considered.**
- Searching for the color name as text ("red minimalist outfit"). Rejected: CLIP's sense of color words is fuzzy, and a picked hex value is precise.
- A hard color filter. Rejected: it empties out results for unusual colors, whereas a blended ranking degrades gracefully.

**How it's measured (feature 10).**
- The mean Delta E of the top 20 results should be lower than for random items.
- The style match of the top 20 should be higher than for a color-only ranking.

Design rules decided up front:

- **Provenance before privacy stripping.** Uploads have their C2PA/IPTC provenance and EXIF `DateTimeOriginal` read and stored *before* any re-encoding or GPS removal. A test checks that a C2PA-signed upload keeps its label afterwards.
- **No guessing the original.** If duplicates share a timestamp, or only ingestion times are known, the card says "original unclear" instead of crediting one. Uploads always count as newer than catalog items.
- **Labels demo with real evidence.** A hand-labeled set (the author's phone photos and AI images carrying Content Credentials) is added in feature 5, so all three label states appear. Feature 10's eval reuses it.

### UI approach

The layout follows conventions shared by visual-discovery apps: a masonry grid of rounded cards with titles underneath, a Save button on hover, a close-up view with the image on one side and actions and "More like this" on the other, and a settings-style side nav. Colors and corner rounding come from [Gestalt](https://github.com/pinterest/gestalt), Pinterest's open-source design system (Apache-2.0). That way the app feels native to the surface it's pitched for without copying anything proprietary. The name, logo, and wordmark are original. Pinterest's logo and its "Pin Sans" font are not used; the app uses the same system-font fallback stack instead. One accessibility change from Gestalt: its focus ring is semi-transparent, so the app uses a solid ring of the same blue that meets the 3:1 contrast guideline.

**Light and dark mode.** Light is the default. The sun/moon button in the header switches modes, the choice is remembered, and a feature tip points it out.

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
