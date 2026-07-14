"""Pre-Check source-code call scanner (doc 07 §6.2, PC-05/PC-06).

A pure, comment/string-aware tokenizer that extracts *semantic* TA/condition
call nodes from a package's source body — the production requirement that a
declared-dependency echo can never satisfy on its own:

* ``ta.rsi`` / ``cond.above`` inside a ``// comment`` or a string literal is
  **not** a dependency (PC-06: regex-only matching must never drive
  Passed/Blocked).
* ``ta.supertrend(...)`` written as a real call **is** a dependency even when
  the caller forgot to declare it (PC-05/PC-06: the source is the source of
  truth; an undeclared source call must Block).

The scanner recognizes a call as ``<namespace>.<member>`` immediately followed
by ``(`` (optionally across whitespace), where ``<namespace>`` is one of the
scanned namespaces and the match is not preceded by an identifier character
(so ``myta.rsi(`` is not a ``ta`` call). Only ``//`` line comments, ``/* */``
block comments and ``'``/``"`` string literals (with backslash escapes) form
non-code regions — the PineScript lexical surface. ``#`` is deliberately *not*
a comment: in PineScript ``#FF0000`` is a color literal, and swallowing the
rest of that line could hide a real call.

No I/O, no registry access. The command layer reconciles the returned call set
against the declared dependencies (undeclared → Blocker, unused → Warning).
"""

from __future__ import annotations

from dataclasses import dataclass

# Canonical call namespaces the scanner understands. A declared dependency
# whose key does not start with one of these is outside the scanner's reach, so
# the command layer must not raise an "unused declaration" warning for it.
SCANNED_NAMESPACES: tuple[str, ...] = ("ta.", "cond.")

# Scanner semantics identity — bump when the tokenizer's behavior changes so a
# prior scan pinned to the old contract is not treated as equivalent (mirrors
# the ENGINE_VERSION / GENERATOR_VERSION namespace-shift convention).
SOURCE_SCANNER_VERSION = "source-lexer-1.0"

_NAMESPACES: tuple[str, ...] = tuple(ns.rstrip(".") for ns in SCANNED_NAMESPACES)


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def is_scannable_key(key: str) -> bool:
    """True when ``key`` belongs to a namespace the scanner can detect in source."""
    return any(key.startswith(ns) for ns in SCANNED_NAMESPACES)


@dataclass(frozen=True, slots=True)
class SourceScanResult:
    """The ordered, de-duplicated canonical calls found as real call nodes."""

    calls: tuple[str, ...]


def scan_source_calls(source: str) -> SourceScanResult:
    """Extract semantic ``ta.*`` / ``cond.*`` call nodes from ``source``.

    Comments and string literals are skipped by a small state machine, so a
    call token that only appears inside them is never reported. The result
    preserves first-seen order and reports each canonical key at most once.
    """
    calls: list[str] = []
    seen: set[str] = set()
    length = len(source)
    i = 0
    while i < length:
        ch = source[i]

        # --- Non-code regions -------------------------------------------------
        if ch == "/" and i + 1 < length and source[i + 1] == "/":
            i = _skip_line_comment(source, i + 2)
            continue
        if ch == "/" and i + 1 < length and source[i + 1] == "*":
            i = _skip_block_comment(source, i + 2)
            continue
        if ch == '"' or ch == "'":
            i = _skip_string(source, i + 1, ch)
            continue

        # --- Candidate call node ---------------------------------------------
        matched = _match_call(source, i)
        if matched is not None:
            key, end = matched
            if key not in seen:
                seen.add(key)
                calls.append(key)
            i = end
            continue
        i += 1

    return SourceScanResult(calls=tuple(calls))


def _skip_line_comment(source: str, i: int) -> int:
    length = len(source)
    while i < length and source[i] != "\n":
        i += 1
    return i


def _skip_block_comment(source: str, i: int) -> int:
    length = len(source)
    while i < length:
        if source[i] == "*" and i + 1 < length and source[i + 1] == "/":
            return i + 2
        i += 1
    return length


def _skip_string(source: str, i: int, quote: str) -> int:
    length = len(source)
    while i < length:
        ch = source[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1
        i += 1
    return length


def _match_call(source: str, i: int) -> tuple[str, int] | None:
    """If a ``<namespace>.<member>(`` call starts at ``i``, return (key, end)."""
    # The match must begin a fresh identifier — a preceding identifier char
    # means this is a member access on some other name (``myta.rsi``).
    if i > 0 and _is_ident_char(source[i - 1]):
        return None
    length = len(source)
    for ns in _NAMESPACES:
        end = i + len(ns)
        if source[i:end] != ns:
            continue
        if end >= length or source[end] != ".":
            continue
        member_start = end + 1
        j = member_start
        if j >= length or not (source[j].isalpha() or source[j] == "_"):
            continue
        while j < length and _is_ident_char(source[j]):
            j += 1
        member = source[member_start:j]
        # Require the call parenthesis (optionally across whitespace) so a bare
        # ``ta.rsi`` reference without invocation is not a dependency.
        k = j
        while k < length and source[k] in " \t\r\n":
            k += 1
        if k < length and source[k] == "(":
            return f"{ns}.{member}", j
    return None
