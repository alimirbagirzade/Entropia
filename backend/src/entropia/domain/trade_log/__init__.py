"""Trade Log domain layer (Stage 3d, doc 05).

A Trade Log is an EXTERNAL work object (``object_kind=trade_log``, CR-01 — never a
``PackageKind``, TL-01). It represents *historical* executed/provided entry/exit
records; it does NOT produce live signals (contrast the 3c Trading Signal event
model). Its root/revision reuse the 3a ``work_object_root`` /
``work_object_revision`` tables (native work object, no mirror revision). This layer
owns:

* ``enums`` — canonical direction / content-profile / resolution / price / OHLCV
  policy enums.
* ``config`` — the typed §10.2 revision payload (``TradeLogConfig``).
* ``compiler`` — structural + cross-field validation and the config hash.
* ``records`` — the pure, infra-free CSV/TXT ledger parser + normalizer that the
  durable import worker wraps.

Unlike Trading Signal, a Trade Log carries no per-event ``available_time``
anti-lookahead contract — the backtest reads the record timestamps directly
(doc 05 §10.4). Invalid rows are never silently dropped: they are reported with a
row number, reason code and severity as immutable evidence.
"""
