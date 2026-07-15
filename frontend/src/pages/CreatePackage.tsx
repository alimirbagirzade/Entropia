import { useState, type ChangeEvent, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  CREATE_PACKAGE_KINDS,
  CREATION_MODES,
  SOURCE_LANGUAGES,
  SUPPORTED_TARGET_RUNTIME,
  approvalBlockReason,
  asRecordArray,
  baselineParseTone,
  outputKindsFor,
  packageActionAvailability,
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
  useRunPrecheck,
  useRunValidation,
  useStartBaselineParse,
  useUploadBaseline,
  validationRunTone,
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
// Create Package (doc 06) — v18 CP Agent workspace. The page is a single
// composition plane: a request/AI compose column on the left (chat board + draft
// files) and a Package Status / Baseline / Resolver / Validation / Library-Target
// panel on the right. Every action reuses the real backend hooks unchanged; the
// server re-validates every field/transition and a denial (e.g. a guest, or a
// non-Admin approve) surfaces the canonical error envelope verbatim.
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

      <div className="cp-create-layout">
        <section>
          <RequestColumn
            detail={detail}
            loading={selectedId !== null && request.isLoading}
            error={selectedId !== null && request.isError ? request.error : null}
            onCreated={setSelectedId}
            onClear={() => setSelectedId(null)}
          />
        </section>
        <aside style={{ display: "grid", gap: 4 }}>
          <StatusPanel detail={detail} />
          {detail !== null ? (
            <>
              <BaselinePanel detail={detail} />
              <ResolverPanel detail={detail} />
              <ValidationPanel detail={detail} />
              <LibraryTargetPanel detail={detail} />
            </>
          ) : (
            <p className="cp-note" style={{ marginTop: 8 }}>
              Create or select a request to reveal Baseline, Resolver, Validation
              Tests and the Library Target.
            </p>
          )}
        </aside>
      </div>
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
// Left column — identity controls + the CP Agent chat board + compose + actions
// + draft package files. When no request is selected the compose Send creates an
// immutable request (doc 06 §4). When one is selected the chat board is derived
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

function RequestColumn({
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
  const families = useRationaleFamilies(null);
  const create = useCreatePackageRequest();
  const precheck = useRunPrecheck();
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

  function onSend(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    const declared = form.declared_keys
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((key) => ({ key }));
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

  // Pre-Check runs against the selected request (doc 07). C.D.P chains
  // generate-candidate → create-draft (the mockup "Create Draft Package"); the
  // accepted candidate_hash from generate becomes the draft's staleness token.
  const actionsPending = precheck.isPending || generate.isPending || draft.isPending;
  // The state-machine truth for which lifecycle actions this request permits
  // (F-12): the buttons below reflect it instead of always being clickable.
  const actions = packageActionAvailability(detail);

  function onPrecheck() {
    if (detail === null || !actions.precheck) return;
    precheck.mutate({ request_id: detail.request_id, request_version: detail.request_version });
  }

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
    <form onSubmit={onSend}>
      {/* Identity controls (doc 06 §4 field contract). Requiredness is mirrored
          client-side only for Send gating; the server re-validates every field. */}
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
        <label>
          <span>Output contract kind</span>
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

      {!isEsp && familyRows.length === 0 && !families.isLoading ? (
        <p className="cp-note" style={{ marginTop: -4, marginBottom: 12 }}>
          No active Rationale Family — create one first (required for Indicator / Condition).
        </p>
      ) : null}

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
            <span>Declared dependencies (one canonical key per line, optional)</span>
            <textarea
              aria-label="Declared dependencies"
              value={form.declared_keys}
              onChange={(e) => setForm((prev) => ({ ...prev, declared_keys: e.target.value }))}
              placeholder={"ta.sma\nta.rsi"}
              style={{ minHeight: 64 }}
            />
          </label>
          <div className="cp-button-row">
            <button
              type="button"
              className="btn"
              disabled={!actions.precheck || actionsPending}
              onClick={onPrecheck}
            >
              {precheck.isPending ? "Checking dependencies…" : "Pre-Check"}
            </button>
            <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
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
          {detail !== null && actions.nextStepHint.length > 0 ? (
            <p className="cp-note" aria-live="polite" style={{ marginTop: 8, fontWeight: 600 }}>
              Next step: {actions.nextStepHint}
            </p>
          ) : null}
          <p className="cp-note" style={{ marginTop: 8 }}>
            Pre-Check analyses code TA dependencies through Embedded System Packages. C.D.P creates a
            Draft Package, not an approved package.
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
          {precheck.isError ? (
            <p role="alert" style={alertStyle}>
              {mutationErrorText(precheck.error)}
            </p>
          ) : null}
          {precheck.data ? (
            <p aria-live="polite" style={liveStyle}>
              Pre-Check {precheck.data.status} — scan <code>{precheck.data.scan_id}</code> (attempt{" "}
              {precheck.data.attempt_no}).
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
    </form>
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
// Right column panels.
// ---------------------------------------------------------------------------

function StatusPanel({ detail }: { detail: PackageRequestDetail | null }) {
  return (
    <div className="cp-panel" aria-label="Package status">
      <div className="cp-panel-head">
        <span>Package Status</span>
        <span className="cp-sub">{detail ? detail.request_id : "Not created"}</span>
      </div>
      <div className="cp-panel-body">
        {detail === null ? (
          <EmptyState title="No request" description="Compose a request to see its status." />
        ) : (
          <div className="cp-status-card" style={{ marginBottom: 0 }}>
            <div className="cp-status-row">
              <span className="cp-status-label">Type</span>
              <span>{prettyToken(detail.package_type)}</span>
            </div>
            <div className="cp-status-row">
              <span className="cp-status-label">Version</span>
              <span>{detail.request_version}</span>
            </div>
            <div className="cp-status-row">
              <span className="cp-status-label">Status</span>
              <StatusBadge tone={requestStateTone(detail.state)} label={prettyToken(detail.state)} />
            </div>
            <div className="cp-status-row">
              <span className="cp-status-label">Target Library</span>
              <span>{targetLibrary(detail.package_type)}</span>
            </div>
            <div className="cp-status-row">
              <span className="cp-status-label">TA Pre-Check</span>
              <span>
                {detail.current_scan ? (
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
          </div>
        )}
      </div>
    </div>
  );
}

// Baseline (equivalence evidence) — doc 06 §4.4/§8.3. Real TradingView CSV: the
// file is read as UTF-8 text in the browser (raw bytes never travel; the server
// stores a content-addressed digest + parse report) and fed to the same
// useUploadBaseline hook. A package claiming translation/repair/equivalence may
// publish only with a PASSED baseline parse.
function BaselinePanel({ detail }: { detail: PackageRequestDetail }) {
  const upload = useUploadBaseline();
  const parse = useStartBaselineParse();
  const [file, setFile] = useState<File | null>(null);
  const [metadataText, setMetadataText] = useState("");
  const [metadataError, setMetadataError] = useState<string | null>(null);

  const baseline = detail.current_baseline;
  const anyPending = upload.isPending || parse.isPending;
  const actions = packageActionAvailability(detail);

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    upload.reset();
  }

  function onUpload() {
    setMetadataError(null);
    if (file === null) return;
    let metadata: Record<string, unknown> = {};
    const trimmed = metadataText.trim();
    if (trimmed.length > 0) {
      try {
        const parsed: unknown = JSON.parse(trimmed);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          setMetadataError("Baseline metadata must be a JSON object.");
          return;
        }
        metadata = parsed as Record<string, unknown>;
      } catch {
        setMetadataError("Baseline metadata is not valid JSON.");
        return;
      }
    }
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
    <div className="cp-panel">
      <div className="cp-panel-head">
        <span>TradingView Baseline / Comparison Report</span>
      </div>
      <div className="cp-panel-body">
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

        <label style={{ display: "block", marginTop: 10 }}>
          <span className="cp-note">Baseline metadata (JSON)</span>
          <textarea
            aria-label="Baseline metadata"
            value={metadataText}
            onChange={(e) => setMetadataText(e.target.value)}
            rows={3}
            placeholder='{"provider":"…","symbol":"…","timeframe":"…","range":"…"}'
          />
        </label>

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
      </div>
    </div>
  );
}

// Pine TA / Embedded System Package resolver — the resolved/missing rows from the
// current immutable Pre-Check scan (doc 07 §7.1). Each resolved ref pins the exact
// ESP revision (never name-only/latest); a missing call carries its typed code.
function ResolverPanel({ detail }: { detail: PackageRequestDetail }) {
  const scan = detail.current_scan;
  const resolved = scan ? (asRecordArray(scan.resolved) as ResolvedRef[]) : [];
  const missing = scan ? (asRecordArray(scan.missing) as MissingCall[]) : [];

  return (
    <div className="cp-panel">
      <div className="cp-panel-head">
        <span>Pine TA / ESP Resolver</span>
        {scan ? <span className="cp-sub">{prettyToken(scan.status)}</span> : null}
      </div>
      <div className="cp-panel-body">
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
      </div>
    </div>
  );
}

// Validation Tests + lifecycle actions (doc 06 §7). The per-check rows come from
// the immutable current validation run's ``checks``; the buttons run validation,
// request a revision or approve. Approve is Admin-only SERVER-side (CR-02) — the
// button is never role-gated; a denial surfaces the canonical envelope verbatim.
function ValidationPanel({ detail }: { detail: PackageRequestDetail }) {
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
  const approvalBlocked = approvalBlockReason(detail);

  return (
    <div className="cp-panel">
      <div className="cp-panel-head">
        <span>Validation Tests</span>
        {run ? (
          <span className="cp-sub">
            {prettyToken(run.status)}
            {detail.validation_fresh ? "" : " · stale"}
          </span>
        ) : null}
      </div>
      <div className="cp-panel-body">
        <div className="cp-validation-list">
          {checks.length === 0 ? (
            <div className="cp-validation-row cp-inactive-text">
              <span>No validation run yet.</span>
              <span className="cp-check-result">NOT STARTED</span>
            </div>
          ) : (
            checks.map((check, i) => {
              const name = String(check.name ?? check.check ?? check.id ?? `Check ${i + 1}`);
              const status = String(check.status ?? check.result ?? "—");
              const tone =
                status === "passed" || status === "pass"
                  ? "pass"
                  : status === "failed" || status === "fail"
                    ? "fail"
                    : "ready";
              return (
                <div className="cp-validation-row" key={`c-${i}`}>
                  <span>{prettyToken(name)}</span>
                  <span className={`cp-check-result ${tone}`}>{status.toUpperCase()}</span>
                </div>
              );
            })
          )}
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
        </div>
        {/* Explain the approval gate when eligible but still blocked (stale
            evidence / missing baseline), and why approval is locked before
            eligibility — so a user never guesses at a disabled Approve button. */}
        {approvalBlocked !== null ? (
          <p className="cp-note" style={{ marginTop: 8 }}>
            {approvalBlocked}
          </p>
        ) : !actions.approve && detail.state !== "approved" ? (
          <p className="cp-note" style={{ marginTop: 8 }}>
            Approval unlocks after a passed validation run moves the request to
            eligible for approval — a draft cannot be approved directly.
          </p>
        ) : null}

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
      </div>
    </div>
  );
}

function LibraryTargetPanel({ detail }: { detail: PackageRequestDetail }) {
  const approved = detail.state === "approved" || detail.state === "published";
  return (
    <div className="cp-panel">
      <div className="cp-panel-head">
        <span>Package Library Target</span>
      </div>
      <div className="cp-panel-body">
        <div className="cp-target-pool">
          <span>{targetLibrary(detail.package_type)}</span>
          {approved ? (
            <StatusBadge tone="ok" label={prettyToken(detail.state)} />
          ) : (
            <span className="cp-inactive-text">Awaiting approval</span>
          )}
        </div>
      </div>
    </div>
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
