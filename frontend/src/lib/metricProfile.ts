// Arrange Metrics data access (Stage 5c, doc 17): the metric-definition registry,
// the caller's resolved Result View Metric Profile, and the single Apply/Lock/
// Unlock revision append. PRESENTATION-ONLY (CR-07): nothing here ever touches a
// Backtest Result or recomputes a metric — the profile only drives which persisted
// values a Result view shows, and in what order.
//
// There is no dedicated SSE event for profile changes, so these keys are swept
// only by the `resource.changed` catch-all full refresh (lib/sse.ts); the Apply
// mutation invalidates ["metric-profile"] directly for same-tab freshness.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/queries/metric_profile.py projections)
// ---------------------------------------------------------------------------

export interface MetricDefinition {
  metric_code: string;
  label: string;
  unit: string | null;
  value_format: string | null;
  availability_status: string;
  display_order: number;
  formula_version: string | null;
  description: string | null;
  selectable: boolean;
}

export interface MetricRegistry {
  registry_version: string;
  metric_definitions: MetricDefinition[];
}

export interface ResolvedMetricProfile {
  profile_id: string;
  scope: string;
  is_personal: boolean;
  current_revision_id: string | null;
  selected_metric_codes: string[];
  display_order: string[];
  is_locked: boolean;
  registry_version: string;
  selected_metric_count: number;
  // The id the client POSTs a revision to. "system_default" until the first
  // Apply forks a personal profile root (doc 17 §8.1).
  editable_profile_id: string;
}

export interface MetricProfileRevision {
  profile_id: string;
  scope: string;
  is_personal: boolean;
  current_revision_id: string | null;
  profile_revision_id: string;
  revision_no: number;
  selected_metric_codes: string[];
  display_order: string[];
  is_locked: boolean;
  registry_version: string;
  row_version: number;
  // Canonical transition reason the server derived: apply / lock / unlock.
  reason: string;
  selected_metric_count: number;
}

export interface ApplyMetricProfileInput {
  profile_id: string;
  selected_metric_codes: string[];
  is_locked: boolean;
  // OCC guard: the revision id the client last saw; a mismatch is a 409
  // METRIC_PROFILE_STALE surfaced verbatim, never silently overwritten.
  expected_profile_revision_id: string | null;
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useMetricDefinitions() {
  return useQuery({
    queryKey: ["metric-definitions"],
    queryFn: () => api.get<MetricRegistry>("/metric-definitions"),
    // The registry is versioned server config; it only moves with a deploy.
    staleTime: 5 * 60_000,
  });
}

export function useResolvedMetricProfile() {
  return useQuery({
    queryKey: ["metric-profile", "resolved"],
    queryFn: () => api.get<ResolvedMetricProfile>("/metric-profiles/resolved"),
  });
}

// ---------------------------------------------------------------------------
// Mutation: Apply / Lock / Unlock are ALL the same append (doc 17 §7) — the
// server derives the transition from `is_locked` + the selection.
// ---------------------------------------------------------------------------

export function useApplyMetricProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ApplyMetricProfileInput) =>
      // The OCC guard blocks a stale overwrite, but a network retry of the same
      // Apply still appends a duplicate revision unless the server can dedup it —
      // so send a fresh Idempotency-Key per attempt (the route reads the header).
      apiRequest<MetricProfileRevision>(
        `/metric-profiles/${encodeURIComponent(input.profile_id)}/revisions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            selected_metric_codes: input.selected_metric_codes,
            is_locked: input.is_locked,
            expected_profile_revision_id: input.expected_profile_revision_id,
          },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["metric-profile"] });
    },
  });
}
