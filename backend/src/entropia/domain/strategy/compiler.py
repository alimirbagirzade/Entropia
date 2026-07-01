"""Strategy configuration validation & compilation (Stage 3b, §3.1; doc 02 §7.1).

- validate_strategy_config: Parse + structural + semantic validation, return issues
- validate_semantics: Cross-field business rules (sizing exclusivity, trigger source)
- filter_disabled_sections: Remove disabled blocks from payload (Binding Decision #2)
- compute_config_hash: Deterministic SHA-256 of canonical payload
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from entropia.domain.strategy.config import StrategyConfig

# Machine-coded semantic issue codes (map to typed API errors in the command).
CODE_SIZING_NOT_EXCLUSIVE = "SIZING_METHOD_NOT_EXCLUSIVE"
CODE_TRIGGER_CONDITION_REQUIRED = "TRIGGER_SOURCE_CONDITION_REQUIRED"

_CONDITION_BEARING_TRIGGERS = frozenset(
    {"indicator_native_trigger_plus_condition", "indicator_output_plus_condition"}
)


def validate_strategy_config(
    payload: dict[str, Any],
) -> tuple[StrategyConfig | None, list[dict[str, Any]]]:
    """Parse + structurally + semantically validate a draft StrategyConfig.

    Args:
        payload: Draft JSONB payload (may be partial/invalid)

    Returns:
        ``(config, issues)``. ``config`` is the parsed StrategyConfig, or ``None``
        if the payload failed structural (Pydantic) validation. ``issues`` is a
        list of ``{"field", "code", "message"}`` — structural issues when config
        is ``None``, otherwise the semantic (cross-field) blockers found on the
        structurally-valid config. A non-empty ``issues`` list means the config
        must NOT be persisted as an immutable revision (doc 02 §7.1 step 5).

    Binding Decision #2: disabled sections are filtered OUT before parsing, so a
    returned config contains only enabled blocks.
    """
    filtered_payload = filter_disabled_sections(payload)

    try:
        config = StrategyConfig(**filtered_payload)
    except PydanticValidationError as e:
        errors: list[dict[str, Any]] = []
        for error in e.errors():
            loc = error.get("loc", ("unknown",))
            field_path = ".".join(str(x) for x in loc)
            errors.append(
                {
                    "field": field_path,
                    "code": "STRATEGY_VALIDATION_ERROR",
                    "message": error.get("msg", "Unknown error"),
                }
            )
        return None, errors

    return config, validate_semantics(config)


def validate_semantics(config: StrategyConfig) -> list[dict[str, Any]]:
    """Cross-field business-rule validation over a structurally-valid config.

    Enforces the binding rules that a single-field type check cannot express:

    * **Sizing exclusivity** (doc 02 §6, AT-12): exactly one Position Sizing
      method sub-config may be populated. More than one -> not exclusive.
    * **Trigger-source-conditional** (doc 02 §3, AT-05): an enabled indicator
      block whose trigger source is a ``*_plus_condition`` variant must carry at
      least one enabled Condition block; a Native-only trigger needs none.
    """
    issues: list[dict[str, Any]] = []

    sizing = config.position_sizing
    populated = [
        name
        for name, value in (
            ("base_position_size", sizing.base_position_size),
            ("risk_based", sizing.risk_based),
            ("formula_based", sizing.formula_based),
        )
        if value is not None
    ]
    if len(populated) > 1:
        issues.append(
            {
                "field": "position_sizing",
                "code": CODE_SIZING_NOT_EXCLUSIVE,
                "message": "Select exactly one Position Sizing method.",
            }
        )

    for index, block in enumerate(config.position_entry_logic.indicator_blocks):
        if not block.enabled:
            continue
        if block.trigger_source not in _CONDITION_BEARING_TRIGGERS:
            continue
        active_conditions = [cb for cb in (block.condition_blocks or []) if cb.enabled]
        if not active_conditions:
            issues.append(
                {
                    "field": f"position_entry_logic.indicator_blocks.{index}.condition_blocks",
                    "code": CODE_TRIGGER_CONDITION_REQUIRED,
                    "message": (
                        "Add at least one compatible Condition for the selected Trigger Source."
                    ),
                }
            )

    return issues


def filter_disabled_sections(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove disabled blocks from payload (Binding Decision #2).

    Disabled sections must not appear in the saved revision, ensuring:
    - Immutable revision never has ambiguous disabled/enabled mix
    - Engine manifest is clean and compact
    - No alternative disabled clauses to pick

    Args:
        payload: Draft JSONB payload

    Returns:
        Filtered payload with disabled sections removed
    """
    filtered = dict(payload)

    # Filter position_entry_logic indicator_blocks
    if "position_entry_logic" in filtered and isinstance(filtered["position_entry_logic"], dict):
        entry_logic = dict(filtered["position_entry_logic"])
        if "indicator_blocks" in entry_logic and isinstance(entry_logic["indicator_blocks"], list):
            entry_logic["indicator_blocks"] = [
                block
                for block in entry_logic["indicator_blocks"]
                if isinstance(block, dict) and block.get("enabled", True)
            ]
            filtered["position_entry_logic"] = entry_logic

    # Filter position_exit_logic indicator_blocks
    if "position_exit_logic" in filtered and isinstance(filtered["position_exit_logic"], dict):
        exit_logic = dict(filtered["position_exit_logic"])
        if "indicator_blocks" in exit_logic and isinstance(exit_logic["indicator_blocks"], list):
            exit_logic["indicator_blocks"] = [
                block
                for block in exit_logic["indicator_blocks"]
                if isinstance(block, dict) and block.get("enabled", True)
            ]
            filtered["position_exit_logic"] = exit_logic

    # Filter protection_stop_logic: only keep enabled stops (Binding Decision #2)
    if "protection_stop_logic" in filtered and isinstance(filtered["protection_stop_logic"], dict):
        stop_logic = dict(filtered["protection_stop_logic"])
        filtered_stops = {}
        for stop_key in ("percentage_stop", "trailing_stop", "absolute_stop"):
            stop = stop_logic.get(stop_key)
            if isinstance(stop, dict) and stop.get("enabled", False):
                filtered_stops[stop_key] = stop
        filtered["protection_stop_logic"] = filtered_stops if filtered_stops else None

    # Filter scaling_logic: if enabled=false, entire section becomes None
    if (
        "scaling_logic" in filtered
        and isinstance(filtered["scaling_logic"], dict)
        and not filtered["scaling_logic"].get("enabled", False)
    ):
        filtered["scaling_logic"] = None

    # Filter restrictions_filters: only keep enabled filters
    if "restrictions_filters" in filtered and isinstance(filtered["restrictions_filters"], dict):
        filters_logic = dict(filtered["restrictions_filters"])
        if "filters" in filters_logic and isinstance(filters_logic["filters"], list):
            filters_logic["filters"] = [
                f
                for f in filters_logic["filters"]
                if isinstance(f, dict) and f.get("enabled", True)
            ]
            filtered["restrictions_filters"] = filters_logic

    # Filter condition_blocks nested in indicator_blocks (recursively)
    filtered = _filter_condition_blocks_recursive(filtered)

    return filtered


def _filter_condition_blocks_recursive(payload: dict[str, Any]) -> dict[str, Any]:
    """Recursively filter disabled condition blocks from indicator blocks."""
    filtered = dict(payload)

    for key in ["position_entry_logic", "position_exit_logic"]:
        if key in filtered and isinstance(filtered[key], dict):
            logic = dict(filtered[key])
            if "indicator_blocks" in logic and isinstance(logic["indicator_blocks"], list):
                filtered_blocks = []
                for block in logic["indicator_blocks"]:
                    if isinstance(block, dict):
                        filtered_block = dict(block)
                        if "condition_blocks" in filtered_block and isinstance(
                            filtered_block["condition_blocks"], list
                        ):
                            filtered_block["condition_blocks"] = [
                                cb
                                for cb in filtered_block["condition_blocks"]
                                if isinstance(cb, dict) and cb.get("enabled", True)
                            ]
                        filtered_blocks.append(filtered_block)
                    else:
                        filtered_blocks.append(block)
                logic["indicator_blocks"] = filtered_blocks
                filtered[key] = logic

    return filtered


def compute_config_hash(config: StrategyConfig) -> str:
    """Compute deterministic SHA-256 hash of config (Binding Decision #3).

    Uses canonical JSON serialization (sorted keys, no whitespace) to ensure
    identical configs always produce identical hashes, enabling:
    - Idempotent re-run detection (compare hashes, not object identity)
    - Audit trail immutability proof
    - Engine contract safety

    Args:
        config: Validated StrategyConfig

    Returns:
        SHA-256 hex digest (64 chars)
    """
    # Serialize to canonical form: use model_dump with sorted keys
    canonical_dict = config.model_dump(mode="json")

    # Convert to canonical JSON (sorted keys, no indent/whitespace)
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))

    # Hash
    hash_obj = hashlib.sha256(canonical_json.encode("utf-8"))
    return hash_obj.hexdigest()


def config_to_dict(config: StrategyConfig) -> dict[str, Any]:
    """Serialize StrategyConfig to dict for JSONB storage.

    Args:
        config: Validated StrategyConfig

    Returns:
        Dictionary representation (Decimal fields serialized as strings for JSON)
    """
    # Use model_dump with mode='json' to handle Decimal serialization
    return config.model_dump(mode="json")
