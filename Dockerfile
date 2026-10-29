# MoodBoards for Hugging Face Spaces (Docker SDK). Everything large (dataset, model, index) is
# downloaded and built inside the image, so the git repo stays small.

# --- 1. Build the React app -------------------------------------------------------------------
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Python app ----------------------------------------------------------------------------
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

# Spaces run as uid 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# CPU-only PyTorch (the default Linux wheel pulls ~2 GB of CUDA libraries a free Space can't use),
# then everything else pinned by uv.lock.
COPY --chown=user backend/pyproject.toml backend/uv.lock backend/
RUN cd backend \
    && uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
    && TORCH=$(grep -E '^torch==' /tmp/req.txt | cut -d';' -f1) \
    && grep -vE '^(torch|triton|nvidia-)' /tmp/req.txt > /tmp/req-no-torch.txt \
    && uv venv /home/user/venv \
    && VIRTUAL_ENV=/home/user/venv uv pip install "$TORCH" --index-url https://download.pytorch.org/whl/cpu \
    && VIRTUAL_ENV=/home/user/venv uv pip install -r /tmp/req-no-torch.txt
ENV PATH=/home/user/venv/bin:$PATH

COPY --chown=user backend/ backend/
COPY --chown=user scripts/ scripts/
COPY --chown=user evals/ evals/

# Data: CC0 dataset + Apache-2.0 model (checksum-verified), then the FAISS index.
ENV MOODBOARDS_DATA_DIR=/home/user/app/data
RUN python scripts/download_dataset.py \
    && bash scripts/download_model.sh \
    && cd backend && python ../scripts/build_index.py

COPY --chown=user --from=web /web/dist frontend/dist

# Served over HTTPS by Spaces; the local assistant model isn't available here.
ENV MOODBOARDS_SECURE_COOKIES=1
EXPOSE 7860
WORKDIR /home/user/app/backend
CMD ["uvicorn", "app.serve:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
