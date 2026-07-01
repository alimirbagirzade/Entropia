"""Portfolio / Equity Allocation domain (doc 13).

Pure typed config + semantic rules for the run-scoped shared capital pool that
sits on a Mainboard composition. No persistence or I/O lives here — the
application layer resolves composition-item availability and owns the transaction.
"""

from __future__ import annotations
