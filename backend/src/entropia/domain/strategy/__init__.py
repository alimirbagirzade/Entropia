"""Strategy domain layer (Stage 3b).

Strategy root is a mutable entity_registry row that tracks a strategy's
published revisions. Revisions are immutable snapshots of StrategyConfig.
The editor draft holds in-progress changes (may be partial/invalid).

Binding rules:
- L1 FK Safety: insert root → flush → children
- Disabled Sections: filtered to zero in saved revision
- Package Pin Granularity: (root_id, revision_id, content_hash)
"""
