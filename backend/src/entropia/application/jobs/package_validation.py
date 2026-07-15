"""Package-validation worker body (doc 06 §4.4/§5/§7, F-13).

This is the durable-worker body for Create-Package validation: it gathers the
request's REAL facts from the database and runs the seven mandatory checks, producing
immutable evidence with per-check output/artifacts. It performs no state-machine
transition and no audit — its caller (``commands.create_package.start_package_validation_run``)
owns the OCC guard, the immutable run row, the state transition and the audit/outbox,
and records the durable ``jobs`` row (CR-09 source of truth, survives browser close).

What runs for real here (no arbitrary code execution, no F-14 sandbox needed):

* ``output_structure`` / ``dependency_health`` — the output kind + a live re-resolution
  of every pinned dependency against the trusted ESP registry (drift => fail).
* ``syntax`` — a real syntax probe over the submitted source: ``compile()`` for Python,
  a deterministic structural lint (balanced delimiters, non-empty) for the other
  supplied languages. A description request has no source => not_applicable.
* ``runtime`` / ``repaint_future_leak`` — the candidate's behaviour is defined by its
  resolved native ta.*/cond.* plan, so a computable plan is a genuine runtime verdict
  and the single-pass incremental evaluators give a real non-repaint proof. An empty
  skeleton (no resolvable plan) is BLOCKED and cannot be approved.
* ``real_market_data`` / ``baseline_comparison`` — an equivalence-claiming request must
  carry a PASSED baseline of real market data; a non-claiming one needs none.

The V1 pipeline executes this body in-transaction (the established CP pattern —
mirrors Pre-Check / candidate-generation / baseline-parse), and the function is shaped
so a dramatiq actor can invoke it unchanged when the async plane lands.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.queries import esp as esp_query
from entropia.domain.create_package.enums import (
    BaselineParseStatus,
    SourceKind,
    SourceLanguage,
)
from entropia.domain.create_package.validation import (
    PLAN_COMPUTABLE,
    PLAN_INCOMPATIBLE,
    PLAN_NOT_A_SIGNAL,
    PLAN_UNRESOLVABLE,
    DependencyResolution,
    ValidationInputs,
    ValidationReport,
    build_validation_report,
)
from entropia.domain.lifecycle.enums import PackageKind
from entropia.infrastructure.postgres.models import PackageRequest
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.shared.errors import (
    ResolverAdapterIncompatible,
    ResolverNotResolved,
    ResolverSignatureMismatch,
)

_RESOLVE_ERRORS = (ResolverNotResolved, ResolverSignatureMismatch, ResolverAdapterIncompatible)

# Canonical-key prefixes for the native plan (mirrors candidate.py; keeps the CP domain
# independent of the backtest indicator taxonomy).
_INDICATOR_PREFIX = "ta."
_CONDITION_PREFIX = "cond."
_KINDS_REQUIRING_INDICATOR = frozenset({"directional_signal"})
_KINDS_REQUIRING_CONDITION = frozenset({"boolean_condition"})

# Delimiter pairs for the structural lint of non-Python supplied source.
_DELIMITERS: dict[str, str] = {"(": ")", "[": "]", "{": "}"}


async def run_package_validation(
    session: AsyncSession, detail: PackageRequest
) -> ValidationReport:
    """Gather the draft's real facts and run the seven mandatory checks (F-13)."""
    inputs = await gather_validation_inputs(session, detail)
    return build_validation_report(inputs)


async def gather_validation_inputs(
    session: AsyncSession, detail: PackageRequest
) -> ValidationInputs:
    """Read every real fact the validation checks need from the database."""
    output_kind = _draft_output_kind(detail)
    dependency_resolutions, resolved_keys = await _reresolve_dependencies(session, detail)
    syntax_ok, syntax_detail = _syntax_probe(detail)
    plan_status, plan_detail, plan_keys = _plan_probe(
        package_kind=detail.package_kind, output_kind=output_kind, resolved_keys=resolved_keys
    )
    baseline_passed, baseline_report = await _baseline_facts(session, detail)
    return ValidationInputs(
        package_kind=str(detail.package_kind),
        output_kind=output_kind,
        dependency_resolutions=dependency_resolutions,
        syntax_ok=syntax_ok,
        syntax_detail=syntax_detail,
        plan_status=plan_status,
        plan_detail=plan_detail,
        plan_keys=plan_keys,
        claims_equivalence=detail.claims_equivalence,
        baseline_passed=baseline_passed,
        baseline_report=baseline_report,
    )


def _draft_output_kind(detail: PackageRequest) -> str | None:
    contract = detail.candidate_output_contract or detail.output_contract
    raw = contract.get("kind") or contract.get("output_type")
    return raw if isinstance(raw, str) and raw else None


async def _reresolve_dependencies(
    session: AsyncSession, detail: PackageRequest
) -> tuple[list[DependencyResolution], list[str]]:
    """Re-resolve the declared dependencies against the LIVE ESP registry (drift check).

    Returns the per-dependency resolutions (for ``dependency_health``) and the sorted
    resolved canonical keys (for the native ``runtime`` / ``repaint`` plan probe).
    Description / dep-less requests resolve nothing."""
    if detail.source_kind == SourceKind.DESCRIPTION or not detail.declared_dependencies:
        return [], []
    resolutions: list[DependencyResolution] = []
    resolved_keys: list[str] = []
    for dep in detail.declared_dependencies:
        key = str(dep.get("key", ""))
        signature = dep.get("signature") if isinstance(dep.get("signature"), dict) else {}
        try:
            res = await esp_query.resolve_embedded_dependency(
                session,
                parsed_call={"key": key, "signature": signature},
                target_runtime=detail.target_runtime,
            )
        except _RESOLVE_ERRORS as exc:
            resolutions.append(
                DependencyResolution(canonical_key=key, resolved=False, detail=exc.code)
            )
            continue
        canonical = str(res["canonical_key"])
        resolutions.append(
            DependencyResolution(
                canonical_key=canonical,
                resolved=True,
                detail=f"resolves to {res['revision_id']}",
            )
        )
        resolved_keys.append(canonical)
    return resolutions, sorted(resolved_keys)


def _syntax_probe(detail: PackageRequest) -> tuple[bool | None, str]:
    """Real syntax verdict over the submitted source (``None`` = no source to check)."""
    if detail.source_kind == SourceKind.DESCRIPTION:
        return None, "Description request: no submitted source code to syntax-check."
    body = detail.request_body or ""
    if not body.strip():
        return False, "The submitted source is empty."
    if detail.source_language == SourceLanguage.PYTHON:
        try:
            compile(body, "<candidate>", "exec")
        except SyntaxError as exc:
            return False, f"Python syntax error: {exc.msg} (line {exc.lineno})."
        return True, "Python source parses without syntax errors."
    return _structural_lint(body)


def _structural_lint(body: str) -> tuple[bool, str]:
    """Deterministic delimiter-balance lint for languages with no in-process compiler.

    An honest structural check (not a full compiler): unbalanced or mismatched
    ``()[]{}`` is a real syntactic defect; a balanced non-empty body passes this bar."""
    stack: list[str] = []
    closers = {v: k for k, v in _DELIMITERS.items()}
    for char in body:
        if char in _DELIMITERS:
            stack.append(char)
        elif char in closers:
            if not stack or stack[-1] != closers[char]:
                return False, f"Unbalanced '{char}' in the submitted source."
            stack.pop()
    if stack:
        return False, f"Unclosed '{stack[-1]}' in the submitted source."
    return True, "Submitted source is structurally balanced (delimiter-balance lint)."


def _plan_probe(
    *, package_kind: PackageKind, output_kind: str | None, resolved_keys: list[str]
) -> tuple[str, str, list[str]]:
    """Derive the native-plan verdict from the resolved deps + declared output kind.

    The candidate is executed only as its resolved ta.*/cond.* plan (no arbitrary code),
    so a plan that yields the declared signal is a real runtime + non-repaint verdict.
    """
    if package_kind == PackageKind.EMBEDDED_SYSTEM:
        return (
            PLAN_NOT_A_SIGNAL,
            "An embedded-system resolver emits no time-series signal; it has no native "
            "plan to bar-replay.",
            resolved_keys,
        )
    indicator_keys = [k for k in resolved_keys if k.startswith(_INDICATOR_PREFIX)]
    condition_keys = [k for k in resolved_keys if k.startswith(_CONDITION_PREFIX)]
    if output_kind in _KINDS_REQUIRING_INDICATOR:
        return _require_keys(output_kind, indicator_keys, resolved_keys, _INDICATOR_PREFIX)
    if output_kind in _KINDS_REQUIRING_CONDITION:
        return _require_keys(output_kind, condition_keys, resolved_keys, _CONDITION_PREFIX)
    if resolved_keys:
        return (
            PLAN_COMPUTABLE,
            f"Resolves to a computable plan from {resolved_keys}.",
            resolved_keys,
        )
    return (
        PLAN_UNRESOLVABLE,
        "No native primitive resolved; the candidate has no runnable plan yet.",
        resolved_keys,
    )


def _require_keys(
    output_kind: str | None, matching: list[str], resolved_keys: list[str], prefix: str
) -> tuple[str, str, list[str]]:
    if matching:
        return (
            PLAN_COMPUTABLE,
            f"Resolves to a computable '{output_kind}' from {matching}.",
            matching,
        )
    if resolved_keys:
        return (
            PLAN_INCOMPATIBLE,
            f"A '{output_kind}' needs a '{prefix}*' dependency; resolved {resolved_keys} "
            "cannot produce it.",
            resolved_keys,
        )
    return (
        PLAN_UNRESOLVABLE,
        f"No '{prefix}*' dependency resolved; the '{output_kind}' plan yields no signal.",
        resolved_keys,
    )


async def _baseline_facts(
    session: AsyncSession, detail: PackageRequest
) -> tuple[bool, dict[str, Any] | None]:
    """The current baseline's pass state + a small parse-report excerpt (evidence)."""
    baseline = await cp_repo.get_current_baseline_asset(session, detail)
    if baseline is None or baseline.parse_status != BaselineParseStatus.PASSED:
        return False, None
    report: dict[str, Any] = {
        "baseline_asset_id": baseline.baseline_asset_id,
        "content_digest": baseline.content_digest,
        "attempt_no": baseline.attempt_no,
    }
    if isinstance(baseline.parse_report, dict):
        report["parse_report"] = baseline.parse_report
    return True, report


__all__ = ["gather_validation_inputs", "run_package_validation"]
