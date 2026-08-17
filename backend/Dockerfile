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
#
# Digest-pinned for the same reason as trivy and gitleaks in security.yml. Bump
# deliberately. `:latest` still resolved a different uv on every build even after
# the binary stopped being shipped: it no longer moves the image's scan surface,
# but it does move the resolver, and a resolver that changes underneath a build
# is the one input a lockfile cannot pin. The tag is documentation — the digest
# is what Docker verifies — and it names the multi-arch index, not one platform's
# manifest, so amd64 and arm64 still resolve normally.
COPY --from=ghcr.io/astral-sh/uv:0.12.3@sha256:2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc /uv /uvx /bin/

WORKDIR /app

# Install dependencies from the COMMITTED LOCKFILE, not from the `>=x,<y` ranges
# in pyproject.toml. This is the backend twin of the frontend gap ADIM 33 closed
# (`npm install` -> `npm ci`, PR #656): `uv pip install -e .` re-resolved those
# ranges at build time, so two builds a week apart could ship different dependency
# trees from identical source, and uv.lock — which is committed and which the test
# suite runs against — described a tree the image never actually installed.
#
# `--locked`, not `--frozen`. Both install the lock as written; they differ in what
# happens when pyproject.toml and uv.lock disagree. `--frozen` syncs without
# consulting pyproject at all, so a dependency edit that was never re-locked builds
# green and ships a tree that silently predates it. `--locked` asserts the lock
# will remain unchanged and FAILS the build instead — which is the property worth
# having, since a stale lock is exactly the drift this change exists to catch.
#
# Split in two so the dependency layer still caches against the lock inputs alone:
# `--no-install-project` syncs the locked dependencies without needing src/, so
# editing application code does not re-download them. The second sync installs the
# project itself. It stays EDITABLE (uv's default), which is what keeps the runtime
# stage's /app/src anchor valid — a non-editable install would import from
# site-packages and make the COPY of /app/src dead weight.
#
# Extras are not synced, matching `uv pip install -e .`: `dev` is an extra rather
# than a dependency-group, and uv sync installs no extras unless asked. The runtime
# image gets pytest/ruff/mypy exactly as before — that is, not at all.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project

# Now copy the source and config.
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN uv sync --locked

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

# Debian security updates for the base image's own OS packages — the layer the
# scanner reads first, and the one nothing else in this file touched.
# CVE-2026-53615 (integer overflow in libblkid's DOS partition parser) arrived as
# NINE fixable HIGHs at once because the whole util-linux family ships from one
# source package: bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1,
# libuuid1, login, mount, util-linux — all 2.41-5, all fixed in 2.41.5-0+deb13u1.
#
# Measured before writing this, because a scan failure on a PR looks like the PR's
# fault: it is not a property of any branch. A dispatched `security.yml` run
# against plain `main` (600be00) reproduced the identical nine-line list, and that
# same commit's scheduled scan had passed two days earlier — only the advisory data
# moved. The gap is structural: the image inherited whatever Debian packages
# `python:3.13-slim` was baked with and never applied a security update, so every
# future Debian advisory became a release blocker until Docker Hub happened to
# rebuild the tag. That is the actual defect this fixes; the CVE is the symptom.
#
# `upgrade`, not `dist-upgrade`: upgrade never installs a NEW package, so the
# surface can only shrink or stay flat. Unpinned deliberately, and it is the one
# input in this file that SHOULD move — the digests and the lockfile are pinned
# because a resolver changing underneath a build is undetectable, whereas security
# packages that stop moving are the failure mode. Pinning `2.41.5-0+deb13u1` would
# break the build the day Debian supersedes it. What keeps this honest is external
# and already exists: the Trivy allowlist gate fails on any fixable CRITICAL/HIGH,
# so a regression here surfaces in CI rather than by someone re-reading this file.
#
# Runtime stage only. The builder is discarded and never scanned, and it
# apt-installs nothing, so the "same base, no system library present there and
# missing here" symmetry that makes the venv copy safe is untouched: an upgrade
# adds no library the builder stage needed.
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y --no-install-recommends; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

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
