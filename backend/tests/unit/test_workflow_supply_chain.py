"""ADIM 23 — the CI workflows are themselves a supply-chain surface.

Three ways this repository's automation could be turned against it, each of which
was TRUE on ``main`` before this slice and none of which any existing test saw:

* **Inherited token permissions.** A workflow with no ``permissions:`` block runs
  with the repository's DEFAULT token scopes. On a repo created before GitHub
  flipped that default — this one — that is read/write on ``contents``. ``ci.yml``
  resolves and executes third-party package code (``uv sync``, ``npm install``,
  ``pip-audit``) and ``e2e.yml`` boots the entire application and drives it with
  a browser, both while holding a token that could push to ``main``.

* **Mutable third-party action tags.** ``uses: astral-sh/setup-uv@v7`` resolves at
  run time to whatever commit that tag points at *then*. The tag's owner — or
  anyone who compromises them — can repoint it, and the new code executes in a job
  that has already checked the repository out. ``actions/*`` is exempted on
  purpose: it is GitHub's own org, versioned in step with the runner images, and
  pinning it by SHA would fight the runner rather than protect anything.

* **``pull_request_target``.** It runs with the BASE repo's token and secrets while
  the PR's code is available to check out — the standard fork-PR privilege
  escalation. No workflow here uses it, and this test is what keeps it that way.

These read the workflow files, not a doc, so they cannot drift from them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"

# The one org allowed to be referenced by a mutable tag. Everything else — every
# marketplace action, whoever publishes it — must be a 40-hex commit SHA.
_TAG_ALLOWED_OWNERS = frozenset({"actions"})
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_USES_RE = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.MULTILINE)
# An image reference inside a `docker run` line: owner/name, optionally :tag,
# optionally @sha256:digest. Shell variables are skipped by the caller.
_IMAGE_RE = re.compile(
    r"(?<![\w/@:-])([a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._/-]*(?:[:@][\w.:-]+)?)"
)


def _workflow_files() -> list[Path]:
    files = sorted(_WORKFLOW_DIR.glob("*.yml")) + sorted(_WORKFLOW_DIR.glob("*.yaml"))
    assert files, f"no workflows found under {_WORKFLOW_DIR}"
    return files


def _ids(files: list[Path]) -> list[str]:
    return [f.name for f in files]


_FILES = _workflow_files()


@pytest.mark.parametrize("path", _FILES, ids=_ids(_FILES))
def test_every_workflow_declares_explicit_permissions(path: Path) -> None:
    """No workflow may inherit the repository's default token scopes."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "permissions" in doc, (
        f"{path.name} has no top-level `permissions:` block, so it runs with the "
        "repository's DEFAULT token permissions. Declare the minimum it needs "
        "(usually `permissions:\n  contents: read`) and widen per job if required."
    )


@pytest.mark.parametrize("path", _FILES, ids=_ids(_FILES))
def test_top_level_permissions_grant_no_write_scope(path: Path) -> None:
    """Writes are opted into per job, never granted to a whole workflow."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    top = doc["permissions"]
    # `permissions: write-all` / `read-all` are valid YAML scalars, not mappings.
    assert isinstance(top, dict), (
        f"{path.name}: top-level permissions must be a mapping, got {top!r}"
    )
    writable = sorted(scope for scope, level in top.items() if level != "read" and level != "none")
    assert not writable, (
        f"{path.name} grants {writable} to EVERY job. Move the write scope onto the "
        "single job that needs it (see the codeql job in security.yml)."
    )


@pytest.mark.parametrize("path", _FILES, ids=_ids(_FILES))
def test_no_workflow_uses_pull_request_target(path: Path) -> None:
    """`pull_request_target` hands fork-authored code the base repo's secrets."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    # PyYAML parses the bare key `on` as the boolean True (YAML 1.1), so read both.
    triggers = doc.get("on", doc.get(True)) or {}
    names = set(triggers) if isinstance(triggers, dict) else {triggers}
    assert "pull_request_target" not in names, (
        f"{path.name} uses pull_request_target. It runs with the BASE repo's token "
        "and secrets while the fork's code is checkoutable — use `pull_request`."
    )


@pytest.mark.parametrize("path", _FILES, ids=_ids(_FILES))
def test_third_party_actions_are_pinned_to_a_commit_sha(path: Path) -> None:
    unpinned = []
    for ref in _USES_RE.findall(path.read_text(encoding="utf-8")):
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        repo, _, version = ref.partition("@")
        owner = repo.split("/", 1)[0]
        if owner in _TAG_ALLOWED_OWNERS:
            continue
        if not _SHA_RE.match(version):
            unpinned.append(ref)
    assert not unpinned, (
        f"{path.name} references third-party actions by mutable tag: {unpinned}. "
        "Pin each to a 40-character commit SHA with a trailing `# vN` comment."
    )


@pytest.mark.parametrize("path", _FILES, ids=_ids(_FILES))
def test_scanner_images_are_pinned_by_digest(path: Path) -> None:
    """A `docker run` in CI executes that image's code — pin it by digest.

    Scans EVERY line, not just the ones containing `docker run`. The first
    version of this test looked only at `docker run` lines and at lines starting
    with a known registry owner, which made it blind to exactly the shape this
    workflow uses: `security.yml` hoists the scanner into
    `env: TRIVY: aquasec/trivy@sha256:...` and the run steps reference
    `"$TRIVY"`. The env line starts with `TRIVY:`, and the run lines' only
    candidate is the shell variable — so changing the pin to
    `aquasec/trivy:latest` left the suite green. A gate that cannot fail is
    worse than no gate, because it is reported as coverage.

    `uses:` lines are skipped (SHA pinning for actions is the previous test's
    job) EXCEPT `docker://` refs, which really are container images.
    """
    unpinned = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        uses = _USES_RE.match(stripped)
        if uses and not uses.group(1).startswith("docker://"):
            continue
        for candidate in _IMAGE_RE.findall(stripped):
            # Shell variables resolve elsewhere in the file; whatever they expand
            # to is judged at its definition line, which this loop also sees.
            if "$" in candidate:
                continue
            if "@sha256:" in candidate:
                continue
            # A `/`-joined token only counts as an image reference when its last
            # segment carries a `:tag` — that filters out plain paths such as
            # `reports/trivy-backend.json` or `/work/reports/backend-image.tar`.
            if ":" in candidate.rsplit("/", 1)[-1]:
                unpinned.append(candidate)
    assert not unpinned, (
        f"{path.name} references container images by mutable tag: {unpinned}. "
        "Reference them as `owner/name@sha256:<digest>` instead."
    )
