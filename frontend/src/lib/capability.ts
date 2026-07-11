// Future Dev capability registry data access (doc 22): the read-only registry
// list/detail and Graphic View overview projections open to any authenticated
// principal, plus the Admin-only lifecycle transition. The registry is the
// SERVER-SIDE source of truth for what Future Dev may do — never a frontend
// feature flag (doc 22 §2, §15); UI visibility is never authorization (§3):
// the route re-checks Admin and the command re-checks it at the service.
//
// Query keys live under ["capabilities"] — the registry has no dedicated SSE
// event; rows refresh via this page's own mutations and the `resource.changed`
// full sweep (lib/sse.ts EVENT_QUERY_KEYS catch-all).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/queries/capability.py and
// application/commands/capability.py verbatim)
// ---------------------------------------------------------------------------

export interface Capability {
  capability_key: string;
  title: string;
  menu_path: string;
  lifecycle_state: string;
  is_operational: boolean;
  ui_surface_version: string;
  domain_contract_version: string | null;
  registry_version: number;
  enabled_at: string | null;
  retirement_at: string | null;
  status_message: string;
}

export interface CapabilityListResponse {
  capabilities: Capability[];
  count: number;
}

// A gate entry is a plain boolean or an object carrying `complete` plus
// free-form server-side fields (notes); anything else counts as incomplete
// (domain/capability/lifecycle.py `_gate_complete`).
export type GateEntry = boolean | { complete?: boolean; [key: string]: unknown };

export interface DependencySnapshot {
  gates?: Record<string, GateEntry>;
  [key: string]: unknown;
}

export interface CapabilityDetail extends Capability {
  dependency_snapshot: DependencySnapshot;
  changed_by_actor_id: string | null;
  change_reason: string | null;
}

export interface GraphicViewCard {
  title: string;
  text: string;
}

export interface GraphicViewOverview {
  capability_key: string;
  title: string;
  lifecycle_state: string;
  is_operational: boolean;
  registry_version: number;
  intro: string;
  cards: GraphicViewCard[];
  status_message: string;
}

export interface CapabilityTransitionResult {
  capability_id: string;
  capability_key: string;
  title: string;
  menu_path: string;
  lifecycle_state: string;
  ui_surface_version: string;
  domain_contract_version: string | null;
  registry_version: number;
  enabled_at: string | null;
  retirement_at: string | null;
  activation_event_id: string;
  correlation_id: string | null;
}

// ---------------------------------------------------------------------------
// Server-owned lifecycle taxonomy (domain/capability/{enums,lifecycle}.py,
// doc 22 §9.1/§9.2) mirrored for the composer option lists. The server
// re-validates every edge and every gate on dispatch — these constants
// hydrate <select>s/checklists and are never client authority.
// ---------------------------------------------------------------------------

export const CAPABILITY_STATES = [
  "placeholder",
  "designed",
  "internal",
  "shadow",
  "limited",
  "active",
  "retired",
] as const;
export type CapabilityStateKey = (typeof CAPABILITY_STATES)[number];

// Legal edges (doc 22 §9.1): staged forward progression, explicit rollback
// downgrades, retirement only from an operational state. Retired is terminal.
export const ALLOWED_TRANSITIONS: Record<CapabilityStateKey, readonly CapabilityStateKey[]> = {
  placeholder: ["designed"],
  designed: ["internal"],
  internal: ["shadow"],
  shadow: ["limited"],
  limited: ["active", "shadow", "retired"],
  active: ["limited", "retired"],
  retired: [],
};

export function allowedTargets(state: string): readonly CapabilityStateKey[] {
  return ALLOWED_TRANSITIONS[state as CapabilityStateKey] ?? [];
}

// The seven activation gates (doc 22 §9.2) recorded in dependency_snapshot.
export const ACTIVATION_GATES = [
  "domain",
  "data",
  "policy",
  "ui",
  "backend",
  "verification",
  "rollback",
] as const;

// Badge tones only — the wire state stays a plain string.
export const STATE_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  active: "ok",
  limited: "warn",
  retired: "down",
};

// Mirrors the server's completeness reading: true, or an object whose
// `complete` is exactly true.
export function gateComplete(entry: GateEntry | undefined): boolean {
  if (entry === true) return true;
  return typeof entry === "object" && entry !== null && entry.complete === true;
}

// Merge an Admin's gate checklist back into the stored snapshot WITHOUT
// clobbering server-side note objects: object entries keep their fields and
// only `complete` flips; plain entries become booleans.
export function buildGatesSnapshot(
  original: DependencySnapshot,
  draft: Record<string, boolean>,
): DependencySnapshot {
  const originalGates = original.gates ?? {};
  // Start from the stored record so non-canonical server-side keys survive.
  const gates: Record<string, GateEntry> = { ...originalGates };
  for (const gate of ACTIVATION_GATES) {
    const entry = originalGates[gate];
    const complete = draft[gate] ?? gateComplete(entry);
    gates[gate] = typeof entry === "object" && entry !== null ? { ...entry, complete } : complete;
  }
  return { ...original, gates };
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useCapabilities() {
  return useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilityListResponse>("/capabilities"),
  });
}

export function useCapability(capabilityKey: string | null) {
  return useQuery({
    queryKey: ["capabilities", "detail", capabilityKey],
    queryFn: () =>
      api.get<CapabilityDetail>(`/capabilities/${encodeURIComponent(capabilityKey ?? "")}`),
    enabled: capabilityKey !== null,
  });
}

export function useGraphicViewOverview() {
  return useQuery({
    queryKey: ["capabilities", "graphic-view-overview"],
    queryFn: () => api.get<GraphicViewOverview>("/future-dev/graphic_view/overview"),
  });
}

// ---------------------------------------------------------------------------
// Mutation — Admin lifecycle transition (POST .../lifecycle-transitions)
// ---------------------------------------------------------------------------

export interface TransitionInput {
  capability_key: string;
  to_state: string;
  reason: string;
  expected_registry_version: number;
  dependency_snapshot?: DependencySnapshot;
}

// OCC: expected_registry_version carries the projection's registry_version so
// a stale tab gets the 409 envelope verbatim instead of clobbering a
// concurrent change. The command REQUIRES an Idempotency-Key — one fresh UUID
// per attempt (a retry after a rejection is a new decision, not a replay).
// Omitting dependency_snapshot keeps the server-stored gate record untouched.
export function useTransitionCapability() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TransitionInput) =>
      apiRequest<CapabilityTransitionResult>(
        `/capabilities/${encodeURIComponent(input.capability_key)}/lifecycle-transitions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            to_state: input.to_state,
            reason: input.reason,
            expected_registry_version: input.expected_registry_version,
            ...(input.dependency_snapshot !== undefined
              ? { dependency_snapshot: input.dependency_snapshot }
              : {}),
          },
        },
      ),
    onSuccess: () => {
      // The registry row changed AND the command emitted an audit event.
      void queryClient.invalidateQueries({ queryKey: ["capabilities"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Operational commands (doc 22 §8, §10 — POST /view-datasets/query +
// POST /analysis-artifacts). Both are Limited/Active-gated SERVER-side: the
// command re-checks the registry state on every dispatch, so an inactive
// capability returns CAPABILITY_NOT_ACTIVE and creates nothing (CR-09,
// FD-02). The UI never pre-gates on its cached state — a denial renders the
// canonical envelope verbatim. Creates carry NO OCC token (there is no head
// to race); each attempt sends one fresh Idempotency-Key. On success each
// output now appears in its owner-scoped history (doc 22 §7), so the mutation
// invalidates the matching history key alongside ["audit"].
// ---------------------------------------------------------------------------

// Mirror of commands/capability.py ANALYSIS_ARTIFACT_CAPABILITY (doc 22
// §10.3-§10.6): which capability gates each artifact type. Hydration-only —
// the server re-derives the gate from artifact_type on every dispatch.
export const ANALYSIS_ARTIFACT_CAPABILITY: Record<string, string> = {
  backtest_review: "backtest_review",
  monte_carlo: "backtest_review",
  walk_forward: "backtest_review",
  signal_intelligence: "signal_intelligence",
  regime_research: "regime_research",
  parameter_fields: "parameter_fields",
  sensitivity: "parameter_fields",
};

// Stable composer option order — matches the server's sorted `allowed` list
// on an unknown-type rejection.
export const ANALYSIS_ARTIFACT_TYPES = Object.keys(ANALYSIS_ARTIFACT_CAPABILITY).sort();

export interface ViewDatasetResult {
  view_dataset_id: string;
  capability_key: string;
  source_manifest_refs: string[];
  series_refs: string[];
  marker_refs: string[];
  range_spec: Record<string, unknown> | null;
  schema_version: string;
  correlation_id: string | null;
}

export interface AnalysisArtifactResult {
  artifact_id: string;
  artifact_type: string;
  capability_key: string;
  input_manifest_refs: string[];
  method_version: string;
  output_ref: string | null;
  correlation_id: string | null;
}

export interface ViewDatasetQueryInput {
  source_manifest_refs: string[];
  schema_version: string;
  series_refs?: string[];
  marker_refs?: string[];
  range_spec?: Record<string, unknown>;
}

export interface AnalysisArtifactInput {
  artifact_type: string;
  input_manifest_refs: string[];
  method_version: string;
  output_ref?: string;
}

// Prepare a renderer-independent View Dataset from pinned immutable source
// refs (graphic_view-gated, doc 22 §10.2, FD-04).
export function useQueryViewDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ViewDatasetQueryInput) =>
      apiRequest<ViewDatasetResult>("/view-datasets/query", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: {
          source_manifest_refs: input.source_manifest_refs,
          schema_version: input.schema_version,
          ...(input.series_refs !== undefined ? { series_refs: input.series_refs } : {}),
          ...(input.marker_refs !== undefined ? { marker_refs: input.marker_refs } : {}),
          ...(input.range_spec !== undefined ? { range_spec: input.range_spec } : {}),
        },
      }),
    onSuccess: () => {
      // The prepared dataset now appears in the owner's View Dataset history.
      void queryClient.invalidateQueries({ queryKey: ["view-datasets"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Create one immutable Analysis Artifact (doc 22 §10.3-§10.6, FD-05/09) —
// gated by the capability the server derives from artifact_type.
export function useCreateAnalysisArtifact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AnalysisArtifactInput) =>
      apiRequest<AnalysisArtifactResult>("/analysis-artifacts", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: {
          artifact_type: input.artifact_type,
          input_manifest_refs: input.input_manifest_refs,
          method_version: input.method_version,
          ...(input.output_ref !== undefined ? { output_ref: input.output_ref } : {}),
        },
      }),
    onSuccess: () => {
      // The new artifact now appears in the owner's Analysis Artifact history.
      void queryClient.invalidateQueries({ queryKey: ["analysis-artifacts"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Operational output history (doc 22 §7, §13 — GET /view-datasets[/{id}] +
// GET /analysis-artifacts[/{id}]). The read surface for the outputs the two
// POSTs above create: an owner-scoped, ACTIVE-only, newest-first keyset page
// plus an owner-scoped detail. A principal sees only what it produced; a
// cross-owner or soft-deleted id is a canonical not-found (never leaks). Keys
// live under ["view-datasets"] / ["analysis-artifacts"] — no dedicated SSE
// event, swept by `resource.changed` and by the owning POST's invalidation.
// An empty page is the futureDevNoHistory.empty state (doc 22 §7), never a
// fabricated row. Wire types mirror queries/capability.py row/detail verbatim.
// ---------------------------------------------------------------------------

export interface OutputHistoryMeta {
  cursor: string | null;
  has_more: boolean;
  limit: number;
}

export interface ViewDatasetRow {
  view_dataset_id: string;
  capability_key: string;
  schema_version: string;
  source_manifest_refs: string[];
  series_refs: string[];
  marker_refs: string[];
  range_spec: Record<string, unknown> | null;
  deletion_state: string;
  row_version: number;
  created_at: string | null;
}

export interface ViewDatasetDetail extends ViewDatasetRow {
  owner_principal_id: string | null;
  created_by_principal_id: string | null;
}

export interface ViewDatasetHistoryPage {
  data: ViewDatasetRow[];
  meta: OutputHistoryMeta;
}

export interface AnalysisArtifactRow {
  artifact_id: string;
  artifact_type: string;
  capability_key: string;
  input_manifest_refs: string[];
  method_version: string;
  output_ref: string | null;
  deletion_state: string;
  row_version: number;
  created_at: string | null;
}

export interface AnalysisArtifactDetail extends AnalysisArtifactRow {
  owner_principal_id: string | null;
  created_by_principal_id: string | null;
}

export interface AnalysisArtifactHistoryPage {
  data: AnalysisArtifactRow[];
  // The list meta echoes the normalized artifact_type filter (null when unset).
  meta: OutputHistoryMeta & { artifact_type: string | null };
}

// Owner-scoped View Dataset history — a forward keyset page. A null cursor is
// page one; the placeholder keeps the current table mounted across a page flip.
export function useViewDatasetHistory(cursor: string | null) {
  return useQuery({
    queryKey: ["view-datasets", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<ViewDatasetHistoryPage>(`/view-datasets${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

export function useViewDataset(viewDatasetId: string | null) {
  return useQuery({
    queryKey: ["view-datasets", "detail", viewDatasetId],
    queryFn: () =>
      api.get<ViewDatasetDetail>(`/view-datasets/${encodeURIComponent(viewDatasetId ?? "")}`),
    enabled: viewDatasetId !== null,
  });
}

// Owner-scoped Analysis Artifact history, optionally narrowed to one type.
export function useAnalysisArtifactHistory(artifactType: string | null, cursor: string | null) {
  return useQuery({
    queryKey: ["analysis-artifacts", artifactType, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (artifactType !== null) params.set("artifact_type", artifactType);
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<AnalysisArtifactHistoryPage>(`/analysis-artifacts${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

export function useAnalysisArtifact(artifactId: string | null) {
  return useQuery({
    queryKey: ["analysis-artifacts", "detail", artifactId],
    queryFn: () =>
      api.get<AnalysisArtifactDetail>(`/analysis-artifacts/${encodeURIComponent(artifactId ?? "")}`),
    enabled: artifactId !== null,
  });
}
