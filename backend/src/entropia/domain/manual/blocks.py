"""Canonical content blocks, source parsers and the search chunker (doc 21
§8.2, §8.3, §9.2, §14).

Raw HTML, raw Markdown or a user-supplied filename is NEVER rendered directly
(the innerHTML ban). Every accepted source — pasted text, TXT, Markdown,
allowlisted HTML — normalizes here into the fixed block model the safe
renderer consumes: heading / paragraph / bullet_list / ordered_list / code /
callout / divider. Any tag outside the allowlist is a ``MANUAL_PARSE_FAILED``
rejection — never a partial publication. The normalized checksum feeds
duplicate detection; the chunker builds the title/heading/content search
projection (doc 21 §9.2, §10).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from entropia.domain.manual.enums import BlockType, ManualSourceType
from entropia.shared.errors import ManualParseFailedError

MAX_TITLE_LENGTH = 200

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_ORDERED_RE = re.compile(r"^\d{1,3}[.)]\s+(.*\S)\s*$")
_BULLET_RE = re.compile(r"^[-*+]\s+(.*\S)\s*$")
_DIVIDER_RE = re.compile(r"^(\*{3,}|-{3,}|_{3,})\s*$")
_FENCE_RE = re.compile(r"^```\s*([\w+-]*)\s*$")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class ContentBlock:
    """One canonical safe-render block (doc 21 §9.2). ``payload`` carries the
    per-type required fields; ``anchor`` is the stable deep-link id (headings)."""

    block_type: BlockType
    payload: dict[str, Any]
    anchor: str | None = None


def _clean(text: str) -> str:
    return " ".join(text.split())


def block_text(block: ContentBlock) -> str:
    """The searchable/visible text of a block ('' for a divider)."""
    payload = block.payload
    if block.block_type in (BlockType.HEADING, BlockType.PARAGRAPH):
        return str(payload.get("text", ""))
    if block.block_type in (BlockType.BULLET_LIST, BlockType.ORDERED_LIST):
        return " ".join(str(item) for item in payload.get("items", []))
    if block.block_type is BlockType.CODE:
        return str(payload.get("code_text", ""))
    if block.block_type is BlockType.CALLOUT:
        title = str(payload.get("title") or "")
        return _clean(f"{title} {payload.get('text', '')}")
    return ""


def has_visible_text(blocks: list[ContentBlock]) -> bool:
    """MANUAL_CONTENT_REQUIRED input: at least one visible text block (doc 21 §10)."""
    return any(block_text(block).strip() for block in blocks)


def normalized_checksum(blocks: list[ContentBlock]) -> str:
    """Deterministic checksum of the normalized block collection (doc 21 §9.1),
    used for MANUAL_DUPLICATE_CONTENT detection against the active stream."""
    canonical = [
        {"t": block.block_type.value, "a": block.anchor, "p": block.payload} for block in blocks
    ]
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# --------------------------------------------------------------------------- #
# Anchors                                                                      #
# --------------------------------------------------------------------------- #


class _AnchorAllocator:
    """Stable, unique, slug-based heading anchors within one revision."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def allocate(self, text: str) -> str:
        base = _SLUG_STRIP_RE.sub("-", text.lower()).strip("-") or "section"
        base = base[:80]
        candidate = base
        suffix = 2
        while candidate in self._used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        self._used.add(candidate)
        return candidate


def _assign_anchors(blocks: list[ContentBlock]) -> list[ContentBlock]:
    allocator = _AnchorAllocator()
    assigned: list[ContentBlock] = []
    for block in blocks:
        if block.block_type is BlockType.HEADING:
            anchor = allocator.allocate(str(block.payload.get("text", "")))
            assigned.append(
                ContentBlock(block_type=block.block_type, payload=block.payload, anchor=anchor)
            )
        else:
            assigned.append(block)
    return assigned


# --------------------------------------------------------------------------- #
# Plain text + Markdown (line-based, deterministic subset)                     #
# --------------------------------------------------------------------------- #


def _parse_lines(raw: str, *, markdown: bool) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    ordered: list[str] = []
    quote: list[str] = []
    code_lines: list[str] | None = None
    code_language: str | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph
        text = _clean(" ".join(paragraph))
        if text:
            blocks.append(ContentBlock(BlockType.PARAGRAPH, {"text": text}))
        paragraph = []

    def flush_lists() -> None:
        nonlocal bullets, ordered
        if bullets:
            blocks.append(ContentBlock(BlockType.BULLET_LIST, {"items": bullets}))
            bullets = []
        if ordered:
            blocks.append(ContentBlock(BlockType.ORDERED_LIST, {"items": ordered}))
            ordered = []

    def flush_quote() -> None:
        nonlocal quote
        text = _clean(" ".join(quote))
        if text:
            blocks.append(
                ContentBlock(BlockType.CALLOUT, {"tone": "note", "title": None, "text": text})
            )
        quote = []

    def flush_all() -> None:
        flush_paragraph()
        flush_lists()
        flush_quote()

    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if code_lines is not None:
            if markdown and _FENCE_RE.match(line):
                blocks.append(
                    ContentBlock(
                        BlockType.CODE,
                        {"code_text": "\n".join(code_lines), "language": code_language},
                    )
                )
                code_lines = None
                code_language = None
            else:
                code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            flush_all()
            continue

        if markdown:
            fence = _FENCE_RE.match(stripped)
            if fence:
                flush_all()
                code_lines = []
                code_language = fence.group(1) or None
                continue
            heading = _HEADING_RE.match(stripped)
            if heading:
                flush_all()
                blocks.append(
                    ContentBlock(
                        BlockType.HEADING,
                        {"level": len(heading.group(1)), "text": _clean(heading.group(2))},
                    )
                )
                continue
            if _DIVIDER_RE.match(stripped):
                flush_all()
                blocks.append(ContentBlock(BlockType.DIVIDER, {}))
                continue
            if stripped.startswith(">"):
                flush_paragraph()
                flush_lists()
                quote.append(stripped.lstrip("> "))
                continue

        bullet = _BULLET_RE.match(stripped)
        if bullet and not _DIVIDER_RE.match(stripped):
            flush_paragraph()
            flush_quote()
            bullets.append(_clean(bullet.group(1)))
            continue
        numbered = _ORDERED_RE.match(stripped)
        if numbered:
            flush_paragraph()
            flush_quote()
            ordered.append(_clean(numbered.group(1)))
            continue

        flush_lists()
        flush_quote()
        paragraph.append(stripped)

    if code_lines is not None:
        # An unterminated fence still publishes deterministically as code.
        blocks.append(
            ContentBlock(
                BlockType.CODE, {"code_text": "\n".join(code_lines), "language": code_language}
            )
        )
    flush_all()
    return _assign_anchors(blocks)


def parse_plain_text(raw: str) -> list[ContentBlock]:
    """Pasted/TXT source: paragraphs + simple lists; no markup semantics."""
    return _parse_lines(raw, markdown=False)


def parse_markdown(raw: str) -> list[ContentBlock]:
    """Markdown subset: ATX headings, fenced code, lists, quotes, dividers."""
    return _parse_lines(raw, markdown=True)


# --------------------------------------------------------------------------- #
# Allowlisted HTML                                                             #
# --------------------------------------------------------------------------- #

_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_CONTAINER_TAGS = frozenset({"html", "body"})
_SKIPPED_SUBTREE_TAGS = frozenset({"head"})
_INLINE_TAGS = frozenset({"strong", "em", "b", "i", "u", "span", "a", "code", "br"})
_VOID_TAGS = frozenset({"br", "hr", "meta", "link"})


class _ManualHTMLParser(HTMLParser):
    """Strict allowlist HTML -> canonical blocks (doc 21 §8.3, §14). Any tag
    outside the allowlist (script, img, iframe, style, table, ...) aborts the
    parse — allowlist violations are rejected, never stripped-and-published."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[ContentBlock] = []
        self._skip_depth = 0
        self._heading_level: int | None = None
        self._pre_depth = 0
        self._quote_depth = 0
        self._list_stack: list[tuple[BlockType, list[str]]] = []
        self._in_item = False
        self._parts: list[str] = []

    # -- text buffers ---------------------------------------------------- #

    def _flush_text(self, block_type: BlockType) -> None:
        text = _clean(" ".join(self._parts))
        self._parts = []
        if not text:
            return
        if block_type is BlockType.HEADING and self._heading_level is not None:
            self.blocks.append(
                ContentBlock(BlockType.HEADING, {"level": self._heading_level, "text": text})
            )
        elif block_type is BlockType.CALLOUT:
            self.blocks.append(
                ContentBlock(BlockType.CALLOUT, {"tone": "note", "title": None, "text": text})
            )
        else:
            self.blocks.append(ContentBlock(BlockType.PARAGRAPH, {"text": text}))

    def _flush_pre(self) -> None:
        code_text = "\n".join(part for part in "".join(self._parts).split("\n")).strip("\n")
        self._parts = []
        if code_text.strip():
            self.blocks.append(
                ContentBlock(BlockType.CODE, {"code_text": code_text, "language": None})
            )

    def _flush_loose_text(self) -> None:
        if self._parts:
            self._flush_text(BlockType.CALLOUT if self._quote_depth else BlockType.PARAGRAPH)

    # -- tag events ------------------------------------------------------ #

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth:
            self._skip_depth += 1 if tag not in _VOID_TAGS else 0
            return
        if tag in _SKIPPED_SUBTREE_TAGS:
            self._flush_loose_text()
            self._skip_depth = 1
            return
        if tag in _CONTAINER_TAGS or tag == "meta" or tag == "link":
            return
        if tag in _HEADING_TAGS:
            self._flush_loose_text()
            self._heading_level = _HEADING_TAGS[tag]
            return
        if tag == "p":
            self._flush_loose_text()
            return
        if tag in ("ul", "ol"):
            self._flush_loose_text()
            kind = BlockType.BULLET_LIST if tag == "ul" else BlockType.ORDERED_LIST
            self._list_stack.append((kind, []))
            return
        if tag == "li":
            self._parts = []
            self._in_item = True
            return
        if tag == "pre":
            self._flush_loose_text()
            self._pre_depth += 1
            return
        if tag == "blockquote":
            self._flush_loose_text()
            self._quote_depth += 1
            return
        if tag == "hr":
            self._flush_loose_text()
            self.blocks.append(ContentBlock(BlockType.DIVIDER, {}))
            return
        if tag == "br":
            self._parts.append(" ")
            return
        if tag in _INLINE_TAGS:
            return
        raise ManualParseFailedError(f"HTML tag '<{tag}>' is not allowed in manual content.")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            if tag not in _VOID_TAGS:
                self._skip_depth -= 1
            return
        if tag in _HEADING_TAGS:
            self._flush_text(BlockType.HEADING)
            self._heading_level = None
            return
        if tag == "p":
            self._flush_text(BlockType.CALLOUT if self._quote_depth else BlockType.PARAGRAPH)
            return
        if tag == "li":
            if self._list_stack:
                item = _clean(" ".join(self._parts))
                if item:
                    self._list_stack[-1][1].append(item)
            self._parts = []
            self._in_item = False
            return
        if tag in ("ul", "ol"):
            if self._list_stack:
                kind, items = self._list_stack.pop()
                if items:
                    self.blocks.append(ContentBlock(kind, {"items": items}))
            return
        if tag == "pre":
            self._pre_depth = max(0, self._pre_depth - 1)
            if self._pre_depth == 0:
                self._flush_pre()
            return
        if tag == "blockquote":
            self._flush_loose_text()
            self._quote_depth = max(0, self._quote_depth - 1)
            return

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._pre_depth:
            self._parts.append(data)
            return
        if data.strip() or self._parts:
            self._parts.append(data)

    def close_and_collect(self) -> list[ContentBlock]:
        self.close()
        self._flush_loose_text()
        return _assign_anchors(self.blocks)


def parse_html(raw: str) -> list[ContentBlock]:
    """Allowlisted HTML -> canonical blocks; violations raise MANUAL_PARSE_FAILED."""
    parser = _ManualHTMLParser()
    try:
        parser.feed(raw)
        return parser.close_and_collect()
    except ManualParseFailedError:
        raise
    except Exception as exc:  # malformed markup the stdlib parser cannot walk
        raise ManualParseFailedError() from exc


_PARSERS = {
    ManualSourceType.BUILT_IN: parse_markdown,
    ManualSourceType.ADDED_TEXT: parse_plain_text,
    ManualSourceType.UPLOADED_TXT: parse_plain_text,
    ManualSourceType.UPLOADED_MARKDOWN: parse_markdown,
    ManualSourceType.UPLOADED_HTML: parse_html,
}


def parse_source(source_type: ManualSourceType, raw: str) -> list[ContentBlock]:
    """Normalize one accepted source into canonical blocks (doc 21 §8.2, §8.3)."""
    return _PARSERS[source_type](raw)


# --------------------------------------------------------------------------- #
# Search chunker (doc 21 §9.2 manual_search_chunk)                             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SearchChunkDraft:
    """One title/heading/content search unit with its deep-link anchor."""

    heading_path: str
    anchor: str
    content_text: str
    block_indexes: tuple[int, ...]


def build_search_chunks(
    title: str, section_anchor: str, blocks: list[ContentBlock]
) -> list[SearchChunkDraft]:
    """Title chunk + one chunk per heading group (preamble included). Search
    must cover titles, headings AND content — never a document-level substring
    filter (doc 21 §8.1, §14)."""
    chunks: list[SearchChunkDraft] = [
        SearchChunkDraft(
            heading_path=title, anchor=section_anchor, content_text=title, block_indexes=()
        )
    ]
    heading_stack: list[tuple[int, str]] = []
    texts: list[str] = []
    indexes: list[int] = []
    anchor = section_anchor

    def flush() -> None:
        nonlocal texts, indexes
        content = _clean(" ".join(texts))
        if content:
            path = " > ".join([title, *(text for _, text in heading_stack)])
            chunks.append(
                SearchChunkDraft(
                    heading_path=path,
                    anchor=anchor,
                    content_text=content,
                    block_indexes=tuple(indexes),
                )
            )
        texts = []
        indexes = []

    for index, block in enumerate(blocks):
        if block.block_type is BlockType.HEADING:
            flush()
            level = int(block.payload.get("level", 1))
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, str(block.payload.get("text", ""))))
            anchor = block.anchor or section_anchor
            texts.append(str(block.payload.get("text", "")))
            indexes.append(index)
            continue
        text = block_text(block)
        if text.strip():
            texts.append(text)
            indexes.append(index)
    flush()
    return chunks


__all__ = [
    "MAX_TITLE_LENGTH",
    "ContentBlock",
    "SearchChunkDraft",
    "block_text",
    "build_search_chunks",
    "has_visible_text",
    "normalized_checksum",
    "parse_html",
    "parse_markdown",
    "parse_plain_text",
    "parse_source",
]
