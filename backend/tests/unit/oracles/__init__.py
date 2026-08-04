"""Independent financial oracles for the V1 bar-replay backtest engine (ADIM 12).

Every expected value in this package is computed BY HAND from the canonical rule, written
as a literal, and compared against what the engine produced. Nothing here imports an
engine arithmetic helper (``_effective_fill``, ``_position_size``, ``_resolve_stop``,
``due_funding_charges``, ...) to build an expectation — that would make the test a mirror
of the implementation instead of a check on it. The only production import is
``run_engine`` itself, plus the typed inputs it consumes.

Why this exists
---------------
The existing engine suite locks behaviour through golden digests and through helper-level
unit tests. Both are load-bearing and stay. Neither answers the question this package
answers: *is the number the engine produced the number the arithmetic says it should be?*
A digest survives any change that also updates the digest; a helper test that calls
``_effective_fill`` to build its own expectation agrees with the helper by construction.

These fixtures are deliberately tiny (5-20 bars) so the whole ledger is hand-checkable, and
every module carries the arithmetic in its docstrings. The written-out calculations live in
``docs/audit/backtest_oracle_fixtures.md``.

Scope boundary: these oracles pin the CURRENT single-item engine. They are the baseline the
unified-clock work is measured against — not a specification of what a multi-item co-
simulation should do.
"""
