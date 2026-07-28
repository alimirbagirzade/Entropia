"""Extracted, independently testable sub-systems of the bar-replay engine (K-09).

``domain.backtest.engine`` grew into a single 5.2k-line module whose 2.9k-line
``run_engine`` mixed the bar loop with fill matching, sizing, cost application and
portfolio composition. This package holds those responsibilities as their own
modules. Every extraction is BEHAVIOUR-PRESERVING by construction: the moved code is
relocated verbatim, ``ENGINE_VERSION`` is untouched, and each slice is gated on a
byte-equality proof (identical ``execution_key`` + identical full ``EngineOutput``
digest over the shipped fixture matrix, before vs after).

Dependency direction is one-way — ``execution.*`` imports from ``engine``, never the
reverse — so no import cycle is introduced.
"""
