"""F-14 — deterministic candidate generation → a loadable, executable implementation.

Pure unit tests over ``domain/create_package/generator`` and the validation worker's
sandbox executor ``jobs/package_validation._execute_generated``. Prove:

* the generated source is real Python that ``compile()``s and executes in the sandbox
  (empty ``__builtins__``) to a non-empty resolver-loadable plan;
* generation is deterministic (same inputs -> same source + hash) and namespace-shifts
  with ``GENERATOR_VERSION``;
* an empty skeleton (no resolved primitive) is marked non-executable and the sandbox
  blocks it, and a missing / malformed implementation is a non-pass — never a silent
  success (F-14: empty skeletons / hashes without implementation cannot be approved).
"""

from __future__ import annotations

import pytest

from entropia.application.jobs.package_validation import _execute_generated
from entropia.domain.create_package.enums import SourceKind, SourceLanguage
from entropia.domain.create_package.generator import (
    ENTRY_SYMBOL,
    GENERATOR_VERSION,
    generate_candidate,
)
from entropia.domain.create_package.validation import (
    EXEC_ABSENT,
    EXEC_EMPTY,
    EXEC_ERROR,
    EXEC_EXECUTED,
)
from entropia.shared.errors import OutputContractInvalid

_TA_RSI = {
    "canonical_key": "ta.rsi",
    "embedded_revision_id": "pkgrev_1",
    "content_hash": "sha256:a",
}
_TA_EMA = {
    "canonical_key": "ta.ema",
    "embedded_revision_id": "pkgrev_2",
    "content_hash": "sha256:b",
}


def _generate(**overrides):
    kwargs = {
        "request_id": "cpr_1",
        "package_kind": "indicator",
        "source_kind": SourceKind.CODE,
        "output_contract": {"kind": "directional_signal"},
        "resolved_refs": [_TA_RSI, _TA_EMA],
        "source_language": SourceLanguage.PYTHON,
    }
    kwargs.update(overrides)
    return generate_candidate(**kwargs)


def _sandbox_exec(source: str):
    namespace: dict = {"__builtins__": {}}
    exec(compile(source, "<gen>", "exec"), namespace)
    return namespace


def test_generated_source_compiles_and_executes_to_the_plan() -> None:
    gen = _generate()
    impl = gen.implementation
    assert impl.language == str(SourceLanguage.PYTHON)
    assert impl.entry_symbol == ENTRY_SYMBOL
    ns = _sandbox_exec(impl.source)
    plan = ns[ENTRY_SYMBOL]()
    assert plan == {
        "output_kind": "directional_signal",
        "package_kind": "indicator",
        # resolved refs are ordered by canonical key inside the manifest.
        "primitives": ["ta.ema", "ta.rsi"],
    }
    assert impl.executable is True
    assert impl.test_source  # a real, compile-able test draft
    compile(impl.test_source, "<test>", "exec")


def test_generation_is_deterministic_and_order_independent() -> None:
    a = _generate(resolved_refs=[_TA_RSI, _TA_EMA])
    b = _generate(resolved_refs=[_TA_EMA, _TA_RSI])
    assert a.candidate_hash == b.candidate_hash
    assert a.implementation.source == b.implementation.source


def test_generator_version_shifts_the_hash_namespace(monkeypatch) -> None:
    baseline = _generate().candidate_hash
    monkeypatch.setattr(
        "entropia.domain.create_package.generator.GENERATOR_VERSION", "cp-candidate-gen-vX"
    )
    assert _generate().candidate_hash != baseline


def test_provenance_is_traceable() -> None:
    prov = _generate().implementation.provenance
    assert prov["request_id"] == "cpr_1"
    assert prov["generator_version"] == GENERATOR_VERSION
    assert prov["output_kind"] == "directional_signal"
    assert [r["canonical_key"] for r in prov["resolved_dependencies"]] == ["ta.ema", "ta.rsi"]


def test_empty_skeleton_is_marked_non_executable() -> None:
    # A description request resolves no primitive -> an empty, non-executable skeleton.
    gen = _generate(source_kind=SourceKind.DESCRIPTION, resolved_refs=None, source_language=None)
    assert gen.implementation.executable is False
    ns = _sandbox_exec(gen.implementation.source)
    assert ns[ENTRY_SYMBOL]()["primitives"] == []


def test_contract_incompatible_with_deps_fails_closed() -> None:
    # directional_signal needs an indicator dep; a lone condition dep cannot back it.
    with pytest.raises(OutputContractInvalid):
        _generate(resolved_refs=[{"canonical_key": "cond.above"}])


def test_output_contract_without_kind_fails_closed() -> None:
    with pytest.raises(OutputContractInvalid):
        _generate(output_contract={})


# --- sandbox executor (jobs/package_validation._execute_generated) ---------------------


def test_sandbox_executes_generated_implementation() -> None:
    impl = _generate().implementation.as_dict()
    status, detail, plan = _execute_generated(impl)
    assert status == EXEC_EXECUTED
    assert plan is not None and plan["primitives"] == ["ta.ema", "ta.rsi"]
    assert "ta.rsi" in detail


def test_sandbox_reports_empty_skeleton() -> None:
    impl = _generate(
        source_kind=SourceKind.DESCRIPTION, resolved_refs=None, source_language=None
    ).implementation.as_dict()
    status, _detail, plan = _execute_generated(impl)
    assert status == EXEC_EMPTY
    assert plan is not None and plan["primitives"] == []


def test_sandbox_reports_absent_when_no_implementation() -> None:
    assert _execute_generated(None)[0] == EXEC_ABSENT
    assert _execute_generated({"entry_symbol": "build_signal_plan"})[0] == EXEC_ABSENT  # no source


def test_sandbox_reports_error_on_non_loadable_source() -> None:
    status, detail, _plan = _execute_generated(
        {"source": "def (:\n  broken", "entry_symbol": "build_signal_plan"}
    )
    assert status == EXEC_ERROR
    assert "failed to load" in detail


def test_sandbox_is_isolated_from_builtins() -> None:
    # A generated body that reaches for a builtin cannot — the sandbox has none.
    status, detail, _plan = _execute_generated(
        {
            "source": "def build_signal_plan():\n    return {'primitives': __import__('os')}\n",
            "entry_symbol": "build_signal_plan",
        }
    )
    assert status == EXEC_ERROR
    assert "raised" in detail
