"""Unit tests for the Pre-Check source-call lexer (doc 07 §6.2, PC-05/PC-06)."""

from __future__ import annotations

from entropia.domain.create_package.source_scan import (
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
