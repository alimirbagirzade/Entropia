import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { type FutureDevSubpage } from "@/app/nav";
import { formatUtc } from "@/lib/backtest";
import { STATE_TONES, useCapabilities } from "@/lib/capability";

// v18 mockup About-dialog copy for the Future Dev sections — rendered verbatim
// as the documented introduction of every placeholder sub-page.
const PLACEHOLDER_INTRO =
  "Future development sections are displayed as visual placeholders. They are included to " +
  "show where later operational modules may live, but they are intentionally inactive in " +
  "this prototype stage.";

// Future Dev capability placeholder sub-page (spec §UI-22): a VALID route for
// each Future Dev submenu target (Backtest Review, Signal Intelligence and the
// Research entries) so no menu click resolves to Page Not Found. The page is a
// pure documented placeholder over the server-truth Capability Registry row —
// it renders NO input, table, lifecycle control or operational form (§UI-22).
// The registry's gated operational commands live on the /future-dev registry
// page behind their own server-truth capability/permission gates.
export function FutureDevCapability({ subpage }: { subpage: FutureDevSubpage }) {
  const capabilities = useCapabilities();
  const row = capabilities.data?.capabilities.find(
    (capability) => capability.capability_key === subpage.capabilityKey,
  );
  return (
    <>
      <h1 className="page-title">Future Dev / {subpage.label}</h1>
      <p className="page-sub">{subpage.area} — controlled Future Dev placeholder (doc 22)</p>
      <section className="card" aria-labelledby="future-capability-h">
        <h3 id="future-capability-h" style={{ marginTop: 0 }}>
          {subpage.label}
        </h3>
        {capabilities.isLoading ? (
          <Loading label="Loading capability registry…" />
        ) : capabilities.isError ? (
          <ErrorState error={capabilities.error} onRetry={() => void capabilities.refetch()} />
        ) : capabilities.data ? (
          row ? (
            <>
              <p>
                <StatusBadge
                  label={row.lifecycle_state}
                  tone={STATE_TONES[row.lifecycle_state] ?? "neutral"}
                />{" "}
                {row.status_message}
              </p>
              <p>{PLACEHOLDER_INTRO}</p>
              <dl className="kv">
                <dt>Capability</dt>
                <dd>
                  {row.title} (<code>{row.capability_key}</code>)
                </dd>
                <dt>Menu path</dt>
                <dd>{row.menu_path}</dd>
                <dt>Registry version</dt>
                <dd>{row.registry_version}</dd>
                <dt>Enabled</dt>
                <dd>{formatUtc(row.enabled_at)}</dd>
              </dl>
              {row.is_operational ? (
                <p style={{ marginBottom: 0 }}>
                  This capability is operational — its gated commands are available on the{" "}
                  <Link to="/future-dev">Future Dev registry</Link> page.
                </p>
              ) : (
                <p style={{ marginBottom: 0 }}>
                  Operational commands stay hidden until this capability reaches a Limited or
                  Active state — lifecycle progress is tracked on the{" "}
                  <Link to="/future-dev">Future Dev registry</Link> page.
                </p>
              )}
            </>
          ) : (
            <EmptyState
              title="Not registered"
              description={`No capability with key "${subpage.capabilityKey}" exists in the server registry.`}
            />
          )
        ) : null}
      </section>
    </>
  );
}
