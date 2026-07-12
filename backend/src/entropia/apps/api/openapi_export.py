"""Deterministic OpenAPI schema export + drift guard (GAP-19).

The committed snapshot at ``docs/openapi.json`` is regenerated from the live
FastAPI app and diffed in CI. Any intentional change to the HTTP surface must
regenerate it (``make openapi``), which makes the API change reviewable in the
pull-request diff instead of drifting silently.

Generation is database-free: ``create_app().openapi()`` builds the schema from
route/model metadata and never triggers the ``lifespan`` startup (which is what
opens I/O). So this runs in CI with no Postgres service and no network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from entropia.apps.api.main import create_app

_REPO_MARKER = Path("backend") / "pyproject.toml"


def _find_repo_root() -> Path:
    """Walk up from this module to the repo root (dir holding backend/pyproject.toml).

    Robust to both an editable install (``__file__`` under ``backend/src/...``)
    and being run from any working directory. Raises loudly rather than writing
    the snapshot to the wrong place if the layout is unexpected.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / _REPO_MARKER).is_file():
            return parent
    raise RuntimeError(
        "Could not locate the repo root (no ancestor contains "
        f"{_REPO_MARKER}); is the package installed editable?"
    )


SNAPSHOT_PATH = _find_repo_root() / "docs" / "openapi.json"


def generate_schema() -> dict[str, Any]:
    """Return the app's OpenAPI schema — no running server or database required."""
    return create_app().openapi()


def render_schema(schema: dict[str, Any]) -> str:
    """Render the schema to deterministic JSON (sorted keys, trailing newline).

    Key order is not semantically meaningful in OpenAPI, so sorting guarantees a
    stable, minimal diff regardless of route registration order.
    """
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_snapshot(path: Path = SNAPSHOT_PATH) -> Path:
    path.write_text(render_schema(generate_schema()), encoding="utf-8", newline="\n")
    return path


def _check(path: Path = SNAPSHOT_PATH) -> int:
    rendered = render_schema(generate_schema())
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current == rendered:
        print(f"OpenAPI snapshot is up to date: {path}")
        return 0
    print(
        "OpenAPI snapshot is STALE. The HTTP surface changed but "
        f"{path.name} was not regenerated.\n"
        "Run `make openapi` and commit docs/openapi.json.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed snapshot is stale (do not write).",
    )
    args = parser.parse_args(argv)
    if args.check:
        return _check()
    written = write_snapshot()
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
