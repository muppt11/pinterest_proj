"""MoodBoards evals: writes evals/reports/<date>.md and evals/reports/latest.md.

Sections: retrieval, search relevance cutoff, board splitting, color, duplicates, trip weather rules +
permission tests, AI labels, and the assistant (skipped, and reported as skipped, if Ollama is down).

Usage (from backend/): uv run python ../evals/run_evals.py [--quick]
Heavy imports (faiss) live inside main(): the embedding worker process re-imports this file.
"""

import argparse
import io
import json
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.embedder import ProcessEmbedder  # noqa: E402

RNG = random.Random(7)


def pct(x: float) -> str:
    return f"{x:.1%}"


# --- 1. Retrieval ------------------------------------------------------------------------------


def eval_retrieval(catalog, n_queries: int) -> list[str]:  # type: ignore[no-untyped-def]
    """Held-out image queries: each query item is excluded (with its duplicate group) from its own results."""
    rows = RNG.sample(range(len(catalog.items)), n_queries)
    hits, precisions = [], []
    per_cat: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        item = catalog.items[r]
        exclude = catalog.reposts.group_members(item["id"])
        res = catalog.search(catalog.matrix[r], k=10, exclude_ids=exclude, collapse_reposts=False)
        same = [h.item["category"] == item["category"] for h in res]
        hits.append(any(same))
        precisions.append(sum(same) / len(same))
        per_cat[item["category"]].append(sum(same) / len(same))
    lines = [
        "## 1. Retrieval (image → similar items)",
        "",
        f"{n_queries} held-out catalog photos used as queries; each query and its duplicate copies are excluded from its own results. "
        "\"Relevant\" = same dataset category (a strict proxy: a blazer returned for a coat counts as a miss).",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| **Recall@10** (≥ 1 same-category item in the top 10) | **{pct(np.mean(hits))}** |",
        f"| Precision@10 (share of the top 10 in the same category) | {pct(np.mean(precisions))} |",
        "",
        "| Category (queries) | Precision@10 |",
        "|---|---|",
    ]
    for cat, ps in sorted(per_cat.items(), key=lambda kv: -len(kv[1]))[:10]:
        lines.append(f"| {cat} ({len(ps)}) | {pct(np.mean(ps))} |")
    return lines + [""]


# --- 2. Relevance cutoff on held-out queries ---------------------------------------------------

HELD_OUT_ON = ["flowy maxi skirt", "grey crewneck sweatshirt", "brown leather belt bag", "striped polo", "linen trousers",
               "chunky white sneakers", "floral summer dress", "oversized denim jacket", "black ankle boots", "knitted beanie",
               "pleated tennis skirt", "olive cargo pants"]
HELD_OUT_OFF = ["chocolate cake recipe", "mountain bike", "living room lamp", "golden retriever", "tax return", "sunset over the sea",
                "kitchen sink", "guitar chords", "car engine", "houseplant care", "qwerty", "office chair"]


def eval_relevance(catalog, embedder) -> list[str]:  # type: ignore[no-untyped-def]
    from app.routers.search import MIN_TEXT_RELEVANCE, RELEVANCE_WINDOW

    def flagged(q: str) -> bool:
        hits = catalog.search(embedder.embed_texts([q])[0], k=RELEVANCE_WINDOW)
        return float(np.mean([h.score for h in hits])) < MIN_TEXT_RELEVANCE

    on_ok = sum(not flagged(q) for q in HELD_OUT_ON)
    off_ok = sum(flagged(q) for q in HELD_OUT_OFF)
    return [
        "## 2. \"Nothing matched\" cutoff on held-out queries",
        "",
        f"The cutoff ({MIN_TEXT_RELEVANCE}) was tuned on 26 queries; these 24 are new.",
        "",
        "| Query set | Correct |",
        "|---|---|",
        f"| Clothing queries shown normally | {on_ok}/{len(HELD_OUT_ON)} |",
        f"| Non-clothing queries flagged | {off_ok}/{len(HELD_OUT_OFF)} |",
        "",
    ]


# --- 3. Board splitting --------------------------------------------------------------------------

PAIRS = [("Dress", "Shoes"), ("Pants", "Hat"), ("T-Shirt", "Skirt"), ("Outwear", "Shorts"), ("Shirt", "Shoes"), ("Hoodie", "Dress")]


def eval_boards(catalog, n: int) -> tuple[list[str], dict]:  # type: ignore[no-untyped-def]
    from app.services import board as board_mod

    by_cat: dict[str, list[int]] = defaultdict(list)
    for r, i in enumerate(catalog.items):
        if not i["kids"]:
            by_cat[i["category"]].append(r)
    singles = [RNG.sample(by_cat[RNG.choice(["T-Shirt", "Dress", "Pants", "Shoes", "Longsleeve"])], 6) for _ in range(n)]
    mixes = []
    for _ in range(n):
        a, b = RNG.choice(PAIRS)
        mixes.append(RNG.sample(by_cat[a], 3) + RNG.sample(by_cat[b], 3))

    def accuracy(gap: float, sil: float) -> tuple[float, float]:
        one = np.mean([board_mod.choose_clusters(catalog.matrix[s], min_silhouette=sil, min_gap=gap).k == 1 for s in singles])
        two = np.mean([board_mod.choose_clusters(catalog.matrix[m], min_silhouette=sil, min_gap=gap).k >= 2 for m in mixes])
        return float(one), float(two)

    rows = []
    best = None
    for gap in (0.1, 0.15, 0.2, 0.25, 0.3, 0.35):
        one, two = accuracy(gap, board_mod.MIN_SILHOUETTE)
        balanced = (one + two) / 2
        rows.append(f"| {gap} | {pct(one)} | {pct(two)} | {pct(balanced)} |")
        if best is None or balanced > best[0]:
            best = (balanced, gap, one, two)
    current = accuracy(board_mod.MIN_CENTROID_DISTANCE, board_mod.MIN_SILHOUETTE)
    lines = [
        "## 3. Board analysis: does it find the right number of aesthetics?",
        "",
        f"{n} synthetic one-look boards (6 photos of one category) and {n} two-look boards (3 + 3 photos from clearly different "
        "categories, e.g. dresses + shoes). One category is a proxy for \"one look\", so some genuine splits count as errors.",
        "",
        f"Current `MIN_CENTROID_DISTANCE` = {board_mod.MIN_CENTROID_DISTANCE}: one-look boards kept whole **{pct(current[0])}**, "
        f"two-look boards split **{pct(current[1])}**.",
        "",
        "| Centroid gap | One-look kept whole | Two-look split | Balanced |",
        "|---|---|---|---|",
        *rows,
        "",
        f"Best balanced setting: gap **{best[1]}** ({pct(best[0])}).",  # type: ignore[index]
        "",
    ]
    return lines, {"best_gap": best[1], "current": current}  # type: ignore[index]


# --- 4. Color ----------------------------------------------------------------------------------


def eval_color(catalog, embedder) -> list[str]:  # type: ignore[no-untyped-def]
    from app.services.aesthetics import STYLE_WORDS, bank_for, phrases_for
    from app.services.color import delta_e_2000, hex_to_rgb, rgb_to_lab
    from app.services.color_search import COLOR_NAMES, color_index, color_search

    index = color_index(catalog)
    names = RNG.sample(sorted(COLOR_NAMES), 15)
    top_de, rand_de = [], []
    for name in names:
        hexv = "#{:02x}{:02x}{:02x}".format(*COLOR_NAMES[name])
        target = rgb_to_lab(np.array(hex_to_rgb(hexv)))
        de, _ = index.distances(target)
        hits = color_search(catalog, index, hexv, k=20)
        top_de.append(np.mean([h.delta_e for h in hits]))
        valid = np.flatnonzero(np.isfinite(de))
        rand_de.append(float(np.mean(de[RNG.sample(list(valid), 20)])))

    bank = bank_for(embedder)
    lifts = []
    for style in RNG.sample(STYLE_WORDS, 6):
        hexv = "#{:02x}{:02x}{:02x}".format(*COLOR_NAMES[RNG.choice(names)])
        scores = bank.score(catalog.matrix, phrases_for([style]))
        norm = scores.normalized()
        mood = color_search(catalog, index, hexv, k=20, color_weight=0.5, style=scores)
        color_only = color_search(catalog, index, hexv, k=20)
        lifts.append((np.mean([norm[h.row] for h in mood]), np.mean([norm[h.row] for h in color_only])))
    return [
        "## 4. Color search and the mood picker",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Mean CIEDE2000 of the top 20 color-search results ({len(names)} named colors) | **{np.mean(top_de):.1f}** |",
        f"| Mean CIEDE2000 of 20 random items | {np.mean(rand_de):.1f} |",
        f"| Mood picker: style match of the top 20 vs. color-only ranking (6 aesthetics) | **{np.mean([a for a, _ in lifts]):.2f}** vs {np.mean([b for _, b in lifts]):.2f} |",
        "",
        "Delta E reading: under 10 looks like the same color at a glance; over 25 is clearly different. "
        "Each result's Delta E includes a small penalty when the matching color covers little of the garment.",
        "",
    ]


# --- 5. Duplicates -----------------------------------------------------------------------------


def _jpeg(im: Image.Image, q: int) -> Image.Image:
    b = io.BytesIO()
    im.save(b, format="JPEG", quality=q)
    b.seek(0)
    return Image.open(b).convert("RGB")


TRANSFORMS = {
    "resized 50%": lambda im: im.resize((im.width // 2, im.height // 2)),
    "JPEG quality 20": lambda im: _jpeg(im, 20),
    "color-shifted": lambda im: ImageEnhance.Color(ImageEnhance.Brightness(im).enhance(1.25)).enhance(0.6),
    "cropped 5%/side": lambda im: im.crop((int(im.width * 0.05), int(im.height * 0.05), int(im.width * 0.95), int(im.height * 0.95))),
}


def eval_duplicates(catalog, embedder, settings, n: int) -> list[str]:  # type: ignore[no-untyped-def]
    from app.services.color import delta_e_2000, dominant_colors
    from app.services.color_families import main_lab
    from app.services.reposts import (
        MAX_MAIN_COLOR_DE, MIN_CLIP_SIMILARITY, REPOST_THRESHOLD, STRICT_PHASH, STRICT_TIER_CLIP,
        hamming, hashes_to_uint64, is_duplicate, phash_hex,
    )

    catalog_labs = main_lab(catalog.items)

    rows = RNG.sample(range(len(catalog.items)), n)
    lines = [
        "## 5. Repost detection (pHash + CLIP must agree)",
        "",
        f"Known duplicates: {n} catalog photos × {len(TRANSFORMS)} edits. Rule: (pHash ≤ {REPOST_THRESHOLD} bits and CLIP ≥ {MIN_CLIP_SIMILARITY}) "
        f"or (pHash ≤ {STRICT_PHASH} and CLIP ≥ {STRICT_TIER_CLIP} and main colors within Delta E {MAX_MAIN_COLOR_DE:g}).",
        "",
        "| Edit | Recall | pHash-only recall |",
        "|---|---|---|",
    ]
    all_hits = []
    for name, fn in TRANSFORMS.items():
        edited, originals = [], []
        for r in rows:
            with Image.open(settings.images_dir / catalog.items[r]["image_file"]) as im:
                edited.append(fn(im.convert("RGB")))
                originals.append(r)
        vecs = np.concatenate([embedder.embed_images(edited[i : i + 50]) for i in range(0, len(edited), 50)])
        both = phash_only = 0
        for img, r, v in zip(edited, originals, vecs):
            d = int(hamming(*hashes_to_uint64([phash_hex(img), catalog.items[r]["phash"]])))
            phash_only += d <= REPOST_THRESHOLD
            colors = dominant_colors(img)
            de = float(delta_e_2000(np.array(max(colors, key=lambda c: c["weight"])["lab"]), catalog_labs[r])) if colors else np.inf
            both += bool(is_duplicate(np.array([d]), np.array([float(catalog.matrix[r] @ v)]), np.array([de]))[0])
        all_hits.append(both / n)
        lines.append(f"| {name} | {pct(both / n)} | {pct(phash_only / n)} |")

    h = hashes_to_uint64([i["phash"] for i in catalog.items])
    pairs = [(RNG.randrange(len(h)), RNG.randrange(len(h))) for _ in range(50000)]
    pairs = [(a, b) for a, b in pairs if a != b and catalog.items[b]["id"] not in catalog.reposts.group_members(catalog.items[a]["id"])]
    A = np.array([a for a, _ in pairs])
    B = np.array([b for _, b in pairs])
    bits = hamming(h[A], h[B])
    cos = (catalog.matrix[A] * catalog.matrix[B]).sum(1)
    de = np.where(np.isnan(catalog_labs[A, 0]) | np.isnan(catalog_labs[B, 0]), np.inf, delta_e_2000(np.nan_to_num(catalog_labs[A]), np.nan_to_num(catalog_labs[B])))
    false_pos = int(is_duplicate(bits, cos, de).sum())
    groups = [[catalog.get(i)["category"] for i in g] for g in catalog.reposts.groups]
    lines += [
        "",
        f"False matches among {len(pairs):,} random pairs of *different* photos: **{false_pos}**.",
        f"Duplicate groups found in the whole catalog: **{len(groups)}** ({', '.join('/'.join(g) for g in groups)}), each checked by eye to be the same photo.",
        "",
        f"Overall recall across edits: **{pct(np.mean(all_hits))}**. Precision on random pairs: {'100%' if false_pos == 0 else pct(1 - false_pos / max(1, false_pos + sum(all_hits)))}.",
        "",
    ]
    return lines


# --- 6. Trips ----------------------------------------------------------------------------------

SLOT_LABELS = ["beach dinner", "museum day", "hiking", "night out", "brunch", "city walk", "wedding", "airport travel", "boat trip", "picnic"]


def eval_trips(catalog, embedder, n: int) -> list[str]:  # type: ignore[no-untyped-def]
    from app.services.trip_planner import COLD_C, HOT_C, RAIN_LIKELY, SANDAL_SIMILARITY, plan_slot

    sandal = embedder.embed_texts(["open-toe sandals"])[0]
    checks = Counter()
    totals = Counter()
    for _ in range(n):
        taste = catalog.matrix[RNG.sample(range(len(catalog.items)), 5)].mean(0)
        taste /= np.linalg.norm(taste)
        label = RNG.choice(SLOT_LABELS)
        cold = plan_slot(catalog, embedder, taste, label, COLD_C - 7, RAIN_LIKELY + 0.3)
        totals["cold"] += 1
        checks["cold: has outerwear"] += any(s.role == "outerwear" for s in cold)
        checks["cold: no shorts"] += all(s.hit.item["category"] != "Shorts" for s in cold)
        rows = [catalog._row_by_id[s.hit.item["id"]] for s in cold if s.role == "shoes"]
        checks["rain: no open-toe shoes"] += all(float(catalog.matrix[r] @ sandal) < SANDAL_SIMILARITY for r in rows)
        hot = plan_slot(catalog, embedder, taste, label, HOT_C + 3, 0.0)
        checks["hot: no outerwear"] += all(s.hit.item["category"] not in {"Outwear", "Blazer"} for s in hot)
        checks["hot: bottoms are shorts/skirts"] += all(s.hit.item["category"] in {"Shorts", "Skirt"} for s in hot if s.role == "bottoms")
        checks["no kids' items"] += all(not s.hit.item["kids"] for s in cold + hot)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_trips.py", "-k", "viewer or revoked or unpublished or requires"],
        cwd=REPO / "backend", capture_output=True, text=True,
    )
    summary = (result.stdout.strip().splitlines() or ["(no output)"])[-1]
    lines = [
        "## 6. Trip planner weather rules and permissions",
        "",
        f"{n} random group tastes × random events, each planned for a cold rainy day ({COLD_C - 7:.0f}°C, {RAIN_LIKELY + 0.3:.0%} rain) and a hot dry day ({HOT_C + 3:.0f}°C).",
        "",
        "| Rule | Pass rate |",
        "|---|---|",
    ]
    for rule, ok in checks.items():
        lines.append(f"| {rule} | {pct(ok / totals['cold'])} |")
    lines += ["", f"Permission tests (viewer can't edit, revoked/expired links fail, unpublished page 404s, sign-up required): `{summary}`", ""]
    return lines


# --- 7. Labels ---------------------------------------------------------------------------------


def eval_labels() -> list[str]:
    from app.services.provenance import assess

    handset = REPO / "evals" / "labels_handset"
    expected_by_folder = {"ai": "ai_generated", "human": "human_verified", "other": "unknown"}
    real = [(p, expected_by_folder[p.parent.name]) for p in handset.glob("*/*") if p.parent.name in expected_by_folder and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".heic"}]
    lines = ["## 7. AI labels", ""]
    if real:
        results = [(exp, assess(p.read_bytes(), "image/jpeg" if p.suffix.lower() in {".jpg", ".jpeg"} else f"image/{p.suffix[1:].lower()}").label) for p, exp in real]
        lines += [f"Hand-labeled set: {len(real)} files. Accuracy **{pct(np.mean([e == g for e, g in results]))}**; "
                  f"{sum(g == 'unknown' for _, g in results)} landed in Unknown.", ""]
    else:
        lines += ["No hand-labeled files in `evals/labels_handset/` (optional in the light version). Using generated test files instead:", ""]
    sys.path.insert(0, str(REPO / "backend"))
    from tests.c2pa_fixtures import iptc_xmp, jpeg_bytes, sign_jpeg

    cases = {
        "C2PA signed, AI source": (lambda: sign_jpeg(jpeg_bytes(), "trainedAlgorithmicMedia"), "ai_generated"),
        "C2PA signed, camera capture": (lambda: sign_jpeg(jpeg_bytes(), "digitalCapture"), "human_verified"),
        "C2PA tampered after signing": (lambda: _tamper(sign_jpeg(jpeg_bytes(), "trainedAlgorithmicMedia")), "unknown"),
        "IPTC AI tag": (lambda: jpeg_bytes(xmp=iptc_xmp("trainedAlgorithmicMedia")), "ai_generated"),
        "IPTC camera claim (unsigned)": (lambda: jpeg_bytes(xmp=iptc_xmp("digitalCapture")), "unknown"),
        "No metadata": (lambda: jpeg_bytes(), "unknown"),
    }
    lines += ["| Case | Expected | Got |", "|---|---|---|"]
    for name, (make, expected) in cases.items():
        got = assess(make(), "image/jpeg").label
        lines.append(f"| {name} | {expected} | {'✅ ' if got == expected else '❌ '}{got} |")
    return lines + ["", "Catalog: all 5,163 photos are Unknown (the dataset has no metadata at all).", ""]


def _tamper(data: bytes) -> bytes:
    b = bytearray(data)
    b[-200] ^= 0xFF
    return bytes(b)


# --- 8. Assistant ------------------------------------------------------------------------------


def eval_agent(catalog) -> list[str]:  # type: ignore[no-untyped-def]
    import urllib.request

    import yaml

    settings = get_settings()
    try:
        tags = json.load(urllib.request.urlopen(f"{settings.ollama_host}/api/tags", timeout=3))
        models = {m["name"] for m in tags.get("models", [])}
    except Exception:
        models = set()
    if settings.agent_model not in models:
        return ["## 8. Assistant", "", f"**Skipped**: Ollama isn't running with `{settings.agent_model}` pulled. Run `make models`, then `make eval` again. (Not faked.)", ""]

    from fastapi.testclient import TestClient

    from app.deps import get_catalog
    from app.main import app

    app.dependency_overrides[get_catalog] = lambda: catalog
    client = TestClient(app)
    prompts = yaml.safe_load((REPO / "evals" / "agent_prompts.yaml").read_text())
    by_cat: dict[str, list[str]] = defaultdict(list)
    for i in catalog.items:
        by_cat[i["category"]].append(i["id"])
    rows, passes = [], 0
    for case in prompts:
        context = [RNG.choice(by_cat[c]) for c in case.get("context_items", [])] or ([RNG.choice(by_cat[case["context_item"]])] if case.get("context_item") else [])
        t = time.time()
        body = client.post("/assistant/chat", json={"message": case["prompt"], "context_item_ids": context}).text
        events = [(blk.split("\n")[0][7:], json.loads(blk.split("\n", 1)[1][6:])) for blk in body.strip().split("\n\n") if blk.startswith("event:")]
        done = next((d for e, d in events if e == "done"), None)
        if done is None:
            rows.append(f"| {case['prompt']} | error | ❌ |")
            continue
        used = set(done["tools_used"])
        expect = set(case["expect_tools"])
        tools_ok = (not used) if not expect else bool(used & expect)
        ids_ok = all(catalog.get(i["id"]) is not None for i in done["items"])
        invented = len(done["removed_ids"])
        extra_ok = (not done["items"]) if case.get("expect_no_items") else True
        text_ok = not any(s.lower() in done["text"].lower() for s in case.get("must_not_contain", []))
        ok = tools_ok and ids_ok and extra_ok and text_ok
        passes += ok
        rows.append(f"| {case['prompt']} | {', '.join(sorted(used)) or 'none'} | {len(done['items'])} | {invented} | {time.time() - t:.0f}s | {'✅' if ok else '❌'} |")
    app.dependency_overrides.clear()
    return [
        "## 8. Assistant (15 prompts)",
        "",
        f"Model `{settings.agent_model}` via Ollama. A prompt passes when the expected tools ran (or none, for off-topic), every shown item exists, "
        "and no forbidden text (prices) appears. \"Stripped\" = cited IDs the grounding check removed because no tool returned them.",
        "",
        f"**{passes}/{len(prompts)} passed.**",
        "",
        "| Prompt | Tools called | Items shown | Stripped | Time | Pass |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]


# --- main --------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="smaller samples")
    args = parser.parse_args()
    n = 150 if args.quick else 500

    from app.services.catalog import Catalog

    settings = get_settings()
    catalog = Catalog.load(settings.index_dir)
    embedder = ProcessEmbedder(settings.model_dir)
    started = time.time()
    lines = [
        f"# MoodBoards eval report ({date.today().isoformat()})",
        "",
        f"Catalog: {len(catalog.items):,} items. Generated by `make eval` ({'quick' if args.quick else 'full'} run). Random seed 7.",
        "",
    ]
    lines += eval_retrieval(catalog, n)
    lines += eval_relevance(catalog, embedder)
    board_lines, _ = eval_boards(catalog, n // 5)
    lines += board_lines
    lines += eval_color(catalog, embedder)
    lines += eval_duplicates(catalog, embedder, settings, n // 5)
    lines += eval_trips(catalog, embedder, n // 10)
    lines += eval_labels()
    lines += eval_agent(catalog)
    embedder.close()
    lines += [f"_Ran in {time.time() - started:.0f}s._", ""]

    out_dir = REPO / "evals" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    (out_dir / f"{date.today().isoformat()}.md").write_text(text)
    (out_dir / "latest.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
