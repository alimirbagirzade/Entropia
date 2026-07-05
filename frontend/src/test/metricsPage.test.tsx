import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { Metrics } from "@/pages/Metrics";

const HEALTHY = `# TYPE entropia_http_requests_total counter
entropia_http_requests_total{method="GET",path="/v1/meta",status="200"} 15
entropia_http_requests_total{method="GET",path="/v1/library",status="404"} 2
entropia_http_requests_total{method="GET",path="/v1/metrics",status="500"} 1
# TYPE entropia_http_request_duration_seconds histogram
entropia_http_request_duration_seconds_sum{method="GET",path="/v1/meta"} 0.36
entropia_http_request_duration_seconds_count{method="GET",path="/v1/meta"} 18
# TYPE entropia_http_requests_in_flight gauge
entropia_http_requests_in_flight 2
# TYPE entropia_jobs_depth gauge
entropia_jobs_depth{queue="data",status="succeeded"} 20
# TYPE entropia_outbox_lag_seconds gauge
entropia_outbox_lag_seconds 0.512
# TYPE entropia_job_lease_age_seconds gauge
entropia_job_lease_age_seconds 3.14
`;

const DEGRADED = `# TYPE entropia_http_requests_total counter
entropia_http_requests_total{method="GET",path="/v1/meta",status="200"} 5
# TYPE entropia_http_requests_in_flight gauge
entropia_http_requests_in_flight 0
# operational gauges unavailable (database unreachable)
`;

function stubFetch(body: string, ok = true, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok,
      status,
      statusText: ok ? "OK" : "ERROR",
      text: async () => body,
    })),
  );
}

function renderMetrics() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Metrics />
    </QueryClientProvider>,
  );
}

describe("Metrics dashboard", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders golden signals and gauges from a healthy scrape", async () => {
    stubFetch(HEALTHY);
    renderMetrics();

    // Waits for the query to resolve and the panels to mount.
    expect(await screen.findByText("18")).toBeInTheDocument(); // traffic (requests)
    expect(screen.getByText("Golden signals")).toBeInTheDocument();
    expect(screen.getByText("Traffic (requests)")).toBeInTheDocument();
    expect(screen.getByText("20.0 ms")).toBeInTheDocument(); // 0.36s / 18 -> 20ms avg
    expect(screen.getByText("5xx: 1")).toBeInTheDocument();
    expect(screen.getByText("0.51 s")).toBeInTheDocument(); // outbox lag
    expect(screen.getByText("3.14 s")).toBeInTheDocument(); // lease age
    // Jobs depth table.
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("data")).toBeInTheDocument();
  });

  it("shows the degraded banner when the operational gauges are unavailable", async () => {
    stubFetch(DEGRADED);
    renderMetrics();

    expect(await screen.findByText(/operational gauges degraded/i)).toBeInTheDocument();
    expect(screen.getByText(/database unreachable/i)).toBeInTheDocument();
    // Outbox lag + lease age both render the em-dash placeholder.
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("surfaces a fetch failure through the error state", async () => {
    stubFetch("boom", false, 503);
    renderMetrics();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
  });
});
