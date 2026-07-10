"""Data-queue job-kind discriminator + actor registry (INF-03, doc 20 §6).

Pure, infra-free. Proves the discriminator resolves only recognized kinds (legacy
rows without it stay un-routable) and that every canonical kind has an actor in
the redelivery registry — a new data actor added without a registry entry would
fail here rather than silently drop stuck jobs.
"""

from __future__ import annotations

from entropia.application.jobs.data_queue import (
    DATA_JOB_KINDS,
    MARKET_DATA_ANALYSIS,
    RESEARCH_DATA_ANALYSIS,
    TRADE_LOG_IMPORT,
    TRADING_SIGNAL_IMPORT,
    data_job_kind,
)

_ALL_KINDS = (
    MARKET_DATA_ANALYSIS,
    RESEARCH_DATA_ANALYSIS,
    TRADING_SIGNAL_IMPORT,
    TRADE_LOG_IMPORT,
)


def test_recognized_kind_resolves() -> None:
    for kind in _ALL_KINDS:
        assert kind in DATA_JOB_KINDS
        assert data_job_kind({"job_kind": kind, "entity_id": "e"}) == kind


def test_missing_or_unknown_discriminator_is_none() -> None:
    assert data_job_kind(None) is None
    assert data_job_kind({}) is None
    assert data_job_kind({"entity_id": "e"}) is None  # legacy row, no discriminator
    assert data_job_kind({"job_kind": "not_a_kind"}) is None
    assert data_job_kind({"job_kind": 123}) is None  # wrong type never routes


def test_registry_covers_every_kind() -> None:
    from entropia.apps.worker.actors import DATA_ACTOR_BY_KIND

    assert set(DATA_ACTOR_BY_KIND) == DATA_JOB_KINDS
    assert all(callable(actor) for actor in DATA_ACTOR_BY_KIND.values())
