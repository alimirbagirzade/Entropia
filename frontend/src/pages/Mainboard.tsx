import { useMeta, useReadiness } from "@/lib/hooks";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";

// Stage 0 Mainboard: proves the frontend↔backend contract is live (meta + health).
// The real Mainboard (working objects, allocation rows, run status) lands in Stage 3.
export function Mainboard() {
  const meta = useMeta();
  const ready = useReadiness();

  return (
    <>
      <h1 className="page-title">Mainboard</h1>
      <p className="page-sub">System overview · live backend connectivity</p>

      <div style={{ display: "grid", gap: 18, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
        <section className="card" aria-labelledby="meta-h">
          <h3 id="meta-h" style={{ marginTop: 0 }}>Runtime</h3>
          {meta.isLoading ? (
            <Loading />
          ) : meta.isError ? (
            <ErrorState error={meta.error} onRetry={() => meta.refetch()} />
          ) : (
            <dl className="kv">
              <dt>Product</dt><dd>{meta.data?.name}</dd>
              <dt>Version</dt><dd>{meta.data?.version}</dd>
              <dt>Environment</dt><dd>{meta.data?.environment}</dd>
              <dt>API base</dt><dd>{meta.data?.api_base_path}</dd>
            </dl>
          )}
        </section>

        <section className="card" aria-labelledby="health-h">
          <h3 id="health-h" style={{ marginTop: 0 }}>Dependencies</h3>
          {ready.isLoading ? (
            <Loading />
          ) : ready.isError ? (
            <ErrorState error={ready.error} onRetry={() => ready.refetch()} />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {Object.entries(ready.data?.checks ?? {}).map(([name, status]) => (
                <StatusBadge
                  key={name}
                  label={`${name}: ${status}`}
                  tone={status === "ok" ? "ok" : "down"}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
