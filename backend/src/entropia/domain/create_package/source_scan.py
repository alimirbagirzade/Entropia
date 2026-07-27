"""Pre-Check source-code call scanner (doc 07 §6.2, §12; PC-05/PC-06).

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

**Fail-closed accounting (doc 07 §12 ``PARSE_UNSUPPORTED``).** Silently stepping
over a character the lexer does not understand is the dangerous failure mode: a
binary blob, a truncated export or a foreign grammar would yield *zero* detected
calls, reconcile cleanly against an empty declared list and reach ``Passed`` — a
green result produced by a scanner that never understood the file. So every
code-region character is classified, and the scan reports whether safe extraction
was possible at all:

* an unterminated string / block comment means the tail of the file was swallowed
  as non-code and may hide real calls — unconditionally unsupported,
* a share of unrecognized characters above ``_MAX_UNRECOGNIZED_RATIO`` (with a
  small absolute floor so a single stray byte in a short snippet is not fatal)
  means the body is not the lexical surface this scanner parses.

The caller turns either condition into ``PARSE_UNSUPPORTED`` — Failed / manual
review, never ``Passed``. Characters inside comments and string literals are NOT
classified: prose, unicode and punctuation are legitimate there.

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
# the ENGINE_VERSION / GENERATOR_VERSION namespace-shift convention). 2.0 adds
# the unrecognized-token accounting that produces PARSE_UNSUPPORTED.
SOURCE_SCANNER_VERSION = "source-lexer-2.0"

# Structured ``unsupported_reason`` values (persisted as scan evidence).
UNTERMINATED_STRING = "unterminated_string"
UNTERMINATED_BLOCK_COMMENT = "unterminated_block_comment"
UNRECOGNIZED_TOKEN_RATIO = "unrecognized_token_ratio"

# Punctuation the PineScript/Python lexical surface is built from. Anything that
# is neither alphanumeric (unicode identifiers included — a Turkish variable name
# is legitimate code), an underscore, whitespace nor one of these is a character
# this scanner cannot account for.
_CODE_PUNCTUATION = frozenset("()[]{}<>,.;:+-*/%=!&|^~?@#$\\'\"`")

# A body is unsupported when BOTH hold: enough unrecognized characters that this
# cannot be a stray byte, and a share of them above the ratio. The floor keeps a
# short, legitimate snippet from failing on one odd character.
_MIN_UNRECOGNIZED_CHARS = 3
_MAX_UNRECOGNIZED_RATIO = 0.10

_NAMESPACES: tuple[str, ...] = tuple(ns.rstrip(".") for ns in SCANNED_NAMESPACES)


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _is_recognized_code_char(ch: str) -> bool:
    """True when ``ch`` belongs to the lexical surface this scanner parses."""
    return ch.isalnum() or ch == "_" or ch in _CODE_PUNCTUATION


def is_scannable_key(key: str) -> bool:
    """True when ``key`` belongs to a namespace the scanner can detect in source."""
    return any(key.startswith(ns) for ns in SCANNED_NAMESPACES)


@dataclass(frozen=True, slots=True)
class SourceScanResult:
    """The calls found as real call nodes, plus whether extraction was safe.

    ``calls`` is the ordered, de-duplicated canonical call set. The accounting
    fields describe the *lexer's own confidence*: ``code_chars`` counts
    non-whitespace characters seen outside comments/strings, of which
    ``unrecognized_chars`` were not classifiable, and ``unterminated_region``
    names a non-code region that ran to EOF.
    """

    calls: tuple[str, ...]
    code_chars: int = 0
    unrecognized_chars: int = 0
    unterminated_region: str | None = None

    @property
    def unrecognized_ratio(self) -> float:
        """Share of code characters the lexer could not account for (0.0 if empty)."""
        return self.unrecognized_chars / self.code_chars if self.code_chars else 0.0

    @property
    def unsupported_reason(self) -> str | None:
        """The structured reason safe extraction was impossible, else ``None``."""
        if self.unterminated_region is not None:
            return self.unterminated_region
        if (
            self.unrecognized_chars >= _MIN_UNRECOGNIZED_CHARS
            and self.unrecognized_ratio > _MAX_UNRECOGNIZED_RATIO
        ):
            return UNRECOGNIZED_TOKEN_RATIO
        return None

    @property
    def is_parse_unsupported(self) -> bool:
        """True when the caller must raise PARSE_UNSUPPORTED instead of a verdict."""
        return self.unsupported_reason is not None

    def as_evidence(self) -> dict[str, object]:
        """The scan-evidence payload persisted alongside a PARSE_UNSUPPORTED result."""
        return {
            "reason": self.unsupported_reason,
            "code_chars": self.code_chars,
            "unrecognized_chars": self.unrecognized_chars,
            "unrecognized_ratio": round(self.unrecognized_ratio, 4),
            "scanner_version": SOURCE_SCANNER_VERSION,
        }


def scan_source_calls(source: str) -> SourceScanResult:
    """Extract semantic ``ta.*`` / ``cond.*`` call nodes from ``source``.

    Comments and string literals are skipped by a small state machine, so a
    call token that only appears inside them is never reported. The result
    preserves first-seen order and reports each canonical key at most once, and
    carries the accounting the caller needs to decide PARSE_UNSUPPORTED.
    """
    calls: list[str] = []
    seen: set[str] = set()
    code_chars = 0
    unrecognized_chars = 0
    unterminated: str | None = None
    length = len(source)
    i = 0
    while i < length:
        ch = source[i]

        # --- Non-code regions -------------------------------------------------
        if ch == "/" and i + 1 < length and source[i + 1] == "/":
            i = _skip_line_comment(source, i + 2)
            continue
        if ch == "/" and i + 1 < length and source[i + 1] == "*":
            i, closed = _skip_block_comment(source, i + 2)
            if not closed and unterminated is None:
                unterminated = UNTERMINATED_BLOCK_COMMENT
            continue
        if ch == '"' or ch == "'":
            i, closed = _skip_string(source, i + 1, ch)
            if not closed and unterminated is None:
                unterminated = UNTERMINATED_STRING
            continue

        # --- Candidate call node ---------------------------------------------
        matched = _match_call(source, i)
        if matched is not None:
            key, end = matched
            if key not in seen:
                seen.add(key)
                calls.append(key)
            code_chars += end - i
            i = end
            continue

        # --- Plain code character --------------------------------------------
        if not ch.isspace():
            code_chars += 1
            if not _is_recognized_code_char(ch):
                unrecognized_chars += 1
        i += 1

    return SourceScanResult(
        calls=tuple(calls),
        code_chars=code_chars,
        unrecognized_chars=unrecognized_chars,
        unterminated_region=unterminated,
    )


def _skip_line_comment(source: str, i: int) -> int:
    length = len(source)
    while i < length and source[i] != "\n":
        i += 1
    return i


def _skip_block_comment(source: str, i: int) -> tuple[int, bool]:
    """Advance past a ``/* */`` block. Returns ``(index, closed)``."""
    length = len(source)
    while i < length:
        if source[i] == "*" and i + 1 < length and source[i + 1] == "/":
            return i + 2, True
        i += 1
    return length, False


def _skip_string(source: str, i: int, quote: str) -> tuple[int, bool]:
    """Advance past a string literal. Returns ``(index, closed)``."""
    length = len(source)
    while i < length:
        ch = source[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1, True
        i += 1
    return length, False


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
