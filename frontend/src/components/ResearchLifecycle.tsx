import { useState, type CSSProperties, type FormEvent } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  AVAILABLE_TIME_POLICIES,
  CUSTOM_TIMEZONE_MODE,
  EVENT_TIME_SEMANTICS,
  FIXED_DELAY_POLICY,
  OTHER_CUSTOM_CATEGORY,
  RESEARCH_CATEGORIES,
  RESEARCH_TIMEZONE_MODES,
  USAGE_SCOPES,
  researchStateTone,
  useApproveRevision,
  useCompileAgentBundle,
  useCompileEvidenceBundle,
  useCreateRevision,
  useDefineFeature,
  useDefineField,
  useRevokeApproval,
  useSetTimePolicy,
  type BundleResult,
  type ResearchDatasetDetail,
} from "@/lib/researchData";

// Command failures surface the backend canonical envelope verbatim — the client
// never invents research-data-domain messages (mirrors pages/ResearchData.tsx).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Parse an optional JSON object for transport only; domain validation stays
// server-side. Returns the object, or null with the error message set via onError.
function parseJsonObject(
  text: string,
  onError: (message: string) => void,
): Record<string, unknown> | null {
  if (text.trim().length === 0) return {};
  try {
    const parsed: unknown = JSON.parse(text);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      onError("Must be a JSON object.");
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    onError("Not valid JSON.");
    return null;
  }
}

// One id per line; blank lines stripped (transport shaping only).
function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

const GRID: CSSProperties = {
  display: "grid",
  gap: 12,
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
};

function ErrorLine({ error }: { error: unknown }) {
  return (
    <p role="alert" style={{ color: "var(--down)" }}>
      {mutationErrorText(error)}
    </p>
  );
}

// Research Data revision lifecycle (doc 12 §5, §7, §8, §9) — the eight actions
// past ingest: revise (OCC), set time policy, declare a field/feature definition,
// Admin approve/revoke (OCC), and compile agent/backtest evidence bundles (pure
// read). Draft edits are owner-or-Admin, approve/revoke Admin-only — ALL enforced
// server-side; the UI never pre-gates. A denial renders the envelope verbatim.
export function ResearchLifecycle({ detail }: { detail: ResearchDatasetDetail }) {
  return (
    <>
      <h4>Revision lifecycle</h4>
      <p className="page-sub" style={{ marginTop: 0 }}>
        Revise + approve/revoke carry the root row_version as an If-Match OCC token (rv{" "}
        {detail.row_version}); time-policy, field/feature and the bundle probes carry none.
        Approve/revoke are Admin-only server-side.
      </p>
      <ReviseComposer detail={detail} />
      <TimePolicyComposer entityId={detail.entity_id} />
      <FieldDefinitionComposer entityId={detail.entity_id} />
      <FeatureDefinitionComposer entityId={detail.entity_id} />
      <ApprovalComposer detail={detail} />
      <BundleComposer detail={detail} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Revise — append a DRAFT revision under OCC (If-Match rv-N + Idempotency-Key).
// ---------------------------------------------------------------------------

function ReviseComposer({ detail }: { detail: ResearchDatasetDetail }) {
  const revise = useCreateRevision();
  const [category, setCategory] = useState<string>(RESEARCH_CATEGORIES[0]);
  const [customCategory, setCustomCategory] = useState("");
  const [usageScope, setUsageScope] = useState<string>(USAGE_SCOPES[0]);
  const [timezoneMode, setTimezoneMode] = useState<string>(RESEARCH_TIMEZONE_MODES[0]);
  const [timezoneIana, setTimezoneIana] = useState("");
  const [marketEntityId, setMarketEntityId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [providerName, setProviderName] = useState("");
  const [baseRevisionId, setBaseRevisionId] = useState("");
  const [payloadText, setPayloadText] = useState("");
  const [payloadError, setPayloadError] = useState<string | null>(null);

  const isCustomCategory = category === OTHER_CUSTOM_CATEGORY;
  const isCustomTimezone = timezoneMode === CUSTOM_TIMEZONE_MODE;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const payload = parseJsonObject(payloadText, setPayloadError);
    if (payload === null) return;
    setPayloadError(null);
    revise.mutate({
      entity_id: detail.entity_id,
      row_version: detail.row_version,
      payload,
      category,
      usage_scope: usageScope,
      timezone_mode: timezoneMode,
      // Only `other_custom` carries a custom category; switching away sends null.
      custom_category: isCustomCategory ? customCategory.trim() || null : null,
      // Only `custom` carries an IANA zone; every other mode sends null.
      timezone_iana: isCustomTimezone ? timezoneIana.trim() || null : null,
      market_entity_id: marketEntityId.trim() || null,
      display_name: displayName.trim() || null,
      provider_name: providerName.trim() || null,
      base_revision_id: baseRevisionId.trim() || null,
    });
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Revise — append a DRAFT revision (OCC)</strong>
      <form onSubmit={submit}>
        <div style={GRID}>
          <label htmlFor="rl-category">
            Revision category
            <select id="rl-category" value={category} onChange={(e) => setCategory(e.target.value)}>
              {RESEARCH_CATEGORIES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {isCustomCategory ? (
            <label htmlFor="rl-custom-category">
              Revision custom category
              <input
                id="rl-custom-category"
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                required
              />
            </label>
          ) : null}
          <label htmlFor="rl-usage">
            Revision usage scope
            <select id="rl-usage" value={usageScope} onChange={(e) => setUsageScope(e.target.value)}>
              {USAGE_SCOPES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="rl-tz">
            Revision timezone
            <select id="rl-tz" value={timezoneMode} onChange={(e) => setTimezoneMode(e.target.value)}>
              {RESEARCH_TIMEZONE_MODES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {isCustomTimezone ? (
            <label htmlFor="rl-tz-iana">
              Revision IANA zone
              <input
                id="rl-tz-iana"
                value={timezoneIana}
                onChange={(e) => setTimezoneIana(e.target.value)}
                placeholder="America/New_York"
                required
              />
            </label>
          ) : null}
          <label htmlFor="rl-market">
            Re-link market entity id (optional)
            <input
              id="rl-market"
              value={marketEntityId}
              onChange={(e) => setMarketEntityId(e.target.value)}
              placeholder="md_…"
            />
          </label>
          <label htmlFor="rl-display">
            Revision display name (optional)
            <input id="rl-display" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </label>
          <label htmlFor="rl-provider">
            Revision provider (optional)
            <input id="rl-provider" value={providerName} onChange={(e) => setProviderName(e.target.value)} />
          </label>
          <label htmlFor="rl-base">
            Base revision id (optional)
            <input
              id="rl-base"
              value={baseRevisionId}
              onChange={(e) => setBaseRevisionId(e.target.value)}
              placeholder="rrev_…"
            />
          </label>
          <label htmlFor="rl-payload">
            Revision payload (optional JSON object)
            <textarea
              id="rl-payload"
              rows={2}
              value={payloadText}
              onChange={(e) => setPayloadText(e.target.value)}
              placeholder='{"note":"revised"}'
            />
          </label>
        </div>
        <button type="submit" className="btn" disabled={revise.isPending} style={{ marginTop: 8 }}>
          Append revision
        </button>
      </form>
      {payloadError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {payloadError}
        </p>
      ) : null}
      {revise.isError ? <ErrorLine error={revise.error} /> : null}
      {revise.data ? (
        <p aria-live="polite">
          Revision appended — {revise.data.revision_id} (v{revise.data.revision_no}); root now rv{" "}
          {revise.data.row_version}.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Time policy — event/available time rules (no OCC header). Only `fixed_delay`
// carries a positive delay; every other rule sends delay=null.
// ---------------------------------------------------------------------------

function TimePolicyComposer({ entityId }: { entityId: string }) {
  const setPolicy = useSetTimePolicy();
  const [eventSemantics, setEventSemantics] = useState<string>(EVENT_TIME_SEMANTICS[0]);
  const [availablePolicy, setAvailablePolicy] = useState<string>(AVAILABLE_TIME_POLICIES[0]);
  const [timezoneMode, setTimezoneMode] = useState<string>(RESEARCH_TIMEZONE_MODES[0]);
  const [timezoneIana, setTimezoneIana] = useState("");
  const [delaySeconds, setDelaySeconds] = useState("");

  const isFixedDelay = availablePolicy === FIXED_DELAY_POLICY;
  const isCustomTimezone = timezoneMode === CUSTOM_TIMEZONE_MODE;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setPolicy.mutate({
      entity_id: entityId,
      event_time_semantics: eventSemantics,
      available_time_policy: availablePolicy,
      timezone_mode: timezoneMode,
      delay_seconds: isFixedDelay ? Number(delaySeconds) : null,
      timezone_iana: isCustomTimezone ? timezoneIana.trim() || null : null,
    });
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Time policy — event &amp; available time rules</strong>
      <form onSubmit={submit}>
        <div style={GRID}>
          <label htmlFor="rl-event-sem">
            Event time semantics
            <select
              id="rl-event-sem"
              value={eventSemantics}
              onChange={(e) => setEventSemantics(e.target.value)}
            >
              {EVENT_TIME_SEMANTICS.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="rl-avail">
            Available time policy
            <select id="rl-avail" value={availablePolicy} onChange={(e) => setAvailablePolicy(e.target.value)}>
              {AVAILABLE_TIME_POLICIES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {isFixedDelay ? (
            <label htmlFor="rl-delay">
              Delay (seconds)
              <input
                id="rl-delay"
                type="number"
                min={1}
                value={delaySeconds}
                onChange={(e) => setDelaySeconds(e.target.value)}
                required
              />
            </label>
          ) : null}
          <label htmlFor="rl-tp-tz">
            Time policy timezone
            <select id="rl-tp-tz" value={timezoneMode} onChange={(e) => setTimezoneMode(e.target.value)}>
              {RESEARCH_TIMEZONE_MODES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {isCustomTimezone ? (
            <label htmlFor="rl-tp-iana">
              Time policy IANA zone
              <input
                id="rl-tp-iana"
                value={timezoneIana}
                onChange={(e) => setTimezoneIana(e.target.value)}
                placeholder="Asia/Tokyo"
                required
              />
            </label>
          ) : null}
        </div>
        <button type="submit" className="btn" disabled={setPolicy.isPending} style={{ marginTop: 8 }}>
          Set time policy
        </button>
      </form>
      {setPolicy.isError ? <ErrorLine error={setPolicy.error} /> : null}
      {setPolicy.data ? (
        <p aria-live="polite">
          Time policy set — {setPolicy.data.available_time_policy} (<code>{setPolicy.data.time_policy_id}</code>
          ).
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field definition — the eight semantic attributes (doc 12 §8.3). Seven are
// required (FIELD_MEANING_INSUFFICIENT otherwise); unit_or_scale is optional.
// ---------------------------------------------------------------------------

type FieldKey =
  | "field_name"
  | "semantic_type"
  | "measurement_method"
  | "null_semantics"
  | "event_time_source"
  | "availability_rule"
  | "allowed_usage"
  | "unit_or_scale";

const FIELD_INPUTS: Array<{ key: FieldKey; label: string; required: boolean }> = [
  { key: "field_name", label: "Field name", required: true },
  { key: "semantic_type", label: "Semantic type", required: true },
  { key: "measurement_method", label: "Measurement method", required: true },
  { key: "null_semantics", label: "Null semantics", required: true },
  { key: "event_time_source", label: "Event time source", required: true },
  { key: "availability_rule", label: "Availability rule", required: true },
  { key: "allowed_usage", label: "Allowed usage", required: true },
  { key: "unit_or_scale", label: "Unit or scale (optional)", required: false },
];

function FieldDefinitionComposer({ entityId }: { entityId: string }) {
  const define = useDefineField();
  const [fields, setFields] = useState<Record<FieldKey, string>>({
    field_name: "",
    semantic_type: "",
    measurement_method: "",
    null_semantics: "",
    event_time_source: "",
    availability_rule: "",
    allowed_usage: "",
    unit_or_scale: "",
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    define.mutate({
      entity_id: entityId,
      field_name: fields.field_name.trim(),
      semantic_type: fields.semantic_type.trim(),
      measurement_method: fields.measurement_method.trim(),
      null_semantics: fields.null_semantics.trim(),
      event_time_source: fields.event_time_source.trim(),
      availability_rule: fields.availability_rule.trim(),
      allowed_usage: fields.allowed_usage.trim(),
      unit_or_scale: fields.unit_or_scale.trim() || null,
    });
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Field definition — one native field's meaning</strong>
      <form onSubmit={submit}>
        <div style={GRID}>
          {FIELD_INPUTS.map((spec) => (
            <label key={spec.key} htmlFor={`rl-field-${spec.key}`}>
              {spec.label}
              <input
                id={`rl-field-${spec.key}`}
                value={fields[spec.key]}
                onChange={(e) => setFields((prev) => ({ ...prev, [spec.key]: e.target.value }))}
                required={spec.required}
              />
            </label>
          ))}
        </div>
        <button type="submit" className="btn" disabled={define.isPending} style={{ marginTop: 8 }}>
          Define field
        </button>
      </form>
      {define.isError ? <ErrorLine error={define.error} /> : null}
      {define.data ? (
        <p aria-live="polite">
          Field defined — {define.data.field_name} (<code>{define.data.field_definition_id}</code>).
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature definition — a versioned feature (doc 12 §9.3). Required before a
// Feature-Input-Only revision can feed Strategy logic.
// ---------------------------------------------------------------------------

function FeatureDefinitionComposer({ entityId }: { entityId: string }) {
  const define = useDefineFeature();
  const [featureName, setFeatureName] = useState("");
  const [definitionText, setDefinitionText] = useState("");
  const [featureVersion, setFeatureVersion] = useState("1");
  const [approvalState, setApprovalState] = useState("");
  const [definitionError, setDefinitionError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const definition = parseJsonObject(definitionText, setDefinitionError);
    if (definition === null) return;
    setDefinitionError(null);
    define.mutate({
      entity_id: entityId,
      feature_name: featureName.trim(),
      definition,
      feature_version: Number(featureVersion) || 1,
      approval_state: approvalState.trim() || null,
    });
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Feature definition — versioned Strategy input</strong>
      <form onSubmit={submit}>
        <div style={GRID}>
          <label htmlFor="rl-feature-name">
            Feature name
            <input
              id="rl-feature-name"
              value={featureName}
              onChange={(e) => setFeatureName(e.target.value)}
              required
            />
          </label>
          <label htmlFor="rl-feature-version">
            Feature version
            <input
              id="rl-feature-version"
              type="number"
              min={1}
              value={featureVersion}
              onChange={(e) => setFeatureVersion(e.target.value)}
            />
          </label>
          <label htmlFor="rl-feature-approval">
            Approval state (optional)
            <input
              id="rl-feature-approval"
              value={approvalState}
              onChange={(e) => setApprovalState(e.target.value)}
              placeholder="approved"
            />
          </label>
          <label htmlFor="rl-feature-def">
            Feature definition (JSON object)
            <textarea
              id="rl-feature-def"
              rows={2}
              value={definitionText}
              onChange={(e) => setDefinitionText(e.target.value)}
              placeholder='{"window":14}'
            />
          </label>
        </div>
        <button type="submit" className="btn" disabled={define.isPending} style={{ marginTop: 8 }}>
          Define feature
        </button>
      </form>
      {definitionError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {definitionError}
        </p>
      ) : null}
      {define.isError ? <ErrorLine error={define.error} /> : null}
      {define.data ? (
        <p aria-live="polite">
          Feature defined — {define.data.feature_name} (<code>{define.data.feature_definition_id}</code>).
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Approve / revoke — Admin only, under OCC (If-Match rv-N + Idempotency-Key). The
// UI never role-pre-gates; a non-Admin -> 403 APPROVAL_REQUIRES_ADMIN verbatim.
// ---------------------------------------------------------------------------

function ApprovalComposer({ detail }: { detail: ResearchDatasetDetail }) {
  const approve = useApproveRevision();
  const revoke = useRevokeApproval();
  const [revisionId, setRevisionId] = useState(detail.revision_id);
  const [note, setNote] = useState("");

  const options =
    detail.revisions.length > 0
      ? detail.revisions
      : [
          {
            revision_id: detail.revision_id,
            revision_no: detail.revision_no,
            revision_state: detail.revision_state,
          },
        ];

  const decide = (action: "approve" | "revoke") => {
    const input = {
      entity_id: detail.entity_id,
      revision_id: revisionId,
      note: note.trim() || null,
      row_version: detail.row_version,
    };
    if (action === "approve") approve.mutate(input);
    else revoke.mutate(input);
  };

  const result = approve.data ?? revoke.data;
  const isError = approve.isError || revoke.isError;
  const error = approve.error ?? revoke.error;

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Approve / revoke — Admin only (OCC)</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Approve moves a VERIFIED revision to APPROVED (re-checks the market link + time policy);
        revoke stops new use without mutating pinned manifests. Both carry the root row_version as
        the If-Match token.
      </p>
      <div style={{ display: "flex", alignItems: "end", gap: 12, flexWrap: "wrap" }}>
        <label htmlFor="rl-approve-rev">
          Revision to decide
          <select id="rl-approve-rev" value={revisionId} onChange={(e) => setRevisionId(e.target.value)}>
            {options.map((r) => (
              <option key={r.revision_id} value={r.revision_id}>
                v{r.revision_no} · {r.revision_state}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="rl-approve-note">
          Decision note (optional)
          <input id="rl-approve-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button type="button" className="btn" disabled={approve.isPending} onClick={() => decide("approve")}>
          Approve
        </button>
        <button type="button" className="btn" disabled={revoke.isPending} onClick={() => decide("revoke")}>
          Revoke
        </button>
      </div>
      {isError ? <ErrorLine error={error} /> : null}
      {result ? (
        <p aria-live="polite">
          {result.revision_id} is now{" "}
          <StatusBadge tone={researchStateTone(result.revision_state)} label={result.revision_state} />.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bundles — compile an immutable, content-addressed evidence bundle (pure read).
// No durable row, no Idempotency-Key; pins exact revision + market ids/hashes.
// ---------------------------------------------------------------------------

function BundleComposer({ detail }: { detail: ResearchDatasetDetail }) {
  const agent = useCompileAgentBundle();
  const evidence = useCompileEvidenceBundle();
  const [revisionIdsText, setRevisionIdsText] = useState(detail.revision_id);
  const [taskId, setTaskId] = useState("");
  const [runRequestId, setRunRequestId] = useState("");

  const revisionIds = linesToList(revisionIdsText);
  const compileAgent = () =>
    agent.mutate({ research_revision_ids: revisionIds, task_id: taskId.trim() || null });
  const compileEvidence = () =>
    evidence.mutate({ research_revision_ids: revisionIds, run_request_id: runRequestId.trim() || null });

  const result = agent.data ?? evidence.data;
  const isError = agent.isError || evidence.isError;
  const error = agent.error ?? evidence.error;
  const pending = agent.isPending || evidence.isPending;
  const noIds = revisionIds.length === 0;

  return (
    <div>
      <strong>Bundles — pin an immutable evidence bundle (read-only probe)</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Agent bundles accept any consumable revision; evidence bundles require ACTIVE+APPROVED,
        usage-scope-eligible, time-policy-valid revisions. The probe creates nothing — it returns a
        content-addressed hash over the exact pinned ids, never &quot;latest&quot;.
      </p>
      <div style={GRID}>
        <label htmlFor="rl-bundle-ids">
          Research revision ids (one per line)
          <textarea
            id="rl-bundle-ids"
            rows={2}
            value={revisionIdsText}
            onChange={(e) => setRevisionIdsText(e.target.value)}
          />
        </label>
        <label htmlFor="rl-bundle-task">
          Agent task id (optional)
          <input
            id="rl-bundle-task"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            placeholder="task_…"
          />
        </label>
        <label htmlFor="rl-bundle-run">
          Run request id (optional)
          <input
            id="rl-bundle-run"
            value={runRequestId}
            onChange={(e) => setRunRequestId(e.target.value)}
            placeholder="run_…"
          />
        </label>
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn" disabled={pending || noIds} onClick={compileAgent}>
          Compile agent bundle
        </button>
        <button type="button" className="btn" disabled={pending || noIds} onClick={compileEvidence}>
          Compile evidence bundle
        </button>
      </div>
      {isError ? <ErrorLine error={error} /> : null}
      {result ? <BundleResultView bundle={result} /> : null}
    </div>
  );
}

function BundleResultView({ bundle }: { bundle: BundleResult }) {
  return (
    <div aria-live="polite" style={{ marginTop: 8 }}>
      <p>
        {bundle.bundle_kind} sealed — <code>{bundle.bundle_hash}</code> ({bundle.members.length} member
        {bundle.members.length === 1 ? "" : "s"}, {bundle.compiler_version}).
      </p>
      <ul>
        {bundle.members.map((m) => (
          <li key={m.research_revision_id}>
            <code>{m.research_revision_id}</code>
            {m.usage_scope !== null ? ` · ${m.usage_scope}` : ""}
            {m.market_dataset_revision_id !== null ? ` · market ${m.market_dataset_revision_id}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
