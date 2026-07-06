// Prometheus text exposition parser + a derived ops summary for the /v1/metrics
// dashboard. The backend (apps/api/routes/metrics.py) serves text/plain in the
// Prometheus 0.0.4 exposition format; the browser owns no state here — it only
// parses and presents what the server scrapes. Pure and dependency-free so the
// dashboard component stays a thin renderer and the parsing stays unit-testable.

export type MetricType = "counter" | "gauge" | "histogram" | "summary" | "untyped";

export interface MetricSample {
  readonly name: string;
  readonly labels: Readonly<Record<string, string>>;
  readonly value: number;
}

export interface MetricFamily {
  readonly name: string;
  readonly type: MetricType;
  readonly help?: string;
  readonly samples: readonly MetricSample[];
}

export interface ParsedMetrics {
  readonly families: Readonly<Record<string, MetricFamily>>;
  // Freeform `#` comments that are neither HELP nor TYPE — e.g. the backend's
  // "operational gauges unavailable (database unreachable)" degradation notice.
  readonly notes: readonly string[];
}

// A sample is `name{labels}? value [timestamp]?`; we ignore the optional trailing
// scrape timestamp (the backend never emits one).
const SAMPLE_RE = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{.*\})?\s+(.+)$/;
const LABEL_RE = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^\\"])*)"/g;
const HELP_RE = /^#\s+HELP\s+(\S+)\s+(.*)$/;
const TYPE_RE = /^#\s+TYPE\s+(\S+)\s+(\w+)$/;

function parseValue(token: string): number {
  if (token === "+Inf" || token === "Inf") return Number.POSITIVE_INFINITY;
  if (token === "-Inf") return Number.NEGATIVE_INFINITY;
  if (token === "NaN") return Number.NaN;
  return Number(token);
}

function unescapeLabel(raw: string): string {
  // Prometheus escapes only \\, \" and \n inside a label value.
  return raw.replace(/\\([\\"n])/g, (_m, c: string) => (c === "n" ? "\n" : c));
}

function parseLabels(block: string): Record<string, string> {
  const labels: Record<string, string> = {};
  LABEL_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = LABEL_RE.exec(block)) !== null) {
    labels[match[1]] = unescapeLabel(match[2]);
  }
  return labels;
}

function normalizeType(raw: string): MetricType {
  return raw === "counter" || raw === "gauge" || raw === "histogram" || raw === "summary"
    ? raw
    : "untyped";
}

// Histogram/summary samples carry a suffixed name (_bucket/_sum/_count) but belong
// to the base family declared by `# TYPE`. Resolve a sample's owning family.
function ownerFamily(sampleName: string, types: Record<string, MetricType>): string {
  if (types[sampleName]) return sampleName;
  for (const suffix of ["_bucket", "_sum", "_count"] as const) {
    if (!sampleName.endsWith(suffix)) continue;
    const base = sampleName.slice(0, -suffix.length);
    const baseType = types[base];
    if (baseType === "histogram" || (baseType === "summary" && suffix !== "_bucket")) {
      return base;
    }
  }
  return sampleName;
}

export function parsePrometheus(text: string): ParsedMetrics {
  const types: Record<string, MetricType> = {};
  const helps: Record<string, string> = {};
  const builders: Record<string, MetricSample[]> = {};
  const order: string[] = [];
  const notes: string[] = [];

  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (line === "") continue;

    if (line.startsWith("#")) {
      const help = HELP_RE.exec(line);
      if (help) {
        helps[help[1]] = help[2];
        continue;
      }
      const type = TYPE_RE.exec(line);
      if (type) {
        types[type[1]] = normalizeType(type[2]);
        continue;
      }
      notes.push(line.replace(/^#\s*/, ""));
      continue;
    }

    const match = SAMPLE_RE.exec(line);
    if (!match) continue;
    const [, name, labelBlock, rest] = match;
    const value = parseValue(rest.trim().split(/\s+/)[0]);
    const labels = labelBlock ? parseLabels(labelBlock) : {};
    const family = ownerFamily(name, types);
    if (!builders[family]) {
      builders[family] = [];
      order.push(family);
    }
    builders[family].push({ name, labels, value });
  }

  const families: Record<string, MetricFamily> = {};
  for (const family of order) {
    families[family] = {
      name: family,
      type: types[family] ?? "untyped",
      help: helps[family],
      samples: builders[family],
    };
  }
  return { families, notes };
}

// ---------------------------------------------------------------------------
// Derived ops summary — the four golden signals plus the operational gauges the
// backend computes at scrape time (jobs depth, outbox lag, oldest RUNNING lease).
// ---------------------------------------------------------------------------

export interface GoldenSignals {
  readonly requestsTotal: number; // traffic
  readonly serverErrors: number; // errors (5xx)
  readonly clientErrors: number; // 4xx (shown for context)
  readonly inFlight: number | null; // saturation
  readonly avgLatencyMs: number | null; // latency (histogram sum / count)
  readonly statusClasses: Readonly<Record<string, number>>;
}

export interface JobsDepthRow {
  readonly queue: string;
  readonly status: string;
  readonly count: number;
}

export interface MetricsSummary {
  readonly golden: GoldenSignals;
  readonly jobsDepth: readonly JobsDepthRow[];
  readonly jobsDepthTotal: number;
  readonly outboxLagSeconds: number | null;
  readonly leaseAgeSeconds: number | null;
  // The backend degrades gracefully when Postgres is unreachable: it drops the
  // gauge block and emits a note instead of failing the scrape.
  readonly degraded: boolean;
  readonly familyCount: number;
}

const REQUESTS_TOTAL = "entropia_http_requests_total";
const DURATION = "entropia_http_request_duration_seconds";
const IN_FLIGHT = "entropia_http_requests_in_flight";
const JOBS_DEPTH = "entropia_jobs_depth";
const OUTBOX_LAG = "entropia_outbox_lag_seconds";
const LEASE_AGE = "entropia_job_lease_age_seconds";
const DB_UNAVAILABLE_NOTE = "operational gauges unavailable";
const MS_PER_SECOND = 1000;

function samplesOf(metrics: ParsedMetrics, family: string): readonly MetricSample[] {
  return metrics.families[family]?.samples ?? [];
}

// A no-label scalar gauge (outbox lag, lease age, in-flight): the single sample.
function scalar(metrics: ParsedMetrics, family: string): number | null {
  const samples = samplesOf(metrics, family);
  return samples.length > 0 ? samples[0].value : null;
}

function statusClass(status: string): string {
  return /^[1-5]\d\d$/.test(status) ? `${status[0]}xx` : "other";
}

function goldenSignals(metrics: ParsedMetrics): GoldenSignals {
  const statusClasses: Record<string, number> = {};
  let requestsTotal = 0;
  for (const sample of samplesOf(metrics, REQUESTS_TOTAL)) {
    requestsTotal += sample.value;
    const cls = statusClass(sample.labels.status ?? "");
    statusClasses[cls] = (statusClasses[cls] ?? 0) + sample.value;
  }

  let durationSum = 0;
  let durationCount = 0;
  for (const sample of samplesOf(metrics, DURATION)) {
    if (sample.name.endsWith("_sum")) durationSum += sample.value;
    else if (sample.name.endsWith("_count")) durationCount += sample.value;
  }

  return {
    requestsTotal,
    serverErrors: statusClasses["5xx"] ?? 0,
    clientErrors: statusClasses["4xx"] ?? 0,
    inFlight: scalar(metrics, IN_FLIGHT),
    avgLatencyMs: durationCount > 0 ? (durationSum / durationCount) * MS_PER_SECOND : null,
    statusClasses,
  };
}

function jobsDepthRows(metrics: ParsedMetrics): JobsDepthRow[] {
  return samplesOf(metrics, JOBS_DEPTH)
    .map((sample) => ({
      queue: sample.labels.queue ?? "?",
      status: sample.labels.status ?? "?",
      count: sample.value,
    }))
    .sort((a, b) => a.queue.localeCompare(b.queue) || a.status.localeCompare(b.status));
}

export function summarizeMetrics(metrics: ParsedMetrics): MetricsSummary {
  const rows = jobsDepthRows(metrics);
  const outboxLagSeconds = scalar(metrics, OUTBOX_LAG);
  const leaseAgeSeconds = scalar(metrics, LEASE_AGE);
  const noteDegraded = metrics.notes.some((note) => note.includes(DB_UNAVAILABLE_NOTE));
  const gaugesMissing = outboxLagSeconds === null && leaseAgeSeconds === null && rows.length === 0;

  return {
    golden: goldenSignals(metrics),
    jobsDepth: rows,
    jobsDepthTotal: rows.reduce((acc, row) => acc + row.count, 0),
    outboxLagSeconds,
    leaseAgeSeconds,
    degraded: noteDegraded || gaugesMissing,
    familyCount: Object.keys(metrics.families).length,
  };
}

// Convenience for the query hook: raw exposition text -> ready-to-render summary.
export function parseMetricsSummary(text: string): MetricsSummary {
  return summarizeMetrics(parsePrometheus(text));
}
