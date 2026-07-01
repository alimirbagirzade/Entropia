"""Admin Panel domain: log-event taxonomy + canonical role-scope matrix (doc 19).

Pure, dependency-free projections used by the Admin-only Panel surface. The Panel
never mutates domain state through these — it reads a role registry, a canonical
policy matrix, and an append-only projection over immutable audit events.
"""

from __future__ import annotations

from entropia.domain.admin_panel.log_taxonomy import (
    ACTOR_TYPE_TO_KIND,
    LOG_EVENT_FAMILIES,
    LOG_SEVERITIES,
    LOGS_CURSOR_NAMESPACE,
    decode_log_cursor,
    encode_log_cursor,
    event_family,
    family_kind_prefixes,
    normalize_actor_type,
    normalize_family,
    normalize_severity,
)
from entropia.domain.admin_panel.role_matrix import ROLE_MATRIX_REVISION, build_role_matrix

__all__ = [
    "ACTOR_TYPE_TO_KIND",
    "LOGS_CURSOR_NAMESPACE",
    "LOG_EVENT_FAMILIES",
    "LOG_SEVERITIES",
    "ROLE_MATRIX_REVISION",
    "build_role_matrix",
    "decode_log_cursor",
    "encode_log_cursor",
    "event_family",
    "family_kind_prefixes",
    "normalize_actor_type",
    "normalize_family",
    "normalize_severity",
]
