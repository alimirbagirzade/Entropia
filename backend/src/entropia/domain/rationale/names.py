"""Family name + metadata normalization and validation (doc 10 §5, §10.1, §13.6).

Pure functions, applied identically on every create/revise path (server is the
authority; client validation is advisory). Display name keeps its original case
but is trimmed + internal-whitespace-collapsed; ``normalized_name`` is the
casefolded form used for case-insensitive uniqueness. Subfamilies / compatible
output types are advisory string lists (≤100 items, each ≤160 visible chars).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from entropia.shared.errors import (
    RationaleFamilyInvalidText,
    RationaleFamilyMetadataLimit,
    RationaleFamilyNameRequired,
    RationaleFamilyNameTooLong,
)

NAME_MIN_LEN = 2
NAME_MAX_LEN = 120
METADATA_MAX_ITEMS = 100
METADATA_ITEM_MAX_LEN = 160

_WHITESPACE = re.compile(r"\s+")


def _has_control_chars(value: str) -> bool:
    """True if any character is a control/format/surrogate codepoint (doc 10 §10.1
    "Invalid text"). Ordinary whitespace is collapsed before this check runs."""
    return any(unicodedata.category(ch) in {"Cc", "Cf", "Cs"} for ch in value)


def _collapse(value: str) -> str:
    """Trim and collapse internal whitespace runs to a single space."""
    return _WHITESPACE.sub(" ", value).strip()


def clean_display_name(raw: str) -> str:
    """Validate + normalize a family display name (2-120 visible chars).

    Raises the precise typed error (doc 10 §10.1): blank -> NAME_REQUIRED, too
    long -> NAME_TOO_LONG, control characters -> INVALID_TEXT.
    """
    collapsed = _collapse(raw)
    if not collapsed:
        raise RationaleFamilyNameRequired()
    if _has_control_chars(collapsed):
        raise RationaleFamilyInvalidText()
    length = len(collapsed)
    if length < NAME_MIN_LEN:
        raise RationaleFamilyNameRequired(
            f"A Rationale Family name must be at least {NAME_MIN_LEN} characters."
        )
    if length > NAME_MAX_LEN:
        raise RationaleFamilyNameTooLong()
    return collapsed


def normalized_name(display_name: str) -> str:
    """Casefolded, whitespace-collapsed key for case-insensitive uniqueness."""
    return _collapse(display_name).casefold()


def clean_metadata_list(items: Iterable[str] | None) -> list[str]:
    """Normalize an advisory string list (subfamilies / compatible output types).

    Trims each item and drops empties; rejects control characters (INVALID_TEXT)
    and enforces the count/length caps (METADATA_LIMIT). A blank input is a valid
    empty list (doc 10 §5 "Blank is valid empty list").
    """
    if items is None:
        return []
    cleaned: list[str] = []
    for item in items:
        value = _collapse(item)
        if not value:
            continue
        if _has_control_chars(value):
            raise RationaleFamilyInvalidText()
        if len(value) > METADATA_ITEM_MAX_LEN:
            raise RationaleFamilyMetadataLimit(
                f"Each list item must be at most {METADATA_ITEM_MAX_LEN} characters."
            )
        cleaned.append(value)
    if len(cleaned) > METADATA_MAX_ITEMS:
        raise RationaleFamilyMetadataLimit(
            f"A list may contain at most {METADATA_MAX_ITEMS} items."
        )
    return cleaned
