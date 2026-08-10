#!/usr/bin/env python3
"""Block a git commit that deletes a `## ` record from the project history docs.

Rationale: three separate docs PRs (#590, #604, and one earlier) were branched
from a stale base and silently removed landed slice records from
docs/PROJECT_HISTORY.md on merge. No CI gate reads docs/, so nothing caught it.
CLAUDE.md prescribes a manual check nobody runs; this is that check, automated.

Compares the about-to-be-committed content of the guarded files against
origin/main and refuses the commit when a `## ` heading present on origin/main
is missing. Escape hatch: ENTROPIA_DOCS_GUARD=off.
"""

import json
import os
import re
import subprocess
import sys

GUARDED_FILES = (
    "docs/PROJECT_HISTORY.md",
    "docs/STAGE2_HANDOFF.md",
)
BASE_REF = "origin/main"
REMOVED_HEADING = re.compile(r"^-(##\s+\S.*)$")
COMMIT_ALL_FLAG = re.compile(r"(?:^|\s)-(?:\w*a\w*)(?:\s|$)|(?:^|\s)--all(?:\s|$)")


def run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(args, capture_output=True, text=True)
    return proc.returncode, proc.stdout


def is_git_commit(command: str) -> bool:
    return re.search(r"(?:^|[;&|]\s*)git\s+(?:-\S+\s+)*commit\b", command) is not None


def removed_headings(compare_worktree: bool) -> list[str]:
    args = ["git", "diff"]
    if not compare_worktree:
        args.append("--cached")
    args += [BASE_REF, "--", *GUARDED_FILES]
    code, out = run(args)
    if code != 0:
        return []
    return [m.group(1) for line in out.splitlines() if (m := REMOVED_HEADING.match(line))]


def main() -> int:
    if os.environ.get("ENTROPIA_DOCS_GUARD") == "off":
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if not is_git_commit(command):
        return 0

    # No base ref (fresh clone, no origin) -> nothing to compare against.
    if run(["git", "rev-parse", "--verify", "--quiet", BASE_REF])[0] != 0:
        return 0

    headings = removed_headings(compare_worktree=bool(COMMIT_ALL_FLAG.search(command)))
    if not headings:
        return 0

    listed = "\n".join(f"    {h}" for h in headings)
    print(
        "docs history guard: this commit removes record headings that exist on "
        f"{BASE_REF}:\n{listed}\n\n"
        "This is the docs-regression pattern from PRs #590 and #604 — a stale base "
        "silently dropping landed slice records. Rebase onto origin/main and re-apply "
        "your edit on top of the current file.\n"
        "If the removal is deliberate, re-run with ENTROPIA_DOCS_GUARD=off.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
