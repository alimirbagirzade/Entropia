import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { formatUtc } from "@/lib/backtest";
import {
  ESP_PERFORMANCE_FIELDS,
  RESOLVER_TRUST_STATES,
  RUNTIME_ADAPTERS,
  parseSignatureParams,
  trustTone,
  useEspPackage,
  useEspRegistry,
  useResolveProbe,
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

// Embedded System Packages (doc 09): the role-aware resolver-registry catalog
// plus a Pre-Check-parity resolve probe. Visibility is enforced server-side;
// registry mutations (activate / deprecate — Admin-only, OCC-guarded) belong
// to later slices, so this page is read-only over the live registry.
export function Embedded() {
  return (
    <>
      <h1 className="page-title">Embedded System Packages</h1>
      <p className="page-sub">
        Trusted resolver registry for source-code TA dependencies · trust and
        visibility are server-computed per role
      </p>
      <RegistryCard />
      <ResolveProbeCard />
    </>
  );
}

function RegistryCard() {
  const [trustState, setTrustState] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pager = useCursorStack();
  const registry = useEspRegistry(trustState, pager.cursor);

  return (
    <section className="card" aria-labelledby="esp-h">
      <h3 id="esp-h" style={{ marginTop: 0 }}>
        Resolver registry
      </h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
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
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Resolver key</th>
                  <th scope="col">Trust</th>
                  <th scope="col">Adapter</th>
                  <th scope="col">Registry ver</th>
                  <th scope="col">Trusted revision</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {registry.data.data.map((row) => (
                  <RegistryRowView
                    key={row.registry_id}
                    row={row}
                    onDetail={() => setSelectedId(row.package_entity_id)}
                  />
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={registry.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}

      {selectedId ? (
        <EspDetailCard entityId={selectedId} onClose={() => setSelectedId(null)} />
      ) : null}
    </section>
  );
}

function RegistryRowView({ row, onDetail }: { row: EspRegistryRow; onDetail: () => void }) {
  return (
    <tr>
      <td>
        <code>{row.canonical_key}</code>
      </td>
      <td>
        <StatusBadge tone={trustTone(row.trust_state)} label={row.trust_state} />
      </td>
      <td>{row.runtime_adapter}</td>
      <td>{row.registry_version}</td>
      <td>{row.trusted_active_revision_id ? <code>{row.trusted_active_revision_id}</code> : "—"}</td>
      <td>
        <button type="button" className="btn" onClick={onDetail}>
          Detail
        </button>
      </td>
    </tr>
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

// Pre-Check-parity resolve probe (doc 09 §9.1–§9.3): try a parsed call against
// the live registry. Success pins the EXACT revision; each failure mode is the
// server's typed error rendered verbatim.
function ResolveProbeCard() {
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
    <section className="card" aria-labelledby="esp-probe-h">
      <h3 id="esp-probe-h" style={{ marginTop: 0 }}>
        Resolve probe
      </h3>
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
