# Entropia V18 backend — single image, many entrypoints (api + worker planes).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_PREFERENCE=only-system \
    PATH="/app/.venv/bin:$PATH"

# uv: fast, reproducible Python dependency management.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer) using only the lock inputs.
COPY pyproject.toml README.md ./
RUN uv venv /app/.venv && uv pip install -e .

# Now copy the source and config.
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN uv pip install -e .

# Non-root runtime user.
RUN useradd --create-home --uid 10001 entropia && chown -R entropia /app
USER entropia

EXPOSE 8000

# Default command runs the API; compose overrides it for worker planes.
CMD ["uvicorn", "entropia.apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
