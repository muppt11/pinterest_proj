.PHONY: help setup models index dev backend frontend test test-backend test-frontend eval

help: ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install backend (uv, Python 3.11) and frontend (npm) dependencies
	cd backend && uv sync --python 3.11
	cd frontend && npm install

models: ## Pull the local Ollama models used by the assistant
	ollama pull qwen3:8b
	ollama pull qwen2.5vl:7b

index: ## Download the dataset and build embeddings, FAISS index, and metadata (feature 1)
	python3 scripts/download_dataset.py
	cd backend && uv run python ../scripts/build_index.py

backend: ## Run the FastAPI dev server on :8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend: ## Run the Vite dev server on :5173
	cd frontend && npm run dev

dev: ## Run backend and frontend together (Ctrl-C stops both)
	$(MAKE) -j2 backend frontend

test-backend: ## pytest
	cd backend && uv run pytest -q

test-frontend: ## Vitest
	cd frontend && npm test

test: test-backend test-frontend ## Run all tests

eval: ## Run evals and write a markdown report to evals/reports/ (feature 10)
	cd backend && uv run python ../evals/run_evals.py
