"""Render the canonical capability matrix to its TypeScript mirror (F-05).

``entropia.domain.backtest.capabilities.CAPABILITY_MATRIX`` is the ONE source of truth
for which strategy options this build executes. The Strategy editor needs the same table
to disable ``future_dev`` options, and the frontend cannot import Python — so this script
renders the matrix verbatim into
``frontend/src/lib/engineCapabilityMatrix.generated.ts``.

The generated file is COMMITTED, and ``tests/unit/test_capability_matrix.py`` re-renders it
in memory and asserts byte equality. Drift therefore fails CI instead of shipping a UI that
disagrees with the engine. Regenerate with::

    cd backend && uv run python tools/export_capability_matrix.py

A no-network, no-DB pure function of the matrix — safe to run anywhere.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from entropia.domain.backtest.capabilities import CAPABILITY_MATRIX

_MIRROR_PATH = "frontend/src/lib/engineCapabilityMatrix.generated.ts"
_TARGET = Path(__file__).resolve().parents[2] / _MIRROR_PATH

_HEADER = """// GENERATED FILE — DO NOT EDIT BY HAND.
//
// Rendered from backend/src/entropia/domain/backtest/capabilities.py (the canonical
// machine-readable engine capability matrix, F-05) by:
//
//     cd backend && uv run python tools/export_capability_matrix.py
//
// backend/tests/unit/test_capability_matrix.py re-renders this file and asserts byte
// equality, so editing it here (or changing the Python matrix without regenerating)
// fails CI. The engine fail-closes on every `future_dev` option and Ready Check blocks
// it with STRATEGY_CAPABILITY_NOT_IN_BUILD; this mirror exists so the Strategy editor
// can disable those options BEFORE a user builds a strategy on one.

/** Whether this build actually executes an option value. */
export type CapabilityStatus = "active_v1" | "future_dev";

export interface CapabilityOption {
  /** Canonical dotted path of the option in the saved strategy payload. */
  fieldPath: string;
  /** The saved enum literal (never the human label). */
  value: string;
  /** `active_v1` = executes; `future_dev` = never executes in this build. */
  status: CapabilityStatus;
  /** The V18 surface label, mirrored from the backend matrix. */
  label: string;
  /**
   * For `active_v1`: the extra condition the option needs to run (empty = none).
   * For `future_dev`: WHY it cannot run — the missing data series or model.
   */
  dependency: string;
  /** The Ready Check code that enforces this row. */
  blockerCode: string;
}

export const ENGINE_CAPABILITY_MATRIX: readonly CapabilityOption[] = """

_FOOTER = """;

/** Index for O(1) lookup by `${fieldPath}\\u0000${value}`. */
const BY_FIELD_VALUE = new Map<string, CapabilityOption>(
  ENGINE_CAPABILITY_MATRIX.map((option) => [`${option.fieldPath}\\u0000${option.value}`, option]),
);

/**
 * The matrix row for one option value, or `undefined` when unenumerated.
 *
 * `undefined` means the value is not a capability decision (the field is absent from
 * the matrix because every value executes identically). Callers must treat it as NOT
 * `future_dev`: the matrix enumerates what is gated, never what is permitted.
 */
export function capabilityOption(fieldPath: string, value: string): CapabilityOption | undefined {
  return BY_FIELD_VALUE.get(`${fieldPath}\\u0000${value}`);
}

/** Does this build refuse to execute the given option value? */
export function isFutureDev(fieldPath: string, value: string): boolean {
  return capabilityOption(fieldPath, value)?.status === "future_dev";
}
"""


def render() -> str:
    """The exact expected contents of the generated TS mirror."""
    rows = [
        {
            "fieldPath": option["field_path"],
            "value": option["value"],
            "status": option["status"],
            "label": option["label"],
            "dependency": option["dependency"],
            "blockerCode": option["blocker_code"],
        }
        for option in (asdict(o) for o in CAPABILITY_MATRIX)
    ]
    # indent=2 + a trailing newline keeps the artifact prettier/eslint-stable, so the
    # parity assertion never fails on formatting alone.
    body = json.dumps(rows, indent=2, ensure_ascii=False)
    return f"{_HEADER}{body}{_FOOTER}"


def main() -> int:
    rendered = render()
    if _TARGET.exists() and _TARGET.read_text(encoding="utf-8") == rendered:
        print(f"up to date: {_TARGET}")
        return 0
    _TARGET.write_text(rendered, encoding="utf-8")
    print(f"wrote {len(CAPABILITY_MATRIX)} rows -> {_TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
