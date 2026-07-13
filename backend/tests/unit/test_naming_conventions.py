"""GAP-21 naming-convention guard (see docs/adr/0001-naming-conventions.md).

Introspects the LIVE application surface — OpenAPI paths, SQLAlchemy metadata, and the
``AppError`` hierarchy — and asserts the adopted naming conventions hold, so future
drift fails a unit test instead of relying on reviewer memory.

Only the objectively introspectable, contract-bearing surfaces are enforced here (REST,
DB, error codes). Frontend and Python-internal naming stay convention + review enforced
(documented in the ADR) to avoid brittle source scanning.
"""

from __future__ import annotations

import re

from entropia.apps.api.main import create_app
from entropia.infrastructure.postgres import models  # noqa: F401  populate Base.metadata
from entropia.infrastructure.postgres.base import Base
from entropia.shared.errors import AppError

_KEBAB = re.compile(r"[a-z][a-z0-9-]*")
_SNAKE = re.compile(r"[a-z][a-z0-9_]*")
_UPPER_SNAKE = re.compile(r"[A-Z][A-Z0-9_]*")


def _endpoint_paths() -> list[str]:
    return sorted(create_app().openapi().get("paths", {}).keys())


def _iter_subclasses(cls: type) -> list[type]:
    out: list[type] = []
    for sub in cls.__subclasses__():
        out.append(sub)
        out.extend(_iter_subclasses(sub))
    return out


def test_rest_literal_segments_are_kebab_case() -> None:
    """Every literal REST path segment is lowercase kebab-case."""
    offenders: dict[str, list[str]] = {}
    for path in _endpoint_paths():
        for seg in path.strip("/").split("/"):
            if not seg:
                continue
            literal = seg.split(":", 1)[0]  # strip any custom-method verb
            if literal.startswith("{") and literal.endswith("}"):
                continue  # path parameter — checked separately
            if not _KEBAB.fullmatch(literal):
                offenders.setdefault(path, []).append(seg)
    assert not offenders, f"non-kebab-case REST segments: {offenders}"


def test_path_parameters_are_snake_case() -> None:
    """Every ``{param}`` path parameter is snake_case."""
    offenders: dict[str, list[str]] = {}
    for path in _endpoint_paths():
        for seg in path.strip("/").split("/"):
            if seg.startswith("{") and seg.endswith("}"):
                name = seg[1:-1]
                if not _SNAKE.fullmatch(name):
                    offenders.setdefault(path, []).append(name)
    assert not offenders, f"non-snake_case path params: {offenders}"


def test_custom_method_verbs_are_kebab_case() -> None:
    """Custom methods use the ``resource:verb`` form with a kebab-case verb."""
    offenders: dict[str, list[str]] = {}
    for path in _endpoint_paths():
        for seg in path.strip("/").split("/"):
            if ":" in seg:
                verb = seg.split(":", 1)[1]
                if not _KEBAB.fullmatch(verb):
                    offenders.setdefault(path, []).append(seg)
    assert not offenders, f"non-kebab custom-method verbs: {offenders}"


def test_db_tables_are_snake_case() -> None:
    """Every mapped table name is snake_case."""
    offenders = sorted(t for t in Base.metadata.tables if not _SNAKE.fullmatch(t))
    assert not offenders, f"non-snake_case tables: {offenders}"


def test_error_codes_are_upper_snake_case() -> None:
    """Every ``AppError`` subclass code is UPPER_SNAKE_CASE."""
    create_app()  # load every domain error module before walking the hierarchy
    offenders: dict[str, str] = {}
    seen: set[str] = set()
    for sub in _iter_subclasses(AppError):
        code = getattr(sub, "code", None)
        if not isinstance(code, str) or code in seen:
            continue
        seen.add(code)
        if not _UPPER_SNAKE.fullmatch(code):
            offenders[sub.__name__] = code
    assert seen, "no error codes discovered — introspection wired wrong"
    assert not offenders, f"non-UPPER_SNAKE_CASE error codes: {offenders}"
