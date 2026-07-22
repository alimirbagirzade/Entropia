import { Link } from "react-router-dom";

import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { useMe } from "@/lib/hooks";
import { useBootstrapStatus, type BootstrapStatus } from "@/lib/provisioning";

// Admin Provisioning (post-V1 TIER 2): the onboarding surface for the very
// first Admin. The mechanism is server-side and signup-time only — set
// ENTROPIA_BOOTSTRAP_ADMIN_EMAIL, then sign up with that email while no active
// Admin exists (PR #76). This page never provisions anything itself: it reads
// the anonymous booleans-only GET /auth/bootstrap-status to show whether the
// bootstrap window is open, echoes the caller's identity from GET /me, and
// documents the flow. Ongoing role management stays in the Panel — this page
// links there for Admins rather than duplicating role assignment.
export function Provisioning() {
  const status = useBootstrapStatus();
  const me = useMe();

  return (
    <>
      <h1 className="page-title">Admin Provisioning</h1>
      <p className="page-sub">
        First-Admin bootstrap onboarding · server-side opt-in, applied at sign-up time
      </p>

      <section className="card" aria-labelledby="window-h">
        <h3 id="window-h" style={{ marginTop: 0 }}>
          Bootstrap window
        </h3>
        {status.isLoading ? (
          <Loading label="Reading bootstrap status…" />
        ) : status.isError ? (
          <ErrorState error={status.error} onRetry={() => void status.refetch()} />
        ) : status.data ? (
          <BootstrapWindow status={status.data} />
        ) : null}
      </section>

      <section className="card" aria-labelledby="identity-h">
        <h3 id="identity-h" style={{ marginTop: 0 }}>
          Your identity
        </h3>
        {me.isLoading ? (
          <Loading label="Resolving your identity…" />
        ) : me.isError ? (
          <ErrorState error={me.error} onRetry={() => void me.refetch()} />
        ) : me.data ? (
          <>
            <dl className="kv">
              <dt>Authenticated</dt>
              <dd>{me.data.is_authenticated ? "yes" : "no (anonymous)"}</dd>
              <dt>Role</dt>
              <dd>
                <span className="badge">{me.data.role ?? "—"}</span>
              </dd>
              <dt>Admin</dt>
              <dd>{me.data.is_admin ? "yes" : "no"}</dd>
              <dt>Principal</dt>
              <dd>
                <code>{me.data.principal_id ?? "—"}</code> · {me.data.principal_type}
              </dd>
            </dl>
            {me.data.is_admin ? (
              <p aria-live="polite">
                You are an Admin — manage roles and promotions in the{" "}
                <Link to="/panel">Panel</Link>.
              </p>
            ) : null}
          </>
        ) : null}
      </section>

      <BootstrapExplainer />
    </>
  );
}

interface WindowGuidance {
  tone: "ok" | "warn" | "neutral";
  headline: string;
  detail: string;
}

// The operative signal is login_capable_admin_exists, NOT active_admin_exists
// (PROV-05): a legacy credentialless Admin ROLE ROW exists but nobody can log in
// as it, so the window must still read OPEN. Only a credentialed Admin closes it.
function windowGuidance(status: BootstrapStatus): WindowGuidance {
  if (status.login_capable_admin_exists) {
    return {
      tone: "ok",
      headline: "Closed — a login-capable Admin already exists",
      detail:
        "Provisioning is complete. First-Admin bootstrap no longer applies; " +
        "manage roles and promotions from the Panel.",
    };
  }
  if (status.active_admin_exists) {
    // Legacy credentialless Admin present but not login-capable: the window is
    // OPEN because credential-aware bootstrap (PROV-02) ignores that row.
    return {
      tone: "warn",
      headline: "Open — a legacy Admin exists but cannot log in",
      detail:
        "An Admin role row exists but has no login credential, so nobody can " +
        "operate this install yet. " +
        (status.bootstrap_configured
          ? "Sign up with the configured bootstrap email to provision the first " +
            "real Admin over it — the legacy row is left untouched."
          : "Set ENTROPIA_BOOTSTRAP_ADMIN_EMAIL on the API, restart it, then sign " +
            "up with that email to provision the first real Admin."),
    };
  }
  if (status.bootstrap_configured) {
    return {
      tone: "warn",
      headline: "Open — configured, awaiting first sign-up",
      detail:
        "Sign up with the configured bootstrap email to be provisioned as the " +
        "first Admin. Any other signup receives the baseline role.",
    };
  }
  return {
    tone: "neutral",
    headline: "Open — bootstrap email not configured",
    detail:
      "No Admin exists yet and the mechanism is off. Set " +
      "ENTROPIA_BOOTSTRAP_ADMIN_EMAIL on the API, restart it, then sign up " +
      "with that email.",
  };
}

function BootstrapWindow({ status }: { status: BootstrapStatus }) {
  const guidance = windowGuidance(status);
  return (
    <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        <StatusBadge
          label={status.login_capable_admin_exists ? "window closed" : "window open"}
          tone={status.login_capable_admin_exists ? "ok" : "warn"}
        />
        {status.active_admin_exists && !status.login_capable_admin_exists ? (
          <StatusBadge label="legacy admin (no login)" tone="warn" />
        ) : null}
        <StatusBadge
          label={status.bootstrap_configured ? "email configured" : "email not configured"}
          tone={status.bootstrap_configured ? "ok" : "neutral"}
        />
      </div>
      <p style={{ fontWeight: 600, margin: "0 0 4px" }}>{guidance.headline}</p>
      <p style={{ margin: 0, color: "var(--text-dim)" }}>{guidance.detail}</p>
    </>
  );
}

// Read-only documentation of the server mechanism (PR #76) — mirrors the
// backend command docstring so the page never over-promises a runtime action
// the API does not expose.
function BootstrapExplainer() {
  return (
    <section className="card" aria-labelledby="how-h">
      <h3 id="how-h" style={{ marginTop: 0 }}>
        How first-Admin bootstrap works
      </h3>
      <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
        <li>
          An operator sets <code>ENTROPIA_BOOTSTRAP_ADMIN_EMAIL</code> on the API (empty
          disables the mechanism — zero behavior change).
        </li>
        <li>Restart the API so the setting is read.</li>
        <li>
          Sign up with that email <strong>while no active Admin exists</strong> — the account is
          provisioned as Admin (audited <code>user.admin_bootstrapped</code>).
        </li>
        <li>
          Fail-closed: if an Admin already exists, a matching signup receives the baseline role.
        </li>
        <li>
          Applies at sign-up time only — there is no retro-promotion of an existing account. Later
          promotions are role assignments in the Panel.
        </li>
      </ol>
    </section>
  );
}
