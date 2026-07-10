// Mainboard composition plane (doc 01). The backend is the source of truth for
// the workspace projection; this module never keeps a client-side array as
// authority — every mutation returns the canonical row and the page rehydrates
// from ["mainboard","default"] (doc 01 §14 rule 1).
//
// Endpoint OCC/Idempotency contract (empirical, routes/mainboard.py):
//   POST /external-work-object-drafts/{kind}  — NO Idempotency-Key, NO OCC
//        (transient opener; the real object is created in the TS/TL workbench).
//   POST /work-objects                        — Idempotency-Key; NO OCC.
//   POST /work-objects/{root}/revisions       — Idempotency-Key; BODY-form OCC
//        expected_head_revision_id (STR, optional — the head guard).
//   POST /mainboards/{ws}/items (attach)      — Idempotency-Key; NO OCC.
//   PATCH /mainboard-items/{item}             — Idempotency-Key; BODY-form OCC
//        expected_row_version (INT, REQUIRED; the route prefers body over
//        If-Match). Only pin_revision / set_enabled change the composition hash.
//   POST /mainboards/{ws}/snapshots           — Idempotency-Key; NO OCC.
//   DELETE /work-objects/{root}               — Idempotency-Key; NO OCC.
//
// No dedicated SSE event exists for the Mainboard — resource.changed sweeps the
// ["mainboard"] key. Mutations invalidate explicitly for immediacy.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// The read hook + item/workspace projection types already live in lib/backtest.ts
// (its RUN flow was the first consumer). Re-export so the page has one import.
export { useDefaultMainboard } from "./backtest";
export type { DefaultMainboard, MainboardItem } from "./backtest";

// --------------------------------------------------------------------------- //
// Taxonomy (mirrors domain/mainboard/enums.py — hydration only, server         //
// re-validates every command).                                                //
// --------------------------------------------------------------------------- //

// The single canonical kind facet for both a work object's object_kind and a
// working item's item_kind (CR-01). Strategy is internal; Trading Signal and
// Trade Log are EXTERNAL work objects, never a PackageKind.
export const MAINBOARD_ITEM_KIND_LABELS: Record<string, string> = {
  strategy: "Strategy",
  trading_signal: "Trading Signal",
  trade_log: "Trade Log",
};

// Add Outsource Signal opener kinds (the two external work-object kinds). Each
// carries the workbench route the opener deep-links to (CR-01).
export const EXTERNAL_DRAFT_KINDS: ReadonlyArray<{
  value: string;
  label: string;
  path: string;
}> = [
  { value: "trading_signal", label: "Trading Signal", path: "/trading-signal" },
  { value: "trade_log", label: "Trade Log", path: "/trade-log" },
];

export type PatchIntent = "pin_revision" | "set_enabled" | "reorder" | "set_label";

// Ready status line text (doc 01 §6.2 — Mainboard-owned text catalog). The
// backend query currently emits "not_ready" as a placeholder; the full state
// set is honored here so the line is correct the moment readiness lands.
const READY_STATUS_TEXT: Record<string, string> = {
  not_ready: "Backtest Ready: Not Ready",
  checking: "Backtest Ready: Checking current composition…",
  ready: "Backtest Ready: Ready",
  ready_with_warnings: "Backtest Ready: Ready with warnings",
  failed: "Backtest Ready: Not Ready",
  stale: "Changes detected. Run Backtest Ready Check again.",
};

export function readyStatusText(state: string): string {
  return READY_STATUS_TEXT[state] ?? "Backtest Ready: Not Ready";
}

export function readyStatusTone(state: string): "ok" | "warn" | "down" {
  if (state === "ready") return "ok";
  if (state === "ready_with_warnings" || state === "stale") return "warn";
  return "down";
}

export function itemKindLabel(kind: string): string {
  return MAINBOARD_ITEM_KIND_LABELS[kind] ?? kind;
}

// --------------------------------------------------------------------------- //
// Wire result types (mirror the command return dicts verbatim).               //
// --------------------------------------------------------------------------- //

export interface ExternalDraft {
  draft_id: string;
  kind: string;
  unsaved: boolean;
}

export interface WorkObjectResult {
  root_id: string;
  revision_id: string;
  revision_no: number;
  object_kind: string;
  row_version: number;
}

// A revision append omits object_kind (the root's kind is immutable).
export interface WorkObjectRevisionResult {
  root_id: string;
  revision_id: string;
  revision_no: number;
  row_version: number;
}

// attach + patch both return _item_projection(item) + composition_hash.
export interface MainboardItemResult {
  item_id: string;
  item_kind: string;
  work_object_root_id: string;
  pinned_revision_id: string | null;
  position_index: number;
  is_enabled: boolean;
  display_label_override: string | null;
  row_version: number;
  composition_hash: string | null;
}

export interface SnapshotResult {
  snapshot_id: string;
  composition_hash: string;
  item_count: number;
}

export interface SoftDeleteResult {
  root_id: string;
  deletion_state: string;
}

// --------------------------------------------------------------------------- //
// Mutations.                                                                   //
// --------------------------------------------------------------------------- //

function freshIdempotency(): Record<string, string> {
  return { "Idempotency-Key": crypto.randomUUID() };
}

// Add Outsource Signal opener. Transient: no Idempotency-Key, no OCC, no
// invalidation (nothing is persisted until the workbench save).
export function useStartExternalDraft() {
  return useMutation({
    mutationFn: (kind: string) =>
      api.post<ExternalDraft>(
        `/external-work-object-drafts/${encodeURIComponent(kind)}`,
      ),
  });
}

export interface CreateWorkObjectInput {
  object_kind: string;
  payload: Record<string, unknown>;
  source_provenance?: Record<string, unknown> | null;
  available_time?: string | null;
}

// Create a work-object root + first immutable revision. No board item is
// attached and no composition changes — only the audit trail moves.
export function useCreateWorkObject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateWorkObjectInput) =>
      apiRequest<WorkObjectResult>("/work-objects", {
        method: "POST",
        body: {
          object_kind: input.object_kind,
          payload: input.payload,
          source_provenance: input.source_provenance ?? null,
          available_time: input.available_time ?? null,
        },
        headers: freshIdempotency(),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export interface CreateRevisionInput {
  rootId: string;
  payload: Record<string, unknown>;
  source_provenance?: Record<string, unknown> | null;
  available_time?: string | null;
  expectedHeadRevisionId?: string | null;
}

// Append revision N+1 to an existing root. OCC travels BODY-form as
// expected_head_revision_id (the head guard; server-optional).
export function useCreateWorkObjectRevision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateRevisionInput) =>
      apiRequest<WorkObjectRevisionResult>(
        `/work-objects/${encodeURIComponent(input.rootId)}/revisions`,
        {
          method: "POST",
          body: {
            payload: input.payload,
            source_provenance: input.source_provenance ?? null,
            available_time: input.available_time ?? null,
            expected_head_revision_id: input.expectedHeadRevisionId ?? null,
          },
          headers: freshIdempotency(),
        },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export interface AttachItemInput {
  workspaceId: string;
  root_id: string;
  revision_id: string;
  item_kind?: string | null;
  position_index?: number | null;
}

// Attach a work object onto the workspace as a new enabled item. The item kind
// is server-derived from the root (CR-01); a divergent client value is
// rejected. Composition changes -> prior Ready report goes stale.
export function useAttachItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: AttachItemInput) =>
      apiRequest<MainboardItemResult>(
        `/mainboards/${encodeURIComponent(input.workspaceId)}/items`,
        {
          method: "POST",
          body: {
            root_id: input.root_id,
            revision_id: input.revision_id,
            item_kind: input.item_kind ?? null,
            position_index: input.position_index ?? null,
          },
          headers: freshIdempotency(),
        },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["mainboard"] });
      void qc.invalidateQueries({ queryKey: ["readiness"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export interface PatchItemInput {
  itemId: string;
  intent: PatchIntent;
  expectedRowVersion: number;
  revision_id?: string;
  is_enabled?: boolean;
  position_index?: number;
  display_label_override?: string;
}

// Apply exactly one intent to a working item. expected_row_version is REQUIRED
// (stale -> ROW_VERSION_CONFLICT). Only the field the intent needs is sent.
export function usePatchItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PatchItemInput) => {
      const body: Record<string, unknown> = {
        intent: input.intent,
        expected_row_version: input.expectedRowVersion,
      };
      if (input.revision_id !== undefined) body.revision_id = input.revision_id;
      if (input.is_enabled !== undefined) body.is_enabled = input.is_enabled;
      if (input.position_index !== undefined) body.position_index = input.position_index;
      if (input.display_label_override !== undefined) {
        body.display_label_override = input.display_label_override;
      }
      return apiRequest<MainboardItemResult>(
        `/mainboard-items/${encodeURIComponent(input.itemId)}`,
        { method: "PATCH", body, headers: freshIdempotency() },
      );
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["mainboard"] });
      void qc.invalidateQueries({ queryKey: ["readiness"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Freeze the current ENABLED composition as an immutable snapshot. This does
// not mutate the board, so it invalidates only the audit trail.
export function useCreateSnapshot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (workspaceId: string) =>
      apiRequest<SnapshotResult>(
        `/mainboards/${encodeURIComponent(workspaceId)}/snapshots`,
        { method: "POST", headers: freshIdempotency() },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Soft-delete a work object root. The active item leaves the board and a Trash
// entry is created in the same tx.
export function useSoftDeleteWorkObject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rootId: string) =>
      apiRequest<SoftDeleteResult>(
        `/work-objects/${encodeURIComponent(rootId)}`,
        { method: "DELETE", headers: freshIdempotency() },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["mainboard"] });
      void qc.invalidateQueries({ queryKey: ["readiness"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
      void qc.invalidateQueries({ queryKey: ["trash"] });
    },
  });
}
