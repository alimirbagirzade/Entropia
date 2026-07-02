"""Built-in baseline guide seed (doc 21 §1, §3.3, §9.1).

The baseline ships with the product (``is_baseline=true``), renders FIRST in
the continuous stream and is immutable through the page
(``BASELINE_MANUAL_IMMUTABLE``); updates arrive only via system release /
migration. The prototype's stale wording is corrected here: Trading Signal and
Trade Log are EXTERNAL Mainboard working items, never Package Library types
(doc 21 §3.3 alignment note).

``build_baseline_seed`` is the single content source for BOTH the alembic
seed (migration 0019) and test fixtures, so every environment addresses the
same fixed ids.
"""

from __future__ import annotations

from dataclasses import dataclass

from entropia.domain.manual.blocks import (
    ContentBlock,
    SearchChunkDraft,
    build_search_chunks,
    normalized_checksum,
    parse_markdown,
)
from entropia.domain.manual.enums import (
    BASELINE_DOCUMENT_ID,
    BASELINE_REVISION_ID,
    BASELINE_STREAM_ENTRY_ID,
    BASELINE_STREAM_POSITION,
)
from entropia.domain.manual.stream import section_anchor

BASELINE_TITLE = "Entropia Interface Guide"

# Canonical-corrected baseline text (Markdown master; parsed to safe blocks).
BASELINE_MARKDOWN = """\
# Entropia Interface Guide

Entropia is a research and backtesting workbench. This guide explains the main
pages, the safe usage boundaries and where each decision is actually made.
Manual content is product knowledge; it never overrides a domain policy,
package classification or role permission (those come from the server).

## Mainboard and working items

The Mainboard composes your working items: strategies, trading signals and
trade logs. Trading Signal and Trade Log are external Mainboard working items
imported from outside sources; they are not Package Library package types.
Items pin exact revisions — changing the composition marks earlier readiness
reports as stale.

## Packages and data

The Package Library holds strategy, indicator, condition and embedded-system
packages with immutable revisions and Admin approval. Market Data and Research
Data revisions become usable only after validation and approval; research data
respects event time versus available time so backtests never look ahead.

## Backtesting

Run the Backtest Ready Check before every run. A run executes from a pinned
manifest; results are immutable and appear in Results History only when the
run succeeds. Metrics arrangement changes presentation, never stored values.

## Roles and recovery

Admin manages roles, logs, Trash recovery and manual documents. Deleted
objects move to Trash where an Admin can restore them or request permanent
deletion. Only an Admin can add, upload, revise, remove or restore manual
documents; every role can read and search this manual.
"""


@dataclass(frozen=True, slots=True)
class BaselineSeed:
    """Deterministic baseline rows for the migration seed + tests."""

    document_id: str
    revision_id: str
    stream_entry_id: str
    stream_position: int
    title: str
    blocks: list[ContentBlock]
    chunks: list[SearchChunkDraft]
    checksum: str


def build_baseline_seed() -> BaselineSeed:
    blocks = parse_markdown(BASELINE_MARKDOWN)
    anchor = section_anchor(BASELINE_DOCUMENT_ID)
    return BaselineSeed(
        document_id=BASELINE_DOCUMENT_ID,
        revision_id=BASELINE_REVISION_ID,
        stream_entry_id=BASELINE_STREAM_ENTRY_ID,
        stream_position=BASELINE_STREAM_POSITION,
        title=BASELINE_TITLE,
        blocks=blocks,
        chunks=build_search_chunks(BASELINE_TITLE, anchor, blocks),
        checksum=normalized_checksum(blocks),
    )


__all__ = ["BASELINE_MARKDOWN", "BASELINE_TITLE", "BaselineSeed", "build_baseline_seed"]
