"""Content-based source-language signal for Pre-Check (doc 07 §12, PC-10).

The Create-Package form asks the caller to *declare* a source language. A
declaration is an assertion, not evidence: a PineScript export pasted under
``python`` (or the reverse) would otherwise walk straight into the PineScript
call lexer, produce zero detected calls and reach ``Passed`` on an empty
dependency set. Doc 07 §9.5 requires the opposite — the content detector and the
parser must agree with the selection, and a disagreement lands the request in a
FAILED state, never a positive ``passed``.

This module is the *detector* half. It is deliberately evidence-only:

* a language is reported ONLY when its markers actually appear in the source,
* competing evidence (two languages scoring within ``_AMBIGUITY_MARGIN`` of each
  other) is reported as **ambiguous** rather than guessed — the caller turns that
  into ``REQUIRES_CLARIFICATION``,
* **absence of evidence is not evidence of mismatch**: a snippet too small or too
  generic to carry any marker yields ``language=None, is_ambiguous=False`` and
  the caller must NOT fail the scan on it. An honest boundary — this detector can
  only ever downgrade a Pre-Check result, never upgrade one to Passed.

No I/O, no registry access. Markers are scored over the raw text; unlike the
dependency lexer (which must be comment/string aware because a commented
``ta.rsi`` is not a dependency), a language marker inside a comment is still
genuine evidence of the language the file was written in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from entropia.domain.create_package.enums import SourceLanguage

# Detector semantics identity — bump together with SOURCE_SCANNER_VERSION when the
# marker set or the decision rule changes, so a scan pinned to the old contract is
# not treated as equivalent.
LANGUAGE_DETECTOR_VERSION = "language-detector-1.0"

# A language must clear this score before it is reported at all: one weak marker
# (a lone ``//`` or ``#`` line) is not enough to contradict a caller's selection.
_MIN_CONFIDENT_SCORE = 3
# Two languages within this many points of each other are competing evidence.
_AMBIGUITY_MARGIN = 1

_MARKERS: dict[SourceLanguage, tuple[tuple[re.Pattern[str], int], ...]] = {
    SourceLanguage.PINESCRIPT: (
        (re.compile(r"//\s*@version\s*="), 3),
        (re.compile(r"\bindicator\s*\("), 2),
        (re.compile(r"\bstrategy\s*\("), 2),
        (re.compile(r"\bstudy\s*\("), 2),
        (re.compile(r"\brequest\.security\s*\("), 2),
        (re.compile(r"\bta\."), 1),
        (re.compile(r"\bplot(shape|char)?\s*\("), 1),
        (re.compile(r":="), 1),
        (re.compile(r"^\s*//", re.MULTILINE), 1),
    ),
    SourceLanguage.PYTHON: (
        (re.compile(r"^\s*def\s+\w+\s*\(", re.MULTILINE), 3),
        (re.compile(r"^\s*(import\s+\w|from\s+[\w.]+\s+import\s+)", re.MULTILINE), 3),
        (re.compile(r"^\s*class\s+\w+\s*[(:]", re.MULTILINE), 2),
        (re.compile(r"\b__(name|init|main)__\b"), 2),
        (re.compile(r"\bself\."), 2),
        (re.compile(r"^\s*(elif|except|finally)\b", re.MULTILINE), 2),
        (re.compile(r"^\s*#", re.MULTILINE), 1),
    ),
    SourceLanguage.CPP: (
        (re.compile(r"^\s*#\s*include\b", re.MULTILINE), 3),
        (re.compile(r"\bstd::"), 3),
        (re.compile(r"\bint\s+main\s*\("), 3),
        (re.compile(r"^\s*template\s*<", re.MULTILINE), 2),
        (re.compile(r"^\s*namespace\s+\w+", re.MULTILINE), 2),
        (re.compile(r"^\s*(public|private|protected)\s*:", re.MULTILINE), 2),
    ),
}


@dataclass(frozen=True, slots=True)
class LanguageSignal:
    """What the content says about the language, and how sure the evidence is."""

    language: SourceLanguage | None
    scores: dict[str, int]
    is_ambiguous: bool

    @property
    def has_verdict(self) -> bool:
        """True when the detector produced actionable evidence either way."""
        return self.is_ambiguous or self.language is not None


def score_language_markers(source: str) -> dict[SourceLanguage, int]:
    """Score each known language's markers over ``source`` (weights, not counts).

    A marker contributes its weight once no matter how often it appears, so a file
    that repeats ``plot(`` fifty times does not outscore one carrying a decisive
    ``//@version=`` header.
    """
    scores: dict[SourceLanguage, int] = {}
    for language, markers in _MARKERS.items():
        scores[language] = sum(weight for pattern, weight in markers if pattern.search(source))
    return scores


def detect_source_language(source: str) -> LanguageSignal:
    """Derive the content language signal for ``source`` (doc 07 §9.5, PC-10).

    Returns the single best-supported language, or an ambiguous signal when the
    top two are within ``_AMBIGUITY_MARGIN``, or no verdict at all when nothing
    clears ``_MIN_CONFIDENT_SCORE``.
    """
    scores = score_language_markers(source)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
    readable = {str(language): score for language, score in scores.items()}

    top_language, top_score = ranked[0]
    if top_score < _MIN_CONFIDENT_SCORE:
        return LanguageSignal(language=None, scores=readable, is_ambiguous=False)

    runner_up_score = ranked[1][1] if len(ranked) > 1 else 0
    if runner_up_score >= _MIN_CONFIDENT_SCORE and top_score - runner_up_score <= _AMBIGUITY_MARGIN:
        return LanguageSignal(language=None, scores=readable, is_ambiguous=True)

    return LanguageSignal(language=top_language, scores=readable, is_ambiguous=False)


__all__ = [
    "LANGUAGE_DETECTOR_VERSION",
    "LanguageSignal",
    "detect_source_language",
    "score_language_markers",
]
