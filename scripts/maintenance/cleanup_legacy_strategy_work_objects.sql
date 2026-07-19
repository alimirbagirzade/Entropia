-- Cleanup: legacy bare-work-object "strategy" roots (pre-#314 debris).
--
-- Before PR #314 the Mainboard "Add Strategy" flow created a generic work object
-- (entity id prefix `wo_`, work_object_root.object_kind = 'strategy') WITHOUT a
-- strategy_root / strategy_revision detail. The Strategy editor can never load
-- such a root (its read endpoints answer STRATEGY_NOT_FOUND /
-- STRATEGY_REVISION_NOT_FOUND). #314 switched the flow to the editor family
-- (`strat_` roots that carry a strategy_root detail), leaving these bare roots as
-- orphan debris that surfaces in no active projection.
--
-- This script SOFT-DELETES (reversible) only the UNATTACHED orphans — a bare
-- `strategy` work-object root with no strategy_root detail and no Mainboard item.
-- ATTACHED orphans are intentionally left alone: delete those from the Mainboard
-- with the row's × (soft-delete → Trash) so the composition hash is recomputed
-- and an audit/outbox/trash entry is written by the application command.
--
-- Idempotent (only flips rows still `active`). Reversible: restore by setting
-- deletion_state back to 'active' for the affected entity_ids.
--
-- Preview first (no writes):
--   SELECT wo.entity_id, er.deletion_state
--   FROM work_object_root wo
--   JOIN entity_registry er ON er.entity_id = wo.entity_id
--   LEFT JOIN strategy_root sr ON sr.entity_id = wo.entity_id
--   WHERE wo.object_kind = 'strategy' AND sr.entity_id IS NULL
--     AND er.deletion_state = 'active'
--     AND NOT EXISTS (
--       SELECT 1 FROM mainboard_working_item m WHERE m.work_object_root_id = wo.entity_id
--     );

UPDATE entity_registry er
SET deletion_state = 'soft_deleted', row_version = row_version + 1
WHERE er.deletion_state = 'active'
  AND er.entity_id IN (
    SELECT wo.entity_id
    FROM work_object_root wo
    LEFT JOIN strategy_root sr ON sr.entity_id = wo.entity_id
    WHERE wo.object_kind = 'strategy' AND sr.entity_id IS NULL
  )
  AND NOT EXISTS (
    SELECT 1 FROM mainboard_working_item m WHERE m.work_object_root_id = er.entity_id
  )
RETURNING entity_id, deletion_state, row_version;
