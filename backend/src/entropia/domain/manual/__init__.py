"""User Manual domain (Stage 7a, doc 21).

Root/revision/stream-entry separation with canonical safe-render blocks:
``manual_document`` (permanent identity + baseline flag), immutable
``manual_document_revision`` content versions, ``manual_stream_entry`` rows
that pin each document's unique ``stream_position`` in the continuous reader,
and the title/heading/content search projection. Raw HTML/Markdown is never
rendered directly; every source normalizes through ``blocks``.
"""

from entropia.domain.manual.enums import (
    MANUAL_ENTITY_TYPE,
    BlockType,
    ManualSourceType,
    PublicationState,
    StreamEntryState,
)

__all__ = [
    "MANUAL_ENTITY_TYPE",
    "BlockType",
    "ManualSourceType",
    "PublicationState",
    "StreamEntryState",
]
