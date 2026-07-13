"""Unit tests for the pure ESP validation-run test-vector runner (post-V1 R8, doc 09 §11.1).

No DB/infra: exercises ``run_resolver_validation`` over the deterministic engine compute
(``compute_resolver_series``). Proves a real vector match -> ``passed``, a mismatch or a
non-executable key -> ``failed`` (fail-closed, doc 09 §7), and a repaint flag -> ``warning``.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.indicators import compute_resolver_series
from entropia.domain.esp.validation import run_resolver_validation
from entropia.domain.package.enums import PackageValidationState

_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}


_SERIES_KW = {"high": "highs", "low": "lows", "volume": "volumes"}


def _expected(key: str, length: int, closes: list[int], **series: list[int]) -> list[str | None]:
    """Build a vector's expected column FROM the engine compute (self-consistent).

    ``series`` uses the vector's singular field names (``high``/``low``/``volume``) and is
    mapped to ``compute_resolver_series``' plural keyword args."""
    kwargs = {_SERIES_KW[k]: [Decimal(x) for x in v] for k, v in series.items()}
    out = compute_resolver_series(key, length, [Decimal(c) for c in closes], **kwargs)
    return [None if v is None else str(v) for v in out]


def test_matching_sma_vector_passes() -> None:
    closes = [1, 2, 3, 4, 5]
    evidence = {
        "test_vectors": [
            {
                "name": "sma3",
                "length": 3,
                "close": closes,
                "expected": _expected("ta.sma", 3, closes),
            }
        ]
    }
    report = run_resolver_validation(canonical_key="ta.sma", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.PASSED
    assert report.vectors_run == 1
    names = {c.name for c in report.checks}
    assert names == {"contract_schema", "test_vectors", "timing_integrity"}


def test_mismatched_vector_fails_with_index_detail() -> None:
    evidence = {
        "test_vectors": [
            {"length": 3, "close": [1, 2, 3, 4, 5], "expected": [None, None, 2, 3, 99]}
        ]
    }
    report = run_resolver_validation(canonical_key="ta.sma", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.FAILED
    tv = next(c for c in report.checks if c.name == "test_vectors")
    assert "index 4" in tv.detail


def test_within_tolerance_passes() -> None:
    # Expected off by 1e-12, tolerance 1e-9 -> still passes.
    evidence = {
        "test_vectors": [
            {
                "length": 3,
                "close": [1, 2, 3],
                "expected": [None, None, "2.000000000001"],
                "tolerance": "1e-9",
            }
        ]
    }
    report = run_resolver_validation(canonical_key="ta.sma", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.PASSED


def test_warmup_shape_mismatch_fails() -> None:
    # Expected a value where the resolver is still warming up (None) -> mismatch.
    evidence = {"test_vectors": [{"length": 3, "close": [1, 2, 3], "expected": [1, 2, 2]}]}
    report = run_resolver_validation(canonical_key="ta.sma", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.FAILED


def test_rsi_vector_passes() -> None:
    closes = [10, 11, 12, 11, 13, 14, 13, 15]
    evidence = {
        "test_vectors": [{"length": 3, "close": closes, "expected": _expected("ta.rsi", 3, closes)}]
    }
    report = run_resolver_validation(canonical_key="ta.rsi", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.PASSED


def test_vwap_vector_with_volume_passes() -> None:
    closes = [10, 11, 12, 13]
    highs = [11, 12, 13, 14]
    lows = [9, 10, 11, 12]
    volumes = [100, 200, 150, 300]
    expected = _expected("ta.vwap", 2, closes, high=highs, low=lows, volume=volumes)
    evidence = {
        "test_vectors": [
            {
                "length": 2,
                "close": closes,
                "high": highs,
                "low": lows,
                "volume": volumes,
                "expected": expected,
            }
        ]
    }
    report = run_resolver_validation(canonical_key="ta.vwap", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.PASSED


def test_non_executable_key_fails_closed() -> None:
    # ta.atr has no directional series compute -> a run cannot certify it (doc 09 §7).
    evidence = {"test_vectors": [{"length": 3, "close": [1, 2, 3], "expected": [None, None, 2]}]}
    report = run_resolver_validation(canonical_key="ta.atr", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.FAILED
    tv = next(c for c in report.checks if c.name == "test_vectors")
    assert "No executable compute" in tv.detail


def test_placeholder_string_vectors_cannot_pass() -> None:
    # The old seed evidence shape carried non-executable STRING labels — presence is not
    # a pass (doc 09 §7 "a successful one-off sample is not sufficient evidence").
    evidence = {"test_vectors": ["warmup", "boundary", "normal"], "review": "passed"}
    report = run_resolver_validation(canonical_key="ta.sma", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.FAILED


def test_empty_and_missing_evidence_fail() -> None:
    for evidence in (None, {}, {"test_vectors": []}):
        report = run_resolver_validation(canonical_key="ta.sma", signature=_SIG, evidence=evidence)
        assert report.status == PackageValidationState.FAILED


def test_malformed_vector_fails() -> None:
    evidence = {"test_vectors": [{"close": [1, 2, 3], "expected": [None, None, 2]}]}  # no length
    report = run_resolver_validation(canonical_key="ta.sma", signature=_SIG, evidence=evidence)
    assert report.status == PackageValidationState.FAILED


def test_invalid_signature_fails_contract_schema() -> None:
    evidence = {
        "test_vectors": [
            {"length": 3, "close": [1, 2, 3], "expected": _expected("ta.sma", 3, [1, 2, 3])}
        ]
    }
    report = run_resolver_validation(
        canonical_key="ta.sma", signature={"params": []}, evidence=evidence
    )
    assert report.status == PackageValidationState.FAILED
    schema = next(c for c in report.checks if c.name == "contract_schema")
    assert schema.status == PackageValidationState.FAILED


def test_repaint_flag_warns_and_blocks_pass() -> None:
    closes = [1, 2, 3, 4, 5]
    evidence = {
        "test_vectors": [{"length": 3, "close": closes, "expected": _expected("ta.sma", 3, closes)}]
    }
    report = run_resolver_validation(
        canonical_key="ta.sma", signature=_SIG, evidence=evidence, repaint=True
    )
    # A repaint resolver's vectors still match, but timing integrity WARNS -> not PASSED,
    # so the activation gate (requires PASSED) blocks it (doc 09 §4.2 future-leak/repaint).
    assert report.status == PackageValidationState.WARNING
