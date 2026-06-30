"""Unit tests for Create-Package request normalization + hashing (Stage 2e)."""

from __future__ import annotations

import pytest

from entropia.domain.create_package.enums import CreationMode, SourceKind, SourceLanguage
from entropia.domain.create_package.value_objects import (
    context_hash,
    normalize_request,
    source_hash,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import PackageKind
from entropia.shared.errors import (
    ClientLegacyTypeRejected,
    EmptySource,
    OutputContractInvalid,
    RuntimeUnavailable,
    SourceLanguageMismatch,
)

_INDICATOR_OUTPUT = {"kind": "directional_signal"}


def _normalize(**overrides: object):
    base: dict[str, object] = {
        "package_type": "indicator",
        "creation_mode": CreationMode.TRANSLATE_EXISTING_CODE,
        "source_language": SourceLanguage.PINESCRIPT,
        "other_language_label": None,
        "target_runtime": RuntimeAdapter.PYTHON,
        "request_body": "//@version=5\nindicator('x')",
        "output_contract": _INDICATOR_OUTPUT,
    }
    base.update(overrides)
    return normalize_request(**base)  # type: ignore[arg-type]


def test_translate_code_requires_language() -> None:
    result = _normalize()
    assert result.source_kind == SourceKind.CODE
    assert result.source_language == SourceLanguage.PINESCRIPT
    with pytest.raises(SourceLanguageMismatch):
        _normalize(source_language=None)


def test_generate_from_description_nulls_language() -> None:
    result = _normalize(
        creation_mode=CreationMode.GENERATE_FROM_DESCRIPTION,
        source_language=None,
        request_body="A reversal indicator over closed bars.",
    )
    assert result.source_kind == SourceKind.DESCRIPTION
    assert result.source_language is None


def test_legacy_and_strategy_types_rejected() -> None:
    with pytest.raises(ClientLegacyTypeRejected):
        _normalize(package_type="trading_signal")
    with pytest.raises(ClientLegacyTypeRejected):
        _normalize(package_type="strategy")


def test_empty_body_and_bad_runtime_and_output() -> None:
    with pytest.raises(EmptySource):
        _normalize(request_body="   ")
    with pytest.raises(RuntimeUnavailable):
        _normalize(target_runtime=RuntimeAdapter.PINE_V5)
    with pytest.raises(OutputContractInvalid):
        _normalize(
            package_type="condition",
            output_contract={"kind": "directional_signal"},  # not valid for condition
            creation_mode=CreationMode.GENERATE_FROM_DESCRIPTION,
            source_language=None,
            request_body="boolean cross condition",
        )


def test_other_language_requires_label() -> None:
    with pytest.raises(SourceLanguageMismatch):
        _normalize(source_language=SourceLanguage.OTHER, other_language_label="  ")
    result = _normalize(
        source_language=SourceLanguage.OTHER, other_language_label="EasyLanguage 10"
    )
    assert result.other_language_label == "EasyLanguage 10"


def test_context_hash_changes_with_each_input() -> None:
    sh = source_hash("body-1")
    base = context_hash(
        source_hash_value=sh,
        source_language=SourceLanguage.PINESCRIPT,
        target_runtime=RuntimeAdapter.PYTHON,
        output_contract=_INDICATOR_OUTPUT,
        declared_dependencies=[{"key": "ta.rsi"}],
    )
    # Same inputs -> identical hash (deterministic).
    assert base == context_hash(
        source_hash_value=sh,
        source_language=SourceLanguage.PINESCRIPT,
        target_runtime=RuntimeAdapter.PYTHON,
        output_contract=_INDICATOR_OUTPUT,
        declared_dependencies=[{"key": "ta.rsi"}],
    )
    # Any change -> different hash (staleness anchor).
    assert base != context_hash(
        source_hash_value=source_hash("body-2"),
        source_language=SourceLanguage.PINESCRIPT,
        target_runtime=RuntimeAdapter.PYTHON,
        output_contract=_INDICATOR_OUTPUT,
        declared_dependencies=[{"key": "ta.rsi"}],
    )
    assert base != context_hash(
        source_hash_value=sh,
        source_language=SourceLanguage.PINESCRIPT,
        target_runtime=RuntimeAdapter.PYTHON,
        output_contract=_INDICATOR_OUTPUT,
        declared_dependencies=[{"key": "ta.sma"}],
    )


def test_package_kind_returned_normalized() -> None:
    assert _normalize().package_kind == PackageKind.INDICATOR
