# Entropia V18 backend — single image, many entrypoints (api + worker planes).
#
# Two stages, because `uv` is a BUILD tool and shipping it into the runtime image
# was a security defect rather than merely dead weight. `COPY --from=ghcr.io/
# astral-sh/uv:latest /uv /uvx /bin/` put a statically-linked Rust binary into the
# final layer set, and the scanner reads the crate metadata embedded in that
# binary as if it described installed packages: Trivy reported setuptools 70.3.0
# (CVE-2025-47273) and msgpack 1.1.2 (GHSA-6v7p-g79w-8964) as fixable HIGHs
# against container:backend. Neither version exists anywhere in the filesystem —
# the image carries setuptools 84.0.0 and msgpack 1.2.1 — and both findings came
# back with PkgPath=null, attributed to the uv COPY layer, while `usr/bin/uv` and
# `usr/bin/uvx` were separately listed as `rustbinary` scan targets. That is why
# `uv pip install --upgrade` could not clear them (PR #660 tried it in a later
# layer and again in the same layer): there was no installed package to upgrade.
# The only thing that removes embedded metadata is not shipping the binary.
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_PREFERENCE=only-system \
    PATH="/app/.venv/bin:$PATH"

# uv: fast, reproducible Python dependency management. Build-time only now.
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

# The runtime stage starts from the SAME base as the builder, which is what makes
# copying a prebuilt venv across stages safe: the interpreter that the venv's
# pyvenv.cfg and console-script shebangs point at (/usr/local) is identical here,
# and the builder apt-installs nothing, so there is no system library present
# there and missing here. Every dependency resolves to a manylinux wheel.
FROM python:3.13-slim AS runtime

# UV_* are deliberately absent — nothing in this stage runs uv. PATH still leads
# with the venv, which is how compose's `alembic` / `python` / `uvicorn` commands
# resolve; none of them invokes uv, so dropping the binary moves no entrypoint.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Drop the SYSTEM pip, which is where the two HIGHs actually live. Measured, and
# it is not what PR #660 concluded: the vulnerable metadata is neither installed
# in site-packages nor embedded in the uv binary. `python:3.13-slim` ships pip
# 26.2.1, and pip vendors its own dependencies — `pip/_vendor/vendor.txt` pins
# `msgpack==1.1.2` and `setuptools==70.3.0` verbatim. Trivy's python-pkg analyzer
# parses that file, which is why both findings came back with PkgPath=null: there
# is no dist-info behind them to upgrade. The layer both were attributed to
# (diff_id 71f5bc32…) is the base image's own CPython build layer, not the uv
# COPY — the two happened to sit at the same index, which is what made the uv
# binary look guilty.
#
# Nothing here needs a package installer: the venv on PATH carries no pip, no
# application code imports pip, and all ten compose entrypoints are alembic /
# python / uvicorn. Removing it clears the finding at its source and takes an
# installer out of a production image, which is worth doing on its own.
#
# The last line is the fail-closed half. The `find`s are written to survive a
# Python version bump, but a base image that relocated its prefix would turn
# every `rm` into a silent no-op and quietly hand the findings back; instead the
# build STOPS if any pip vendor manifest survives. Verified by building the guard
# alone on stock python:3.13-slim: it exits 1.
RUN set -eux; \
    find /usr/local/lib -type d -name 'pip' -path '*/site-packages/*' -exec rm -rf {} +; \
    find /usr/local/lib -type d -name 'pip-*.dist-info' -exec rm -rf {} +; \
    find /usr/local/lib -type d -name 'ensurepip' -exec rm -rf {} +; \
    rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*; \
    ! find /usr/local -name 'vendor.txt' -path '*pip*' | grep -q .

WORKDIR /app

# Non-root runtime user, created BEFORE the copy so ownership is applied in the
# same layer instead of duplicating the whole tree with a follow-up `chown -R`.
RUN useradd --create-home --uid 10001 entropia

# /app in one piece: the venv, plus the editable install's absolute path anchor
# (/app/src), alembic.ini and alembic/. The path must not move — an editable
# install records where its source lives, so a copy to a different prefix would
# import nothing.
COPY --from=builder --chown=entropia:entropia /app /app

USER entropia

EXPOSE 8000

# Default command runs the API; compose overrides it for worker planes.
CMD ["uvicorn", "entropia.apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
