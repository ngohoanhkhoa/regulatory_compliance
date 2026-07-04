FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

# Copy source + README (referenced by pyproject.toml)
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY tests/ ./tests/
COPY README.md ./README.md

# Pre-download embedding model is not viable in the image (size); it downloads
# on first ingestion. The corpus CSV must be mounted at runtime.

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]