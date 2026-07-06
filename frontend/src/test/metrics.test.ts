import { describe, expect, it } from "vitest";
import { parsePrometheus, summarizeMetrics, parseMetricsSummary } from "@/lib/metrics";

// A representative healthy scrape mirroring apps/api/routes/metrics.py output:
// process-local golden signals + the DB-backed operational gauge block.
const HEALTHY = `# TYPE entropia_http_requests_total counter
entropia_http_requests_total{method="GET",path="/v1/meta",status="200"} 12
entropia_http_requests_total{method="POST",path="/v1/auth/login",status="200"} 3
entropia_http_requests_total{method="GET",path="/v1/library",status="404"} 2
entropia_http_requests_total{method="GET",path="/v1/metrics",status="500"} 1
# TYPE entropia_http_request_duration_seconds histogram
entropia_http_request_duration_seconds_bucket{method="GET",path="/v1/meta",le="0.01"} 5
entropia_http_request_duration_seconds_bucket{method="GET",path="/v1/meta",le="+Inf"} 12
entropia_http_request_duration_seconds_sum{method="GET",path="/v1/meta"} 0.24
entropia_http_request_duration_seconds_count{method="GET",path="/v1/meta"} 12
entropia_http_request_duration_seconds_sum{method="POST",path="/v1/auth/login"} 0.06
entropia_http_request_duration_seconds_count{method="POST",path="/v1/auth/login"} 3
# TYPE entropia_http_requests_in_flight gauge
entropia_http_requests_in_flight 2
# TYPE entropia_jobs_depth gauge
entropia_jobs_depth{queue="default",status="running"} 1
entropia_jobs_depth{queue="default",status="queued"} 4
entropia_jobs_depth{queue="data",status="succeeded"} 20
# TYPE entropia_outbox_lag_seconds gauge
entropia_outbox_lag_seconds 0.512
# TYPE entropia_job_lease_age_seconds gauge
entropia_job_lease_age_seconds 3.14
`;

// The degraded scrape: Postgres unreachable, so the backend drops the gauge block
// and emits a note instead of failing the scrape.
const DEGRADED = `# TYPE entropia_http_requests_total counter
entropia_http_requests_total{method="GET",path="/v1/meta",status="200"} 5
# TYPE entropia_http_request_duration_seconds histogram
entropia_http_request_duration_seconds_sum{method="GET",path="/v1/meta"} 0.1
entropia_http_request_duration_seconds_count{method="GET",path="/v1/meta"} 5
# TYPE entropia_http_requests_in_flight gauge
entropia_http_requests_in_flight 0
# operational gauges unavailable (database unreachable)
`;

describe("parsePrometheus", () => {
  it("groups samples into typed families", () => {
    const parsed = parsePrometheus(HEALTHY);
    expect(Object.keys(parsed.families)).toHaveLength(6);
    expect(parsed.families["entropia_http_requests_total"].type).toBe("counter");
    expect(parsed.families["entropia_http_request_duration_seconds"].type).toBe("histogram");
    expect(parsed.families["entropia_outbox_lag_seconds"].type).toBe("gauge");
  });

  it("assigns histogram _bucket/_sum/_count samples to the base family", () => {
    const family = parsePrometheus(HEALTHY).families["entropia_http_request_duration_seconds"];
    expect(family.samples).toHaveLength(6);
    const bucket = family.samples.find((s) => s.name.endsWith("_bucket") && s.labels.le === "+Inf");
    expect(bucket?.value).toBe(12);
  });

  it("parses labels and no-label scalars", () => {
    const parsed = parsePrometheus(HEALTHY);
    const login = parsed.families["entropia_http_requests_total"].samples.find(
      (s) => s.labels.method === "POST",
    );
    expect(login?.labels).toEqual({ method: "POST", path: "/v1/auth/login", status: "200" });
    expect(parsed.families["entropia_http_requests_in_flight"].samples[0].labels).toEqual({});
    expect(parsed.families["entropia_http_requests_in_flight"].samples[0].value).toBe(2);
  });

  it("unescapes backslash and quote escapes in label values", () => {
    // Raw exposition bytes: value is  a\"b\\c  -> unescapes to  a"b\c .
    const parsed = parsePrometheus(String.raw`x_metric{k="a\"b\\c"} 1`);
    expect(parsed.families["x_metric"].samples[0].labels.k).toBe(String.raw`a"b\c`);
    expect(parsed.families["x_metric"].type).toBe("untyped");
  });

  it("captures freeform notes but not HELP/TYPE comments", () => {
    const parsed = parsePrometheus(DEGRADED);
    expect(parsed.notes).toContain("operational gauges unavailable (database unreachable)");
    expect(parsed.notes.some((n) => n.startsWith("TYPE"))).toBe(false);
  });

  it("ignores blank and malformed lines", () => {
    const parsed = parsePrometheus("\n   \ngarbage_without_value\n# TYPE g gauge\ng 7\n");
    expect(parsed.families["g"].samples[0].value).toBe(7);
    expect(parsed.families["garbage_without_value"]).toBeUndefined();
  });
});

describe("summarizeMetrics", () => {
  it("derives the golden signals from a healthy scrape", () => {
    const s = summarizeMetrics(parsePrometheus(HEALTHY));
    expect(s.golden.requestsTotal).toBe(18);
    expect(s.golden.statusClasses).toEqual({ "2xx": 15, "4xx": 2, "5xx": 1 });
    expect(s.golden.serverErrors).toBe(1);
    expect(s.golden.clientErrors).toBe(2);
    expect(s.golden.inFlight).toBe(2);
    // sum 0.30s over count 15 -> 0.02s -> 20ms.
    expect(s.golden.avgLatencyMs).toBeCloseTo(20, 6);
  });

  it("sorts jobs depth and totals it", () => {
    const s = summarizeMetrics(parsePrometheus(HEALTHY));
    expect(s.jobsDepth).toEqual([
      { queue: "data", status: "succeeded", count: 20 },
      { queue: "default", status: "queued", count: 4 },
      { queue: "default", status: "running", count: 1 },
    ]);
    expect(s.jobsDepthTotal).toBe(25);
    expect(s.outboxLagSeconds).toBe(0.512);
    expect(s.leaseAgeSeconds).toBe(3.14);
    expect(s.degraded).toBe(false);
  });

  it("flags the degraded scrape and nulls the operational gauges", () => {
    const s = parseMetricsSummary(DEGRADED);
    expect(s.degraded).toBe(true);
    expect(s.outboxLagSeconds).toBeNull();
    expect(s.leaseAgeSeconds).toBeNull();
    expect(s.jobsDepth).toHaveLength(0);
    expect(s.golden.requestsTotal).toBe(5);
    expect(s.golden.avgLatencyMs).toBeCloseTo(20, 6);
  });

  it("treats an empty scrape as degraded with null signals", () => {
    const s = parseMetricsSummary("");
    expect(s.degraded).toBe(true);
    expect(s.golden.requestsTotal).toBe(0);
    expect(s.golden.avgLatencyMs).toBeNull();
    expect(s.familyCount).toBe(0);
  });
});
