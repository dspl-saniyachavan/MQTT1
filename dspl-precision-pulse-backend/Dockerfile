FROM python:3.11-slim

WORKDIR /app

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install production deps from the locked lockfile — no network resolution
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Install the project itself (editable)
RUN uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -f http://localhost:5000/api/internal/health || exit 1

CMD ["python", "run.py"]
