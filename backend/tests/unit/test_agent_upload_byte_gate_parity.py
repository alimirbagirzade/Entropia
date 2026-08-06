"""ADIM 23 — the Agent plane must not be able to upload what a human cannot.

``_handle_trading_signal_upload_source`` states the rule in its own docstring:
the F-03 byte gate (size / whole-document UTF-8 / CSV header) lives at the
multipart route on the human plane, so the UI-less Agent plane has to run it
itself, "off ONE shared ceiling, so the Agent can never upload what a human
cannot."

``_handle_trade_log_upload_source`` did not run it. Both planes share the
command's extension+sniff gate, but the byte gate is at
``routes/trade_log.py`` -> ``validate_multipart_upload(file, require_csv_schema=True)``
— which the Agent never passes through. So on that one tool there was no size
ceiling, no whole-document UTF-8 check and no CSV-header check: the page refused
a 200 MB headerless file and the Agent stored it.

These are unit tests on purpose. The gate runs BEFORE the command, so nothing
here needs a database — and that ordering is itself part of the guarantee: a
rejected upload must never reach object storage or an evidence row. Passing
``session=None`` is what proves it; if the gate ever moved after the command,
these tests would fail with AttributeError rather than pass quietly.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from entropia.application.jobs import agent_tools
from entropia.domain.agent_lab.tool_gateway import PolicyScope, ToolName
from entropia.domain.identity import Actor
from entropia.domain.importing.source_file import MAX_SOURCE_UPLOAD_BYTES
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.shared.errors import (
    UploadEncodingInvalidError,
    UploadSchemaInvalidError,
    UploadTooLargeError,
    ValidationError,
)

_HEADER = "trade_id,symbol,side,quantity,price,executed_at"

_UPLOAD_HANDLERS = {
    "trade_log": agent_tools._handle_trade_log_upload_source,
    "trading_signal": agent_tools._handle_trading_signal_upload_source,
}


def _ctx(payload: dict[str, Any]) -> Any:
    """A context whose session is deliberately unusable. Reaching it is a bug."""
    return agent_tools._Ctx(
        session=cast("Any", None),
        actor=Actor(
            principal_id="agent_test",
            principal_type=PrincipalType.AGENT,
            role=Role.USER,
        ),
        agent_id="agent_test",
        tool=ToolName.TRADE_LOG_UPLOAD_SOURCE,
        scope=PolicyScope.RESEARCH,
        task_id=None,
        checkpoint_id=None,
        request=payload,
        call=None,
    )


@pytest.mark.parametrize("plane", sorted(_UPLOAD_HANDLERS))
async def test_oversize_upload_is_refused_before_any_storage_write(plane: str) -> None:
    oversize = f"{_HEADER}\n".encode() + b"x" * MAX_SOURCE_UPLOAD_BYTES
    with pytest.raises(UploadTooLargeError):
        await _UPLOAD_HANDLERS[plane](
            _ctx({"content": oversize.decode("utf-8"), "original_filename": "rows.csv"})
        )


@pytest.mark.parametrize("plane", sorted(_UPLOAD_HANDLERS))
async def test_headerless_upload_is_refused_before_any_storage_write(plane: str) -> None:
    """Bytes are present, but there is no CSV header row to import against."""
    with pytest.raises(UploadSchemaInvalidError):
        await _UPLOAD_HANDLERS[plane](
            _ctx({"content": "   \n  \n", "original_filename": "rows.csv"})
        )


@pytest.mark.parametrize("plane", sorted(_UPLOAD_HANDLERS))
async def test_empty_upload_is_refused_before_any_storage_write(plane: str) -> None:
    with pytest.raises(ValidationError):
        await _UPLOAD_HANDLERS[plane](_ctx({"content": "", "original_filename": "rows.csv"}))


@pytest.mark.parametrize("plane", sorted(_UPLOAD_HANDLERS))
async def test_non_utf8_upload_is_refused_before_any_storage_write(plane: str) -> None:
    with pytest.raises(UploadEncodingInvalidError):
        await _UPLOAD_HANDLERS[plane](
            _ctx({"content": b"\xff\xfe\x00bad", "original_filename": "rows.csv"})
        )


@pytest.mark.parametrize("plane", sorted(_UPLOAD_HANDLERS))
@pytest.mark.parametrize("bad", [None, 5, {}, []], ids=["none", "int", "dict", "list"])
async def test_malformed_content_fails_closed_on_both_planes(plane: str, bad: Any) -> None:
    """``bytes(5)`` would silently produce five NUL bytes — a file the caller
    never meant to store. Trade Log used to take that path."""
    with pytest.raises(agent_tools.AgentToolRequestInvalidError):
        await _UPLOAD_HANDLERS[plane](_ctx({"content": bad, "original_filename": "rows.csv"}))
