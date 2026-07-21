import { useState, type FormEvent } from "react";

import { AdminApprovalNote, useIsAdmin } from "@/components/AdminGate";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { formatUtc } from "@/lib/backtest";
import {
  ESP_PERFORMANCE_FIELDS,
  RESOLVER_TRUST_STATES,
  RUNTIME_ADAPTERS,
  VISIBILITY_SCOPES,
  canActivate,
  canDeprecate,
  parseSignatureParams,
  trustTone,
  useActivateResolver,
  useCreateEsp,
  useDeprecateResolver,
  useEspPackage,
  useEspRegistry,
  useResolveProbe,
  type EspPackageDetail,
  type EspRegistryRow,
} from "@/lib/esp";
import { approvalTone, lifecycleTone, validationTone } from "@/lib/library";

// Wide JSON payloads wrap + scroll inside their own box (never widen the page).
const contractStyle = {
  fontFamily: "monospace",
  fontSize: 12,
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
  maxHeight: 240,
  overflow: "auto",
  margin: 0,
  padding: 8,
  border: "1px solid var(--border)",
  borderRadius: 6,
} as const;

// Forward-only opaque keyset cursors (server contract): Prev replays the
// cursor stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? stack[stack.length - 1] : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
    reset: () => setStack([]),
  };
}

// Embedded System Packages (doc 09): the role-aware resolver-registry catalog,
// a Pre-Check-parity resolve probe, and the registry lifecycle. Visibility is
// enforced server-side; propose (create) is open to any authenticated actor,
// while activate / deprecate are Admin-only and OCC-guarded — the UI never
// pre-gates, a denial surfaces the 403 envelope verbatim. The catalog is the
// primary surface (rendered first); proposing a resolver and running a
// resolve probe are secondary actions opened in a dialog.
export function Embedded() {
  const [proposeOpen, setProposeOpen] = useState(false);
  const [probeOpen, setProbeOpen] = useState(false);

  return (
    <>
      <h1 className="page-title">Embedded System Packages</h1>
      <p className="page-sub">
        Trusted resolver registry for source-code TA dependencies · trust and
        visibility are server-computed per role
      </p>
      <RegistryCard onPropose={() => setProposeOpen(true)} onProbe={() => setProbeOpen(true)} />

      <Modal
        open={proposeOpen}
        onClose={() => setProposeOpen(false)}
        titleId="esp-propose-h"
        wide
      >
        <ProposeResolverCard onClose={() => setProposeOpen(false)} />
      </Modal>
      <Modal open={probeOpen} onClose={() => setProbeOpen(false)} titleId="esp-probe-h" wide>
        <ResolveProbeCard onClose={() => setProbeOpen(false)} />
      </Modal>
    </>
  );
}

function RegistryCard({ onPropose, onProbe }: { onPropose: () => void; onProbe: () => void }) {
  const [trustState, setTrustState] = useState<string | null>(null);
  const [scope, setScope] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pager = useCursorStack();
  const registry = useEspRegistry(trustState, pager.cursor, scope);

  return (
    <section className="card" aria-labelledby="esp-h">
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 12,
        }}
      >
        <h3 id="esp-h" style={{ margin: 0 }}>
          Resolver registry
        </h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="btn" onClick={onPropose}>
            Propose resolver
          </button>
          <button type="button" className="btn" onClick={onProbe}>
            Resolve probe
          </button>
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, margin: "12px 0" }}>
        <label htmlFor="esp-trust">
          Trust state{" "}
          <select
            id="esp-trust"
            value={trustState ?? ""}
            onChange={(event) => {
              setTrustState(event.target.value || null);
              pager.reset();
            }}
          >
            <option value="">all</option>
            {RESOLVER_TRUST_STATES.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="esp-scope">
          Scope{" "}
          <select
            id="esp-scope"
            value={scope ?? ""}
            onChange={(event) => {
              setScope(event.target.value || null);
              pager.reset();
            }}
          >
            <option value="">all</option>
            {VISIBILITY_SCOPES.map((visScope) => (
              <option key={visScope} value={visScope}>
                {visScope}
              </option>
            ))}
          </select>
        </label>
      </div>

      {registry.isLoading ? (
        <Loading label="Loading resolver registry…" />
      ) : registry.isError ? (
        <ErrorState error={registry.error} onRetry={() => void registry.refetch()} />
      ) : registry.data ? (
        <>
          {registry.data.data.length === 0 ? (
            <EmptyState title="No resolver matches the current filters" />
          ) : (
            // v18 mockup: expandable .package-row registry rows (open → light-cyan)
            // that embed the resolver detail inline, instead of a wide table.
            <div className="package-list" role="list" aria-label="Resolver registry">
              {registry.data.data.map((row) => (
                <RegistryRowView
                  key={row.registry_id}
                  row={row}
                  open={selectedId === row.package_entity_id}
                  onToggle={() =>
                    setSelectedId((current) =>
                      current === row.package_entity_id ? null : row.package_entity_id,
                    )
                  }
                />
              ))}
            </div>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={registry.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
    </section>
  );
}

function RegistryRowView({
  row,
  open,
  onToggle,
}: {
  row: EspRegistryRow;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div role="listitem" className="package-card">
      <div className={`package-row${open ? " open" : ""}`}>
        <div className="package-text">
          <code>{row.canonical_key}</code>
          <StatusBadge tone={trustTone(row.trust_state)} label={row.trust_state} />
          <span>{row.visibility_scope ?? "—"}</span>
          <span>{row.runtime_adapter}</span>
          {row.trusted_active_revision_id ? (
            <code>{row.trusted_active_revision_id}</code>
          ) : (
            <span>—</span>
          )}
        </div>
        {/* aria-label keeps the accessible name "Detail"; the glyph mirrors the mockup arrow. */}
        <button
          type="button"
          className="package-arrow"
          aria-label="Detail"
          aria-expanded={open}
          onClick={onToggle}
        >
          {open ? "▲" : "▼"}
        </button>
      </div>
      {open ? (
        <div className="package-details">
          <EspDetailCard entityId={row.package_entity_id} onClose={onToggle} />
        </div>
      ) : null}
    </div>
  );
}

function EspDetailCard({ entityId, onClose }: { entityId: string; onClose: () => void }) {
  const detail = useEspPackage(entityId);
  const esp = detail.data;
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h4 style={{ margin: 0 }}>Resolver detail</h4>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
      {detail.isLoading ? (
        <Loading label="Loading resolver…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : esp ? (
        <>
          <dl className="kv">
            <dt>Package</dt>
            <dd>
              <code>{esp.package_kind}</code> ({esp.entity_id})
            </dd>
            <dt>Head revision</dt>
            <dd>
              v{esp.revision_no} · <code>{esp.revision_id}</code>
            </dd>
            <dt>States</dt>
            <dd>
              <StatusBadge tone={lifecycleTone(esp.lifecycle_state)} label={esp.lifecycle_state} />{" "}
              <StatusBadge
                tone={validationTone(esp.validation_state)}
                label={esp.validation_state}
              />{" "}
              <StatusBadge tone={approvalTone(esp.approval_state)} label={esp.approval_state} /> ·{" "}
              {esp.visibility_scope}
            </dd>
            <dt>Origin</dt>
            <dd>
              owner {esp.owner_principal_id ?? "—"}
              {` · created ${formatUtc(esp.created_at)}`}
            </dd>
            <dt>Content hash</dt>
            <dd>
              <code>{esp.content_hash}</code>
            </dd>
            <dt>Row version</dt>
            <dd>{esp.row_version}</dd>
          </dl>

          {esp.registry ? (
            <>
              <h5 style={{ marginBottom: 4 }}>Registry entry</h5>
              <dl className="kv">
                <dt>Trust</dt>
                <dd>
                  <StatusBadge
                    tone={trustTone(esp.registry.trust_state)}
                    label={esp.registry.trust_state}
                  />{" "}
                  · registry v{esp.registry.registry_version}
                </dd>
                <dt>Trusted revision</dt>
                <dd>
                  {esp.registry.trusted_active_revision_id ? (
                    <code>{esp.registry.trusted_active_revision_id}</code>
                  ) : (
                    "—"
                  )}
                </dd>
                {esp.registry.replacement_revision_id ? (
                  <>
                    <dt>Replacement</dt>
                    <dd>
                      <code>{esp.registry.replacement_revision_id}</code>
                    </dd>
                  </>
                ) : null}
              </dl>
            </>
          ) : null}

          {esp.contract ? (
            <>
              <h5 style={{ marginBottom: 4 }}>Resolver contract</h5>
              <dl className="kv">
                <dt>Canonical key</dt>
                <dd>
                  <code>{esp.contract.canonical_key}</code> · {esp.contract.runtime_adapter}
                </dd>
                <dt>Warm-up / timing</dt>
                <dd>
                  {esp.contract.warm_up_period ?? "—"} ·{" "}
                  {esp.contract.timing_semantics ?? "—"} ·{" "}
                  {esp.contract.repaint ? "repaints" : "no repaint"}
                </dd>
              </dl>
              <h5 style={{ marginBottom: 4 }}>Signature</h5>
              <pre style={contractStyle}>{JSON.stringify(esp.contract.signature, null, 2)}</pre>
              {esp.contract.evidence ? (
                <>
                  <h5 style={{ marginBottom: 4 }}>Evidence</h5>
                  <pre style={contractStyle}>
                    {JSON.stringify(esp.contract.evidence, null, 2)}
                  </pre>
                </>
              ) : null}
            </>
          ) : null}

          <h5 style={{ marginBottom: 4 }}>Performance</h5>
          <dl className="kv">
            {ESP_PERFORMANCE_FIELDS.map((field) => (
              <PerformanceField key={field} field={field} value={esp[field]} />
            ))}
          </dl>

          <LifecycleActions esp={esp} />
        </>
      ) : null}
    </div>
  );
}

// L4 / doc 09 §14: resolver performance fields render their availability label
// verbatim — never a fabricated number.
function PerformanceField({ field, value }: { field: string; value: string | undefined }) {
  return (
    <>
      <dt>{field}</dt>
      <dd>{value === "not_applicable" ? "N/A (not applicable)" : (value ?? "—")}</dd>
    </>
  );
}

// Registry lifecycle for the open resolver. The OCC token is the registry's own
// registry_version; the legal action is a UI hint (state machine). R2-09 (GAP
// item 10): the composers render only for a server-confirmed Admin (/me
// projection, fail-closed) — everyone else keeps the read-only trust state plus
// the "Admin approval required" note. Presentation only — the server re-validates
// the transition AND the Admin gate, so a stale token (409), illegal jump, or
// stale-cache non-Admin (403) all surface verbatim. Without a registry pointer
// there is nothing to transition.
function LifecycleActions({ esp }: { esp: EspPackageDetail }) {
  const isAdmin = useIsAdmin();
  const registry = esp.registry;
  if (!registry) return null;
  return (
    <>
      <h5 style={{ marginBottom: 4 }}>Registry lifecycle</h5>
      {!isAdmin ? (
        <AdminApprovalNote
          detail={`The registry stays read-only for your role (currently ${registry.trust_state}); an Admin performs activate/deprecate.`}
        />
      ) : canActivate(registry.trust_state) ? (
        <ActivateComposer esp={esp} registry={registry} />
      ) : canDeprecate(registry.trust_state) ? (
        <DeprecateComposer esp={esp} registry={registry} />
      ) : (
        <p className="page-sub" style={{ marginTop: 0 }}>
          No lifecycle action is available from the <code>{registry.trust_state}</code> state.
        </p>
      )}
    </>
  );
}

// Activate a CANDIDATE → TRUSTED_ACTIVE (Admin-only). The revision to trust
// defaults to the head; canonical_key + registry_version come from the pinned
// registry row (never re-derived on the client).
function ActivateComposer({
  esp,
  registry,
}: {
  esp: EspPackageDetail;
  registry: EspRegistryRow;
}) {
  const [revisionId, setRevisionId] = useState(esp.revision_id);
  const [note, setNote] = useState("");
  const activate = useActivateResolver();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    activate.mutate({
      entityId: esp.entity_id,
      registryVersion: registry.registry_version,
      revision_id: revisionId.trim(),
      canonical_key: registry.canonical_key,
      note: note.trim() || undefined,
    });
  };

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 480 }}>
      <p className="page-sub" style={{ margin: 0 }}>
        Activate <code>{registry.canonical_key}</code> (candidate → trusted_active).
        Admin-only — a non-Admin is rejected verbatim.
      </p>
      <label htmlFor="esp-act-rev">
        Revision to trust{" "}
        <input
          id="esp-act-rev"
          value={revisionId}
          onChange={(event) => setRevisionId(event.target.value)}
        />
      </label>
      <label htmlFor="esp-act-note">
        Note (optional){" "}
        <input id="esp-act-note" value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      <div>
        <button
          type="submit"
          className="btn"
          disabled={activate.isPending || revisionId.trim() === ""}
        >
          {activate.isPending ? "Activating…" : "Activate resolver"}
        </button>
      </div>
      {activate.isError ? (
        <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
          {(activate.error as Error).message}
        </p>
      ) : null}
      {activate.isSuccess ? (
        <p role="status" style={{ color: "var(--ok)", margin: 0 }}>
          Activated — now {activate.data.trust_state} (registry v
          {activate.data.registry_version}).
        </p>
      ) : null}
    </form>
  );
}

// Deprecate a TRUSTED_ACTIVE → DEPRECATED (Admin-only). A reason is required
// (doc 09 §6). An optional replacement revision points new work elsewhere;
// historical pins keep reading their exact revision.
function DeprecateComposer({
  esp,
  registry,
}: {
  esp: EspPackageDetail;
  registry: EspRegistryRow;
}) {
  const [reason, setReason] = useState("");
  const [replacement, setReplacement] = useState("");
  const deprecate = useDeprecateResolver();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    deprecate.mutate({
      entityId: esp.entity_id,
      registryVersion: registry.registry_version,
      canonical_key: registry.canonical_key,
      reason: reason.trim(),
      replacement_revision_id: replacement.trim() || undefined,
    });
  };

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 480 }}>
      <p className="page-sub" style={{ margin: 0 }}>
        Deprecate <code>{registry.canonical_key}</code> (trusted_active → deprecated).
        Admin-only — a non-Admin is rejected verbatim.
      </p>
      <label htmlFor="esp-dep-reason">
        Deprecation reason{" "}
        <input
          id="esp-dep-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Superseded by v2 resolver"
        />
      </label>
      <label htmlFor="esp-dep-repl">
        Replacement revision (optional){" "}
        <input
          id="esp-dep-repl"
          value={replacement}
          onChange={(event) => setReplacement(event.target.value)}
        />
      </label>
      <div>
        <button
          type="submit"
          className="btn"
          disabled={deprecate.isPending || reason.trim() === ""}
        >
          {deprecate.isPending ? "Deprecating…" : "Deprecate resolver"}
        </button>
      </div>
      {deprecate.isError ? (
        <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
          {(deprecate.error as Error).message}
        </p>
      ) : null}
      {deprecate.isSuccess ? (
        <p role="status" style={{ color: "var(--ok)", margin: 0 }}>
          Deprecated — now {deprecate.data.trust_state} (registry v
          {deprecate.data.registry_version}).
        </p>
      ) : null}
    </form>
  );
}

// Propose a new resolver (doc 09 §5): any authenticated actor may submit a
// CANDIDATE — not trusted until an Admin activates it. Ordered signature param
// TYPES are identity (parseSignatureParams is reused from the resolve probe);
// input/output contracts default to {} server-side. No OCC / Idempotency-Key.
function ProposeResolverCard({ onClose }: { onClose: () => void }) {
  const [key, setKey] = useState("");
  const [runtime, setRuntime] = useState<string>(RUNTIME_ADAPTERS[1]);
  const [paramsText, setParamsText] = useState("");
  const [returnShape, setReturnShape] = useState("");
  const [visibility, setVisibility] = useState<string>(VISIBILITY_SCOPES[0]);
  const [warmUp, setWarmUp] = useState("");
  const [timing, setTiming] = useState("");
  const [repaint, setRepaint] = useState(false);
  const [note, setNote] = useState("");
  const create = useCreateEsp();

  const params = parseSignatureParams(paramsText);
  // The server needs a signature with params OR a return shape; mirror that guard
  // client-side (it re-validates and returns RESOLVER_CONTRACT_INVALID otherwise).
  const canSubmit = key.trim() !== "" && (params.length > 0 || returnShape.trim() !== "");

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const warmUpValue = warmUp.trim();
    create.mutate({
      canonical_key: key.trim(),
      signature: { params, return: returnShape.trim() },
      runtime_adapter: runtime,
      visibility_scope: visibility,
      warm_up_period:
        warmUpValue !== "" && Number.isFinite(Number(warmUpValue)) ? Number(warmUpValue) : null,
      timing_semantics: timing.trim() || null,
      repaint,
      change_note: note.trim() || null,
    });
  };

  const result = create.data;
  return (
    <section aria-labelledby="esp-propose-h">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 id="esp-propose-h" style={{ margin: 0 }}>
          Propose resolver
        </h3>
        <button type="button" className="page-button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="page-sub">
        Submit a new resolver as a candidate. It stays untrusted until an Admin
        activates it — Pre-Check cannot select a candidate.
      </p>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, maxWidth: 560 }}>
        <label htmlFor="propose-key">
          Canonical key{" "}
          <input
            id="propose-key"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder="ta.rsi"
          />
        </label>
        <label htmlFor="propose-runtime">
          Runtime adapter{" "}
          <select
            id="propose-runtime"
            value={runtime}
            onChange={(event) => setRuntime(event.target.value)}
          >
            {RUNTIME_ADAPTERS.map((adapter) => (
              <option key={adapter} value={adapter}>
                {adapter}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="propose-params">
          Signature params (one per line, "name:type" or "type"){" "}
          <textarea
            id="propose-params"
            rows={3}
            value={paramsText}
            onChange={(event) => setParamsText(event.target.value)}
            placeholder={"source:series\nlength:int"}
          />
        </label>
        <label htmlFor="propose-return">
          Return shape{" "}
          <input
            id="propose-return"
            value={returnShape}
            onChange={(event) => setReturnShape(event.target.value)}
            placeholder="series"
          />
        </label>
        <label htmlFor="propose-visibility">
          Visibility{" "}
          <select
            id="propose-visibility"
            value={visibility}
            onChange={(event) => setVisibility(event.target.value)}
          >
            {VISIBILITY_SCOPES.map((scope) => (
              <option key={scope} value={scope}>
                {scope}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="propose-warmup">
          Warm-up period (optional){" "}
          <input
            id="propose-warmup"
            type="number"
            value={warmUp}
            onChange={(event) => setWarmUp(event.target.value)}
          />
        </label>
        <label htmlFor="propose-timing">
          Timing semantics (optional){" "}
          <input
            id="propose-timing"
            value={timing}
            onChange={(event) => setTiming(event.target.value)}
            placeholder="bar_close"
          />
        </label>
        <label htmlFor="propose-repaint" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            id="propose-repaint"
            type="checkbox"
            checked={repaint}
            onChange={(event) => setRepaint(event.target.checked)}
          />
          Repaints
        </label>
        <label htmlFor="propose-note">
          Change note (optional){" "}
          <input id="propose-note" value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <div>
          <button type="submit" className="btn" disabled={create.isPending || !canSubmit}>
            {create.isPending ? "Proposing…" : "Propose resolver"}
          </button>
        </div>
      </form>

      {create.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {(create.error as Error).message}
        </p>
      ) : null}
      {result ? (
        <p role="status" style={{ color: "var(--ok)", marginBottom: 0 }}>
          Proposed <code>{result.canonical_key}</code> as {result.trust_state} —{" "}
          {result.entity_id}
        </p>
      ) : null}
    </section>
  );
}

// Pre-Check-parity resolve probe (doc 09 §9.1–§9.3): try a parsed call against
// the live registry. Success pins the EXACT revision; each failure mode is the
// server's typed error rendered verbatim.
function ResolveProbeCard({ onClose }: { onClose: () => void }) {
  const [key, setKey] = useState("");
  const [paramsText, setParamsText] = useState("");
  const [returnShape, setReturnShape] = useState("");
  const [runtime, setRuntime] = useState<string>(RUNTIME_ADAPTERS[1]);
  const probe = useResolveProbe();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    probe.mutate({
      key: key.trim(),
      params: parseSignatureParams(paramsText),
      returnShape: returnShape.trim(),
      target_runtime: runtime,
    });
  };

  const result = probe.data;
  return (
    <section aria-labelledby="esp-probe-h">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 id="esp-probe-h" style={{ margin: 0 }}>
          Resolve probe
        </h3>
        <button type="button" className="page-button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="page-sub">
        Pre-Check parity: resolve a parsed call to the exact trusted revision.
        Ordered parameter types are identity — names are display-only.
      </p>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, maxWidth: 560 }}>
        <label htmlFor="probe-key">
          Canonical key{" "}
          <input
            id="probe-key"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder="ta.rsi"
          />
        </label>
        <label htmlFor="probe-params">
          Signature params (one per line, "name:type" or "type"){" "}
          <textarea
            id="probe-params"
            rows={3}
            value={paramsText}
            onChange={(event) => setParamsText(event.target.value)}
            placeholder={"source:series\nlength:int"}
          />
        </label>
        <label htmlFor="probe-return">
          Return shape{" "}
          <input
            id="probe-return"
            value={returnShape}
            onChange={(event) => setReturnShape(event.target.value)}
            placeholder="series"
          />
        </label>
        <label htmlFor="probe-runtime">
          Target runtime{" "}
          <select
            id="probe-runtime"
            value={runtime}
            onChange={(event) => setRuntime(event.target.value)}
          >
            {RUNTIME_ADAPTERS.map((adapter) => (
              <option key={adapter} value={adapter}>
                {adapter}
              </option>
            ))}
          </select>
        </label>
        <div>
          <button type="submit" className="btn" disabled={probe.isPending || key.trim() === ""}>
            {probe.isPending ? "Resolving…" : "Resolve"}
          </button>
        </div>
      </form>

      {probe.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {(probe.error as Error).message}
        </p>
      ) : null}
      {result ? (
        <dl className="kv" style={{ marginTop: 12 }}>
          <dt>Resolved</dt>
          <dd>
            <code>{result.canonical_key}</code> → pinned revision{" "}
            <code>{result.revision_id}</code>
          </dd>
          <dt>Package</dt>
          <dd>{result.entity_id}</dd>
          <dt>Content hash</dt>
          <dd>
            <code>{result.content_hash}</code>
          </dd>
          <dt>Adapter / registry</dt>
          <dd>
            {result.runtime_adapter} · registry v{result.registry_version}
          </dd>
        </dl>
      ) : null}
    </section>
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
