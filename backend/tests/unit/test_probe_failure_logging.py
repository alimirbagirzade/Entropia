"""I-13 — a red Ready Check must say WHY.

The four dependency probes swallow every exception by design: an unreachable
dependency degrades the readiness/scrape response, it never 500s. Before this
slice they swallowed it *silently*, so an operator seeing ``"redis": "down"``
had no way to learn whether it was a refused connection, a timeout, or a bad
credential.

These tests pin BOTH halves of the fix:

* behaviour is untouched — ``False`` / the degrade string still come back;
* a ``<component>.probe_failed`` warning is emitted carrying the exception
  CLASS NAME ONLY. The secret-leak assertion is the point of the slice: driver
  errors quote the DSN (``redis://user:hunter2@host``), so ``str(exc)`` must
  never reach the log.
"""

from __future__ import annotations

import pytest
import structlog

from entropia.apps.api.routes import metrics as metrics_route
from entropia.infrastructure.postgres import health as pg_health
from entropia.infrastructure.redis import client as redis_client
from entropia.infrastructure.s3 import client as s3_client

# A realistic driver message: the kind of string that must NOT be logged.
SECRET_DSN = "redis://entropia:hunter2@10.0.0.7:6379/0"


class Boom(ConnectionError):
    """Stands in for a driver-level connectivity error."""


def _raise_with_secret(*_args, **_kwargs):
    raise Boom(f"Error connecting to {SECRET_DSN}: Connection refused")


@pytest.fixture
def captured(monkeypatch):
    """Swap each module's bound logger for structlog's capturing logger.

    ``get_logger`` caches on first use, so patching the module attribute is the
    reliable way to observe the emitted event regardless of test ordering.
    """
    logger = structlog.testing.CapturingLogger()
    for module in (s3_client, redis_client, pg_health, metrics_route):
        monkeypatch.setattr(module, "log", logger)
    return logger


def _only_call(captured) -> tuple[str, dict]:
    assert len(captured.calls) == 1, f"expected one log call, got {captured.calls}"
    call = captured.calls[0]
    assert call.method_name == "warning"
    return call.args[0], call.kwargs


def _assert_no_secret(event: str, kwargs: dict) -> None:
    blob = f"{event} {kwargs}"
    assert "hunter2" not in blob
    assert SECRET_DSN not in blob
    assert "Connection refused" not in blob
    # Only the classification travels — no free-text error field at all.
    assert set(kwargs) == {"error_type"}


def test_object_storage_probe_logs_error_type_and_still_returns_false(captured, monkeypatch):
    monkeypatch.setattr(s3_client, "get_s3_client", _raise_with_secret)

    assert s3_client.check_object_storage() is False

    event, kwargs = _only_call(captured)
    assert event == "object_storage.probe_failed"
    assert kwargs["error_type"] == "Boom"
    _assert_no_secret(event, kwargs)


async def test_redis_probe_logs_error_type_and_still_returns_false(captured, monkeypatch):
    monkeypatch.setattr(redis_client, "get_redis", _raise_with_secret)

    assert await redis_client.check_redis() is False

    event, kwargs = _only_call(captured)
    assert event == "redis.probe_failed"
    assert kwargs["error_type"] == "Boom"
    _assert_no_secret(event, kwargs)


async def test_postgres_probe_logs_error_type_and_still_returns_false(captured, monkeypatch):
    monkeypatch.setattr(pg_health, "get_engine", _raise_with_secret)

    assert await pg_health.check_postgres() is False

    event, kwargs = _only_call(captured)
    assert event == "postgres.probe_failed"
    assert kwargs["error_type"] == "Boom"
    _assert_no_secret(event, kwargs)


async def test_metrics_gauges_log_error_type_and_still_degrade(captured, monkeypatch):
    monkeypatch.setattr(
        "entropia.infrastructure.postgres.engine.get_session_factory", _raise_with_secret
    )

    body = await metrics_route._operational_gauges()

    # The degrade payload is byte-identical to the pre-slice behaviour.
    assert body == "# operational gauges unavailable (database unreachable)\n"
    event, kwargs = _only_call(captured)
    assert event == "metrics.operational_gauges_probe_failed"
    assert kwargs["error_type"] == "Boom"
    _assert_no_secret(event, kwargs)


def test_healthy_probe_logs_nothing(captured, monkeypatch):
    """The warning fires on failure only — a green probe stays quiet."""

    class _Client:
        def head_bucket(self, **_kwargs):
            return {}

    monkeypatch.setattr(s3_client, "get_s3_client", lambda: _Client())

    assert s3_client.check_object_storage() is True
    assert captured.calls == []
