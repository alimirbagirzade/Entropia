import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  CREATE_PACKAGE_KINDS,
  CREATION_MODES,
  SOURCE_LANGUAGES,
  SUPPORTED_TARGET_RUNTIME,
  baselineParseTone,
  outputKindsFor,
  requestStateTone,
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
  type PackageRequestDetail,
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

// Create Package (doc 06): compose an immutable create-package request, list the
// actor's own requests and open the read-only request projection. Any
// authenticated actor may create + operate on their OWN request; a denial (e.g.
// a guest) surfaces the server 403 envelope verbatim.
export function CreatePackage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return (
    <>
      <h1 className="page-title">Create Package</h1>
      <p className="page-sub">
        Compose an immutable create-package request (Indicator / Condition /
        Embedded System). Pre-Check, candidate generation, draft and approve run
        from the request once it exists.
      </p>
      <CreateForm onCreated={setSelectedId} />
      <RequestsCard selectedId={selectedId} onSelect={setSelectedId} />
      {selectedId !== null ? <RequestDetailCard requestId={selectedId} /> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Compose — the create-request form (doc 06 §4 field contract). Requiredness is
// mirrored client-side only for submit gating; the server is authoritative and
// re-validates every field, returning the canonical error envelope verbatim.
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

function CreateForm({ onCreated }: { onCreated: (requestId: string) => void }) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const families = useRationaleFamilies(null);
  const create = useCreatePackageRequest();

  const isCodeMode = sourceKindForMode(form.creation_mode) === "code";
  const isEsp = form.package_type === "embedded_system";
  const needsLabel = isCodeMode && form.source_language === "other";
  const kindOptions = outputKindsFor(form.package_type);

  const canSubmit =
    form.request_body.trim().length > 0 &&
    form.output_kind.length > 0 &&
    (!isCodeMode || form.source_language.length > 0) &&
    (!needsLabel || form.other_language_label.trim().length > 0) &&
    (isEsp || form.rationale_family_id.length > 0) &&
    !create.isPending;

  // Switching the package type resets the output kind to the first kind valid
  // for the new type (doc 06 §4.3) so a stale incompatible kind never submits.
  function onPackageType(next: CreatePackageKind) {
    const nextKinds = outputKindsFor(next);
    setForm((prev) => ({ ...prev, package_type: next, output_kind: nextKinds[0] ?? "" }));
  }

  function onSubmit(event: FormEvent) {
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

  const familyRows = families.data?.data ?? [];

  return (
    <section className="card" aria-labelledby="cp-create-h">
      <h3 id="cp-create-h" style={{ marginTop: 0 }}>
        New request
      </h3>
      <form className="cp-form" onSubmit={onSubmit}>
        <div className="cp-field">
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
        </div>

        <div className="cp-field">
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
        </div>

        {isCodeMode ? (
          <div className="cp-field">
            <span>Source language</span>
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
          </div>
        ) : (
          <div className="cp-field">
            <span>Source language</span>
            <p className="cp-note">Not applicable — Generate From Description carries no code.</p>
          </div>
        )}

        {needsLabel ? (
          <div className="cp-field">
            <span>Other language + version</span>
            <input
              aria-label="Other language and version"
              value={form.other_language_label}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, other_language_label: e.target.value }))
              }
              placeholder="e.g. MQL5 build 3980"
            />
          </div>
        ) : null}

        <div className="cp-field">
          <span>Target runtime</span>
          <select aria-label="Target runtime" value={SUPPORTED_TARGET_RUNTIME} disabled>
            <option value={SUPPORTED_TARGET_RUNTIME}>{SUPPORTED_TARGET_RUNTIME}</option>
          </select>
        </div>

        <div className="cp-field">
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
        </div>

        {isEsp ? (
          <div className="cp-field">
            <span>Rationale family</span>
            <p className="cp-note">
              Not applicable — Embedded System takes the system classification.
            </p>
          </div>
        ) : (
          <div className="cp-field">
            <span>Rationale family</span>
            <select
              aria-label="Rationale family"
              value={form.rationale_family_id}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, rationale_family_id: e.target.value }))
              }
            >
              <option value="">Select a family…</option>
              {familyRows.map((fam) => (
                <option key={fam.entity_id} value={fam.entity_id}>
                  {fam.display_name}
                </option>
              ))}
            </select>
            {familyRows.length === 0 && !families.isLoading ? (
              <p className="cp-note">
                No active Rationale Family — create one first (required for Indicator /
                Condition).
              </p>
            ) : null}
          </div>
        )}

        <div className="cp-field cp-wide">
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
        </div>

        <div className="cp-field cp-wide">
          <span>Declared dependencies (one canonical key per line, optional)</span>
          <textarea
            aria-label="Declared dependencies"
            value={form.declared_keys}
            onChange={(e) => setForm((prev) => ({ ...prev, declared_keys: e.target.value }))}
            placeholder={"ta.sma\nta.rsi"}
            style={{ minHeight: 72 }}
          />
        </div>

        <div className="cp-field cp-wide">
          <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
            {create.isPending ? "Creating…" : "Create request"}
          </button>
        </div>
      </form>

      {create.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(create.error)}
        </p>
      ) : null}
      {create.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Request created — <code>{create.data.request_id}</code> ({create.data.package_type},{" "}
          {create.data.state}).
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Requests index — the actor's own requests (Admins see all), keyset-paged.
// ---------------------------------------------------------------------------

function RequestsCard({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (requestId: string) => void;
}) {
  const pager = useCursorStack();
  const requests = usePackageRequests(pager.cursor);

  return (
    <section className="card" aria-labelledby="cp-requests-h">
      <h3 id="cp-requests-h" style={{ marginTop: 0 }}>
        My requests
      </h3>
      {requests.isLoading ? (
        <Loading label="Loading requests…" />
      ) : requests.isError ? (
        <ErrorState error={requests.error} onRetry={() => void requests.refetch()} />
      ) : requests.data ? (
        <>
          {requests.data.data.length === 0 ? (
            <EmptyState title="No requests yet" description="Create your first request above." />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Request</th>
                  <th scope="col">Type</th>
                  <th scope="col">Source</th>
                  <th scope="col">State</th>
                  <th scope="col" />
                </tr>
              </thead>
              <tbody>
                {requests.data.data.map((req) => (
                  <tr key={req.request_id}>
                    <td>
                      <code>{req.request_id}</code>
                    </td>
                    <td>{req.package_type}</td>
                    <td>{req.source_kind}</td>
                    <td>
                      <StatusBadge tone={requestStateTone(req.state)} label={req.state} />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        aria-pressed={selectedId === req.request_id}
                        onClick={() => onSelect(req.request_id)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={requests.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Request detail — the read-only projection (flow state + current scan hints).
// ---------------------------------------------------------------------------

function RequestDetailCard({ requestId }: { requestId: string }) {
  const request = usePackageRequest(requestId);
  return (
    <section className="card" aria-labelledby="cp-detail-h">
      <h3 id="cp-detail-h" style={{ marginTop: 0 }}>
        Request detail
      </h3>
      {request.isLoading ? (
        <Loading label="Loading request…" />
      ) : request.isError ? (
        <ErrorState error={request.error} onRetry={() => void request.refetch()} />
      ) : request.data ? (
        <RequestDetailBody detail={request.data} />
      ) : null}
    </section>
  );
}

function RequestDetailBody({ detail }: { detail: PackageRequestDetail }) {
  const scan = detail.current_scan;
  const declaredKeys = detail.declared_dependencies
    .map((dep) => String((dep as { key?: unknown }).key ?? ""))
    .filter((key) => key.length > 0);
  return (
    <>
      {/* v18 mockup PACKAGE STATUS side-panel — a status summary derived
          strictly from the real request projection (no fabricated validation
          results; the mockup's per-check rows have no backend equivalent). */}
      <div className="cp-status-card" aria-label="Package status">
        <div className="cp-status-row">
          <span className="cp-status-label">Type</span>
          <span>{prettyToken(detail.package_type)}</span>
        </div>
        <div className="cp-status-row">
          <span className="cp-status-label">Version</span>
          <span>{detail.request_version}</span>
        </div>
        <div className="cp-status-row">
          <span className="cp-status-label">Request state</span>
          <StatusBadge tone={requestStateTone(detail.state)} label={prettyToken(detail.state)} />
        </div>
        <div className="cp-status-row">
          <span className="cp-status-label">TA Pre-Check</span>
          <span>
            {detail.precheck_fresh ? "Fresh" : "Stale"}
            {scan ? ` · ${prettyToken(scan.status)}` : ""}
          </span>
        </div>
        <div className="cp-status-row">
          <span className="cp-status-label">Candidate</span>
          <span>{detail.can_generate_candidate ? "Ready" : "Not ready"}</span>
        </div>
        <div className="cp-status-row">
          <span className="cp-status-label">Draft</span>
          <span>{detail.draft_revision_id ? "Present" : "—"}</span>
        </div>
        <div className="cp-status-row">
          <span className="cp-status-label">Validation</span>
          <span>
            {detail.current_validation_run ? (
              <>
                <StatusBadge
                  tone={validationRunTone(detail.current_validation_run.status)}
                  label={prettyToken(detail.current_validation_run.status)}
                />
                {detail.validation_fresh ? "" : " · stale"}
              </>
            ) : (
              "—"
            )}
          </span>
        </div>
        <div className="cp-status-row">
          <span className="cp-status-label">Baseline</span>
          <span>
            {detail.current_baseline ? (
              <StatusBadge
                tone={baselineParseTone(detail.current_baseline.parse_status)}
                label={prettyToken(detail.current_baseline.parse_status)}
              />
            ) : detail.baseline_required ? (
              "Required — none"
            ) : (
              "Not required"
            )}
          </span>
        </div>
      </div>

      <dl className="kv">
        <dt>Request</dt>
        <dd>
          <code>{detail.request_id}</code>
        </dd>
        <dt>State</dt>
        <dd>
          <StatusBadge tone={requestStateTone(detail.state)} label={detail.state} />
        </dd>
        <dt>Type / mode</dt>
        <dd>
          {detail.package_type} · {detail.creation_mode}
        </dd>
        <dt>Source</dt>
        <dd>
          {detail.source_kind}
          {detail.source_language ? ` · ${detail.source_language}` : ""} → {detail.target_runtime}
        </dd>
        <dt>Output contract</dt>
        <dd>
          <code>{JSON.stringify(detail.output_contract)}</code>
        </dd>
        <dt>Rationale family</dt>
        <dd>{detail.rationale_family_id ?? "—"}</dd>
        <dt>Pre-Check fresh</dt>
        <dd>{detail.precheck_fresh ? "yes" : "no"}</dd>
        <dt>Can generate candidate</dt>
        <dd>{detail.can_generate_candidate ? "yes" : "no"}</dd>
        <dt>Draft revision</dt>
        <dd>{detail.draft_revision_id ?? "—"}</dd>
        <dt>Context hash</dt>
        <dd>
          <code>{detail.context_hash}</code>
        </dd>
        <dt>Version</dt>
        <dd>{detail.request_version}</dd>
        <dt>Created</dt>
        <dd>{formatUtc(detail.created_at)}</dd>
      </dl>

      {declaredKeys.length > 0 ? (
        <p style={{ marginBottom: 0 }}>Declared: {declaredKeys.join(", ")}</p>
      ) : null}

      {scan ? (
        <div style={{ marginTop: 14 }}>
          <h4 style={{ margin: "0 0 8px" }}>Current Pre-Check scan</h4>
          <dl className="kv">
            <dt>Scan</dt>
            <dd>
              <code>{scan.scan_id}</code> (attempt {scan.attempt_no})
            </dd>
            <dt>Status</dt>
            <dd>{scan.status}</dd>
            <dt>Scanner</dt>
            <dd>{scan.scanner_version ?? "—"}</dd>
          </dl>
        </div>
      ) : (
        <p className="cp-note" style={{ marginTop: 14, marginBottom: 0 }}>
          No Pre-Check scan yet.
        </p>
      )}

      {detail.current_validation_run ? (
        <div style={{ marginTop: 14 }}>
          <h4 style={{ margin: "0 0 8px" }}>Validation evidence</h4>
          <dl className="kv">
            <dt>Run</dt>
            <dd>
              <code>{detail.current_validation_run.validation_run_id}</code> (attempt{" "}
              {detail.current_validation_run.attempt_no})
            </dd>
            <dt>Status</dt>
            <dd>
              <StatusBadge
                tone={validationRunTone(detail.current_validation_run.status)}
                label={detail.current_validation_run.status}
              />
              {detail.validation_fresh ? "" : " — stale (candidate regenerated)"}
            </dd>
            <dt>Validator</dt>
            <dd>{detail.current_validation_run.validator_version ?? "—"}</dd>
            <dt>Checks</dt>
            <dd>
              <code>{JSON.stringify(detail.current_validation_run.checks)}</code>
            </dd>
          </dl>
        </div>
      ) : null}

      <RequestActions detail={detail} />

      <BaselineSection detail={detail} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Baseline evidence (doc 06 §4.4/§8.3): a mode-aware equivalence gate. A package
// that claims translation/repair/equivalence may publish only with a PASSED
// baseline parse; a non-claiming package never requires one. The UI never
// pre-judges the gate — it uploads the composed CSV + metadata and runs the
// parse; the server enforces file-type / metadata-complete / parseable and
// returns the canonical envelope verbatim. Raw bytes never travel: the content
// is UTF-8 CSV text, the evidence is a content-addressed digest + parse report.
// ---------------------------------------------------------------------------

function BaselineSection({ detail }: { detail: PackageRequestDetail }) {
  const upload = useUploadBaseline();
  const parse = useStartBaselineParse();
  const [filename, setFilename] = useState("");
  const [content, setContent] = useState("");
  const [metadataText, setMetadataText] = useState("");
  const [metadataError, setMetadataError] = useState<string | null>(null);

  const baseline = detail.current_baseline;
  const anyPending = upload.isPending || parse.isPending;

  function onUpload() {
    setMetadataError(null);
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
    upload.mutate({
      request_id: detail.request_id,
      request_version: detail.request_version,
      content,
      baseline_metadata: metadata,
      content_type: "text/csv",
      original_filename: filename.trim().length > 0 ? filename.trim() : null,
    });
  }

  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 8px" }}>Baseline (equivalence evidence)</h4>
      <p className="cp-note" style={{ marginTop: 0 }}>
        {detail.baseline_required
          ? "This request claims equivalence — a PASSED baseline parse is required to publish."
          : "This request does not claim equivalence — a baseline is optional."}
      </p>

      {baseline ? (
        <dl className="kv">
          <dt>Asset</dt>
          <dd>
            <code>{baseline.baseline_asset_id}</code> (attempt {baseline.attempt_no})
          </dd>
          <dt>Parse status</dt>
          <dd>
            <StatusBadge tone={baselineParseTone(baseline.parse_status)} label={baseline.parse_status} />
          </dd>
          <dt>File</dt>
          <dd>
            {baseline.original_filename ?? "—"}
            {baseline.size_bytes !== null ? ` · ${baseline.size_bytes} bytes` : ""}
          </dd>
          <dt>Digest</dt>
          <dd>
            <code>{baseline.content_digest ?? "—"}</code>
          </dd>
          <dt>Metadata</dt>
          <dd>
            <code>{JSON.stringify(baseline.baseline_metadata)}</code>
          </dd>
        </dl>
      ) : (
        <p className="cp-note" style={{ marginTop: 0 }}>
          No baseline uploaded yet.
        </p>
      )}

      <div className="cp-field" style={{ marginTop: 10 }}>
        <span>Baseline filename (.csv)</span>
        <input
          aria-label="Baseline filename"
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          placeholder="baseline.csv"
        />
      </div>
      <div className="cp-field" style={{ marginTop: 10 }}>
        <span>Baseline CSV content</span>
        <textarea
          aria-label="Baseline CSV content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={4}
          placeholder="time,open,high,low,close,volume…"
        />
      </div>
      <div className="cp-field" style={{ marginTop: 10 }}>
        <span>Baseline metadata (JSON)</span>
        <textarea
          aria-label="Baseline metadata"
          value={metadataText}
          onChange={(e) => setMetadataText(e.target.value)}
          rows={4}
          placeholder='{"provider":"…","symbol":"…","timeframe":"…","range":"…","timezone":"…","settings":{},"source_revision_context":{}}'
        />
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 10 }}>
        <button
          type="button"
          className="btn"
          disabled={anyPending || content.trim().length === 0 || filename.trim().length === 0}
          onClick={onUpload}
        >
          {upload.isPending ? "Uploading…" : "Upload baseline"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={baseline === null || anyPending}
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

      {metadataError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {metadataError}
        </p>
      ) : null}
      {upload.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(upload.error)}
        </p>
      ) : null}
      {upload.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Baseline uploaded — asset <code>{upload.data.baseline_asset_id}</code> (attempt{" "}
          {upload.data.attempt_no}, {upload.data.size_bytes} bytes).
        </p>
      ) : null}
      {parse.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(parse.error)}
        </p>
      ) : null}
      {parse.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Baseline parse {parse.data.parse_status} — parser {parse.data.parser_version}.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Request actions — the lifecycle commands (doc 06 §7, doc 07 §8). Button
// gating mirrors server hints only (can_generate_candidate, candidate_ready,
// draft present); the server re-validates every transition and a denial
// surfaces the canonical envelope verbatim. Approve is Admin-only SERVER-side
// (CR-02) — the button is never role-gated in the UI.
// ---------------------------------------------------------------------------

function RequestActions({ detail }: { detail: PackageRequestDetail }) {
  const precheck = useRunPrecheck();
  const generate = useGenerateCandidate();
  const draft = useCreateDraft();
  const validate = useRunValidation();
  const revision = useRequestRevision();
  const approve = useApproveRequest();
  const [note, setNote] = useState("");

  const anyPending =
    precheck.isPending ||
    generate.isPending ||
    draft.isPending ||
    validate.isPending ||
    revision.isPending ||
    approve.isPending;
  const hasDraft = detail.draft_revision_id !== null;
  // The accepted candidate hash from THIS card is the draft's staleness token;
  // after a reload it is absent and the server-side state check alone gates.
  const candidateHash = generate.data?.candidate_hash ?? null;
  const canDraft = detail.state === "candidate_ready" || hasDraft;

  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 8px" }}>Actions</h4>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn"
          disabled={anyPending}
          onClick={() =>
            precheck.mutate({
              request_id: detail.request_id,
              request_version: detail.request_version,
            })
          }
        >
          {precheck.isPending ? "Checking dependencies…" : "Run Pre-Check"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={!detail.can_generate_candidate || anyPending}
          onClick={() =>
            generate.mutate({
              request_id: detail.request_id,
              request_version: detail.request_version,
            })
          }
        >
          {generate.isPending ? "Generating…" : "Generate candidate"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={!canDraft || anyPending}
          onClick={() =>
            draft.mutate({
              request_id: detail.request_id,
              expected_candidate_hash: candidateHash,
            })
          }
        >
          {draft.isPending ? "Drafting…" : "Create draft"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={!hasDraft || anyPending}
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
          disabled={anyPending}
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
          className="btn btn-primary"
          disabled={!hasDraft || anyPending}
          onClick={() =>
            approve.mutate({
              request_id: detail.request_id,
              expected_head_revision_id: detail.draft_revision_id,
              note: note.trim().length > 0 ? note.trim() : null,
            })
          }
        >
          {approve.isPending ? "Approving…" : "Approve & publish"}
        </button>
      </div>

      <div className="cp-field" style={{ marginTop: 10 }}>
        <span>Approval note (optional)</span>
        <input
          aria-label="Approval note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Recorded on the approval decision…"
        />
      </div>

      {precheck.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(precheck.error)}
        </p>
      ) : null}
      {precheck.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Pre-Check {precheck.data.status} — scan <code>{precheck.data.scan_id}</code> (attempt{" "}
          {precheck.data.attempt_no}).
        </p>
      ) : null}
      {generate.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(generate.error)}
        </p>
      ) : null}
      {generate.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Candidate {generate.data.state} — hash <code>{generate.data.candidate_hash}</code>.
        </p>
      ) : null}
      {draft.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(draft.error)}
        </p>
      ) : null}
      {draft.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Draft created — revision <code>{draft.data.draft_revision_id ?? "—"}</code>.
        </p>
      ) : null}
      {validate.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(validate.error)}
        </p>
      ) : null}
      {validate.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Validation {validate.data.status} — run <code>{validate.data.validation_run_id}</code>{" "}
          (attempt {validate.data.attempt_no}) → {prettyToken(validate.data.state)}.
        </p>
      ) : null}
      {revision.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(revision.error)}
        </p>
      ) : null}
      {revision.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Revision requested — {prettyToken(revision.data.state)}, new candidate{" "}
          <code>{revision.data.candidate_hash}</code>.
        </p>
      ) : null}
      {approve.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(approve.error)}
        </p>
      ) : null}
      {approve.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
          Approved &amp; published — revision <code>{approve.data.revision_id ?? "—"}</code> (
          {approve.data.visibility_scope}).
        </p>
      ) : null}
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
