#!/usr/bin/env bash
# Download Marqo-FashionCLIP (Apache-2.0) into data/models/ with resumable, retried transfers,
# then verify the weights against the SHA-256 that Hugging Face publishes for the file.
# Usage: scripts/download_model.sh [data_dir]
set -euo pipefail

DATA_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)/data}"
DEST="$DATA_DIR/models/marqo-fashionCLIP"
BASE="https://huggingface.co/Marqo/marqo-fashionCLIP/resolve/main"
WEIGHTS="open_clip_model.safetensors"
SHA256="2bd31a2e6ba195c4890941f61ea6ada9dbf242f9c6e5ee27eec8cf13a2dc9ffe"

mkdir -p "$DEST"
curl -fsSL --retry 5 -o "$DEST/open_clip_config.json" "$BASE/open_clip_config.json"

sha256_of() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
verified() { [ -f "$DEST/$WEIGHTS" ] && [ "$(sha256_of "$DEST/$WEIGHTS")" = "$SHA256" ]; }

if verified; then
  echo "Model already downloaded and verified: $DEST"
  exit 0
fi

# -C - resumes from the partial file; --speed-limit/--speed-time abort stalled connections so the loop retries.
for attempt in $(seq 1 100); do
  if curl -fL -C - --speed-limit 1000 --speed-time 30 -o "$DEST/$WEIGHTS.part" "$BASE/$WEIGHTS"; then
    break
  fi
  echo "attempt $attempt stalled at $(du -h "$DEST/$WEIGHTS.part" | cut -f1); retrying"
  sleep 3
done

mv "$DEST/$WEIGHTS.part" "$DEST/$WEIGHTS"
if ! verified; then
  echo "Checksum mismatch; deleting $DEST/$WEIGHTS. Re-run to download again." >&2
  rm -f "$DEST/$WEIGHTS"
  exit 1
fi
echo "Model downloaded and verified: $DEST"
