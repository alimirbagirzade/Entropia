import { useRef, useState, type ChangeEvent, type FormEvent } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { InstrumentPicker } from "@/components/InstrumentPicker";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import { useMe } from "@/lib/hooks";
import {
  MARKET_DATA_TYPES,
  TIMEZONE_MODES,
  invalidateAfterRawUpload,
  linesToList,
  parseMappingLines,
  rawUploadPath,
  revisionStateTone,
  useApproveRevision,
  useApprovedBundle,
  useConfirmMapping,
  useCreateDataset,
  useCreateRevision,
  useCreateSuccessor,
  useDeprecateRevision,
  useFinalizeUpload,
  useMarketDataset,
  useMarketDatasets,
  useRequestAnalysis,
  type MarketDatasetDetail,
  type MarketDatasetRow,
  type MarketRevisionRef,
  type RevisionBody,
  type StartUploadResult,
} from "@/lib/marketData";
import { useFileUpload } from "@/lib/upload";

// Command failures surface the backend canonical envelope verbatim — the client
// never invents market-data-domain messages (mirrors Rationale / Trash / Panel).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the cursor
// stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? (stack[stack.length - 1] ?? null) : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
  };
}

// Market Data (doc 11): the primary price/execution layer for research and
// backtests — only OHLCV, tick/trades and spread/execution data live here. This
// page binds the read surface, the owner ingest chain (upload -> analyze -> map)
// AND the revision lifecycle actions: append a DRAFT revision under OCC, append a
// superseding successor, and Admin approve/deprecate. The detail row_version is
// the If-Match OCC token for revisions + approve; buttons are never role-pre-gated
// — a denial (403/409) renders the canonical envelope verbatim.
export function MarketData() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [setupOpen, setSetupOpen] = useState(false);
  const pager = useCursorStack();
  const datasets = useMarketDatasets(pager.cursor);
  // Shared cache with DetailCard's useMarketDataset — react-query dedupes on the
  // ["market-data","detail",id] key, so the ribbon reads the SELECTED dataset's
  // real revision_state with NO extra fetch (presentation-only derivation).
  const detail = useMarketDataset(selectedId);
  const steps = deriveWorkflowSteps(detail.data?.revision_state ?? null);

  // REGISTERED DATASETS reflects the role-aware page projection (soft-deleted /
  // unauthorized rows are already excluded server-side); a trailing "+" signals a
  // further page exists rather than fabricating a total the API does not return.
  const registeredLabel = datasets.data
    ? `${datasets.data.data.length}${datasets.data.meta.has_more ? "+" : ""}`
    : "—";

  return (
    <div className="market-data-page">
      <div className="data-page-title-row">
        <h1 className="page-title" style={{ margin: 0 }}>
          Market Data
        </h1>
        <ProcessGuide />
      </div>
      <p className="data-page-intro">
        <strong>Market Data</strong> is the primary price and execution layer for research and
        backtests. Keep only price / execution inputs here: OHLCV, tick / trades, and spread /
        execution data. Funding, open interest, liquidations, order-book research features and other
        supporting context belong in <strong>Research Data</strong>. Verified is distinct from
        approved — only an ACTIVE + APPROVED revision feeds research and backtests.
      </p>

      <WorkflowRibbon steps={steps} />
      <SummaryCards registeredLabel={registeredLabel} />

      <div className="data-page-actions">
        <button
          type="button"
          className="btn"
          aria-expanded={setupOpen}
          onClick={() => setSetupOpen((open) => !open)}
        >
          {setupOpen ? "Close Dataset Setup" : "+ Add Market Dataset"}
        </button>
      </div>
      {setupOpen ? <CreateDatasetCard onCreated={setSelectedId} /> : null}

      <RegistryCard datasets={datasets} pager={pager} selectedId={selectedId} onOpen={setSelectedId} />
      {selectedId !== null ? <DetailCard entityId={selectedId} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Workflow ribbon (doc 11 §3.1) — the four ingest steps. Step states are DERIVED
// from the selected dataset's real revision_state projection (no new fetch): the
// pipeline is DRAFT -> UPLOADING -> ANALYZING -> NEEDS_REVIEW -> VERIFIED ->
// (Admin) APPROVED, with REJECTED/DEPRECATED as off-ladder terminals.
// ---------------------------------------------------------------------------

export type WorkflowStepStatus = "pending" | "active" | "complete" | "blocked" | "error";

export interface WorkflowStep {
  label: string;
  status: WorkflowStepStatus;
}

const WORKFLOW_STEP_LABELS = [
  "Upload raw source",
  "Analyze & map fields",
  "Create dataset version",
  "Verify / approve for use",
] as const;

// Ladder position of each revision_state along the ingest pipeline. `rejected`
// sits at the verify tier (a rejected verify decision); `deprecated` sits at the
// approved tier (it reached approval, then was retired).
const STATE_LADDER: Record<string, number> = {
  draft: 0,
  uploading: 1,
  analyzing: 2,
  needs_review: 3,
  verified: 4,
  rejected: 4,
  approved: 5,
  deprecated: 5,
};

// The ladder position at which each ribbon step (index 0..3) is COMPLETE.
const STEP_COMPLETE_AT = [1, 3, 4, 5];

// Pure, projection-driven derivation (unit-tested directly). null = no dataset in
// focus yet -> the whole ribbon is idle, never falsely "active". Co-located with
// the page per the UI-11 hot-file constraint (lib/marketData.ts is data-logic and
// off-limits); the export is a pure helper, not a component.
// eslint-disable-next-line react-refresh/only-export-components
export function deriveWorkflowSteps(revisionState: string | null): WorkflowStep[] {
  if (revisionState === null) {
    return WORKFLOW_STEP_LABELS.map((label) => ({ label, status: "pending" as const }));
  }
  const progress = STATE_LADDER[revisionState] ?? 0;
  const rejected = revisionState === "rejected";
  const needsReview = revisionState === "needs_review";
  const deprecated = revisionState === "deprecated";
  let activeAssigned = false;
  return WORKFLOW_STEP_LABELS.map((label, index) => {
    const completeAt = STEP_COMPLETE_AT[index] ?? Number.MAX_SAFE_INTEGER;
    if (progress >= completeAt) {
      // A deprecated dataset reached approval but is no longer usable — the final
      // gate reads blocked, not a clean complete.
      const status: WorkflowStepStatus =
        index === WORKFLOW_STEP_LABELS.length - 1 && deprecated ? "blocked" : "complete";
      return { label, status };
    }
    if (!activeAssigned) {
      activeAssigned = true;
      // The first not-yet-complete step is where the pipeline currently sits: a
      // rejected verify decision is an error, a needs-review gate is blocked.
      const status: WorkflowStepStatus = rejected ? "error" : needsReview ? "blocked" : "active";
      return { label, status };
    }
    return { label, status: "pending" };
  });
}

function workflowStatusLabel(status: WorkflowStepStatus): string {
  switch (status) {
    case "complete":
      return "Complete";
    case "active":
      return "Active";
    case "blocked":
      return "Blocked";
    case "error":
      return "Error";
    default:
      return "Pending";
  }
}

function WorkflowRibbon({ steps }: { steps: WorkflowStep[] }) {
  return (
    <ol className="data-workflow" aria-label="Market data ingestion workflow">
      {steps.map((step, index) => (
        <li
          key={step.label}
          className={`data-workflow-step wf-${step.status}`}
          aria-current={step.status === "active" ? "step" : undefined}
        >
          <span className="workflow-number">{index + 1}</span>
          <span className="workflow-step-body">
            <span className="workflow-step-label">{step.label}</span>
            {/* State word is textual, never colour-only (WCAG 1.4.1). */}
            <span className="workflow-step-state">{workflowStatusLabel(step.status)}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function SummaryCards({ registeredLabel }: { registeredLabel: string }) {
  return (
    <div className="dataset-summary-grid">
      <div className="dataset-summary-card">
        <div className="dataset-summary-label">REGISTERED DATASETS</div>
        <div className="dataset-summary-value">{registeredLabel}</div>
        <div>Reusable primary data sources visible to you.</div>
      </div>
      <div className="dataset-summary-card">
        <div className="dataset-summary-label">ALLOWED DATA TYPES</div>
        {/* Canonical count from the type registry mirror — never a magic literal. */}
        <div className="dataset-summary-value">{MARKET_DATA_TYPES.length}</div>
        <div>OHLCV, tick / trades, spread / execution.</div>
      </div>
      <div className="dataset-summary-card">
        <div className="dataset-summary-label">BACKTEST RULE</div>
        <div className="dataset-summary-value">Known Time</div>
        <div>Time basis must be declared before approval.</div>
      </div>
    </div>
  );
}

// The ⓘ SÜREÇ REHBERİ process guide (doc 11 §7). A native <details>/<summary> so
// it is keyboard-focusable and toggles with Enter/Space (no ARIA hand-rolling);
// help-only — it writes no form value. Content is the canonical Turkish guide from
// the v18 mockup (getMarketDataWorkflowGuide), the production-final copy.
function ProcessGuide() {
  return (
    <details className="data-guide">
      <summary className="data-workflow-guide-button">ⓘ SÜREÇ REHBERİ</summary>
      <div className="data-guide-body" role="note">
        <p className="data-guide-lead">
          <strong>Amaç:</strong> Market Data; ana fiyat ve işlem yürütme katmanıdır. Bir backtest,
          fiyat zemini olarak onaylanmış bir Market Data sürümünü kullanır. Bu sayfada yalnızca
          OHLCV, tick / trades veya spread / execution girdileri yer almalıdır.
        </p>
        <div className="data-guide-grid">
          <section className="data-guide-card">
            <h4>1. Bu sayfaya hangi veriler gelir?</h4>
            <ul>
              <li>
                <strong>OHLCV:</strong> bar temelli fiyat ve hacim verisi.
              </li>
              <li>
                <strong>Tick / Trades:</strong> tekil fiyat, miktar ve yön olayları.
              </li>
              <li>
                <strong>Spread / Execution:</strong> bid/ask veya işlem maliyeti girdileri.
              </li>
            </ul>
            <p>
              Funding, open interest, liquidation, heatmap ve araştırma feature&apos;ları burada
              değil, Research Data altında tutulur.
            </p>
          </section>
          <section className="data-guide-card">
            <h4>2. Zorunlu kimlik bilgileri</h4>
            <ul>
              <li>Dataset adı ve kaynak / sağlayıcı</li>
              <li>Gerçek instrument kapsamı</li>
              <li>Veri tipi ve çözünürlük</li>
              <li>Timezone ve kayıt zamanının neyi temsil ettiği</li>
              <li>Değiştirilmeden saklanan ham kaynak dosyası</li>
            </ul>
          </section>
          <section className="data-guide-card data-guide-wide">
            <h4>3. Zorunlu süreç</h4>
            <ol>
              <li>
                <strong>Ham kaynağı yükle:</strong> Orijinal dosya kanıt olarak saklanır; mapping
                işlemi ham dosyanın üzerine yazmaz.
              </li>
              <li>
                <strong>Analiz et ve eşle:</strong> Ingestion servisi kolonları, timestamp&apos;leri
                ve kaynak yapısını okur; uygun canonical şemayı önerir.
              </li>
              <li>
                <strong>Validasyonu incele:</strong> Kapsamı, eksik zaman aralıklarını, duplicate
                kayıtları, geçersiz değerleri ve belirtilen zaman bağlamını kontrol et.
              </li>
              <li>
                <strong>Dataset sürümü oluştur:</strong> Sürüm numarası taşıyan bir araştırma nesnesi
                oluşur. Mevcut çalışmalar kendi kullandıkları orijinal sürüme sabit kalır.
              </li>
              <li>
                <strong>Verify / approve:</strong> Ana backtest kaynağı olarak yalnızca Approved
                durumundaki sürüm seçilebilir olmalıdır.
              </li>
            </ol>
          </section>
          <section className="data-guide-card">
            <h4>4. Backtest korumaları</h4>
            <ul>
              <li>Instrument, stratejinin hedeflediği piyasa ile gerçekten eşleşmelidir.</li>
              <li>Timezone ile bar / event time bilgisi açık biçimde tanımlanmış olmalıdır.</li>
              <li>
                15m veri kaynağı, görünmeyen intrabar ayrıntısına dayanan varsayımları
                destekleyemez.
              </li>
              <li>Gap, duplicate ve geçersiz OHLC / fiyat kayıtları onaydan önce incelenmelidir.</li>
            </ul>
          </section>
        </div>
        <p className="data-guide-warning">
          <strong>Canlı sistem kuralı:</strong> Bu bağımsız arayüz süreci gösterir; gerçek onay ise
          dosyayı ayrıştıran, ham ve eşlenmiş sürümleri saklayan, validasyon sonuçlarını hesaplayan
          ve onaysız sürümlerin backtest&apos;e girmesini engelleyen backend işleriyle zorunlu olarak
          uygulanmalıdır.
        </p>
      </div>
    </details>
  );
}

// ---------------------------------------------------------------------------
// Create dataset — Root + first DRAFT revision (workflow entry)
// ---------------------------------------------------------------------------

// v18 §4 presentation option sets (mockup renderMarketDataUploader). These are
// display facets folded into the free-form `payload` — the wire body shape
// (market_data_type / payload / title / instrument_id) is unchanged.
const MARKETS = ["Crypto", "Forex", "Other"] as const;
const RESOLUTIONS = ["1m", "5m", "15m", "1h", "1D", "Event Based"] as const;
const DISPLAY_TIMEZONES = ["UTC", "Exchange Time", "Custom"] as const;
const RECORD_TIME_BASES = [
  "Bar Close / End Time",
  "Bar Open / Start Time",
  "Event Time",
] as const;

// Canonical MARKET_DATA_TYPES value → v18 human label (option VALUES stay the
// canonical server tokens; only the visible text mirrors the mockup).
const DATA_TYPE_LABELS: Record<string, string> = {
  ohlcv: "OHLCV",
  tick_trades: "Tick / Trades",
  spread_execution: "Spread / Execution",
};

// The post-create quality checks the analysis/verify pipeline runs (doc 11 §3.1
// column 3). Static guidance — the real states land on the revision after
// Analyze; the ribbon + detail reflect live progress.
const QUALITY_CHECKS = [
  "Schema mapping",
  "Time gaps / duplicates",
  "Price / execution consistency",
  "Instrument & timezone",
] as const;

// v18 §4 "MARKET DATASET SETUP" shell (mockup renderMarketDataUploader): a
// three-column setup form (SOURCE & IDENTITY / TIME & INSTRUMENT / ANALYSIS &
// USE). The descriptive facets (market, source/provider, resolution, timezone,
// record-time basis) fold into the create command's free-form `payload`; the
// wire body shape is unchanged. The raw source file is transferred AFTER create,
// in the detail Ingest workflow (upload needs the created entity id) — the ribbon
// step 1 and the detail's Step 1 hold the real <input type="file"> (F-01).
function CreateDatasetCard({ onCreated }: { onCreated: (entityId: string) => void }) {
  const create = useCreateDataset();
  const [dataType, setDataType] = useState<string>(MARKET_DATA_TYPES[0]);
  const [title, setTitle] = useState("");
  const [market, setMarket] = useState<string>(MARKETS[0]);
  const [sourceProvider, setSourceProvider] = useState("");
  const [instrumentId, setInstrumentId] = useState("");
  const [resolution, setResolution] = useState<string>("15m");
  const [timezone, setTimezone] = useState<string>(DISPLAY_TIMEZONES[0]);
  const [recordTimeBasis, setRecordTimeBasis] = useState<string>(RECORD_TIME_BASES[0]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    // Descriptive facets fold into the free-form payload — same route, same body
    // shape, no new headers. Domain validation stays server-side.
    const payload: Record<string, unknown> = {
      market,
      source_provider: sourceProvider.trim() || null,
      resolution,
      timezone,
      record_time_basis: recordTimeBasis,
    };
    create.mutate(
      {
        market_data_type: dataType,
        payload,
        title: title.trim() || null,
        instrument_id: instrumentId.trim() || null,
      },
      { onSuccess: (result) => onCreated(result.entity_id) },
    );
  };

  return (
    <section className="card" aria-labelledby="md-create-h">
      <h3 id="md-create-h" style={{ marginTop: 0 }}>
        Add market dataset
      </h3>
      <form onSubmit={submit}>
        <div className="data-setup-shell">
          <div className="data-setup-heading">MARKET DATASET SETUP</div>
          <div className="data-setup-grid">
            <section className="data-setup-column" aria-label="Source and identity">
              <div className="data-column-title">SOURCE &amp; IDENTITY</div>
              <div className="data-upload-box">
                <b>
                  Raw source file <span className="required-hint">*</span>
                </b>
                <p className="data-inline-note" style={{ marginTop: 4 }}>
                  Create the dataset first, then transfer the original CSV/TXT bytes in the Ingest
                  workflow below (Step 1). The raw source is stored unchanged as evidence.
                </p>
              </div>
              <div className="data-field">
                <label htmlFor="md-title">
                  Dataset Name <span className="required-hint">*</span>
                </label>
                <input
                  id="md-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="e.g. Binance Futures BTCUSDT · 15m OHLCV"
                />
              </div>
              <div className="data-field">
                <label htmlFor="md-market">
                  Market <span className="required-hint">*</span>
                </label>
                <select id="md-market" value={market} onChange={(event) => setMarket(event.target.value)}>
                  {MARKETS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
              <div className="data-field">
                <label htmlFor="md-type">
                  Data Type <span className="required-hint">*</span>
                </label>
                <select id="md-type" value={dataType} onChange={(event) => setDataType(event.target.value)}>
                  {MARKET_DATA_TYPES.map((value) => (
                    <option key={value} value={value}>
                      {DATA_TYPE_LABELS[value] ?? value}
                    </option>
                  ))}
                </select>
              </div>
              <div className="data-field">
                <label htmlFor="md-source">
                  Source / Provider <span className="required-hint">*</span>
                </label>
                <input
                  id="md-source"
                  value={sourceProvider}
                  onChange={(event) => setSourceProvider(event.target.value)}
                  placeholder="e.g. Binance Futures"
                />
              </div>
            </section>

            <section className="data-setup-column" aria-label="Time and instrument">
              <div className="data-column-title">TIME &amp; INSTRUMENT</div>
              <div className="data-field">
                <label htmlFor="md-instrument">
                  Instrument Scope <span className="required-hint">*</span>
                </label>
                <input
                  id="md-instrument"
                  value={instrumentId}
                  onChange={(event) => setInstrumentId(event.target.value)}
                  placeholder="e.g. BTCUSDT Perpetual"
                />
              </div>
              <div className="data-field">
                <label htmlFor="md-resolution">
                  Resolution <span className="required-hint">*</span>
                </label>
                <select
                  id="md-resolution"
                  value={resolution}
                  onChange={(event) => setResolution(event.target.value)}
                >
                  {RESOLUTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
              <div className="data-field">
                <label htmlFor="md-tz">
                  Timezone <span className="required-hint">*</span>
                </label>
                <select id="md-tz" value={timezone} onChange={(event) => setTimezone(event.target.value)}>
                  {DISPLAY_TIMEZONES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
              <div className="data-field">
                <label htmlFor="md-record-time">
                  Record Time Basis <span className="required-hint">*</span>
                </label>
                <select
                  id="md-record-time"
                  value={recordTimeBasis}
                  onChange={(event) => setRecordTimeBasis(event.target.value)}
                >
                  {RECORD_TIME_BASES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
              <div className="data-preview-card">
                <b>What will be standardized?</b>
                <br />
                Only the price / execution fields needed by the selected data type. The raw source
                remains unchanged and is stored separately.
              </div>
            </section>

            <section className="data-setup-column" aria-label="Analysis and use">
              <div className="data-column-title">ANALYSIS &amp; USE</div>
              <div className="data-preview-card">
                <b>Standardization preview</b>
                <br />
                Choose the source and minimum context, then create the dataset and run Analyze in the
                Ingest workflow. The backend maps fields into the correct canonical schema.
              </div>
              <ul className="data-quality-list" aria-label="Post-create quality checks">
                {QUALITY_CHECKS.map((check) => (
                  <li key={check}>
                    <span>{check}</span>
                    <span className="dataset-status-pill">Runs after analyze</span>
                  </li>
                ))}
              </ul>
              <div className="data-action-row">
                <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                  Create dataset
                </button>
              </div>
              <p className="data-compact-help">
                Analyze &amp; map, verify and Admin approve happen on the created dataset below.
              </p>
            </section>
          </div>
        </div>
      </form>
      {create.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(create.error)}
        </p>
      ) : null}
      {create.data ? (
        <p aria-live="polite">
          Created — {create.data.entity_id} ({create.data.revision_state}).
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Registry — role-aware head-revision catalog (doc 11 §3.3)
// ---------------------------------------------------------------------------

function RegistryCard({
  datasets,
  pager,
  selectedId,
  onOpen,
}: {
  datasets: ReturnType<typeof useMarketDatasets>;
  pager: ReturnType<typeof useCursorStack>;
  selectedId: string | null;
  onOpen: (entityId: string) => void;
}) {
  return (
    <section className="card" aria-labelledby="md-registry-h">
      <h3 id="md-registry-h" style={{ marginTop: 0 }}>
        Dataset registry
        {datasets.data ? (
          <span className="page-sub" style={{ marginLeft: 8 }}>
            ({datasets.data.data.length} visible on this page)
          </span>
        ) : null}
      </h3>
      {datasets.isLoading ? (
        <Loading label="Loading market datasets…" />
      ) : datasets.isError ? (
        <ErrorState error={datasets.error} onRetry={() => void datasets.refetch()} />
      ) : datasets.data ? (
        <>
          {datasets.data.data.length === 0 ? (
            <EmptyState title="No market datasets visible yet — create the first one above" />
          ) : (
            <div className="table-scroll">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Dataset</th>
                  <th scope="col">Type</th>
                  <th scope="col">Instrument</th>
                  <th scope="col">Revision state</th>
                  <th scope="col">Validation</th>
                  <th scope="col">Rev</th>
                  <th scope="col">Created (UTC)</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {datasets.data.data.map((row) => (
                  <RegistryRow
                    key={row.entity_id}
                    row={row}
                    isOpen={selectedId === row.entity_id}
                    onOpen={() => onOpen(row.entity_id)}
                  />
                ))}
              </tbody>
            </table>
            </div>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={datasets.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
    </section>
  );
}

function RegistryRow({
  row,
  isOpen,
  onOpen,
}: {
  row: MarketDatasetRow;
  isOpen: boolean;
  onOpen: () => void;
}) {
  return (
    <tr style={isOpen ? { background: "var(--bg-elev)" } : undefined}>
      <td>{row.title ?? row.entity_id}</td>
      <td>
        <code>{row.market_data_type}</code>
      </td>
      <td>{row.instrument_id ?? "—"}</td>
      <td>
        <StatusBadge tone={revisionStateTone(row.revision_state)} label={row.revision_state} />
      </td>
      <td>{row.validation_status ?? "—"}</td>
      <td>v{row.revision_no}</td>
      <td>{formatUtc(row.created_at)}</td>
      <td>
        <button type="button" className="btn" onClick={onOpen}>
          Open
        </button>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Detail — identity + revision history + ingest workflow + bundle probe
// ---------------------------------------------------------------------------

function DetailCard({ entityId }: { entityId: string }) {
  const detail = useMarketDataset(entityId);

  return (
    <section className="card" aria-labelledby="md-detail-h">
      <h3 id="md-detail-h" style={{ marginTop: 0 }}>
        Dataset detail
      </h3>
      {detail.isLoading ? (
        <Loading label="Loading dataset…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : detail.data ? (
        <>
          <IdentitySection detail={detail.data} />
          <IngestSection detail={detail.data} />
          <LifecycleSection detail={detail.data} />
          <BundleProbe entityId={entityId} />
        </>
      ) : null}
    </section>
  );
}

function IdentitySection({ detail }: { detail: MarketDatasetDetail }) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <strong>{detail.title ?? detail.entity_id}</strong>
        <StatusBadge tone={revisionStateTone(detail.revision_state)} label={detail.revision_state} />
        <StatusBadge label={detail.lifecycle_state} />
        {detail.validation_status !== null ? <StatusBadge label={detail.validation_status} /> : null}
      </div>
      <div className="table-scroll">
      <table className="metrics-table" style={{ marginTop: 12 }}>
        <tbody>
          <tr>
            <th scope="row">Root / revision</th>
            <td>
              <code>{detail.entity_id}</code> · <code>{detail.revision_id}</code> · v
              {detail.revision_no} <span className="page-sub">(rv {detail.row_version})</span>
            </td>
          </tr>
          <tr>
            <th scope="row">Type / instrument</th>
            <td>
              <code>{detail.market_data_type}</code> · {detail.instrument_id ?? "—"}
            </td>
          </tr>
          <tr>
            <th scope="row">Owner</th>
            <td>{detail.owner_principal_id ?? "—"}</td>
          </tr>
          <tr>
            <th scope="row">Content hash</th>
            <td>{detail.content_hash !== null ? <code>{detail.content_hash}</code> : "—"}</td>
          </tr>
          <tr>
            <th scope="row">Manifest hash</th>
            <td>{detail.manifest_hash !== null ? <code>{detail.manifest_hash}</code> : "—"}</td>
          </tr>
          <tr>
            <th scope="row">Created (UTC)</th>
            <td>{formatUtc(detail.created_at)}</td>
          </tr>
        </tbody>
      </table>
      </div>
      <h4>Revision history</h4>
      {detail.revisions.length === 0 ? (
        <p className="page-sub">No revisions recorded.</p>
      ) : (
        <ul>
          {detail.revisions.map((revision) => (
            <li key={revision.revision_id}>
              v{revision.revision_no} · <code>{revision.revision_id}</code> ·{" "}
              {revision.revision_state}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

// The owner ingest chain (doc 11 §3.1 ribbon): Step 1 register + finalize the
// raw asset, Step 2 run the durable analysis job and confirm the canonical
// schema mapping. Buttons are never role-pre-gated — the server's owner/Admin
// draft gate answers with the canonical envelope verbatim.
function IngestSection({ detail }: { detail: MarketDatasetDetail }) {
  return (
    <>
      <h4>Ingest workflow</h4>
      <UploadComposer entityId={detail.entity_id} />
      <AnalysisAction entityId={detail.entity_id} />
      <MappingComposer entityId={detail.entity_id} marketDataType={detail.market_data_type} />
    </>
  );
}

// Bytes-per-unit thresholds for the human-readable progress label.
const KILOBYTE = 1024;
const MEGABYTE = KILOBYTE * 1024;

function formatBytes(bytes: number): string {
  if (bytes >= MEGABYTE) return `${(bytes / MEGABYTE).toFixed(1)} MB`;
  if (bytes >= KILOBYTE) return `${(bytes / KILOBYTE).toFixed(1)} KB`;
  return `${bytes} B`;
}

// Step 1 — native file chooser + real byte transfer (F-01). The client never
// supplies object key/digest/size/content-type; the server derives all of it
// from the transferred bytes and returns it in the response. Finalize then
// moves the revision DRAFT -> UPLOADING.
function UploadComposer({ entityId }: { entityId: string }) {
  const queryClient = useQueryClient();
  const upload = useFileUpload<StartUploadResult>();
  const finalize = useFinalizeUpload();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    upload.reset();
  };

  const submitUpload = (event: FormEvent) => {
    event.preventDefault();
    if (selectedFile === null) return;
    upload
      .upload(rawUploadPath(entityId), selectedFile, { idempotencyKey: crypto.randomUUID() })
      .then(() => invalidateAfterRawUpload(queryClient))
      .catch(() => {
        // Surfaced via upload.error below; nothing further to do here.
      });
  };

  const retry = () => {
    if (selectedFile === null) return;
    upload
      .upload(rawUploadPath(entityId), selectedFile, { idempotencyKey: crypto.randomUUID() })
      .then(() => invalidateAfterRawUpload(queryClient))
      .catch(() => {
        // Surfaced via upload.error below.
      });
  };

  const progressPercent =
    upload.progress && upload.progress.total > 0
      ? Math.round((upload.progress.loaded / upload.progress.total) * 100)
      : null;

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Step 1 — raw source</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Choose a local CSV/TXT file. The bytes are transferred to object storage and the object key,
        digest, size, and content type are generated automatically — you never enter storage metadata.
      </p>
      <form onSubmit={submitUpload}>
        <label htmlFor="md-file">
          File
          <input
            id="md-file"
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            onChange={onFileChange}
          />
        </label>
        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={selectedFile === null || upload.status === "uploading"}
          >
            Upload file
          </button>
          {upload.status === "uploading" ? (
            <button type="button" className="btn" onClick={upload.cancel}>
              Cancel
            </button>
          ) : null}
          {upload.status === "error" || upload.status === "cancelled" ? (
            <button type="button" className="btn" onClick={retry}>
              Retry
            </button>
          ) : null}
        </div>
      </form>

      {upload.status === "uploading" && upload.progress ? (
        <p aria-live="polite" style={{ marginTop: 8 }}>
          Uploading… {formatBytes(upload.progress.loaded)} / {formatBytes(upload.progress.total)}
          {progressPercent !== null ? ` (${progressPercent}%)` : ""}
        </p>
      ) : null}
      {upload.status === "cancelled" ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          Upload cancelled.
        </p>
      ) : null}
      {upload.status === "error" ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(upload.error)}
        </p>
      ) : null}
      {upload.status === "success" && upload.data ? (
        <p aria-live="polite">
          {upload.data.deduplicated ? "Already uploaded — reused" : "Uploaded"} — asset{" "}
          <code>{upload.data.asset_id}</code> ({formatBytes(upload.data.size_bytes)},{" "}
          digest <code>{upload.data.content_digest.slice(0, 12)}…</code>).
        </p>
      ) : null}

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn"
          disabled={finalize.isPending || upload.data === null}
          onClick={() =>
            upload.data
              ? finalize.mutate({ entity_id: entityId, asset_id: upload.data.asset_id })
              : undefined
          }
        >
          Finalize upload
        </button>
      </div>
      {finalize.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(finalize.error)}
        </p>
      ) : null}
      {finalize.data ? (
        <p aria-live="polite">
          Upload finalized — revision {finalize.data.revision_id} is now{" "}
          {finalize.data.revision_state}.
        </p>
      ) : null}
    </div>
  );
}

function AnalysisAction({ entityId }: { entityId: string }) {
  const analysis = useRequestAnalysis();
  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Step 2 — analyze</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Enqueues the durable profile/mapping job on the data queue; the job row survives browser
        close and progress lands back on the revision state.
      </p>
      <button
        type="button"
        className="btn"
        disabled={analysis.isPending}
        onClick={() => analysis.mutate({ entity_id: entityId })}
      >
        Request analysis
      </button>
      {analysis.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(analysis.error)}
        </p>
      ) : null}
      {analysis.data ? (
        <p aria-live="polite">
          Analysis accepted — job <code>{analysis.data.job_id}</code> on queue{" "}
          <code>{analysis.data.queue}</code> ({analysis.data.status}).
        </p>
      ) : null}
    </div>
  );
}

function MappingComposer({
  entityId,
  marketDataType,
}: {
  entityId: string;
  marketDataType: string;
}) {
  const confirm = useConfirmMapping();
  const [columnsText, setColumnsText] = useState("");
  const [mappingText, setMappingText] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const confirmedLines = mappingText.trim();
    confirm.mutate({
      entity_id: entityId,
      market_data_type: marketDataType,
      source_columns: linesToList(columnsText),
      confirmed_mapping: confirmedLines.length > 0 ? parseMappingLines(mappingText) : undefined,
    });
  };

  return (
    <div>
      <strong>Step 2b — schema mapping</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Proposes the canonical mapping from your source columns; an unambiguous proposal
        auto-confirms, otherwise supply the explicit mapping (one “canonical: source” per line).
      </p>
      <form onSubmit={submit}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label htmlFor="md-columns">
            Source columns (one per line)
            <textarea
              id="md-columns"
              rows={4}
              value={columnsText}
              onChange={(event) => setColumnsText(event.target.value)}
              placeholder={"timestamp\nopen\nhigh\nlow\nclose\nvolume"}
              required
            />
          </label>
          <label htmlFor="md-mapping">
            Confirmed mapping (optional, “canonical: source” per line)
            <textarea
              id="md-mapping"
              rows={4}
              value={mappingText}
              onChange={(event) => setMappingText(event.target.value)}
              placeholder={"timestamp: ts\nclose: last_price"}
            />
          </label>
        </div>
        <button type="submit" className="btn" disabled={confirm.isPending} style={{ marginTop: 8 }}>
          Confirm mapping
        </button>
      </form>
      {confirm.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(confirm.error)}
        </p>
      ) : null}
      {confirm.data ? (
        <div aria-live="polite">
          <p style={{ marginBottom: 4 }}>
            Mapping saved — <code>{confirm.data.mapping_id}</code>
            {confirm.data.review_required ? " (review required)" : ""}.
          </p>
          {confirm.data.confirmed_mapping !== null ? (
            <ul style={{ marginTop: 0 }}>
              {Object.entries(confirm.data.confirmed_mapping).map(([canonical, source]) => (
                <li key={canonical}>
                  <code>{canonical}</code> ← {source !== null ? <code>{source}</code> : "unmapped"}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Revision lifecycle (doc 11 §5): append a DRAFT revision (OCC) or a superseding
// successor, and Admin approve/deprecate. Buttons are never role-pre-gated —
// approve/deprecate are Admin-only server-side and a denial (403) or an illegal
// transition / stale token (409) renders the canonical envelope verbatim.
// ---------------------------------------------------------------------------

function LifecycleSection({ detail }: { detail: MarketDatasetDetail }) {
  return (
    <div style={{ marginTop: 16 }}>
      <h4>Revision lifecycle</h4>
      <RevisionComposer detail={detail} />
      <ApprovalComposer detail={detail} />
    </div>
  );
}

function revisionOptionLabel(revision: MarketRevisionRef): string {
  return `v${revision.revision_no} · ${revision.revision_id} · ${revision.revision_state}`;
}

// Append a new DRAFT revision (OCC via the detail row_version) OR a superseding
// successor (no OCC). Both actions share one field set; a timezone is REQUIRED by
// the revisions route (an IANA id only for `custom` mode). Payload is parsed
// locally as a transport check — domain validation stays server-side.
function RevisionComposer({ detail }: { detail: MarketDatasetDetail }) {
  const createRevision = useCreateRevision();
  const createSuccessor = useCreateSuccessor();
  const me = useMe();
  // Fail-closed role gate (R2-05b pattern): the raw payload disclosure renders
  // only once /me proves is_admin — loading, error and non-admin all hide it.
  const isAdmin = me.data?.is_admin === true;
  const [dataType, setDataType] = useState<string>(detail.market_data_type);
  const [title, setTitle] = useState("");
  const [instrumentId, setInstrumentId] = useState("");
  const [payloadText, setPayloadText] = useState("");
  const [timezoneMode, setTimezoneMode] = useState<string>(TIMEZONE_MODES[0]);
  const [timezoneIana, setTimezoneIana] = useState("");
  const [payloadError, setPayloadError] = useState<string | null>(null);

  // Returns the wire body, or null when the payload is unserializable (a local
  // transport block — never a domain judgement).
  const buildBody = (): RevisionBody | null => {
    let payload: Record<string, unknown> = {};
    if (payloadText.trim().length > 0) {
      try {
        const parsed: unknown = JSON.parse(payloadText);
        if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
          setPayloadError("Payload must be a JSON object.");
          return null;
        }
        payload = parsed as Record<string, unknown>;
      } catch {
        setPayloadError("Payload is not valid JSON.");
        return null;
      }
    }
    setPayloadError(null);
    return {
      market_data_type: dataType,
      payload,
      title: title.trim() || null,
      instrument_id: instrumentId.trim() || null,
      timezone_mode: timezoneMode,
      // Only `custom` carries an IANA id; other modes send null and let the
      // server resolve the zone (exchange/utc).
      timezone_iana: timezoneMode === "custom" ? timezoneIana.trim() || null : null,
    };
  };

  const appendRevision = (event: FormEvent) => {
    event.preventDefault();
    const body = buildBody();
    if (body === null) return;
    createRevision.mutate({
      entity_id: detail.entity_id,
      row_version: detail.row_version,
      ...body,
    });
  };

  const appendSuccessor = () => {
    const body = buildBody();
    if (body === null) return;
    createSuccessor.mutate({ entity_id: detail.entity_id, ...body });
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>New revision</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Append a DRAFT revision under optimistic concurrency (If-Match rv-{detail.row_version}), or a
        successor that supersedes the current head. A stale row_version → 409 STALE_REVISION verbatim.
      </p>
      <form onSubmit={appendRevision}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <label htmlFor="md-rev-type">
            Market data type
            <select id="md-rev-type" value={dataType} onChange={(event) => setDataType(event.target.value)}>
              {MARKET_DATA_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="md-rev-tz">
            Timezone mode
            <select
              id="md-rev-tz"
              value={timezoneMode}
              onChange={(event) => setTimezoneMode(event.target.value)}
            >
              {TIMEZONE_MODES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          {timezoneMode === "custom" ? (
            <label htmlFor="md-rev-iana">
              IANA timezone (required for custom)
              <input
                id="md-rev-iana"
                value={timezoneIana}
                onChange={(event) => setTimezoneIana(event.target.value)}
                placeholder="America/New_York"
              />
            </label>
          ) : null}
          <label htmlFor="md-rev-title">
            Title (optional)
            <input id="md-rev-title" value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
        </div>
        {/* R2-08 (GAP item 7): the instrument is picked from the canonical
            registry; the immutable instrument_id travels system-side and shows
            only as read-only provenance under the selection. */}
        <div style={{ marginTop: 8 }}>
          <InstrumentPicker
            label="Instrument (optional)"
            value={instrumentId}
            onChange={setInstrumentId}
          />
        </div>
        {isAdmin ? (
          <details style={{ marginTop: 8 }}>
            <summary>Advanced (raw revision payload)</summary>
            <p className="cp-note" style={{ marginTop: 8 }}>
              The revision payload has no documented product schema (doc 11 §5) — it stays a JSON
              control, Admin-only under Advanced (GAP item 9).
            </p>
            <label htmlFor="md-rev-payload" style={{ display: "block" }}>
              Payload (optional JSON object)
              <textarea
                id="md-rev-payload"
                rows={3}
                value={payloadText}
                onChange={(event) => setPayloadText(event.target.value)}
                placeholder='{"source": "binance_futures"}'
              />
            </label>
          </details>
        ) : null}
        <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
          <button type="submit" className="btn btn-primary" disabled={createRevision.isPending}>
            Append revision
          </button>
          <button
            type="button"
            className="btn"
            disabled={createSuccessor.isPending}
            onClick={appendSuccessor}
          >
            Create successor
          </button>
        </div>
      </form>
      {payloadError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {payloadError}
        </p>
      ) : null}
      {createRevision.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(createRevision.error)}
        </p>
      ) : null}
      {createRevision.data ? (
        <p aria-live="polite">
          Revision appended — <code>{createRevision.data.revision_id}</code> (v
          {createRevision.data.revision_no}).
        </p>
      ) : null}
      {createSuccessor.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(createSuccessor.error)}
        </p>
      ) : null}
      {createSuccessor.data ? (
        <p aria-live="polite">
          Successor created — <code>{createSuccessor.data.revision_id}</code> (v
          {createSuccessor.data.revision_no}, {createSuccessor.data.revision_state}).
        </p>
      ) : null}
    </div>
  );
}

// Admin approve (VERIFIED → APPROVED, OCC) / deprecate (APPROVED → DEPRECATED, no
// OCC) a chosen revision. The picker defaults to the current head; the server is
// the sole authority on role + legal transition — a 403/409 renders verbatim.
function ApprovalComposer({ detail }: { detail: MarketDatasetDetail }) {
  const approve = useApproveRevision();
  const deprecate = useDeprecateRevision();
  const [revisionId, setRevisionId] = useState<string>(detail.revision_id);
  const [note, setNote] = useState("");

  const noteOrNull = note.trim() || null;

  const submitApprove = (event: FormEvent) => {
    event.preventDefault();
    approve.mutate({
      entity_id: detail.entity_id,
      row_version: detail.row_version,
      revision_id: revisionId,
      note: noteOrNull,
    });
  };

  const submitDeprecate = () => {
    deprecate.mutate({ entity_id: detail.entity_id, revision_id: revisionId, note: noteOrNull });
  };

  return (
    <div>
      <strong>Admin approval</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Approve a VERIFIED revision (If-Match rv-{detail.row_version}) or deprecate an APPROVED one.
        Admin-only server-side — a non-Admin sees the 403 envelope verbatim.
      </p>
      <form onSubmit={submitApprove}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label htmlFor="md-approve-rev">
            Target revision
            <select
              id="md-approve-rev"
              value={revisionId}
              onChange={(event) => setRevisionId(event.target.value)}
            >
              {detail.revisions.map((revision) => (
                <option key={revision.revision_id} value={revision.revision_id}>
                  {revisionOptionLabel(revision)}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="md-approve-note">
            Decision note (optional)
            <input id="md-approve-note" value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
          <button type="submit" className="btn btn-primary" disabled={approve.isPending}>
            Approve (Admin)
          </button>
          <button
            type="button"
            className="btn"
            disabled={deprecate.isPending}
            onClick={submitDeprecate}
          >
            Deprecate (Admin)
          </button>
        </div>
      </form>
      {approve.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(approve.error)}
        </p>
      ) : null}
      {approve.data ? (
        <p aria-live="polite">
          Approved — revision <code>{approve.data.revision_id}</code> is now {approve.data.revision_state}.
        </p>
      ) : null}
      {deprecate.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(deprecate.error)}
        </p>
      ) : null}
      {deprecate.data ? (
        <p aria-live="polite">
          Deprecated — revision <code>{deprecate.data.revision_id}</code> is now{" "}
          {deprecate.data.revision_state}.
        </p>
      ) : null}
    </div>
  );
}

// Read-only resolve probe: which exact APPROVED revision would a Run pin right
// now? A dataset without an ACTIVE+APPROVED revision answers 404 verbatim —
// consumers never silently bind to "latest".
function BundleProbe({ entityId }: { entityId: string }) {
  const [probed, setProbed] = useState(false);
  const bundle = useApprovedBundle(entityId, probed);

  return (
    <div style={{ marginTop: 16 }}>
      <h4>Approved bundle</h4>
      <button
        type="button"
        className="btn"
        onClick={() => (probed ? void bundle.refetch() : setProbed(true))}
        disabled={bundle.isFetching}
      >
        Resolve approved bundle
      </button>
      {probed && bundle.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(bundle.error)}
        </p>
      ) : null}
      {bundle.data ? (
        <p aria-live="polite">
          Pinned — revision <code>{bundle.data.revision_id}</code> (v{bundle.data.revision_no},{" "}
          {bundle.data.revision_state}) · content{" "}
          <code>{bundle.data.content_hash ?? "—"}</code> · manifest{" "}
          <code>{bundle.data.manifest_hash ?? "—"}</code>
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
