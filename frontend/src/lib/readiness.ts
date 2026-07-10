// Backtest Ready Check data access (doc 14 §4, §7, §9). Typed read models over the
// server-side immutable-snapshot validator: the composition's current readiness
// projection, an immutable report deep-link, and the run-check admission. The
// client never computes readiness — currentness (stale / superseded) and every
// issue string are recomputed/authored server-side and rendered verbatim (doc 14
// §3.2, §12.2). Ready Check has NO dedicated SSE event, so the ["readiness"]
// keys are swept by the resource.changed full refresh (lib/sse.ts); a run-check
// mutation also invalidates ["mainboard"] because the default-Mainboard
// ready_summary projection moves with it.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/{queries,commands}/readiness_check.py)
// ---------------------------------------------------------------------------

// A single immutable finding (ReadinessIssue.as_dict / query row). Severity is
// only "blocker" | "warning" — a PASS never produces an issue row (doc 14 §9.1),
// it lives in the summary pass_count. Rendered verbatim, never DOM-derived.
export interface ReadinessIssue {
  code: string;
  severity: string;
  scope: string;
  message: string;
  remediation: string | null;
  field_path: string | null;
  scope_id: string | null;
}

export interface ReadinessSummary {
  blocker_count: number;
  warning_count: number;
  pass_count: number;
  allocation_enabled: boolean;
}

// The immutable report projection (GET /readiness-reports/{id}, and the full
// shape of GET .../readiness when a report exists). ``state`` is the RECOMPUTED
// effective state; ``stored_state`` is what the row persisted; ``is_current``
// is false when the report is stale (composition changed) or superseded (a
// newer report exists) — the client shows a re-run hint, never edits the report.
export interface ReadinessReport {
  report_id: string;
  composition_id: string;
  snapshot_id: string | null;
  composition_fingerprint: string;
  current_fingerprint: string;
  stored_state: string;
  state: string;
  is_current: boolean;
  summary: ReadinessSummary;
  issues: ReadinessIssue[];
}

// GET .../readiness returns either the full report projection above, or — when
// the composition has never been checked — a minimal NOT_CHECKED shape with a
// null report_id and no summary/issues. Optional fields are present only in the
// report case (exactOptionalPropertyTypes is off, so undefined is fine).
export interface CurrentReadiness {
  composition_id: string;
  state: string;
  report_id: string | null;
  snapshot_id?: string | null;
  composition_fingerprint?: string;
  current_fingerprint?: string;
  stored_state?: string;
  is_current?: boolean;
  summary?: ReadinessSummary;
  issues?: ReadinessIssue[];
}

// POST .../readiness-checks return (a NEW immutable report every run, RC-18). It
// omits the read-time currentness fields (current_fingerprint/stored_state/
// is_current) — a just-created report is current by construction.
export interface RunCheckResult {
  report_id: string;
  composition_id: string;
  state: string;
  snapshot_id: string | null;
  composition_fingerprint: string;
  summary: ReadinessSummary;
  issues: ReadinessIssue[];
}

// ---------------------------------------------------------------------------
// Presentation taxonomy (mirror domain/readiness/enums.py — hydration only,
// the server is authoritative for the actual state string it returns)
// ---------------------------------------------------------------------------

export const NOT_CHECKED_STATE = "not_checked";

// Human labels for the server-derived ReadinessState values (doc 14 §4).
export const READINESS_STATE_LABELS: Record<string, string> = {
  not_checked: "Not checked",
  checking: "Checking…",
  not_ready: "Not ready",
  ready_with_warnings: "Ready with warnings",
  ready: "Ready",
  stale: "Stale",
  superseded: "Superseded",
};

// StatusBadge tone per readiness state — a blocker-bearing NOT_READY is a hard
// stop (down), warnings/stale are cautionary (warn), READY passes (ok), the
// transient/no-report states are neutral.
export const READINESS_STATE_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  not_checked: "neutral",
  checking: "warn",
  not_ready: "down",
  ready_with_warnings: "warn",
  ready: "ok",
  stale: "warn",
  superseded: "neutral",
};

export function readinessStateLabel(state: string): string {
  return READINESS_STATE_LABELS[state] ?? state;
}

export function readinessStateTone(state: string): "ok" | "warn" | "down" | "neutral" {
  return READINESS_STATE_TONES[state] ?? "neutral";
}

// Issue severity → tone (doc 14 §9.1: only blocker | warning).
export function severityTone(severity: string): "warn" | "down" | "neutral" {
  if (severity === "blocker") return "down";
  if (severity === "warning") return "warn";
  return "neutral";
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// The composition's latest readiness projection (recomputed currentness). Keyed
// under ["readiness", "current", id] so a run-check invalidation refetches it.
export function useCurrentReadiness(compositionId: string | null) {
  return useQuery({
    queryKey: ["readiness", "current", compositionId],
    queryFn: () =>
      api.get<CurrentReadiness>(
        `/mainboard-compositions/${encodeURIComponent(compositionId ?? "")}/readiness`,
      ),
    enabled: compositionId !== null,
  });
}

// An immutable report by id (Results-History-style deep-link, ?report=<id>).
// The report body never changes, but its effective state is recomputed on each
// read, so this is not marked immutable-stale.
export function useReadinessReport(reportId: string | null) {
  return useQuery({
    queryKey: ["readiness", "report", reportId],
    queryFn: () =>
      api.get<ReadinessReport>(`/readiness-reports/${encodeURIComponent(reportId ?? "")}`),
    enabled: reportId !== null,
  });
}

// ---------------------------------------------------------------------------
// Mutation — run the check (201, a NEW report every time)
// ---------------------------------------------------------------------------

// Run the Ready Check for a composition. ``expectedFingerprint`` is the optional
// OCC guard (doc 14 §11, RC-09): when supplied it must equal the composition's
// current fingerprint, else the server returns 409 CompositionStale and creates
// NOTHING — surfaced verbatim. Unlike the rv-N ETag actions, the readiness OCC
// token is the composition FINGERPRINT and travels in the body, not If-Match.
// A fresh Idempotency-Key per attempt makes a retry a new decision, not a replay
// (mirrors marketData finalize/analysis). Success invalidates ["readiness"] and
// ["mainboard"] (the default-Mainboard ready_summary moves with the new report).
export function useRunReadinessCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { compositionId: string; expectedFingerprint?: string }) =>
      apiRequest<RunCheckResult>(
        `/mainboard-compositions/${encodeURIComponent(input.compositionId)}/readiness-checks`,
        {
          method: "POST",
          body:
            input.expectedFingerprint !== undefined
              ? { expected_fingerprint: input.expectedFingerprint }
              : {},
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      void queryClient.invalidateQueries({ queryKey: ["mainboard"] });
    },
  });
}
