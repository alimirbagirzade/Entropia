# Entropia V18 backend — single image, many entrypoints (api + worker planes).
FROM python:3.13-slim AS base

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

# Security floor for two HIGH advisories the container scan flags as fixable:
#   setuptools  CVE-2025-47273       path traversal in PackageIndex  -> 78.1.1
#   msgpack     GHSA-6v7p-g79w-8964  OOB read on Unpacker reuse      -> 1.2.1
#
# It lives here, in the image, because that is where the packages live. MEASURED,
# not assumed: `python:3.13-slim` ships NEITHER of them (both imports fail in a
# bare container; only pip is present), and neither appears anywhere in
# backend/uv.lock. They enter through `uv pip install -e .` above, which resolves
# at BUILD TIME rather than from the lock — so there is no pin to raise.
#
# HONEST BOUNDARY: this closes the two advisories, not their cause. While the
# image installs by fresh resolution instead of from the lockfile, tomorrow's
# build can pull in another package the lock never recorded. That structural gap
# is the backend twin of the frontend `npm install` -> `npm ci` fix (ADIM 33) and
# is recorded as its own item rather than being silently absorbed here.
RUN uv pip install --upgrade 'setuptools>=78.1.1' 'msgpack>=1.2.1'

# Non-root runtime user.
RUN useradd --create-home --uid 10001 entropia && chown -R entropia /app
USER entropia

EXPOSE 8000

# Default command runs the API; compose overrides it for worker planes.
CMD ["uvicorn", "entropia.apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
