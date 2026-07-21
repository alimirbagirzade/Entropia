import { useState, type ChangeEvent } from "react";

import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { PreCheckModal } from "@/components/PreCheckModal";
import { StatusBadge } from "@/components/StatusBadge";
import { AdminGate, useIsAdmin } from "@/components/AdminGate";
import { ApiError } from "@/lib/apiClient";
import {
  CREATE_PACKAGE_KINDS,
  CREATION_MODES,
  SOURCE_LANGUAGES,
  SUPPORTED_TARGET_RUNTIME,
  asRecordArray,
  baselineParseTone,
  buildBaselineMetadata,
  outputKindsFor,
  packageActionAvailability,
  parseDeclaredDependencies,
  requestStateTone,
  scanStatusTone,
  sourceKindForMode,
  useApproveRequest,
  useCreateDraft,
  useCreatePackageRequest,
  useGenerateCandidate,
  usePackageRequest,
  usePackageRequests,
  useRationaleFamilies,
  useRequestRevision,
  useRunValidation,
  useStartBaselineParse,
  useUploadBaseline,
  validationRunTone,
  type BaselineMetadataFields,
  type CreatePackageKind,
  type CreationMode,
  type MissingCall,
  type PackageRequestDetail,
  type ResolvedRef,
  type SourceLanguage,
} from "@/lib/createPackage";

// Command failures surface the backend canonical envelope verbatim — the client
// never invents Create-Package domain messages (mirrors Panel / AnalysisLab).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Pure presentation: turn a raw wire enum (snake_case) into a Title Case label
// for the v18 status-summary card. Never alters the value sent to the server —
// the raw enum still travels in every request body/header unchanged.
function prettyToken(token: string): string {
  return token
    .split("_")
    .map((part) => (part.length > 0 ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

// The v18 Package Library Target label for a package type. Presentation-only —
// the server owns the real target pool assignment on approval.
function targetLibrary(kind: string): string {
  if (kind === "embedded_system") return "Embedded System Packages";
  if (kind === "condition") return "Condition Packages";
  return "Indicator Packages";
}

// The v18 draft runtime file name for a package type (mockup cpCreateDraft). The
// backend projection carries only the draft revision id, not per-file names, so
// this is a display label alongside the real revision id.
function runtimeFileName(kind: string): string {
  if (kind === "embedded_system") return "embedded_resolver.php";
  if (kind === "condition") return "generated_condition.py";
  return "generated_indicator.py";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the cursor
// stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const top = stack.length > 0 ? stack[stack.length - 1] : null;
  return {
    cursor: top ?? null,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
  };
}

// ---------------------------------------------------------------------------
// Create Package (doc 06) — v18 §3 CP Agent workspace. The page is a single
// composition plane: a full-width controls row + Package Identity / Compatibility
// grid on top, then a two-column split — a request/AI compose column on the left
// (chat board + draft files) and a Package Status / Baseline / Resolver /
// Validation / Library-Target side panel on the right. Every action reuses the
// real backend hooks unchanged; the server re-validates every field/transition
// and a denial (e.g. a guest, or a non-Admin approve) surfaces the canonical
// error envelope verbatim.
// ---------------------------------------------------------------------------

export function CreatePackage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const request = usePackageRequest(selectedId);
  const detail = selectedId !== null ? (request.data ?? null) : null;

  return (
    <>
      <h1 className="page-title">Create Package</h1>
      <p className="page-sub">
        Compose a package request and drive it through the CP Agent workspace —
        Pre-Check, candidate generation, draft, TradingView baseline, validation
        tests and approval, all on one plane.
      </p>

      <RequestSwitcher selectedId={selectedId} onSelect={setSelectedId} />

      <Workspace
        detail={detail}
        loading={selectedId !== null && request.isLoading}
        error={selectedId !== null && request.isError ? request.error : null}
        onCreated={setSelectedId}
        onClear={() => setSelectedId(null)}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Request switcher — a compact strip of the actor's own requests (keyset-paged).
// Selecting one loads it into the workspace; there is no separate generic
// "My requests" / "detail" card — the whole page is the detail.
// ---------------------------------------------------------------------------

function RequestSwitcher({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (requestId: string | null) => void;
}) {
  const pager = useCursorStack();
  const requests = usePackageRequests(pager.cursor);

  return (
    <section className="card" aria-labelledby="cp-switch-h" style={{ marginBottom: 14 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <h3 id="cp-switch-h" style={{ margin: 0 }}>
          My requests
        </h3>
        {selectedId !== null ? (
          <button type="button" className="btn btn-ghost" onClick={() => onSelect(null)}>
            New request
          </button>
        ) : null}
      </div>
      {requests.isLoading ? (
        <Loading label="Loading requests…" />
      ) : requests.isError ? (
        <ErrorState error={requests.error} onRetry={() => void requests.refetch()} />
      ) : requests.data && requests.data.data.length > 0 ? (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            {requests.data.data.map((req) => (
              <button
                key={req.request_id}
                type="button"
                className={selectedId === req.request_id ? "btn btn-primary" : "btn"}
                aria-pressed={selectedId === req.request_id}
                onClick={() => onSelect(req.request_id)}
                title={`${req.package_type} · ${req.source_kind} · ${req.state}`}
              >
                <code>{req.request_id}</code>{" "}
                <StatusBadge tone={requestStateTone(req.state)} label={req.state} />
              </button>
            ))}
          </div>
          <Pager
            canPrev={pager.canPrev}
            nextCursor={requests.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : (
        <p className="cp-note" style={{ marginTop: 10 }}>
          No requests yet — compose your first one below.
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Workspace — full-width identity controls + the CP Agent chat board / compose /
// actions / draft files on the left, and the Package Status side panel on the
// right. When no request is selected the compose Send creates an immutable
// request (doc 06 §4). When one is selected the chat board is derived
// deterministically from its server projection and the lifecycle actions operate
// on it (Pre-Check / C.D.P / Clear); Send always composes a fresh request.
// ---------------------------------------------------------------------------

interface FormState {
  package_type: CreatePackageKind;
  creation_mode: CreationMode;
  source_language: SourceLanguage;
  other_language_label: string;
  request_body: string;
  output_kind: string;
  rationale_family_id: string;
  declared_keys: string;
}

const INITIAL_FORM: FormState = {
  package_type: "indicator",
  creation_mode: "translate_existing_code",
  source_language: "pinescript",
  other_language_label: "",
  request_body: "",
  output_kind: "directional_signal",
  rationale_family_id: "",
  declared_keys: "",
};

function Workspace({
  detail,
  loading,
  error,
  onCreated,
  onClear,
}: {
  detail: PackageRequestDetail | null;
  loading: boolean;
  error: unknown;
  onCreated: (requestId: string) => void;
  onClear: () => void;
}) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  // UI-07: Pre-Check is an accessible overlay opened from this workspace (the
  // request is already selected here — no request table to walk / re-select).
  const [precheckOpen, setPrecheckOpen] = useState(false);
  const families = useRationaleFamilies(null);
  const create = useCreatePackageRequest();
  const generate = useGenerateCandidate();
  const draft = useCreateDraft();

  const isCodeMode = sourceKindForMode(form.creation_mode) === "code";
  const isEsp = form.package_type === "embedded_system";
  const needsLabel = isCodeMode && form.source_language === "other";
  const kindOptions = outputKindsFor(form.package_type);
  const familyRows = families.data?.data ?? [];

  const canSubmit =
    form.request_body.trim().length > 0 &&
    form.output_kind.length > 0 &&
    (!isCodeMode || form.source_language.length > 0) &&
    (!needsLabel || form.other_language_label.trim().length > 0) &&
    (isEsp || form.rationale_family_id.length > 0) &&
    !create.isPending;

  function onPackageType(next: CreatePackageKind) {
    const nextKinds = outputKindsFor(next);
    setForm((prev) => ({ ...prev, package_type: next, output_kind: nextKinds[0] ?? "" }));
  }

  function onSend() {
    if (!canSubmit) return;
    // R2-12: an optional `key(type,…)->return` signature per line — EXACT
    // ordered types are the resolver identity (doc 09 §4.2), so a bare key
    // cannot match a parameterised ESP contract.
    const declared = parseDeclaredDependencies(form.declared_keys);
    create.mutate(
      {
        package_type: form.package_type,
        creation_mode: form.creation_mode,
        target_runtime: SUPPORTED_TARGET_RUNTIME,
        request_body: form.request_body,
        output_contract: { kind: form.output_kind },
        source_language: isCodeMode ? form.source_language : null,
        other_language_label: needsLabel ? form.other_language_label.trim() : null,
        rationale_family_id: isEsp ? null : form.rationale_family_id,
        declared_dependencies: declared,
      },
      { onSuccess: (result) => onCreated(result.request_id) },
    );
  }

  // C.D.P chains generate-candidate → create-draft (the mockup "Create Draft
  // Package"); the accepted candidate_hash from generate becomes the draft's
  // staleness token. Pre-Check itself lives in its own overlay (PreCheckModal).
  const actionsPending = generate.isPending || draft.isPending;
  // The state-machine truth for which lifecycle actions this request permits
  // (F-12): the buttons below reflect it instead of always being clickable.
  const actions = packageActionAvailability(detail);

  function onCdp() {
    if (detail === null || !actions.generateDraft) return;
    generate.mutate(
      { request_id: detail.request_id, request_version: detail.request_version },
      {
        onSuccess: (res) =>
          draft.mutate({
            request_id: detail.request_id,
            expected_candidate_hash: res.candidate_hash,
          }),
      },
    );
  }

  function onClearAll() {
    setForm(INITIAL_FORM);
    onClear();
  }

  return (
    <div className="cp-page">
      {/* Identity controls (doc 06 §4 field contract). Requiredness is mirrored
          client-side only for Send gating; the server re-validates every field.
          The Send button (below) is the only submit path — there is no <form>
          element, so a stray Enter in a side-panel field can never dispatch. */}
      <div className="cp-controls-row">
        <label>
          <span>Package type</span>
          <select
            aria-label="Package type"
            value={form.package_type}
            onChange={(e) => onPackageType(e.target.value as CreatePackageKind)}
          >
            {CREATE_PACKAGE_KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Creation mode</span>
          <select
            aria-label="Creation mode"
            value={form.creation_mode}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, creation_mode: e.target.value as CreationMode }))
            }
          >
            {CREATION_MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Source language</span>
          {isCodeMode ? (
            <select
              aria-label="Source language"
              value={form.source_language}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, source_language: e.target.value as SourceLanguage }))
              }
            >
              {SOURCE_LANGUAGES.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          ) : (
            <p className="cp-note">Not applicable — description carries no code.</p>
          )}
        </label>
        <label>
          <span>Target runtime</span>
          <select aria-label="Target runtime" value={SUPPORTED_TARGET_RUNTIME} disabled>
            <option value={SUPPORTED_TARGET_RUNTIME}>{SUPPORTED_TARGET_RUNTIME}</option>
          </select>
        </label>
        {needsLabel ? (
          <label>
            <span>Other language + version</span>
            <input
              aria-label="Other language and version"
              value={form.other_language_label}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, other_language_label: e.target.value }))
              }
              placeholder="e.g. MQL5 build 3980"
            />
          </label>
        ) : null}
      </div>

      {/* Package Identity / Compatibility grid (mockup §3). Output type and the
          rationale family feed the real request; compatible family + explicit
          indicator link follow the v18 layout but are not yet bound to the
          backend (V1) — the server owns those relationships on approval. */}
      <div className="cp-section-title">Package Identity / Compatibility</div>
      <div className="cp-identity-grid">
        <label>
          <span>Rationale family</span>
          {isEsp ? (
            <p className="cp-note">Not applicable — Embedded System takes the system class.</p>
          ) : (
            <select
              aria-label="Rationale family"
              value={form.rationale_family_id}
              onChange={(e) => setForm((prev) => ({ ...prev, rationale_family_id: e.target.value }))}
            >
              <option value="">Select a family…</option>
              {familyRows.map((fam) => (
                <option key={fam.entity_id} value={fam.entity_id}>
                  {fam.display_name}
                </option>
              ))}
            </select>
          )}
        </label>
        <label>
          <span>Output type</span>
          <select
            aria-label="Output contract kind"
            value={form.output_kind}
            onChange={(e) => setForm((prev) => ({ ...prev, output_kind: e.target.value }))}
          >
            {kindOptions.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Compatible family</span>
          <select aria-label="Compatible family" defaultValue="same" disabled>
            <option value="same">Same Rationale Family</option>
          </select>
        </label>
        <label>
          <span>Explicit indicator link</span>
          <select aria-label="Explicit indicator link" defaultValue="optional" disabled>
            <option value="optional">Optional / Not Required</option>
          </select>
        </label>
      </div>

      {!isEsp && familyRows.length === 0 && !families.isLoading ? (
        <p className="cp-note" style={{ marginTop: -4, marginBottom: 8 }}>
          No active Rationale Family — create one first (required for Indicator / Condition).
        </p>
      ) : null}
      <p className="cp-note" style={{ marginTop: 0, marginBottom: 14 }}>
        Compatible family and explicit indicator link follow the v18 layout; they are not yet sent
        to the backend (V1).
      </p>

      <div className="cp-create-layout">
        <section>
          {/* CP Agent chat board + compose + actions. */}
          <div className="cp-panel">
            <div className="cp-panel-head">
              <span>Package Request / AI Workspace</span>
              <span className="cp-sub">{detail ? detail.request_id : "Not created"}</span>
            </div>
            <MessagesBoard detail={detail} loading={loading} error={error} />
            <div className="cp-compose">
              <label>
                <span>{isCodeMode ? "Source code" : "Description"}</span>
                <textarea
                  aria-label={isCodeMode ? "Source code" : "Description"}
                  value={form.request_body}
                  onChange={(e) => setForm((prev) => ({ ...prev, request_body: e.target.value }))}
                  placeholder={
                    isCodeMode
                      ? "Paste the source to translate / repair / review…"
                      : "Describe the package to generate…"
                  }
                />
              </label>
              <label style={{ display: "block", marginTop: 10 }}>
                <span>
                  Declared dependencies (one per line — optional signature as
                  key(type,…)-&gt;return)
                </span>
                <textarea
                  aria-label="Declared dependencies"
                  value={form.declared_keys}
                  onChange={(e) => setForm((prev) => ({ ...prev, declared_keys: e.target.value }))}
                  placeholder={"ta.sma(series,int)->series\nta.rsi(series,int)->series"}
                  style={{ minHeight: 64 }}
                />
              </label>
              <div className="cp-button-row">
                <button
                  type="button"
                  className="btn"
                  disabled={detail === null}
                  aria-haspopup="dialog"
                  onClick={() => setPrecheckOpen(true)}
                >
                  Pre-Check
                </button>
                {/* Status pill — the direct visual link between the Pre-Check
                    button and the Package Status TA Pre-Check row (UI-07). */}
                {detail?.current_scan ? (
                  <StatusBadge
                    tone={scanStatusTone(detail.current_scan.status)}
                    label={`${detail.current_scan.status}${detail.precheck_fresh ? "" : " · stale"}`}
                  />
                ) : detail !== null ? (
                  <StatusBadge tone="neutral" label="not_checked" />
                ) : null}
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!canSubmit}
                  onClick={onSend}
                >
                  {create.isPending ? "Sending…" : "Send"}
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={!actions.generateDraft || actionsPending}
                  onClick={onCdp}
                  title="Create Draft Package (generate candidate → draft)"
                >
                  {generate.isPending || draft.isPending ? "Drafting…" : "C.D.P"}
                </button>
                <button type="button" className="btn btn-ghost" onClick={onClearAll}>
                  Clear
                </button>
              </div>
              {/* R2-12: the locked-action reasons live NEXT TO their controls,
                  derived from the server projection (never a client guess). */}
              <LockReason reason={actions.reasons.precheck} />
              <LockReason reason={actions.reasons.generateDraft} />
              {detail !== null && actions.nextStepHint.length > 0 ? (
                <p className="cp-note" aria-live="polite" style={{ marginTop: 8, fontWeight: 600 }}>
                  Next step: {actions.nextStepHint}
                </p>
              ) : null}
              <p className="cp-note" style={{ marginTop: 8 }}>
                Pre-Check analyses code TA dependencies through Embedded System Packages. C.D.P
                creates a Draft Package, not an approved package.
              </p>

              {create.isError ? (
                <p role="alert" style={alertStyle}>
                  {mutationErrorText(create.error)}
                </p>
              ) : null}
              {create.data ? (
                <p aria-live="polite" style={liveStyle}>
                  Request created — <code>{create.data.request_id}</code> ({create.data.state}).
                </p>
              ) : null}
              {generate.isError ? (
                <p role="alert" style={alertStyle}>
                  {mutationErrorText(generate.error)}
                </p>
              ) : null}
              {draft.isError ? (
                <p role="alert" style={alertStyle}>
                  {mutationErrorText(draft.error)}
                </p>
              ) : null}
              {draft.data ? (
                <p aria-live="polite" style={liveStyle}>
                  Draft created — revision <code>{draft.data.draft_revision_id ?? "—"}</code>.
                </p>
              ) : null}
            </div>
          </div>

          <div className="cp-section-title">Draft Package Files</div>
          <DraftFiles detail={detail} />
        </section>

        <aside>
          <SidePanel detail={detail} />
        </aside>
      </div>

      {precheckOpen && detail !== null ? (
        <PreCheckModal detail={detail} onClose={() => setPrecheckOpen(false)} />
      ) : null}
    </div>
  );
}

// The chat board — a deterministic transcript derived from the request
// projection (no ad-hoc accumulation, so a reload re-seeds identically).
function MessagesBoard({
  detail,
  loading,
  error,
}: {
  detail: PackageRequestDetail | null;
  loading: boolean;
  error: unknown;
}) {
  if (loading) {
    return (
      <div className="cp-messages">
        <Loading label="Loading request…" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="cp-messages">
        <ErrorState error={error} />
      </div>
    );
  }
  if (detail === null) {
    return (
      <div className="cp-messages">
        <div className="cp-message-empty">CP Agent chat board</div>
      </div>
    );
  }

  const scan = detail.current_scan;
  const messages: Array<{ tag: string; ai: boolean; text: string }> = [
    {
      tag: "Request",
      ai: false,
      text: `${prettyToken(detail.package_type)} request created — mode ${prettyToken(
        detail.creation_mode,
      )}, source ${detail.source_kind}${
        detail.source_language ? ` (${detail.source_language})` : ""
      } → ${detail.target_runtime}.`,
    },
  ];
  if (scan) {
    const resolvedCount = asRecordArray(scan.resolved).length;
    const missingCount = asRecordArray(scan.missing).length;
    messages.push({
      tag: "CP Agent · Pre-Check",
      ai: true,
      text: `Pre-Check ${scan.status} — ${resolvedCount} resolved, ${missingCount} missing${
        detail.precheck_fresh ? "" : " (stale)"
      }.`,
    });
  }
  if (detail.state === "candidate_ready" || detail.can_generate_candidate) {
    messages.push({
      tag: "CP Agent · Candidate",
      ai: true,
      text: detail.can_generate_candidate
        ? "Dependencies resolved — a candidate can be generated (C.D.P)."
        : "Candidate is ready for a draft package.",
    });
  }
  if (detail.draft_revision_id) {
    messages.push({
      tag: "CP Agent · Draft",
      ai: true,
      text: `Draft package created — revision ${detail.draft_revision_id}.`,
    });
  }
  const run = detail.current_validation_run;
  if (run) {
    messages.push({
      tag: "CP Agent · Validation",
      ai: true,
      text: `Validation ${run.status}${detail.validation_fresh ? "" : " (stale)"}.`,
    });
  }
  if (detail.current_baseline) {
    messages.push({
      tag: "CP Agent · Baseline",
      ai: true,
      text: `Baseline ${detail.current_baseline.parse_status} — ${
        detail.current_baseline.original_filename ?? "csv"
      }.`,
    });
  }

  return (
    <div className="cp-messages">
      {messages.map((m, i) => (
        <div key={i} className={m.ai ? "cp-message ai" : "cp-message"}>
          <div className="cp-message-tag">{m.tag}</div>
          {m.text}
        </div>
      ))}
    </div>
  );
}

function DraftFiles({ detail }: { detail: PackageRequestDetail | null }) {
  if (detail === null || detail.draft_revision_id === null) {
    return (
      <div className="cp-file-list">
        <div className="cp-file-row cp-inactive-text">
          <span>No draft package created.</span>
          <span>—</span>
        </div>
      </div>
    );
  }
  return (
    <div className="cp-file-list">
      <div className="cp-file-row">
        <span>
          <code>{runtimeFileName(detail.package_type)}</code>
        </span>
        <span className="cp-file-purpose">Draft revision {detail.draft_revision_id}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right column — a single Package Status side panel (mockup §3 aside). The state
// summary sits at the top; Baseline, Resolver, Validation Tests and the Library
// Target follow as section-titled blocks inside the one panel body.
// ---------------------------------------------------------------------------

function SidePanel({ detail }: { detail: PackageRequestDetail | null }) {
  return (
    <div className="cp-panel" aria-label="Package status">
      <div className="cp-panel-head">
        <span>Package Status</span>
        <span className="cp-sub">{detail ? detail.request_id : "Not created"}</span>
      </div>
      <div className="cp-panel-body">
        <StateCard detail={detail} />
        {detail !== null ? (
          <>
            <BaselineSection detail={detail} />
            <ResolverSection detail={detail} />
            <ValidationSection detail={detail} />
            <LibraryTargetSection detail={detail} />
          </>
        ) : (
          <p className="cp-note" style={{ marginTop: 12 }}>
            Create or select a request to reveal Baseline, Resolver, Validation Tests and the
            Library Target.
          </p>
        )}
      </div>
    </div>
  );
}

// The Package Status state summary card (mockup .cp-state-card). Before a request
// exists the rows show canonical placeholders; once one is selected each value is
// driven by its server projection.
function StateCard({ detail }: { detail: PackageRequestDetail | null }) {
  return (
    <div className="cp-status-card" style={{ marginBottom: 0 }}>
      <div className="cp-status-row">
        <span className="cp-status-label">Package Name</span>
        <span>{detail?.package_root_id ?? "—"}</span>
      </div>
      <div className="cp-status-row">
        <span className="cp-status-label">Type</span>
        <span>{detail ? prettyToken(detail.package_type) : "—"}</span>
      </div>
      <div className="cp-status-row">
        <span className="cp-status-label">Version</span>
        <span>{detail ? detail.request_version : "—"}</span>
      </div>
      <div className="cp-status-row">
        <span className="cp-status-label">Status</span>
        <span>
          {detail ? (
            <StatusBadge tone={requestStateTone(detail.state)} label={prettyToken(detail.state)} />
          ) : (
            <span className="cp-inactive-text">Not Created</span>
          )}
        </span>
      </div>
      <div className="cp-status-row">
        <span className="cp-status-label">Target Library</span>
        <span>{detail ? targetLibrary(detail.package_type) : "—"}</span>
      </div>
      <div className="cp-status-row">
        <span className="cp-status-label">TA Pre-Check</span>
        <span>
          {detail?.current_scan ? (
            <StatusBadge
              tone={scanStatusTone(detail.current_scan.status)}
              label={`${prettyToken(detail.current_scan.status)}${
                detail.precheck_fresh ? "" : " · stale"
              }`}
            />
          ) : (
            "Not Checked"
          )}
        </span>
      </div>
      {detail !== null ? (
        <>
          <div className="cp-status-row">
            <span className="cp-status-label">Candidate</span>
            <span>
              {detail.can_generate_candidate
                ? "Ready"
                : detail.draft_revision_id
                  ? "Drafted"
                  : "Not ready"}
            </span>
          </div>
          <div className="cp-status-row">
            <span className="cp-status-label">Draft</span>
            <span>{detail.draft_revision_id ? "Present" : "—"}</span>
          </div>
          <div className="cp-status-row">
            <span className="cp-status-label">Validation</span>
            <span>
              {detail.current_validation_run ? (
                <StatusBadge
                  tone={validationRunTone(detail.current_validation_run.status)}
                  label={`${prettyToken(detail.current_validation_run.status)}${
                    detail.validation_fresh ? "" : " · stale"
                  }`}
                />
              ) : (
                "—"
              )}
            </span>
          </div>
        </>
      ) : null}
    </div>
  );
}

// R2-12: a small inline "why is this locked" note rendered directly next to a
// disabled lifecycle control (GAP item 11 — the user never guesses at a locked
// button). Renders nothing when the action is available.
function LockReason({ reason }: { reason: string | null }) {
  if (reason === null) return null;
  return (
    <span className="cp-note cp-lock-reason" role="note">
      {reason}
    </span>
  );
}

const EMPTY_BASELINE_FIELDS: BaselineMetadataFields = {
  provider: "",
  symbol: "",
  timeframe: "",
  rangeStart: "",
  rangeEnd: "",
  timezone: "",
  settings: "",
  sourceRevisionContext: "",
};

// Baseline (equivalence evidence) — doc 06 §4.4/§8.3. Real TradingView CSV: the
// file is transferred as multipart bytes (raw bytes never travel as pasted text;
// the server stores a content-addressed digest + parse report) and fed to the
// same useUploadBaseline hook. A package claiming translation/repair/equivalence
// may publish only with a PASSED baseline parse.
function BaselineSection({ detail }: { detail: PackageRequestDetail }) {
  const upload = useUploadBaseline();
  const parse = useStartBaselineParse();
  // Fail-closed role gate (R2-09 AdminGate pattern): the raw metadata JSON
  // renders only once /me proves is_admin.
  const isAdmin = useIsAdmin();
  const [file, setFile] = useState<File | null>(null);
  // R2-12 (GAP item 11): every key the baseline parse gate REQUIRES
  // (REQUIRED_BASELINE_METADATA_FIELDS) is a typed product field — a normal
  // user never writes JSON. Undocumented extra keys stay JSON, Admin-only
  // under Advanced (R2-04/05 disclosure pattern).
  const [fields, setFields] = useState<BaselineMetadataFields>(EMPTY_BASELINE_FIELDS);
  const [metadataText, setMetadataText] = useState("");
  const [metadataError, setMetadataError] = useState<string | null>(null);

  const baseline = detail.current_baseline;
  const anyPending = upload.isPending || parse.isPending;
  const actions = packageActionAvailability(detail);

  function setField(key: keyof BaselineMetadataFields, value: string) {
    setFields((prev) => ({ ...prev, [key]: value }));
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    upload.reset();
  }

  function onUpload() {
    setMetadataError(null);
    if (file === null) return;
    let extras: Record<string, unknown> = {};
    const trimmed = metadataText.trim();
    if (trimmed.length > 0) {
      try {
        const parsed: unknown = JSON.parse(trimmed);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          setMetadataError("Baseline metadata must be a JSON object.");
          return;
        }
        extras = parsed as Record<string, unknown>;
      } catch {
        setMetadataError("Baseline metadata is not valid JSON.");
        return;
      }
    }
    // The typed descriptors win over Advanced extras on key collision; empty
    // typed fields are omitted so the wire object matches what was filled in.
    const metadata = buildBaselineMetadata(fields, extras);
    // F-03: transfer the chosen CSV itself (multipart); the server derives the
    // filename/content type/digest and re-validates size/encoding/schema.
    upload.mutate({
      request_id: detail.request_id,
      request_version: detail.request_version,
      file,
      baseline_metadata: metadata,
    });
  }

  return (
    <>
      <div className="cp-section-title">TradingView Baseline / Comparison Report</div>
      <p className="cp-note" style={{ marginTop: 0 }}>
        {detail.baseline_required
          ? "This request claims equivalence — a PASSED baseline parse is required to publish."
          : "This request does not claim equivalence — a baseline is optional."}
      </p>

      <div className="cp-baseline-upload">
        <span>
          {file
            ? `${file.name} selected (${file.size} bytes)`
            : baseline
              ? `${baseline.original_filename ?? "baseline.csv"} uploaded`
              : "No baseline CSV selected."}
        </span>
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label="TradingView baseline CSV file"
          onChange={onFile}
        />
      </div>

      {baseline ? (
        <dl className="kv" style={{ marginTop: 10 }}>
          <dt>Parse status</dt>
          <dd>
            <StatusBadge
              tone={baselineParseTone(baseline.parse_status)}
              label={baseline.parse_status}
            />
          </dd>
          <dt>Asset</dt>
          <dd>
            <code>{baseline.baseline_asset_id}</code> (attempt {baseline.attempt_no})
          </dd>
          <dt>Digest</dt>
          <dd>
            <code>{baseline.content_digest ?? "—"}</code>
          </dd>
        </dl>
      ) : null}

      {/* R2-12 (GAP item 11): every parse-required descriptor
          (REQUIRED_BASELINE_METADATA_FIELDS) is a typed product field. */}
      <p className="cp-note" style={{ marginTop: 10, marginBottom: 4 }}>
        All descriptors below are required for the baseline parse to PASS — a file upload alone is
        not proof of equivalence.
      </p>
      <div className="strategy-form-grid" style={{ marginTop: 6 }}>
        <label className="cp-field">
          <span>Baseline provider</span>
          <input
            value={fields.provider}
            onChange={(e) => setField("provider", e.target.value)}
            placeholder="TradingView"
          />
        </label>
        <label className="cp-field">
          <span>Baseline symbol</span>
          <input
            value={fields.symbol}
            onChange={(e) => setField("symbol", e.target.value)}
            placeholder="BTCUSDT"
          />
        </label>
        <label className="cp-field">
          <span>Baseline timeframe</span>
          <input
            value={fields.timeframe}
            onChange={(e) => setField("timeframe", e.target.value)}
            placeholder="1h"
          />
        </label>
        <label className="cp-field">
          <span>Baseline range start</span>
          <input
            value={fields.rangeStart}
            onChange={(e) => setField("rangeStart", e.target.value)}
            placeholder="2024-01-01"
          />
        </label>
        <label className="cp-field">
          <span>Baseline range end</span>
          <input
            value={fields.rangeEnd}
            onChange={(e) => setField("rangeEnd", e.target.value)}
            placeholder="2024-06-30"
          />
        </label>
        <label className="cp-field">
          <span>Baseline timezone</span>
          <input
            value={fields.timezone}
            onChange={(e) => setField("timezone", e.target.value)}
            placeholder="UTC"
          />
        </label>
        <label className="cp-field">
          <span>Baseline settings</span>
          <input
            value={fields.settings}
            onChange={(e) => setField("settings", e.target.value)}
            placeholder="length=14, source=close"
          />
        </label>
        <label className="cp-field">
          <span>Source revision context</span>
          <input
            value={fields.sourceRevisionContext}
            onChange={(e) => setField("sourceRevisionContext", e.target.value)}
            placeholder="Pine v5 script r3"
          />
        </label>
      </div>
      {isAdmin ? (
        <details style={{ marginTop: 10 }}>
          <summary>Advanced (extra metadata JSON)</summary>
          <label style={{ display: "block", marginTop: 8 }}>
            <span className="cp-note">Baseline metadata (JSON)</span>
            <textarea
              aria-label="Baseline metadata"
              value={metadataText}
              onChange={(e) => setMetadataText(e.target.value)}
              rows={3}
              placeholder='{"broker_notes":"…"}'
            />
          </label>
        </details>
      ) : null}

      <div className="cp-button-row">
        <button
          type="button"
          className="btn"
          disabled={!actions.uploadBaseline || anyPending || file === null}
          onClick={onUpload}
        >
          {upload.isPending ? "Uploading…" : "Upload CSV"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={!actions.parseBaseline || anyPending}
          onClick={() =>
            parse.mutate({
              request_id: detail.request_id,
              request_version: detail.request_version,
            })
          }
        >
          {parse.isPending ? "Parsing…" : "Run baseline parse"}
        </button>
      </div>
      <LockReason reason={actions.reasons.parseBaseline} />
      <p className="cp-note" style={{ marginTop: 8 }}>
        The Baseline Comparison Report compares the TradingView CSV signals with the translated
        runtime output: matched, missing and extra signals, and timing / value mismatch.
      </p>

      {metadataError ? (
        <p role="alert" style={alertStyle}>
          {metadataError}
        </p>
      ) : null}
      {upload.isError ? (
        <p role="alert" style={alertStyle}>
          {mutationErrorText(upload.error)}
        </p>
      ) : null}
      {upload.data ? (
        <p aria-live="polite" style={liveStyle}>
          Baseline uploaded — asset <code>{upload.data.baseline_asset_id}</code> (
          {upload.data.size_bytes} bytes).
        </p>
      ) : null}
      {parse.isError ? (
        <p role="alert" style={alertStyle}>
          {mutationErrorText(parse.error)}
        </p>
      ) : null}
      {parse.data ? (
        <p aria-live="polite" style={liveStyle}>
          Baseline parse {parse.data.parse_status} — parser {parse.data.parser_version}.
        </p>
      ) : null}
    </>
  );
}

// Pine TA / Embedded System Package resolver — the resolved/missing rows from the
// current immutable Pre-Check scan (doc 07 §7.1). Each resolved ref pins the exact
// ESP revision (never name-only/latest); a missing call carries its typed code.
function ResolverSection({ detail }: { detail: PackageRequestDetail }) {
  const scan = detail.current_scan;
  const resolved = scan ? (asRecordArray(scan.resolved) as ResolvedRef[]) : [];
  const missing = scan ? (asRecordArray(scan.missing) as MissingCall[]) : [];

  return (
    <>
      <div className="cp-section-title">Pine TA / ESP Resolver</div>
      {scan === null ? (
        <p className="cp-note" style={{ marginTop: 0 }}>
          Run Pre-Check to scan code TA calls (ta.sma, ta.ema, ta.rsi, ta.atr…) against the Embedded
          System Packages.
        </p>
      ) : (
        <>
          <div className="cp-file-list">
            {resolved.length === 0 ? (
              <div className="cp-file-row cp-inactive-text">
                <span>No resolved TA calls.</span>
                <span>—</span>
              </div>
            ) : (
              resolved.map((ref, i) => (
                <div className="cp-file-row" key={`r-${i}`}>
                  <span>
                    <code>{ref.call ?? ref.canonical_key ?? "—"}</code>
                  </span>
                  <span className="cp-file-purpose">
                    {ref.embedded_revision_id ? `→ ${ref.embedded_revision_id}` : "resolved"}
                  </span>
                </div>
              ))
            )}
          </div>
          {missing.length > 0 ? (
            <>
              <div className="cp-section-title">Missing dependencies</div>
              <div className="cp-file-list">
                {missing.map((call, i) => (
                  <div className="cp-file-row" key={`m-${i}`}>
                    <span>
                      <code>{call.call ?? "—"}</code>
                    </span>
                    <span className="cp-check-result fail">{call.code ?? "MISSING"}</span>
                  </div>
                ))}
              </div>
              <p className="cp-note" style={{ marginTop: 8 }}>
                Create the missing call as an Embedded System Package in Package Library, then re-run
                Pre-Check.
              </p>
            </>
          ) : null}
        </>
      )}
    </>
  );
}

// The six canonical v18 §3 validation rows (mockup cpVSyntax…cpVBaseline). Server
// checks are mapped onto these fixed rows by name; an unmatched row shows NOT
// STARTED and any surplus server check is appended below so no evidence is hidden.
const VALIDATION_ROWS: Array<{ label: string; keys: string[] }> = [
  { label: "Syntax Check", keys: ["syntax", "syntax_check"] },
  { label: "Runtime Check", keys: ["runtime", "runtime_check"] },
  {
    label: "Output Structure Check",
    keys: ["output_structure", "output", "output_structure_check", "output_contract"],
  },
  {
    label: "Real Market Data Test",
    keys: ["real_market_data", "real_market_data_test", "market_data", "market"],
  },
  {
    label: "Repaint / Future Leak Review",
    keys: ["repaint", "future_leak", "repaint_future_leak", "repaint_review", "risk"],
  },
  { label: "Baseline Comparison", keys: ["baseline", "baseline_comparison"] },
];

function normalizeCheckKey(raw: string): string {
  return raw.trim().toLowerCase().replace(/[\s/-]+/g, "_");
}

// The raw check status (status/result/passed boolean) reduced to a display token
// + a cp-check-result tone class — the server's evidence still drives it.
function checkStatusView(check: Record<string, unknown>): { text: string; tone: string } {
  const rawStatus =
    check.status ??
    check.result ??
    (check.passed === true ? "passed" : check.passed === false ? "failed" : null);
  const status = rawStatus === null || rawStatus === undefined ? "—" : String(rawStatus);
  const lower = status.toLowerCase();
  const tone =
    lower === "passed" || lower === "pass"
      ? "pass"
      : lower === "failed" || lower === "fail"
        ? "fail"
        : lower === "—"
          ? ""
          : "ready";
  return { text: status === "—" ? "—" : status.toUpperCase(), tone };
}

// Validation Tests + lifecycle actions (doc 06 §7). The six fixed rows above come
// from the immutable current validation run's ``checks``; the buttons run
// validation, request a revision or approve. Approve is Admin-only SERVER-side
// (CR-02) — the button is never role-gated; a denial surfaces the canonical
// envelope verbatim.
function ValidationSection({ detail }: { detail: PackageRequestDetail }) {
  const validate = useRunValidation();
  const revision = useRequestRevision();
  const approve = useApproveRequest();
  const [note, setNote] = useState("");

  const run = detail.current_validation_run;
  const checks = run ? run.checks : [];
  const anyPending = validate.isPending || revision.isPending || approve.isPending;
  // Gating truth from the backend state machine (F-12): a draft cannot approve
  // directly — approve unlocks only in eligible_for_approval with fresh evidence
  // (+ a parsed baseline when equivalence is claimed).
  const actions = packageActionAvailability(detail);

  // Map each server check to a normalized key; a row claims the first matching
  // check and surplus checks (no canonical row) are appended below.
  const claimed = new Set<number>();
  const rows = VALIDATION_ROWS.map((row) => {
    const index = checks.findIndex((check, i) => {
      if (claimed.has(i)) return false;
      const key = normalizeCheckKey(String(check.name ?? check.check ?? check.id ?? ""));
      return row.keys.includes(key);
    });
    if (index >= 0) claimed.add(index);
    return { label: row.label, check: index >= 0 ? checks[index] : null };
  });
  const surplus = checks
    .map((check, i) => ({ check, i }))
    .filter(({ i }) => !claimed.has(i));

  return (
    <>
      <div className="cp-section-title">Validation Tests</div>
      <div className="cp-validation-list">
        {rows.map((row) => {
          const view = row.check ? checkStatusView(row.check) : { text: "NOT STARTED", tone: "" };
          return (
            <div className="cp-validation-row" key={row.label}>
              <span>{row.label}</span>
              <span className={`cp-check-result ${view.tone}`}>{view.text}</span>
            </div>
          );
        })}
        {surplus.map(({ check, i }) => {
          const name = String(check.name ?? check.check ?? check.id ?? `Check ${i + 1}`);
          const view = checkStatusView(check);
          return (
            <div className="cp-validation-row" key={`surplus-${i}`}>
              <span>{prettyToken(name)}</span>
              <span className={`cp-check-result ${view.tone}`}>{view.text}</span>
            </div>
          );
        })}
      </div>

      <label style={{ display: "block", marginTop: 10 }}>
        <span className="cp-note">Approval note (optional)</span>
        <input
          aria-label="Approval note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Recorded on the approval decision…"
        />
      </label>

      <div className="cp-button-row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!actions.runValidation || anyPending}
          onClick={() =>
            validate.mutate({
              request_id: detail.request_id,
              request_version: detail.request_version,
            })
          }
        >
          {validate.isPending ? "Running validation…" : "Run Validation Tests"}
        </button>
        {/* Approve is Admin-only end-to-end (CR-02). R2-09/R2-12: the primary
            control is fail-closed behind the /me projection — a non-Admin sees
            WHY instead of a button that can only 403; the server still
            re-checks every dispatch. */}
        <AdminGate
          detail={
            detail.state === "eligible_for_approval"
              ? "This request is eligible — awaiting an Admin approval decision."
              : undefined
          }
        >
          <button
            type="button"
            className="btn"
            disabled={!actions.approve || anyPending}
            onClick={() =>
              approve.mutate({
                request_id: detail.request_id,
                expected_head_revision_id: detail.draft_revision_id,
                note: note.trim().length > 0 ? note.trim() : null,
              })
            }
          >
            {approve.isPending ? "Approving…" : "Approve Package"}
          </button>
        </AdminGate>
        <button
          type="button"
          className="btn"
          disabled={!actions.requestRevision || anyPending}
          onClick={() =>
            revision.mutate({
              request_id: detail.request_id,
              request_version: detail.request_version,
            })
          }
        >
          {revision.isPending ? "Requesting revision…" : "Request Revision"}
        </button>
      </div>
      {/* R2-12: each locked action explains itself next to its control, from
          the server projection (state / freshness / baseline flags) — a user
          never guesses at a disabled button. A draft cannot be approved
          directly (F-12). */}
      <LockReason reason={actions.reasons.runValidation} />
      <LockReason reason={actions.reasons.approve} />

      {validate.isError ? (
        <p role="alert" style={alertStyle}>
          {mutationErrorText(validate.error)}
        </p>
      ) : null}
      {validate.data ? (
        <p aria-live="polite" style={liveStyle}>
          Validation {validate.data.status} — run <code>{validate.data.validation_run_id}</code> →{" "}
          {prettyToken(validate.data.state)}.
        </p>
      ) : null}
      {revision.isError ? (
        <p role="alert" style={alertStyle}>
          {mutationErrorText(revision.error)}
        </p>
      ) : null}
      {revision.data ? (
        <p aria-live="polite" style={liveStyle}>
          Revision requested — {prettyToken(revision.data.state)}.
        </p>
      ) : null}
      {approve.isError ? (
        <p role="alert" style={alertStyle}>
          {mutationErrorText(approve.error)}
        </p>
      ) : null}
      {approve.data ? (
        <p aria-live="polite" style={liveStyle}>
          Approved &amp; published — revision <code>{approve.data.revision_id ?? "—"}</code> (
          {approve.data.visibility_scope}).
        </p>
      ) : null}
    </>
  );
}

function LibraryTargetSection({ detail }: { detail: PackageRequestDetail }) {
  const approved = detail.state === "approved" || detail.state === "published";
  return (
    <>
      <div className="cp-section-title">Package Library Target</div>
      <div className="cp-target-pool">
        <span>{targetLibrary(detail.package_type)}</span>
        {approved ? (
          <StatusBadge tone="ok" label={prettyToken(detail.state)} />
        ) : (
          <span className="cp-inactive-text">Awaiting approval</span>
        )}
      </div>
    </>
  );
}

function Pager({
  canPrev,
  nextCursor,
  onPrev,
  onNext,
}: {
  canPrev: boolean;
  nextCursor: string | null;
  onPrev: () => void;
  onNext: (cursor: string) => void;
}) {
  if (!canPrev && nextCursor === null) return null;
  return (
    <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
      <button type="button" className="btn" disabled={!canPrev} onClick={onPrev}>
        Prev
      </button>
      <button
        type="button"
        className="btn"
        disabled={nextCursor === null}
        onClick={() => (nextCursor !== null ? onNext(nextCursor) : undefined)}
      >
        Next
      </button>
    </div>
  );
}

const alertStyle = { color: "var(--down)", margin: "8px 0 0", fontSize: 13 } as const;
const liveStyle = { margin: "8px 0 0", fontSize: 13 } as const;
