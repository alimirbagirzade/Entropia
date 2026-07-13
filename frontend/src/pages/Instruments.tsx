import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import {
  CONTRACT_TYPES,
  INSTRUMENT_STATES,
  canDeprecate,
  parseAliases,
  stateTone,
  useAddInstrumentAlias,
  useDeprecateInstrument,
  useInstrument,
  useInstruments,
  useRegisterInstrument,
  useResolveScope,
  type InstrumentDetail,
  type InstrumentRow,
} from "@/lib/instrument";

// Forward-only opaque keyset cursors (server contract): Prev replays the cursor
// stack, the client never re-orders or fabricates a page.
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

// Canonical Instrument Registry (GAP-16; Master §8.1): the shared catalog of
// tradable instruments, a free-text scope resolver, and the register/deprecate
// lifecycle. Registration is open to any authenticated actor; deprecation is
// Admin-only and OCC-guarded — the UI never pre-gates, a denial surfaces the
// 403 envelope verbatim.
export function Instruments() {
  return (
    <>
      <h1 className="page-title">Instrument Registry</h1>
      <p className="page-sub">
        Canonical tradable instruments · a free-text scope ("BTCUSDT Perpetual")
        resolves server-side to exactly one instrument — spot and perpetual are
        never equated by symbol match
      </p>
      <RegistryCard />
      <RegisterInstrumentCard />
      <ResolveScopeCard />
    </>
  );
}

function RegistryCard() {
  const [state, setState] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pager = useCursorStack();
  const registry = useInstruments(state, pager.cursor);

  return (
    <section className="card" aria-labelledby="instr-h">
      <h3 id="instr-h" style={{ marginTop: 0 }}>
        Registry
      </h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
        <label htmlFor="instr-state">
          State{" "}
          <select
            id="instr-state"
            value={state ?? ""}
            onChange={(event) => {
              setState(event.target.value || null);
              pager.reset();
            }}
          >
            <option value="">all</option>
            {INSTRUMENT_STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {registry.isLoading ? (
        <Loading label="Loading instrument registry…" />
      ) : registry.isError ? (
        <ErrorState error={registry.error} onRetry={() => void registry.refetch()} />
      ) : registry.data ? (
        <>
          {registry.data.data.length === 0 ? (
            <EmptyState title="No instrument matches the current filters" />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Instrument</th>
                  <th scope="col">Resolution key</th>
                  <th scope="col">Contract</th>
                  <th scope="col">State</th>
                  <th scope="col">Registry ver</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {registry.data.data.map((row) => (
                  <RegistryRowView
                    key={row.instrument_id}
                    row={row}
                    onDetail={() => setSelectedId(row.instrument_id)}
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
        <InstrumentDetailCard instrumentId={selectedId} onClose={() => setSelectedId(null)} />
      ) : null}
    </section>
  );
}

function RegistryRowView({ row, onDetail }: { row: InstrumentRow; onDetail: () => void }) {
  return (
    <tr>
      <td>{row.display_name}</td>
      <td>
        <code>{row.resolution_key}</code>
      </td>
      <td>{row.contract_type}</td>
      <td>
        <StatusBadge tone={stateTone(row.state)} label={row.state} />
      </td>
      <td>{row.registry_version}</td>
      <td>
        <button type="button" className="btn" onClick={onDetail}>
          Detail
        </button>
      </td>
    </tr>
  );
}

function InstrumentDetailCard({
  instrumentId,
  onClose,
}: {
  instrumentId: string;
  onClose: () => void;
}) {
  const detail = useInstrument(instrumentId);
  const instrument = detail.data;
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h4 style={{ margin: 0 }}>Instrument detail</h4>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
      {detail.isLoading ? (
        <Loading label="Loading instrument…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : instrument ? (
        <>
          <dl className="kv">
            <dt>Display name</dt>
            <dd>{instrument.display_name}</dd>
            <dt>Resolution key</dt>
            <dd>
              <code>{instrument.resolution_key}</code>
            </dd>
            <dt>Venue / symbol</dt>
            <dd>
              {instrument.venue_id} · {instrument.symbol} · {instrument.contract_type}
            </dd>
            <dt>Assets</dt>
            <dd>
              base {instrument.base_asset ?? "—"} · quote {instrument.quote_asset ?? "—"} ·
              settlement {instrument.settlement_asset ?? "—"}
            </dd>
            <dt>Multiplier / class</dt>
            <dd>
              {instrument.multiplier ?? "—"} · {instrument.market_class ?? "—"}
            </dd>
            <dt>State</dt>
            <dd>
              <StatusBadge tone={stateTone(instrument.state)} label={instrument.state} /> · registry
              v{instrument.registry_version}
            </dd>
            {instrument.deprecation_reason ? (
              <>
                <dt>Deprecation reason</dt>
                <dd>{instrument.deprecation_reason}</dd>
              </>
            ) : null}
          </dl>

          <h5 style={{ marginBottom: 4 }}>Resolution aliases</h5>
          {instrument.aliases.length === 0 ? (
            <p className="page-sub" style={{ marginTop: 0 }}>
              No aliases yet. Add one so a free-text scope resolves to this instrument.
            </p>
          ) : (
            <ul>
              {instrument.aliases.map((alias) => (
                <li key={alias.alias_id}>
                  <code>{alias.alias_text}</code>{" "}
                  <span className="page-sub">(resolves as "{alias.alias_norm}")</span>
                </li>
              ))}
            </ul>
          )}

          <AddAliasComposer instrument={instrument} />
          <DeprecateComposer instrument={instrument} />
        </>
      ) : null}
    </div>
  );
}

// Attach a display alias so a free-text scope resolves to this instrument. Open
// to any authenticated actor. An alias already resolving elsewhere -> 409 verbatim.
function AddAliasComposer({ instrument }: { instrument: InstrumentDetail }) {
  const [alias, setAlias] = useState("");
  const add = useAddInstrumentAlias(instrument.instrument_id);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate(alias.trim(), { onSuccess: () => setAlias("") });
  };

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 480, marginTop: 8 }}>
      <label htmlFor="instr-alias-add">
        Add alias{" "}
        <input
          id="instr-alias-add"
          value={alias}
          onChange={(event) => setAlias(event.target.value)}
          placeholder="BTCUSDT Perpetual"
        />
      </label>
      <div>
        <button type="submit" className="btn" disabled={add.isPending || alias.trim() === ""}>
          {add.isPending ? "Adding…" : "Add alias"}
        </button>
      </div>
      {add.isError ? (
        <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
          {(add.error as Error).message}
        </p>
      ) : null}
    </form>
  );
}

// Deprecate an ACTIVE instrument (Admin-only). A reason is required. Historical
// pins keep resolving; only new-work selection closes. OCC on registry_version.
function DeprecateComposer({ instrument }: { instrument: InstrumentDetail }) {
  const [reason, setReason] = useState("");
  const deprecate = useDeprecateInstrument(instrument.instrument_id);

  if (!canDeprecate(instrument.state)) {
    return (
      <p className="page-sub" style={{ marginTop: 8 }}>
        No lifecycle action is available from the <code>{instrument.state}</code> state.
      </p>
    );
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    deprecate.mutate({ registryVersion: instrument.registry_version, reason: reason.trim() });
  };

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 480, marginTop: 8 }}>
      <h5 style={{ margin: 0 }}>Deprecate instrument</h5>
      <p className="page-sub" style={{ margin: 0 }}>
        Admin-only — a non-Admin is rejected verbatim. Historical references keep resolving.
      </p>
      <label htmlFor="instr-dep-reason">
        Deprecation reason{" "}
        <input
          id="instr-dep-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Delisted from the venue"
        />
      </label>
      <div>
        <button
          type="submit"
          className="btn"
          disabled={deprecate.isPending || reason.trim() === ""}
        >
          {deprecate.isPending ? "Deprecating…" : "Deprecate instrument"}
        </button>
      </div>
      {deprecate.isError ? (
        <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
          {(deprecate.error as Error).message}
        </p>
      ) : null}
      {deprecate.isSuccess ? (
        <p role="status" style={{ color: "var(--ok)", margin: 0 }}>
          Deprecated — now {deprecate.data.state} (registry v{deprecate.data.registry_version}).
        </p>
      ) : null}
    </form>
  );
}

// Register a canonical instrument (Master §8.1). The identity triple
// (venue/symbol/contract_type) is required + must be unique; aliases resolve the
// free-text scope. Any authenticated actor may register.
function RegisterInstrumentCard() {
  const [venue, setVenue] = useState("");
  const [symbol, setSymbol] = useState("");
  const [contractType, setContractType] = useState<string>(CONTRACT_TYPES[1]);
  const [displayName, setDisplayName] = useState("");
  const [baseAsset, setBaseAsset] = useState("");
  const [quoteAsset, setQuoteAsset] = useState("");
  const [settlementAsset, setSettlementAsset] = useState("");
  const [multiplier, setMultiplier] = useState("");
  const [marketClass, setMarketClass] = useState("");
  const [aliasesText, setAliasesText] = useState("");
  const register = useRegisterInstrument();

  const canSubmit =
    venue.trim() !== "" && symbol.trim() !== "" && displayName.trim() !== "";

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    register.mutate({
      venue_id: venue.trim(),
      symbol: symbol.trim(),
      contract_type: contractType,
      display_name: displayName.trim(),
      base_asset: baseAsset.trim() || null,
      quote_asset: quoteAsset.trim() || null,
      settlement_asset: settlementAsset.trim() || null,
      multiplier: multiplier.trim() || null,
      market_class: marketClass.trim() || null,
      aliases: parseAliases(aliasesText),
    });
  };

  const result = register.data;
  return (
    <section className="card" aria-labelledby="instr-reg-h">
      <h3 id="instr-reg-h" style={{ marginTop: 0 }}>
        Register instrument
      </h3>
      <p className="page-sub">
        The venue, symbol and contract type together form the canonical identity —
        a duplicate is rejected verbatim.
      </p>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, maxWidth: 560 }}>
        <label htmlFor="reg-venue">
          Venue{" "}
          <input
            id="reg-venue"
            value={venue}
            onChange={(event) => setVenue(event.target.value)}
            placeholder="binance"
          />
        </label>
        <label htmlFor="reg-symbol">
          Symbol{" "}
          <input
            id="reg-symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
            placeholder="BTCUSDT"
          />
        </label>
        <label htmlFor="reg-contract">
          Contract type{" "}
          <select
            id="reg-contract"
            value={contractType}
            onChange={(event) => setContractType(event.target.value)}
          >
            {CONTRACT_TYPES.map((ct) => (
              <option key={ct} value={ct}>
                {ct}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="reg-display">
          Display name{" "}
          <input
            id="reg-display"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="BTCUSDT Perpetual"
          />
        </label>
        <label htmlFor="reg-base">
          Base asset (optional){" "}
          <input id="reg-base" value={baseAsset} onChange={(event) => setBaseAsset(event.target.value)} />
        </label>
        <label htmlFor="reg-quote">
          Quote asset (optional){" "}
          <input
            id="reg-quote"
            value={quoteAsset}
            onChange={(event) => setQuoteAsset(event.target.value)}
          />
        </label>
        <label htmlFor="reg-settle">
          Settlement asset (optional){" "}
          <input
            id="reg-settle"
            value={settlementAsset}
            onChange={(event) => setSettlementAsset(event.target.value)}
          />
        </label>
        <label htmlFor="reg-mult">
          Multiplier (optional){" "}
          <input
            id="reg-mult"
            value={multiplier}
            onChange={(event) => setMultiplier(event.target.value)}
            placeholder="1"
          />
        </label>
        <label htmlFor="reg-class">
          Market class (optional){" "}
          <input
            id="reg-class"
            value={marketClass}
            onChange={(event) => setMarketClass(event.target.value)}
            placeholder="crypto"
          />
        </label>
        <label htmlFor="reg-aliases">
          Aliases (one per line){" "}
          <textarea
            id="reg-aliases"
            rows={3}
            value={aliasesText}
            onChange={(event) => setAliasesText(event.target.value)}
            placeholder={"BTCUSDT Perpetual\nBTCUSDT.P"}
          />
        </label>
        <div>
          <button type="submit" className="btn" disabled={register.isPending || !canSubmit}>
            {register.isPending ? "Registering…" : "Register instrument"}
          </button>
        </div>
      </form>

      {register.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {(register.error as Error).message}
        </p>
      ) : null}
      {result ? (
        <p role="status" style={{ color: "var(--ok)", marginBottom: 0 }}>
          Registered <code>{result.resolution_key}</code> ({result.alias_count} aliases) —{" "}
          {result.instrument_id}
        </p>
      ) : null}
    </section>
  );
}

// Resolve a free-text scope (an alias, or a venue/symbol/contract triple) to a
// canonical instrument (Master §8.1). Unresolvable -> the typed error verbatim.
function ResolveScopeCard() {
  const [alias, setAlias] = useState("");
  const [venue, setVenue] = useState("");
  const [symbol, setSymbol] = useState("");
  const [contractType, setContractType] = useState<string>(CONTRACT_TYPES[1]);
  const resolve = useResolveScope();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const aliasValue = alias.trim();
    resolve.mutate(
      aliasValue
        ? { alias: aliasValue }
        : { venue_id: venue.trim(), symbol: symbol.trim(), contract_type: contractType },
    );
  };

  const canSubmit =
    alias.trim() !== "" || (venue.trim() !== "" && symbol.trim() !== "");
  const result = resolve.data;
  return (
    <section className="card" aria-labelledby="instr-resolve-h">
      <h3 id="instr-resolve-h" style={{ marginTop: 0 }}>
        Resolve scope
      </h3>
      <p className="page-sub">
        Turn a free-text scope into a canonical instrument. Provide an alias, or a
        venue/symbol/contract triple.
      </p>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, maxWidth: 560 }}>
        <label htmlFor="resolve-alias">
          Alias{" "}
          <input
            id="resolve-alias"
            value={alias}
            onChange={(event) => setAlias(event.target.value)}
            placeholder="BTCUSDT Perpetual"
          />
        </label>
        <p className="page-sub" style={{ margin: 0 }}>
          …or resolve by the identity triple:
        </p>
        <label htmlFor="resolve-venue">
          Venue{" "}
          <input
            id="resolve-venue"
            value={venue}
            onChange={(event) => setVenue(event.target.value)}
            placeholder="binance"
          />
        </label>
        <label htmlFor="resolve-symbol">
          Symbol{" "}
          <input
            id="resolve-symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
            placeholder="BTCUSDT"
          />
        </label>
        <label htmlFor="resolve-contract">
          Contract type{" "}
          <select
            id="resolve-contract"
            value={contractType}
            onChange={(event) => setContractType(event.target.value)}
          >
            {CONTRACT_TYPES.map((ct) => (
              <option key={ct} value={ct}>
                {ct}
              </option>
            ))}
          </select>
        </label>
        <div>
          <button type="submit" className="btn" disabled={resolve.isPending || !canSubmit}>
            {resolve.isPending ? "Resolving…" : "Resolve"}
          </button>
        </div>
      </form>

      {resolve.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {(resolve.error as Error).message}
        </p>
      ) : null}
      {result ? (
        <dl className="kv" style={{ marginTop: 12 }}>
          <dt>Resolved</dt>
          <dd>
            {result.display_name} → <code>{result.instrument_id}</code>
          </dd>
          <dt>Resolution key</dt>
          <dd>
            <code>{result.resolution_key}</code>
          </dd>
          <dt>State</dt>
          <dd>
            <StatusBadge tone={stateTone(result.state)} label={result.state} />
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
