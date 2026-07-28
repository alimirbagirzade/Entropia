"""Decimal quantization steps shared by the engine and its extracted sub-systems.

These are part of the reproducibility contract: every monetary, percentage, ratio and
quantity figure the engine emits is quantized to one of these steps, so a change here
would shift results exactly like an ``ENGINE_VERSION`` bump. They live in their own
leaf module (K-09) purely so ``engine`` and ``execution.*`` can both import them
DOWNWARD — ``execution.sizing`` is called from inside ``run_engine``, so without a
shared leaf the two modules would import each other and form a cycle.

Values are byte-identical to their pre-extraction definitions in ``engine``.
"""

from __future__ import annotations

from decimal import Decimal

_MONEY = Decimal("0.01")
_PCT = Decimal("0.0001")
_RATIO = Decimal("0.01")
_QTY = Decimal("0.00000001")
_HUNDRED = Decimal("100")
_ZERO = Decimal("0")
_ONE = Decimal("1")
