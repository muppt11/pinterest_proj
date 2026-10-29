#!/usr/bin/env bash
# Push the current commit to a Hugging Face Space (Docker SDK), adding the Space config header to the
# README only in the pushed copy, so the GitHub README stays clean.
# Usage: scripts/deploy_hf.sh <hf-username>/<space-name>
# Needs a Hugging Face write token: run `hf auth login` (or set HF_TOKEN) first.
set -euo pipefail
SPACE="${1:?usage: scripts/deploy_hf.sh <hf-username>/<space-name>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git -C "$ROOT" archive HEAD | tar -x -C "$WORK"
{
  printf -- '---\ntitle: MoodBoards\nemoji: 📌\ncolorFrom: red\ncolorTo: gray\nsdk: docker\napp_port: 7860\npinned: false\nshort_description: Board-level taste, color search, and group trip outfit planning\n---\n\n'
  cat "$WORK/README.md"
} > "$WORK/README.hf.md" && mv "$WORK/README.hf.md" "$WORK/README.md"

cd "$WORK"
git init -q -b main
git add -A
git commit -q -m "Deploy $(git -C "$ROOT" rev-parse --short HEAD)"
REMOTE="https://huggingface.co/spaces/$SPACE"
if [ -n "${HF_TOKEN:-}" ]; then REMOTE="https://user:${HF_TOKEN}@huggingface.co/spaces/$SPACE"; fi
git push --force "$REMOTE" main
echo "Pushed. The Space builds at https://huggingface.co/spaces/$SPACE (about 15-25 minutes the first time)."
