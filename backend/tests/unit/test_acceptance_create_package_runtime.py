"""I-17-COV — CP-05 (docs/audit, doc 06 row 5) "Runtime alignment".

Doc 06 §15 row 5: "V18 PHP/Python çelişkisi Production'da görünmez: target runtime
registered Python Runtime v1'dir. Inactive runtime ID ile Send `RUNTIME_UNAVAILABLE`
döner." Both clauses, asserted against the single registry the normalizer reads.

``docs/audit/acceptance_id_map.md`` §C.1 listed CP-05 as having no test; the second
clause was in fact already exercised (``test_create_package_value_objects.py::
test_empty_body_and_bad_runtime_and_output``) but never named the ID, and the first
clause — that Python is the ONLY registered adapter — was unasserted anywhere.
"""

from __future__ import annotations

import pytest

from entropia.domain.create_package.enums import CreationMode, SourceLanguage
from entropia.domain.create_package.value_objects import (
    SUPPORTED_TARGET_RUNTIMES,
    normalize_request,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import PackageKind
from entropia.shared.errors import RuntimeUnavailable


def _normalize(**overrides: object):
    kwargs: dict[str, object] = {
        "package_type": PackageKind.INDICATOR,
        "creation_mode": CreationMode.TRANSLATE_EXISTING_CODE,
        "source_language": SourceLanguage.PINESCRIPT,
        "other_language_label": None,
        "target_runtime": RuntimeAdapter.PYTHON,
        "request_body": "plot(ta.sma(close, 14))",
        "output_contract": {"kind": "numeric_series"},
    }
    kwargs.update(overrides)
    return normalize_request(**kwargs)  # type: ignore[arg-type]


def test_python_is_the_only_registered_target_runtime() -> None:
    """CP-05 first clause: the V18 PHP/Python contradiction is not reachable in
    Production — the registry holds exactly one adapter, and it is Python."""
    assert set(SUPPORTED_TARGET_RUNTIMES) == {RuntimeAdapter.PYTHON}


def test_registered_runtime_normalizes_and_an_unregistered_one_is_unavailable() -> None:
    """CP-05 second clause: the registered runtime passes; any other adapter id is
    ``RUNTIME_UNAVAILABLE`` — never a silent fallback to a supported one."""
    accepted = _normalize()
    assert accepted.target_runtime == RuntimeAdapter.PYTHON

    with pytest.raises(RuntimeUnavailable) as exc_info:
        _normalize(target_runtime=RuntimeAdapter.PINE_V5)
    assert exc_info.value.code == "RUNTIME_UNAVAILABLE"
