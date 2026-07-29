"""Trash snapshot redaction + size bound (doc 20 §12, §15).

Doc 20 §12 is unambiguous: *"Snapshot contains redacted/size-bounded data only"*
and *"Never render credentials, secrets, tokens or unnecessary raw artifacts in
Trash detail"*. Until I-09 the detail query returned
``TrashEntry.deletion_snapshot`` / ``dependency_snapshot`` **verbatim** — safe
only by accident, because every writer happened to store a fixed set of scalar
keys. The moment one writer added a field (an upload URL, a provider token, a
raw artifact body) it would have reached the Admin drawer silently.

This module is the single gate, and it is **fail-closed by allowlist**:

* A key in :data:`SNAPSHOT_ALLOWED_KEYS` renders its value. Everything else
  renders :data:`REDACTED` — the key name survives as evidence that a field
  exists, the value never does. A NEW writer field is therefore invisible until
  someone deliberately adds it here, which is the whole point.
* Only JSON scalars pass. A nested dict/list under an allowlisted key is
  unvetted by definition (its inner keys were never reviewed), so it is
  redacted whole rather than walked.
* The result is size-bounded twice: per string value
  (:data:`MAX_VALUE_CHARS`) and per encoded snapshot (``max_bytes``). Anything
  cut sets ``"_truncated": True`` — a bound that hides itself would read as a
  complete snapshot.

Pure and synchronous on purpose: no session, no I/O, no ORM. It redacts what is
**rendered**; the raw column stays intact as restore/preflight evidence
(``queries/trash.py::get_restore_preflight``, ``commands/deletion.py`` still
read the stored snapshot directly).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

#: Placeholder rendered in place of any value this module will not vouch for.
REDACTED = "<redacted>"

#: Marker key set whenever ANY value or key was dropped/cut.
TRUNCATED_KEY = "_truncated"

#: Longest string value rendered before it is cut (chars, not bytes).
MAX_VALUE_CHARS = 512

#: Default encoded ceiling for one rendered snapshot (bytes of compact JSON).
DEFAULT_SNAPSHOT_MAX_BYTES = 16_384

#: Every key the Trash-Entry writers actually store, and nothing else
#: (``commands/deletion.py``, ``manual.py``, ``backtest_run.py``,
#: ``agent_artifact.py``, ``rationale.py``). Adding a snapshot field means
#: adding it HERE too — deliberately, after asking whether an Admin may see it.
SNAPSHOT_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "artifact_status",
        "checkpoint_id",
        "current_revision_id",
        "display_name",
        "domain_lifecycle_state",
        "manifest_hash",
        "run_id",
        "source_task_id",
        "stream_position",
        "title",
        "workspace_entity_id",
    }
)


def _safe_value(value: Any) -> tuple[Any, bool]:
    """Return ``(rendered, was_cut)`` for one allowlisted value.

    Non-scalars are redacted rather than walked: the reviewer approved the KEY,
    not whatever tree a future writer might hang under it.
    """
    if value is None or isinstance(value, bool | int | float):
        return value, False
    if isinstance(value, str):
        if len(value) > MAX_VALUE_CHARS:
            return value[:MAX_VALUE_CHARS], True
        return value, False
    return REDACTED, False


def _encoded_size(payload: Mapping[str, Any]) -> int:
    """Compact-JSON byte length, always measured WITH the truncation marker so
    the returned dict cannot cross ``max_bytes`` once the marker is appended."""
    probe = {**payload, TRUNCATED_KEY: True}
    return len(json.dumps(probe, separators=(",", ":"), default=str).encode("utf-8"))


def redact_snapshot(
    snapshot: Any, *, max_bytes: int = DEFAULT_SNAPSHOT_MAX_BYTES
) -> dict[str, Any]:
    """Render ``snapshot`` for Trash detail: allowlisted, scalar, size-bounded.

    ``snapshot`` is deliberately typed ``Any`` — it comes from a nullable JSONB
    column, so ``None`` and non-object JSON are normal inputs, not errors; both
    yield ``{}``.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if not isinstance(snapshot, Mapping):
        return {}

    rendered: dict[str, Any] = {}
    truncated = False
    for raw_key, value in snapshot.items():
        key = str(raw_key)
        if key == TRUNCATED_KEY:
            # A stored key must never be able to forge (or clear) our marker.
            truncated = True
            continue
        if key not in SNAPSHOT_ALLOWED_KEYS:
            rendered[key] = REDACTED
            continue
        rendered[key], was_cut = _safe_value(value)
        truncated = truncated or was_cut

    while rendered and _encoded_size(rendered) > max_bytes:
        rendered.popitem()
        truncated = True

    if truncated:
        rendered[TRUNCATED_KEY] = True
    return rendered


__all__ = [
    "DEFAULT_SNAPSHOT_MAX_BYTES",
    "MAX_VALUE_CHARS",
    "REDACTED",
    "SNAPSHOT_ALLOWED_KEYS",
    "TRUNCATED_KEY",
    "redact_snapshot",
]
