# Data, models, and licenses

Nothing in this repo is scraped from Pinterest or any retailer. Every dataset, model, and design resource is recorded here, along with its license, **before** it is used.

| Asset | Source | License | Confirmed | Notes |
|---|---|---|---|---|
| clothing-dataset | https://github.com/alexeygrigorev/clothing-dataset | CC0-1.0 (public domain dedication) | 2026-10-28, GitHub license metadata + README ("can be freely used for any purpose") | Downloaded by `scripts/download_dataset.py`; only `images.csv` and `images/*.jpg` are extracted |
| Marqo-FashionCLIP | https://huggingface.co/Marqo/marqo-fashionCLIP | Apache-2.0 | 2026-10-28, Hugging Face model card metadata | Loaded via open_clip (`hf-hub:Marqo/marqo-fashionCLIP`) |
| Gestalt design tokens | https://github.com/pinterest/gestalt (`gestalt-design-tokens@177.0.12`) | Apache-2.0 | 2026-10-28, npm package metadata | Color and rounding values only, in `frontend/src/styles/tokens.css`. No Gestalt code, fonts, or logos are bundled |
| qwen3:8b (Ollama) | https://ollama.com/library/qwen3 | _to confirm in feature 4_ | | |
| qwen2.5vl:7b (Ollama) | https://ollama.com/library/qwen2.5vl | _to confirm in feature 4_ | | |
| Hand-labeled provenance set | the author's own photos and generated images | the author's own | | not committed |

Not used: Pinterest's "Pin Sans" font and logo. Both are proprietary and are not covered by Gestalt's license.

## Fields actually available (clothing-dataset)

`images.csv` has exactly four columns. These are the only item facts the app shows:

| Column | Meaning | In the app |
|---|---|---|
| `image` | UUID, also the file name `images/<uuid>.jpg` | item `id` |
| `sender_id` | anonymous ID of the person who contributed the photo | kept in metadata, not shown |
| `label` | one of 20 clothing classes | item `category`, also the card title (there are no product names) |
| `kids` | `True` if kids' clothing | "Kids' clothing: Yes/No" on the close-up |

The index script adds each image's pixel `width` and `height` (read from the file) so the masonry grid can reserve space before images load.

**Snapshot on 2026-10-28:** 5,756 image files and 5,403 rows in `images.csv`. 240 rows are labeled `Not sure` (228) or `Skip` (12), the dataset's own markers for unusable photos, so they're excluded. That leaves 5,163 indexed items. Kids' items make up 476 of the 5,403 rows.

There are **no** prices, sizes, brands, product names, reviews, capture dates, or EXIF provenance. The app never invents them.
