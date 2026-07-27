"""Unit tests for the Pre-Check source-call lexer (doc 07 §6.2, PC-05/PC-06)."""

from __future__ import annotations

from entropia.domain.create_package.source_scan import (
    UNRECOGNIZED_TOKEN_RATIO,
    UNTERMINATED_BLOCK_COMMENT,
    UNTERMINATED_STRING,
    is_scannable_key,
    scan_source_calls,
)


def _calls(source: str) -> list[str]:
    return list(scan_source_calls(source).calls)


def test_detects_real_ta_call() -> None:
    assert _calls("//@version=5\nx = ta.rsi(close, 14)") == ["ta.rsi"]


def test_detects_condition_call() -> None:
    assert _calls("y = cond.above(a, b)") == ["cond.above"]


def test_call_across_whitespace_before_paren() -> None:
    assert _calls("ta.ema  (close, 20)") == ["ta.ema"]


def test_line_comment_call_is_not_a_dependency() -> None:
    # PC-06: a call token inside a // comment must never become a dependency.
    assert _calls("// uses ta.rsi(close, 14) historically\nz = 1") == []


def test_string_literal_call_is_not_a_dependency() -> None:
    assert _calls('label = "ta.rsi(close, 14)"') == []
    assert _calls("label = 'cond.above(a, b)'") == []


def test_block_comment_call_is_not_a_dependency() -> None:
    assert _calls("/* ta.macd(close) */ w = ta.sma(close, 9)") == ["ta.sma"]


def test_bare_reference_without_paren_is_not_a_call() -> None:
    # A namespace member that is never invoked is not a dependency.
    assert _calls("plot(ta.rsi)") == []


def test_member_access_on_other_identifier_is_not_a_call() -> None:
    # ``myta.rsi(`` is a call on ``myta``, not the ``ta`` namespace.
    assert _calls("myta.rsi(close, 14)") == []
    assert _calls("meta.foo(1)") == []


def test_escaped_quote_inside_string_keeps_string_state() -> None:
    # The closing quote is escaped; the ta.ema after it is still string content.
    assert _calls('s = "a\\" ta.ema(x)"') == []


def test_de_duplicates_and_preserves_first_seen_order() -> None:
    source = "a=ta.ema(x)\nb=ta.rsi(x)\nc=ta.ema(y)"
    assert _calls(source) == ["ta.ema", "ta.rsi"]


def test_ignores_non_scanned_namespaces() -> None:
    assert _calls("math.max(a, b)") == []


def test_call_at_start_of_source() -> None:
    assert _calls("ta.rsi(close)") == ["ta.rsi"]


def test_dotless_or_memberless_namespace_is_not_a_call() -> None:
    assert _calls("ta(close)") == []
    assert _calls("ta.(close)") == []


def test_is_scannable_key() -> None:
    assert is_scannable_key("ta.rsi") is True
    assert is_scannable_key("cond.above") is True
    assert is_scannable_key("math.max") is False


# --- PARSE_UNSUPPORTED accounting (doc 07 §12) -------------------------------


def test_clean_source_is_never_unsupported() -> None:
    """The regression that matters most: a legitimate body must keep producing a
    verdict, not a refusal."""
    result = scan_source_calls("//@version=5\nindicator('rsi')\nx = ta.rsi(close, 14)")
    assert result.is_parse_unsupported is False
    assert result.unsupported_reason is None
    assert result.unrecognized_chars == 0
    assert list(result.calls) == ["ta.rsi"]


def test_binary_garbage_is_parse_unsupported() -> None:
    """A body the lexer cannot account for must refuse, not report an empty call set
    that would reconcile to Passed."""
    result = scan_source_calls("\x00\x01\x02\x7f\x1b[31m\x00\x08\x0b\x0c\x00\x01")
    assert result.is_parse_unsupported is True
    assert result.unsupported_reason == UNRECOGNIZED_TOKEN_RATIO
    assert result.unrecognized_ratio > 0.10
    assert list(result.calls) == []


def test_unterminated_string_is_parse_unsupported() -> None:
    """The exact danger case: the unclosed quote swallows the rest of the file, so the
    real ``ta.rsi`` call below it is never seen — reporting zero calls would be a lie."""
    result = scan_source_calls('//@version=5\nlabel = "unclosed\nta.rsi(close, 14)')
    assert list(result.calls) == []
    assert result.unsupported_reason == UNTERMINATED_STRING
    assert result.is_parse_unsupported is True


def test_unterminated_block_comment_is_parse_unsupported() -> None:
    result = scan_source_calls("/* opened and never closed\nta.rsi(close, 14)")
    assert result.unsupported_reason == UNTERMINATED_BLOCK_COMMENT
    assert list(result.calls) == []


def test_single_stray_character_does_not_trip_the_threshold() -> None:
    """The absolute floor keeps one odd byte in an otherwise valid body from failing
    the scan — the ratio alone would over-trigger on short snippets."""
    result = scan_source_calls("x = ta.rsi(close, 14) § y = 1")
    assert result.unrecognized_chars == 1
    assert result.is_parse_unsupported is False
    assert list(result.calls) == ["ta.rsi"]


def test_unicode_identifiers_and_prose_comments_are_not_unsupported() -> None:
    """Non-ASCII is legitimate: Turkish identifiers are alphanumeric code, and comment
    prose is skipped as a non-code region before classification."""
    result = scan_source_calls("// Türkçe yorum: ğüşiöç\ndeğişken = ta.rsi(close, 14)\n")
    assert result.is_parse_unsupported is False
    assert result.unrecognized_chars == 0
    assert list(result.calls) == ["ta.rsi"]


def test_evidence_payload_carries_the_scanner_contract() -> None:
    evidence = scan_source_calls("\x00\x01\x02\x00\x01\x02").as_evidence()
    assert evidence["reason"] == UNRECOGNIZED_TOKEN_RATIO
    assert evidence["unrecognized_chars"] == 6
    assert evidence["scanner_version"] == "source-lexer-2.0"


def test_empty_source_reports_no_unsupported_reason() -> None:
    # Emptiness is EMPTY_SOURCE's job at request normalization, not the lexer's.
    result = scan_source_calls("")
    assert result.unrecognized_ratio == 0.0
    assert result.is_parse_unsupported is False
