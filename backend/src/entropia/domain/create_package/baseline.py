"""Deterministic Create-Package baseline metadata + CSV parse evidence (doc 06
§4.4/§5/§7/§8.3).

A baseline is the external reference an equivalence-claiming package is compared
against (doc 06 cpBaselineInfo): "A file upload alone is not proof of equivalence."
So the baseline carries structured metadata that must reproduce the comparison —
provider, symbol, timeframe, range, timezone, settings and the source revision
context — and the raw CSV must actually parse.

Like ``candidate.py`` / ``validation.py`` this module is PURE (no I/O): the command
supplies the uploaded bytes + submitted metadata and this module derives the parse
report, the missing-metadata list and the equivalence-claim signal. Bumping
``BASELINE_PARSER_VERSION`` shifts the evidence namespace (mirrors VALIDATOR_VERSION).
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass
from typing import Any

from entropia.domain.create_package.enums import CreationMode

# Bumping this shifts the baseline-evidence namespace (mirrors VALIDATOR_VERSION):
# a report produced by an older parser is never silently reused by a newer one.
BASELINE_PARSER_VERSION = "cp-baseline-parse-v1"

# The baseline is an exported reference series — a single CSV file (doc 06 §8.3).
ALLOWED_BASELINE_EXTENSIONS: tuple[str, ...] = (".csv",)

# Metadata a baseline MUST carry to reproduce the equivalence comparison (doc 06
# §4.4 line 536, cpBaselineInfo). A file upload alone is not proof of equivalence.
REQUIRED_BASELINE_METADATA_FIELDS: tuple[str, ...] = (
    "provider",
    "symbol",
    "timeframe",
    "range",
    "timezone",
    "settings",
    "source_revision_context",
)

# Modes whose candidate inherently claims to reproduce/repair/represent existing
# code (doc 06 §4.4 line 535 "translation/repair/equivalence"). Generate From
# Description does NOT auto-claim — its equivalence is opt-in (equivalence_claim).
# Review never publishes a package, so the gate is moot there but captured for
# consistency.
_EQUIVALENCE_CLAIM_MODES: frozenset[CreationMode] = frozenset(
    {
        CreationMode.TRANSLATE_EXISTING_CODE,
        CreationMode.REPAIR_EXISTING_CODE,
        CreationMode.REVIEW_EXISTING_CODE,
    }
)


def resolve_equivalence_claim(mode: CreationMode, explicit: bool | None) -> bool:
    """Resolve whether a request claims equivalence (doc 06 §4.4, §8.3).

    An explicit ``equivalence_claim`` always wins (a Generate From Description
    request may opt IN, a Translate request may opt OUT). Otherwise it is derived
    from the creation mode: translate/repair/review claim equivalence, generate does
    not. This is the signal the mode-aware approval baseline gate reads.
    """
    if explicit is not None:
        return explicit
    return mode in _EQUIVALENCE_CLAIM_MODES


def is_allowed_baseline_file(filename: str | None) -> bool:
    """A baseline upload must be a ``.csv`` file (doc 06 §8.3, FILE_TYPE_NOT_ALLOWED)."""
    if not filename:
        return False
    lowered = filename.strip().lower()
    return lowered.endswith(ALLOWED_BASELINE_EXTENSIONS)


def _is_present(value: Any) -> bool:
    """A metadata field counts as present iff it is a non-empty value."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict | list):
        return len(value) > 0
    return True


def missing_baseline_metadata_fields(metadata: dict[str, Any]) -> list[str]:
    """The required baseline-metadata fields that are absent or empty (doc 06 §4.4).

    Returned in the canonical order; a non-empty result means the parse must reject
    the baseline with BASELINE_METADATA_INVALID (a file upload alone is not proof).
    """
    return [
        field for field in REQUIRED_BASELINE_METADATA_FIELDS if not _is_present(metadata.get(field))
    ]


@dataclass(frozen=True, slots=True)
class BaselineParseReport:
    """Deterministic evidence produced from one uploaded baseline CSV (doc 06 §4.4)."""

    parser_version: str
    is_parseable: bool
    row_count: int
    column_count: int
    columns: list[str]
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_baseline_csv(content: bytes) -> BaselineParseReport:
    """Parse the uploaded baseline CSV into deterministic evidence (doc 06 §4.4).

    ``is_parseable`` is true iff the bytes decode as UTF-8, carry a non-empty header
    row and at least one data row. A non-parseable baseline must be rejected with
    PARSE_FAILED. No I/O — the caller supplies the stored bytes.
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return BaselineParseReport(
            parser_version=BASELINE_PARSER_VERSION,
            is_parseable=False,
            row_count=0,
            column_count=0,
            columns=[],
            detail="The baseline file is not valid UTF-8 text.",
        )
    rows = [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]
    if not rows:
        return BaselineParseReport(
            parser_version=BASELINE_PARSER_VERSION,
            is_parseable=False,
            row_count=0,
            column_count=0,
            columns=[],
            detail="The baseline file has no header or data rows.",
        )
    header = [cell.strip() for cell in rows[0]]
    data_row_count = len(rows) - 1
    is_parseable = data_row_count > 0 and len(header) > 0
    detail = (
        f"Parsed {data_row_count} data row(s) across {len(header)} column(s)."
        if is_parseable
        else "The baseline file has a header but no data rows."
    )
    return BaselineParseReport(
        parser_version=BASELINE_PARSER_VERSION,
        is_parseable=is_parseable,
        row_count=data_row_count,
        column_count=len(header),
        columns=header,
        detail=detail,
    )


__all__ = [
    "ALLOWED_BASELINE_EXTENSIONS",
    "BASELINE_PARSER_VERSION",
    "REQUIRED_BASELINE_METADATA_FIELDS",
    "BaselineParseReport",
    "is_allowed_baseline_file",
    "missing_baseline_metadata_fields",
    "parse_baseline_csv",
    "resolve_equivalence_claim",
]
