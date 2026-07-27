"""Unit tests for the Pre-Check content language detector (doc 07 §9.5, PC-10)."""

from __future__ import annotations

from entropia.domain.create_package.enums import SourceLanguage
from entropia.domain.create_package.language_detect import (
    detect_source_language,
    score_language_markers,
)

_PINESCRIPT = "//@version=5\nindicator('rsi')\nta.rsi(close, 14)"
_PYTHON = "import pandas as pd\n\n\ndef rsi(series, length):\n    return series.mean()\n"
_CPP = "#include <vector>\nint main() { std::vector<int> v; return 0; }\n"


def test_detects_pinescript_from_version_header_and_calls() -> None:
    signal = detect_source_language(_PINESCRIPT)
    assert signal.language == SourceLanguage.PINESCRIPT
    assert signal.is_ambiguous is False


def test_detects_python_from_import_and_def() -> None:
    signal = detect_source_language(_PYTHON)
    assert signal.language == SourceLanguage.PYTHON
    assert signal.is_ambiguous is False


def test_detects_cpp_from_include_and_std_namespace() -> None:
    assert detect_source_language(_CPP).language == SourceLanguage.CPP


def test_competing_evidence_is_ambiguous_not_a_guess() -> None:
    """Two languages within the margin must ask, never pick a winner (PC-10
    REQUIRES_CLARIFICATION)."""
    signal = detect_source_language(_PINESCRIPT + "\n" + _PYTHON)
    assert signal.is_ambiguous is True
    assert signal.language is None
    assert signal.has_verdict is True


def test_weak_or_absent_markers_produce_no_verdict() -> None:
    """Absence of evidence is not evidence of mismatch — a marker-free snippet must
    NOT fail the scan; the lexer's own PARSE_UNSUPPORTED rule decides instead."""
    for source in ("x = 1 + 2", "", "   \n\t "):
        signal = detect_source_language(source)
        assert signal.language is None
        assert signal.is_ambiguous is False
        assert signal.has_verdict is False


def test_single_weak_marker_does_not_contradict_a_selection() -> None:
    # One bare ``//`` line scores below the confidence floor on its own.
    assert detect_source_language("// a note\nvalue = 1").language is None


def test_marker_weights_are_counted_once_per_marker() -> None:
    """A repeated marker must not outweigh a decisive one (weights, not counts)."""
    scores = score_language_markers("plot(close)\n" * 50)
    assert scores[SourceLanguage.PINESCRIPT] == 1


def test_line_anchored_markers_do_not_fire_inside_a_comment() -> None:
    """``import``/``def`` are anchored to the start of a line, so prose *about* them
    inside a comment does not manufacture a Python verdict."""
    scores = score_language_markers("// we ported the import and def logic from python\n")
    assert scores[SourceLanguage.PYTHON] == 0


def test_free_form_markers_count_wherever_they_appear() -> None:
    """A marker with no line anchor (``std::``) is genuine evidence of the language the
    file was written in — the detector reads text, not code structure."""
    assert score_language_markers("std::vector<int> v;\n")[SourceLanguage.CPP] == 3
