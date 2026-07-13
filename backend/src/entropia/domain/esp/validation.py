"""ESP resolver validation-run — deterministic test-vector execution (post-V1 R8, doc 09 §11.1).

GAP-07c fixed the inversion where ``activate_resolver`` fabricated a PASSED validation
state; it left the gate at evidence *presence* only (doc 09 §7: "a successful one-off
sample is not sufficient evidence for activation"). This module lands the missing
plane: a pure, deterministic runner that actually EXECUTES a resolver's stored
test-vectors against the real engine compute and reports a terminal
``PackageValidationState`` (``passed`` / ``warning`` / ``failed``). The application
command persists a run row + moves ``revision.validation_state``; the activation gate
then requires ``passed`` (not mere presence), so registry trust and Pre-Check
resolvability (``resolver.py`` already requires ``validation_state == passed``) finally
agree.

The runner is PURE (no I/O): same evidence + same compute -> byte-identical report. It
reuses ``indicators.compute_resolver_series`` so what is validated is EXACTLY the math
the backtest engine runs — never a divergent second implementation.

Test-vector evidence schema (``contract.evidence``)::

    {
      "test_vectors": [
        {
          "name": "sma_len3_normal",       # optional label
          "length": 3,                       # look-back (int > 0), REQUIRED
          "close": [1, 2, 3, 4, 5],          # input close series, REQUIRED
          "expected": [null, null, 2, 3, 4], # per-bar expected output (null = warm-up)
          "high": [...], "low": [...],       # VWAP only (typical price weighting)
          "volume": [...],                   # VWAP only
          "tolerance": "0.000001"            # optional abs tolerance (default 1e-9)
        }
      ]
    }

Honest boundary: only ``VALIDATABLE_RESOLVER_KEYS`` (the MA family, ``ta.rsi``,
``ta.vwap``) have executable compute; ``ta.atr`` / ``cond.*`` cannot be validated by
this runner and so a run over them yields ``failed`` (fail-closed) — a documented V1
limit, not a silent pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from entropia.domain.backtest.indicators import (
    VALIDATABLE_RESOLVER_KEYS,
    compute_resolver_series,
)
from entropia.domain.package.enums import PackageValidationState

# Bumping this shifts the validation contract namespace (like ENGINE_VERSION): a report
# produced by an older validator version is not silently treated as current.
VALIDATOR_VERSION = "esp-validation-v1"

_DEFAULT_TOLERANCE = Decimal("1e-9")

# Worst-wins aggregation across per-layer checks (doc 09 §11.1).
_RANK: dict[PackageValidationState, int] = {
    PackageValidationState.PASSED: 0,
    PackageValidationState.WARNING: 1,
    PackageValidationState.FAILED: 2,
}


@dataclass(frozen=True, slots=True)
class ResolverCheck:
    """One validation layer's outcome (doc 09 §11.1 rows)."""

    name: str
    status: PackageValidationState
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": str(self.status), "detail": self.detail}


@dataclass(frozen=True, slots=True)
class ResolverValidationReport:
    """The terminal result of a validation-run: overall status + per-check breakdown."""

    status: PackageValidationState
    checks: tuple[ResolverCheck, ...]
    vectors_run: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "validator_version": VALIDATOR_VERSION,
            "status": str(self.status),
            "vectors_run": self.vectors_run,
            "checks": [c.as_dict() for c in self.checks],
        }


def _worst(statuses: list[PackageValidationState]) -> PackageValidationState:
    return max(statuses, key=lambda s: _RANK[s]) if statuses else PackageValidationState.FAILED


def _to_decimal(value: Any) -> Decimal | None:
    """Coerce a JSON scalar to Decimal; ``None`` stays ``None`` (warm-up marker)."""
    if value is None:
        return None
    return Decimal(str(value))


def _check_contract_schema(signature: dict[str, Any]) -> ResolverCheck:
    if not isinstance(signature, dict) or not signature.get("params") or "return" not in signature:
        return ResolverCheck(
            "contract_schema",
            PackageValidationState.FAILED,
            "Signature must define non-empty params and a return shape.",
        )
    return ResolverCheck("contract_schema", PackageValidationState.PASSED, "Signature well-formed.")


def _extract_vectors(evidence: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return the well-formed test-vector dicts (drops non-dict / string placeholders)."""
    if not isinstance(evidence, dict):
        return []
    raw = evidence.get("test_vectors")
    if not isinstance(raw, list):
        return []
    return [v for v in raw if isinstance(v, dict)]


def _run_one_vector(canonical_key: str, vector: dict[str, Any]) -> str | None:
    """Execute one vector; return ``None`` on pass or a failure detail string."""
    length = vector.get("length")
    closes_raw = vector.get("close")
    expected_raw = vector.get("expected")
    if not isinstance(length, int) or length <= 0:
        return "length must be a positive integer"
    if not isinstance(closes_raw, list) or not isinstance(expected_raw, list):
        return "close and expected must be lists"
    if len(closes_raw) != len(expected_raw):
        return "close and expected lengths differ"
    try:
        closes = [_to_decimal(x) for x in closes_raw]
        highs = _decimal_list(vector.get("high"))
        lows = _decimal_list(vector.get("low"))
        volumes = _decimal_list(vector.get("volume"))
        expected = [_to_decimal(x) for x in expected_raw]
        tolerance = _tolerance_of(vector)
    except (InvalidOperation, ValueError):
        return "non-numeric value in vector"
    if any(c is None for c in closes):
        return "close series may not contain null"
    computed = compute_resolver_series(
        canonical_key,
        length,
        [c for c in closes if c is not None],
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    return _diff_series(computed, expected, tolerance)


def _decimal_list(raw: Any) -> list[Decimal] | None:
    if not isinstance(raw, list):
        return None
    out = [_to_decimal(x) for x in raw]
    return [x for x in out if x is not None]


def _tolerance_of(vector: dict[str, Any]) -> Decimal:
    raw = vector.get("tolerance")
    return abs(Decimal(str(raw))) if raw is not None else _DEFAULT_TOLERANCE


def _diff_series(
    computed: list[Decimal | None], expected: list[Decimal | None], tolerance: Decimal
) -> str | None:
    """Compare computed vs expected element-wise; ``None`` must align exactly."""
    for i, (got, want) in enumerate(zip(computed, expected, strict=True)):
        if want is None or got is None:
            if got is not want and (got is None) != (want is None):
                return f"index {i}: warm-up mismatch (got {got}, expected {want})"
            continue
        if abs(got - want) > tolerance:
            return f"index {i}: {got} != {want} (tol {tolerance})"
    return None


def _check_test_vectors(canonical_key: str, vectors: list[dict[str, Any]]) -> ResolverCheck:
    if canonical_key not in VALIDATABLE_RESOLVER_KEYS:
        return ResolverCheck(
            "test_vectors",
            PackageValidationState.FAILED,
            f"No executable compute for '{canonical_key}'; cannot certify test vectors.",
        )
    if not vectors:
        return ResolverCheck(
            "test_vectors",
            PackageValidationState.FAILED,
            "No executable test vectors present.",
        )
    for idx, vector in enumerate(vectors):
        failure = _run_one_vector(canonical_key, vector)
        if failure is not None:
            label = vector.get("name") or f"#{idx}"
            return ResolverCheck(
                "test_vectors",
                PackageValidationState.FAILED,
                f"Vector {label} failed: {failure}",
            )
    return ResolverCheck(
        "test_vectors",
        PackageValidationState.PASSED,
        f"All {len(vectors)} test vectors passed.",
    )


def _check_timing_integrity(repaint: bool) -> ResolverCheck:
    if repaint:
        return ResolverCheck(
            "timing_integrity",
            PackageValidationState.WARNING,
            "Resolver is flagged repaint; timing/future-leak risk blocks trusted activation.",
        )
    return ResolverCheck("timing_integrity", PackageValidationState.PASSED, "No repaint flag.")


def run_resolver_validation(
    *,
    canonical_key: str,
    signature: dict[str, Any],
    evidence: dict[str, Any] | None,
    repaint: bool = False,
) -> ResolverValidationReport:
    """Execute a resolver's test-vectors and return the terminal validation report.

    Layers (doc 09 §11.1): contract schema -> test-vector execution -> timing integrity.
    Overall status is the worst layer status (any FAILED -> failed; any WARNING -> warning;
    else passed). A resolver with no executable vectors fails closed (doc 09 §7)."""
    vectors = _extract_vectors(evidence)
    checks = [
        _check_contract_schema(signature),
        _check_test_vectors(canonical_key, vectors),
        _check_timing_integrity(repaint),
    ]
    overall = _worst([c.status for c in checks])
    return ResolverValidationReport(status=overall, checks=tuple(checks), vectors_run=len(vectors))


__all__ = [
    "VALIDATOR_VERSION",
    "ResolverCheck",
    "ResolverValidationReport",
    "run_resolver_validation",
]
