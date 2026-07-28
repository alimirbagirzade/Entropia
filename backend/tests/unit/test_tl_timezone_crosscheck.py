"""O-28 — the declared source time zone must be REAL, and the config must agree with
the import that produced its records (doc 05 §5.2, doc 04 §5).

Two defects are locked here at the pure-domain level; the save-path half (attach is
refused when the zones disagree) is locked in
``tests/integration/test_tl_timezone_crosscheck_attach.py`` against a real database.

Before this fix:

* ``TimeModel.source_timezone`` / ``TimePolicy.source_timezone`` only checked
  non-emptiness, so ``"EST"`` or a typo'd ``"America/New York"`` saved cleanly into an
  immutable revision and never resolved to a zone anywhere downstream; and
* the import took its own ``source_timezone`` job parameter, so nothing ever compared
  the zone the records were normalized under with the zone the config advertised.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.domain.importing.timezone import (
    is_valid_iana_timezone,
    normalize_iana_timezone,
    timezones_agree,
)
from entropia.domain.trade_log.compiler import validate_trade_log_config
from entropia.domain.trading_signal.compiler import validate_trading_signal_config

# --------------------------------------------------------------------------- #
# The shared gate                                                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", ["UTC", "America/New_York", " Europe/Istanbul ", "Etc/UTC"])
def test_a_real_iana_identifier_is_accepted_and_trimmed(value: str) -> None:
    assert normalize_iana_timezone(value) == value.strip()
    assert is_valid_iana_timezone(value)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "America/New York",  # space instead of underscore — a real user typo
        "Mars/Olympus_Mons",
        "GMT+3:00",
        "../../etc/passwd",
    ],
)
def test_an_unresolvable_identifier_is_rejected(value: str | None) -> None:
    assert not is_valid_iana_timezone(value)
    with pytest.raises(ValueError):
        normalize_iana_timezone(value)


def test_identical_zones_agree_case_insensitively() -> None:
    assert timezones_agree("America/New_York", "America/New_York")
    assert timezones_agree("utc", "UTC")


def test_utc_aliases_agree_because_they_are_one_zone() -> None:
    """``UTC`` and ``Etc/UTC`` name the same zone, so no instant can shift between them."""
    assert timezones_agree("UTC", "Etc/UTC")
    assert timezones_agree("Zulu", "Universal")


def test_different_zones_do_not_agree() -> None:
    assert not timezones_agree("UTC", "America/New_York")
    assert not timezones_agree("Europe/Istanbul", "Europe/London")


@pytest.mark.parametrize(("declared", "imported"), [("UTC", None), ("UTC", ""), (None, "UTC")])
def test_missing_evidence_is_a_disagreement_not_an_assumed_match(
    declared: str | None, imported: str | None
) -> None:
    """Fail-closed: an import that declares no zone cannot be SHOWN to agree, and
    silently assuming UTC is exactly the K-01 class of bug this replaces."""
    assert not timezones_agree(declared, imported)


# --------------------------------------------------------------------------- #
# Config-level IANA validation — doc 05 §5.2 / doc 04 §5                       #
# --------------------------------------------------------------------------- #


def _trade_log_payload(source_timezone: str) -> dict[str, Any]:
    return {
        "kind": "trade_log",
        "identity": {"display_name": "Binance BTCUSDT trade history Q1"},
        "source": {"provider_name": "Binance Futures export", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "time_model": {
            "resolution_kind": "event_based",
            "base_timeframe": None,
            "source_timezone": source_timezone,
            "normalization_timezone": "UTC",
        },
        "classification": {"rationale_family_id": None},
        "data_quality": {"content_profile": "entry_exit_records_only"},
        "price_policy": {
            "source": "trade_log_entry_exit_price",
            "approved_market_data_revision_ref": None,
        },
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000", "currency": "USDT"},
        "import_binding": {
            "source_asset_id": "srcasset_x",
            "record_batch_revision_id": "tlbatch_x",
            "mapping_revision_id": None,
        },
    }


def _trading_signal_payload(source_timezone: str) -> dict[str, Any]:
    return {
        "kind": "trading_signal",
        "identity": {"display_name": "Copy Trading Signal Source A"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {
            "source_timezone": source_timezone,
            "normalization_timezone": "UTC",
        },
        "price_policy": {"source": "suggested_signal_price", "fallback": None},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": "srcasset_x",
            "normalized_event_revision_id": "sigrm_x",
        },
    }


@pytest.mark.parametrize("bad", ["EST5EDT_typo", "America/New York", "   ", "Etc/GMT+99"])
def test_trade_log_config_rejects_an_unresolvable_zone(bad: str) -> None:
    config, issues = validate_trade_log_config(_trade_log_payload(bad))
    assert config is None
    assert any(str(issue["field"]).endswith("source_timezone") for issue in issues)


def test_trade_log_config_accepts_a_real_zone() -> None:
    config, issues = validate_trade_log_config(_trade_log_payload("America/New_York"))
    assert config is not None and issues == []
    assert config.time_model.source_timezone == "America/New_York"


@pytest.mark.parametrize("bad", ["EST5EDT_typo", "America/New York", "   ", "Etc/GMT+99"])
def test_trading_signal_config_rejects_an_unresolvable_zone(bad: str) -> None:
    config, issues = validate_trading_signal_config(_trading_signal_payload(bad))
    assert config is None
    assert any(str(issue["field"]).endswith("source_timezone") for issue in issues)


def test_trading_signal_config_accepts_a_real_zone() -> None:
    config, issues = validate_trading_signal_config(_trading_signal_payload("Europe/Istanbul"))
    assert config is not None and issues == []
    assert config.time_policy.source_timezone == "Europe/Istanbul"
