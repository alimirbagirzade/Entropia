"""Trading Signal domain layer (Stage 3c, doc 04).

A Trading Signal is an EXTERNAL work object (``object_kind=trading_signal``,
CR-01 — never a ``PackageKind``). Its root/revision reuse the 3a
``work_object_root`` / ``work_object_revision`` tables (no mirror revision, unlike
Strategy). This layer owns:

* ``enums`` — canonical direction / signal type / data-quality / policy enums.
* ``config`` — the typed §9.2 revision payload (``TradingSignalConfig``).
* ``compiler`` — structural + cross-field validation and the config hash.
* ``events`` — the pure, infra-free CSV/TXT parser + time-safe normalizer that the
  durable import worker wraps.

Anti-lookahead is enforced at the event level: every accepted event carries a
valid ``available_time`` and the backtest may only see it afterwards.
"""
