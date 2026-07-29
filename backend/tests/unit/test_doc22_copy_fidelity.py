"""Doc 22 §4.1 / §7 copy-fidelity guard (Future Dev placeholder audit).

Every string below is quoted from ``docs/spec/22_Entropia_V18_Future_Dev_Page_
Documentation_v1_1.md``. The placeholder surface is only honest if its wording
is: the §7 catalog is what tells a caller that NOTHING started (CR-09), so a
silent reword is a spec deviation, not a copy-edit. Pure constants — no DB.
"""

from __future__ import annotations

from entropia.domain.capability.baseline import (
    GRAPHIC_VIEW_CARDS,
    GRAPHIC_VIEW_INTRO,
    STATE_MESSAGES,
    UI_SURFACE_VERSION_V18,
)
from entropia.domain.capability.enums import CapabilityState
from entropia.shared.errors import (
    CapabilityAccessDeniedError,
    CapabilityDependencyMissingError,
    CapabilityNotActiveError,
    CapabilityStateStaleError,
)

# --- doc 22 §4.1 Graphic View Placeholder Page ------------------------------ #

DOC22_GRAPHIC_VIEW_INTRO = (
    "Graphic View is reserved for future chart and visual-review development. "
    "The page is intentionally a placeholder until the chart engine, event "
    "markers and structured visual datasets are implemented."
)

DOC22_GRAPHIC_VIEW_CARDS: tuple[tuple[str, str], ...] = (
    ("Price Chart", "Future: entry, exit, stop and scaling markers with S1 / S2 / S3 labels."),
    ("Equity Curve", "Future: total portfolio and strategy-level equity curves."),
    ("Drawdown Chart", "Future: time-based drawdown from equity peaks."),
    ("Exposure / Position Size", "Future: open position size, layer count and leverage impact."),
    (
        "Trade Distribution",
        "Future: profit/loss distribution, average win, average loss and outlier behavior.",
    ),
    ("Regime Overlay", "Future: trend, range, high-volatility and low-volatility context labels."),
)

# --- doc 22 §7 Information Content Catalog ---------------------------------- #

DOC22_OVERVIEW_PLACEHOLDER = (
    "This capability is currently a controlled Future Dev placeholder. It does "
    "not generate operational data, background jobs, execution actions, or "
    "persistent production output. Activation requires a completed domain "
    "contract, data lineage, policy, API/worker, audit, rollback, and "
    "acceptance-test gate."
)
DOC22_OVERVIEW_DESIGNED = (
    "The capability contract and dependencies are being defined. No operational "
    "command is available in this environment."
)
DOC22_OVERVIEW_LIMITED = (
    "This capability is active only for its approved limited scope. Eligibility, "
    "policy, history, and rollback information are shown before an operation can start."
)
DOC22_CAPABILITY_NOT_ACTIVE = (
    "This feature is not active in the current environment. No operation was started."
)
DOC22_CAPABILITY_DEPENDENCY_MISSING = (
    "Activation is blocked because required domain, data, policy, API, test, "
    "or rollback dependencies are incomplete. Review the capability dependency record."
)
DOC22_CAPABILITY_STATE_STALE = (
    "The capability state changed while this page was open. "
    "Refresh capability status before continuing."
)
DOC22_CAPABILITY_ACCESS_DENIED = (
    "You are not permitted to perform this capability operation or lifecycle transition."
)

# --- doc 22 §5 Interaction State Matrix recovery copy ----------------------- #

DOC22_INTERNAL = "Internal validation only. Output is not authoritative."
DOC22_SHADOW = "Shadow output does not affect production decisions."
DOC22_RETIRED = "This capability is retired. Historical records remain read-only."


def test_graphic_view_intro_is_doc22_verbatim() -> None:
    assert GRAPHIC_VIEW_INTRO == DOC22_GRAPHIC_VIEW_INTRO


def test_graphic_view_cards_are_doc22_verbatim_and_ordered() -> None:
    """Six static cards, doc order, doc wording — §4.2 forbids anything that
    reads like a computed metric."""
    shipped = tuple((card["title"], card["text"]) for card in GRAPHIC_VIEW_CARDS)
    assert shipped == DOC22_GRAPHIC_VIEW_CARDS


def test_state_messages_are_doc22_verbatim() -> None:
    assert STATE_MESSAGES[CapabilityState.PLACEHOLDER] == DOC22_OVERVIEW_PLACEHOLDER
    assert STATE_MESSAGES[CapabilityState.DESIGNED] == DOC22_OVERVIEW_DESIGNED
    assert STATE_MESSAGES[CapabilityState.INTERNAL] == DOC22_INTERNAL
    assert STATE_MESSAGES[CapabilityState.SHADOW] == DOC22_SHADOW
    assert STATE_MESSAGES[CapabilityState.LIMITED] == DOC22_OVERVIEW_LIMITED
    assert STATE_MESSAGES[CapabilityState.RETIRED] == DOC22_RETIRED


def test_every_lifecycle_state_has_status_copy() -> None:
    """No state may fall through to an empty/KeyError status message — the
    overview always explains what the caller is looking at."""
    assert set(STATE_MESSAGES) == set(CapabilityState)
    assert all(text.strip() for text in STATE_MESSAGES.values())


def test_capability_error_messages_are_doc22_verbatim() -> None:
    """The four §7 error-catalog texts. CAPABILITY_NOT_ACTIVE in particular must
    keep 'No operation was started.' — that sentence IS the CR-09 promise."""
    assert CapabilityNotActiveError.message == DOC22_CAPABILITY_NOT_ACTIVE
    assert CapabilityDependencyMissingError.message == DOC22_CAPABILITY_DEPENDENCY_MISSING
    assert CapabilityStateStaleError.message == DOC22_CAPABILITY_STATE_STALE
    assert CapabilityAccessDeniedError.message == DOC22_CAPABILITY_ACCESS_DENIED


def test_capability_error_codes_are_doc22_keys() -> None:
    assert CapabilityNotActiveError.code == "CAPABILITY_NOT_ACTIVE"
    assert CapabilityDependencyMissingError.code == "CAPABILITY_DEPENDENCY_MISSING"
    assert CapabilityStateStaleError.code == "CAPABILITY_STATE_STALE"
    assert CapabilityAccessDeniedError.code == "CAPABILITY_ACCESS_DENIED"


def test_ui_surface_version_pins_the_v18_placeholder_surface() -> None:
    """doc 22 §9 future_capability.ui_surface_version: the seeded rows declare
    which UI surface they were designed against — the V18 static placeholder."""
    assert UI_SURFACE_VERSION_V18 == "v18-placeholder"
