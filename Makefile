.PHONY: help install test lint format run frontend-build docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend + frontend dependencies
	uv sync --extra dev
	cd frontend && npm install

test: ## Run the backend test suite
	uv run python -m pytest -q

lint: ## Lint the Python sources
	uv run ruff check src tests

format: ## Auto-format the Python sources
	uv run ruff format src tests

run: ## Run the API server (reload)
	uv run uvicorn src.api.main:app --reload --port 8000

frontend-build: ## Build the frontend
	cd frontend && npm run build

docker-up: ## Start the full stack with Docker Compose
	docker compose up --build -d

docker-down: ## Stop the Docker Compose stack
	docker compose down

clean: ## Remove local caches and build output
	rm -rf .pytest_cache .ruff_cache frontend/dist
	find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
