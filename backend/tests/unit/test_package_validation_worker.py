"""Unit tests for the F-13 validation worker's real-fact probes (no DB).

Covers the pure helpers the durable validation worker uses to turn a request into
``ValidationInputs``: the syntax probe (Python ``compile`` + structural lint), and the
native-plan probe (runtime / repaint verdict from the resolved dependency keys).
"""

from __future__ import annotations

from types import SimpleNamespace

from entropia.application.jobs.package_validation import (
    _plan_probe,
    _structural_lint,
    _syntax_probe,
)
from entropia.domain.create_package.enums import SourceKind, SourceLanguage
from entropia.domain.create_package.validation import (
    PLAN_COMPUTABLE,
    PLAN_INCOMPATIBLE,
    PLAN_NOT_A_SIGNAL,
    PLAN_UNRESOLVABLE,
)
from entropia.domain.lifecycle.enums import PackageKind


def _request(**overrides) -> SimpleNamespace:
    base = {
        "source_kind": SourceKind.CODE,
        "source_language": SourceLanguage.PYTHON,
        "request_body": "x = 1\n",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_syntax_probe_python_valid() -> None:
    ok, detail = _syntax_probe(_request(request_body="def f():\n    return 1\n"))
    assert ok is True
    assert "parses" in detail


def test_syntax_probe_python_invalid() -> None:
    ok, detail = _syntax_probe(_request(request_body="def f(:\n    return 1\n"))
    assert ok is False
    assert "syntax error" in detail.lower()


def test_syntax_probe_description_is_not_applicable() -> None:
    ok, detail = _syntax_probe(
        _request(source_kind=SourceKind.DESCRIPTION, request_body="a moving average")
    )
    assert ok is None
    assert "no submitted source" in detail.lower()


def test_syntax_probe_empty_source_fails() -> None:
    ok, _detail = _syntax_probe(_request(request_body="   \n  "))
    assert ok is False


def test_structural_lint_balanced_passes() -> None:
    ok, _detail = _structural_lint("//@version=5\nindicator('rsi')\nta.rsi(close, 14)")
    assert ok is True


def test_structural_lint_unbalanced_fails() -> None:
    ok, detail = _structural_lint("ta.rsi(close, 14")
    assert ok is False
    assert "unclosed" in detail.lower()


def test_syntax_probe_pinescript_uses_structural_lint() -> None:
    ok, _detail = _syntax_probe(
        _request(source_language=SourceLanguage.PINESCRIPT, request_body="plot(close)")
    )
    assert ok is True


def test_plan_probe_directional_signal_with_indicator_is_computable() -> None:
    status, detail, keys = _plan_probe(
        package_kind=PackageKind.INDICATOR,
        output_kind="directional_signal",
        resolved_keys=["ta.rsi"],
    )
    assert status == PLAN_COMPUTABLE
    assert keys == ["ta.rsi"]
    assert "computable" in detail.lower()


def test_plan_probe_directional_signal_without_indicator_is_unresolvable() -> None:
    status, _detail, _keys = _plan_probe(
        package_kind=PackageKind.INDICATOR, output_kind="directional_signal", resolved_keys=[]
    )
    assert status == PLAN_UNRESOLVABLE


def test_plan_probe_directional_signal_with_wrong_category_is_incompatible() -> None:
    status, _detail, _keys = _plan_probe(
        package_kind=PackageKind.INDICATOR,
        output_kind="directional_signal",
        resolved_keys=["cond.above"],
    )
    assert status == PLAN_INCOMPATIBLE


def test_plan_probe_condition_with_condition_dep_is_computable() -> None:
    status, _detail, keys = _plan_probe(
        package_kind=PackageKind.CONDITION,
        output_kind="boolean_condition",
        resolved_keys=["cond.above"],
    )
    assert status == PLAN_COMPUTABLE
    assert keys == ["cond.above"]


def test_plan_probe_embedded_system_is_not_a_signal() -> None:
    status, _detail, _keys = _plan_probe(
        package_kind=PackageKind.EMBEDDED_SYSTEM, output_kind="series", resolved_keys=[]
    )
    assert status == PLAN_NOT_A_SIGNAL
