"""Deterministic Create-Package candidate generation (doc 06 §5).

Pure unit tests over the manifest compute — no database. Prove reproducibility
(same inputs -> same hash), namespace shift on GENERATOR_VERSION, and fail-closed
output-contract validation against the resolved dependency set.
"""

from __future__ import annotations

import pytest

from entropia.domain.create_package import candidate as cg
from entropia.domain.create_package.candidate import (
    build_candidate_manifest,
    candidate_hash,
)
from entropia.domain.create_package.enums import SourceKind
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
_COND = {
    "canonical_key": "cond.above",
    "embedded_revision_id": "pkgrev_3",
    "content_hash": "sha256:c",
}


def _manifest(**overrides):
    kwargs = {
        "package_kind": "indicator",
        "source_kind": SourceKind.CODE,
        "output_contract": {"kind": "directional_signal"},
        "resolved_refs": [_TA_RSI],
    }
    kwargs.update(overrides)
    return build_candidate_manifest(**kwargs)


def test_manifest_hash_is_deterministic() -> None:
    first = _manifest()
    second = _manifest()
    assert first == second
    assert candidate_hash(first) == candidate_hash(second)
    assert candidate_hash(first).startswith("sha256:")


def test_hash_is_order_independent() -> None:
    forward = _manifest(resolved_refs=[_TA_RSI, _TA_EMA])
    reversed_ = _manifest(resolved_refs=[_TA_EMA, _TA_RSI])
    assert candidate_hash(forward) == candidate_hash(reversed_)


def test_hash_changes_with_output_contract() -> None:
    directional = _manifest(output_contract={"kind": "directional_signal"})
    numeric = _manifest(output_contract={"kind": "numeric_series"})
    assert candidate_hash(directional) != candidate_hash(numeric)


def test_hash_changes_with_resolved_refs() -> None:
    with_rsi = _manifest(resolved_refs=[_TA_RSI])
    with_ema = _manifest(resolved_refs=[_TA_EMA])
    assert candidate_hash(with_rsi) != candidate_hash(with_ema)


def test_generator_version_shifts_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = candidate_hash(_manifest())
    monkeypatch.setattr(cg, "GENERATOR_VERSION", "cp-candidate-gen-v99")
    shifted = candidate_hash(_manifest())
    assert baseline != shifted


def test_missing_output_kind_raises() -> None:
    with pytest.raises(OutputContractInvalid):
        _manifest(output_contract={}, resolved_refs=[])


def test_output_type_alias_accepted() -> None:
    manifest = _manifest(output_contract={"output_type": "directional_signal"})
    assert manifest.signal_kind == "directional_signal"


def test_directional_signal_requires_indicator_dep() -> None:
    with pytest.raises(OutputContractInvalid):
        _manifest(output_contract={"kind": "directional_signal"}, resolved_refs=[_COND])


def test_boolean_condition_requires_condition_dep() -> None:
    with pytest.raises(OutputContractInvalid):
        _manifest(
            package_kind="condition",
            output_contract={"kind": "boolean_condition"},
            resolved_refs=[_TA_RSI],
        )


def test_empty_resolved_skips_dep_validation() -> None:
    # A directional signal with no resolved deps (description / dep-less) never fails.
    manifest = _manifest(output_contract={"kind": "directional_signal"}, resolved_refs=[])
    assert manifest.resolved_dependencies == []


def test_description_adds_uncertainty_note() -> None:
    manifest = _manifest(
        source_kind=SourceKind.DESCRIPTION,
        output_contract={"kind": "boolean_condition"},
        resolved_refs=[],
    )
    assert any("description" in note.lower() for note in manifest.uncertainty)


def test_test_plan_lists_each_dependency() -> None:
    manifest = _manifest(resolved_refs=[_TA_RSI, _TA_EMA])
    joined = " ".join(manifest.test_plan)
    assert "ta.rsi" in joined and "ta.ema" in joined
