import { useEffect, useState } from "react";

import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  useApplyMetricProfile,
  useMetricDefinitions,
  useResolvedMetricProfile,
  type MetricDefinition,
  type ResolvedMetricProfile,
} from "@/lib/metricProfile";

// Mutation failures surface the backend canonical envelope verbatim — the
// client never invents profile-domain messages (mirrors BacktestRun).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Arrange Metrics (Stage 5c, doc 17): the metric-definition registry with the
// caller's resolved profile selection layered on top. Apply / Lock / Unlock are
// ALL the same append-only revision POST — the server derives the transition.
// PRESENTATION-ONLY (CR-07): nothing here recomputes a metric or touches a Result.
export function ArrangeMetrics() {
  const registry = useMetricDefinitions();
  const profile = useResolvedMetricProfile();

  return (
    <>
      <h1 className="page-title">Arrange Metrics</h1>
      <p className="page-sub">
        Choose which metrics your Result views show · presentation only, never a recompute
      </p>
      {registry.isLoading || profile.isLoading ? (
        <Loading label="Loading metric registry…" />
      ) : registry.isError ? (
        <ErrorState error={registry.error} onRetry={() => void registry.refetch()} />
      ) : profile.isError ? (
        <ErrorState error={profile.error} onRetry={() => void profile.refetch()} />
      ) : registry.data && profile.data ? (
        <ProfileEditor definitions={registry.data.metric_definitions} profile={profile.data} />
      ) : null}
    </>
  );
}

function ProfileEditor({
  definitions,
  profile,
}: {
  definitions: MetricDefinition[];
  profile: ResolvedMetricProfile;
}) {
  // Draft selection, seeded from the server's resolved profile. The server is
  // the only authority — a successful Apply refetches the resolved profile and
  // this draft re-seeds from it (keyed on the revision id below).
  const [draft, setDraft] = useState<ReadonlySet<string>>(
    () => new Set(profile.selected_metric_codes),
  );
  useEffect(() => {
    setDraft(new Set(profile.selected_metric_codes));
    // Re-seed whenever the server head moves (apply/lock/unlock or SSE sweep).
  }, [profile.current_revision_id, profile.selected_metric_codes]);

  const apply = useApplyMetricProfile();
  const locked = profile.is_locked;

  const toggle = (code: string) => {
    setDraft((current) => {
      const next = new Set(current);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  };

  // Split the already-fetched registry by availability (doc 17 §3): SELECTABLE
  // metrics drive the checkbox grid; FUTURE/EXPERIMENTAL ones populate the
  // always-visible reference panel below. Sourced from the registry, never
  // hard-coded (doc 17 §3 "gri kutu/serbest metinle hard-code edilmez").
  const selectableDefinitions = definitions.filter((definition) => definition.selectable);
  const futureDefinitions = definitions.filter((definition) => !definition.selectable);

  // Preserve registry display order in the submitted selection; the server
  // normalizes anyway, but the draft mirrors what it will echo back.
  const orderedSelection = selectableDefinitions
    .filter((definition) => draft.has(definition.metric_code))
    .map((definition) => definition.metric_code);

  const submit = (nextLocked: boolean) => {
    apply.mutate({
      profile_id: profile.editable_profile_id,
      selected_metric_codes: orderedSelection,
      is_locked: nextLocked,
      expected_profile_revision_id: profile.current_revision_id,
    });
  };

  return (
    <>
      <section className="card" aria-labelledby="profile-h">
        <h3 id="profile-h" style={{ marginTop: 0 }}>
          Resolved profile
        </h3>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <StatusBadge
            tone={profile.is_personal ? "ok" : "neutral"}
            label={profile.is_personal ? "Personal profile" : "System Default"}
          />
          {locked ? <StatusBadge tone="warn" label="Locked" /> : null}
        </div>
        <dl className="kv">
          <dt>Selected metrics</dt>
          <dd>{profile.selected_metric_count}</dd>
          <dt>Registry version</dt>
          <dd>{profile.registry_version}</dd>
        </dl>
        {!profile.is_personal ? (
          <p className="page-sub" style={{ marginBottom: 0 }}>
            You are on the System Default. Your first Apply creates a personal profile.
          </p>
        ) : null}
      </section>

      <section className="card" aria-labelledby="registry-h" style={{ marginTop: 18 }}>
        <h3 id="registry-h" style={{ marginTop: 0 }}>
          Metric registry
        </h3>
        <div className="metrics-panel">
          {selectableDefinitions.map((definition) => (
            <label className="metric-option" key={definition.metric_code}>
              <input
                type="checkbox"
                aria-label={`Show ${definition.label}`}
                checked={draft.has(definition.metric_code)}
                // A locked profile refuses edits until Unlock; future/experimental
                // metrics are not here at all — they live in the reference panel.
                disabled={locked}
                onChange={() => toggle(definition.metric_code)}
              />
              <span>
                {definition.label}
                <span className="metric-meta">
                  {definition.unit ?? "—"} · {definition.availability_status}
                  {definition.description ? ` — ${definition.description}` : ""}
                </span>
              </span>
            </label>
          ))}
        </div>
        {locked ? (
          <p className="locked-note" style={{ marginTop: 12 }}>
            Metrics are locked — Unlock to edit the selection.
          </p>
        ) : null}

        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14 }}>
          <button
            type="button"
            className="btn btn-primary"
            // The server requires a non-empty selection (min_length=1).
            disabled={apply.isPending || locked || orderedSelection.length === 0}
            onClick={() => submit(locked)}
          >
            {apply.isPending ? "Applying…" : "Apply"}
          </button>
          {locked ? (
            <button
              type="button"
              className="btn"
              disabled={apply.isPending}
              // A locked profile accepts only a PURE unlock: same selection,
              // is_locked=false (doc 17 §7) — submit the server's own selection.
              onClick={() =>
                apply.mutate({
                  profile_id: profile.editable_profile_id,
                  selected_metric_codes: profile.selected_metric_codes,
                  is_locked: false,
                  expected_profile_revision_id: profile.current_revision_id,
                })
              }
            >
              Unlock
            </button>
          ) : (
            <button
              type="button"
              className="btn"
              disabled={apply.isPending || orderedSelection.length === 0}
              onClick={() => submit(true)}
            >
              Apply &amp; Lock
            </button>
          )}
        </div>
        {apply.isError ? (
          <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
            {mutationErrorText(apply.error)}
          </p>
        ) : null}
        {apply.isSuccess ? (
          <p role="status" style={{ color: "var(--ok)", marginBottom: 0 }}>
            Saved — revision {apply.data.revision_no} ({apply.data.reason}).
          </p>
        ) : null}
      </section>

      {/* Future Version Metrics: an always-visible reference panel (doc 17 §3.2).
          These metrics are listed for visibility only — the server marks them
          non-selectable, so they carry no checkbox and can never enter a profile
          (CR-07). The list is the registry's own FUTURE/EXPERIMENTAL rows. */}
      <section
        className="card future-metrics-panel"
        aria-labelledby="future-metrics-h"
        style={{ marginTop: 18 }}
      >
        <h3 id="future-metrics-h" className="future-metrics-title" style={{ marginTop: 0 }}>
          Future Version Metrics
        </h3>
        <p className="future-metrics-note">
          These metrics are intentionally listed for visibility but are not selectable and
          cannot be added to Backtest Results in this version.
        </p>
        <div className="future-metric-list">
          {futureDefinitions.map((definition) => (
            <div className="future-metric-item" key={definition.metric_code}>
              {definition.label}
              <small>Future version only</small>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
