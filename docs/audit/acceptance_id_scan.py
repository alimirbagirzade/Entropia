#!/usr/bin/env python3
"""I-17 — acceptance-ID traceability scanner.

Reads every ``# NN. Acceptance Tests`` table in ``docs/spec/`` and reports, per
page, which acceptance IDs are referenced from a TEST file and which are not.

A referenced ID is a traceability claim, not proof of coverage: it says a test
names the ID. An unreferenced ID does NOT mean the behaviour is untested — it
means nothing in the suite says so.

Only TEST files count (``backend/tests/**/*.py`` and ``frontend/src/**/*.test.*``).
Production-source comments are deliberately excluded: a tag in ``lib/tradeLog.ts``
documents the implementation, it does not evidence a test.

Usage (from the repo root):  python3 docs/audit/acceptance_id_scan.py
Exit code is 0 always; this is a report, not a gate.

SUPERSEDED AS A COVERAGE MEASURE.  A test file containing the string ``PC-19``
satisfies this scan even when the ID appears only in a docstring, so its number
measures *citation*, not coverage.  The gate that measures coverage is
``acceptance_semantic_scan.py`` + ``acceptance_semantic_map.yaml``: it names the
test node that asserts each clause and fails CI when that node stops existing.
This script is kept because the two answer different questions — read its output
as "which IDs are cited anywhere", never as "which behaviour is tested".
"""

from __future__ import annotations

import glob
import os
import re
from collections import Counter

SPEC_GLOB = "docs/spec/{n}_*.md"
ID_RE = re.compile(r"<td>([A-Z]{2,4}-\d{2})\b")
HEADING_RE = re.compile(r"^#+ *\d+\. *Acceptance Tests", re.M)


def spec_ids() -> dict[str, tuple[str, list[str], str]]:
    """page number -> (prefix, ordered ids, spec filename)."""
    out: dict[str, tuple[str, list[str], str]] = {}
    for n in ("%02d" % i for i in range(1, 23)):
        matches = glob.glob(SPEC_GLOB.format(n=n))
        if not matches:
            continue
        text = open(matches[0], encoding="utf-8").read()
        heading = HEADING_RE.search(text)
        if heading is None:
            continue
        found = ID_RE.findall(text[heading.start() :])
        ordered: list[str] = []
        for item in found:
            if item not in ordered:
                ordered.append(item)
        if not ordered:
            continue
        prefix = Counter(i.split("-")[0] for i in ordered).most_common(1)[0][0]
        out[n] = (prefix, [i for i in ordered if i.startswith(prefix + "-")], os.path.basename(matches[0]))
    return out


def test_blobs() -> list[tuple[str, str]]:
    paths: list[str] = []
    for root, _, names in os.walk("backend/tests"):
        paths += [os.path.join(root, f) for f in names if f.endswith(".py")]
    for root, _, names in os.walk("frontend/src"):
        paths += [os.path.join(root, f) for f in names if ".test." in f]
    return [(p, open(p, encoding="utf-8", errors="ignore").read()) for p in paths]


def main() -> None:
    specs, blobs = spec_ids(), test_blobs()
    total = tagged = 0
    print(f"scanned {len(blobs)} test files\n")
    for page, (prefix, ids, _fn) in specs.items():
        hit = [i for i in ids if any(i in body for _p, body in blobs)]
        miss = [i for i in ids if i not in hit]
        total += len(ids)
        tagged += len(hit)
        tail = f"  MISSING: {', '.join(miss)}" if miss else "  COMPLETE"
        print(f"doc {page} [{prefix}] {len(hit)}/{len(ids)}{tail}")
    print(f"\nGLOBAL {tagged}/{total} ({100 * tagged // total}%)  untraced={total - tagged}")
    print("\nNOTE: docs 06, 08 and 09 have NO ID column in their acceptance tables and")
    print("are therefore invisible to this scan. See acceptance_id_map.md §C.")


if __name__ == "__main__":
    main()
