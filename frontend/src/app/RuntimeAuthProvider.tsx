import type { ReactNode } from "react";

import { ApiError } from "@/lib/apiClient";
import { useAuthMode } from "@/lib/authMode";
import { useMeta } from "@/lib/hooks";

// The runtime-auth boot gate (AUTH-02). The backend's AUTH_MODE decides which
// credential the API trusts and which auth UI is legal; the browser cannot infer
// it from a stored token, a build flag or the hostname. So NOTHING mode-dependent
// renders — not /login, not the shell, not DevActorControl, not a single protected
// query — until an explicitly anonymous GET /meta has resolved dev|session.
//
// The three states are the audit's mandated model:
//   loading : /meta in flight. A neutral placeholder — never a guessed auth control.
//   error   : /meta failed. FAIL CLOSED with a visible Retry; we do NOT guess a mode
//             (guessing is what let a dev-mode server flash a login form it ignores).
//   ready   : the store carries dev|session. Children (router + shell + pages) mount
//             here, and only here may a protected query pick its one credential.
//
// Mode readiness is read from the auth-mode store (set inside useMeta's queryFn the
// instant /meta lands), NOT from react-query's success flag — the store IS the
// contract every transport and the shell already read, so gating on it keeps one
// source of truth. Once ready, a later /meta refetch failure never blanks the app:
// the store keeps its resolved mode, so this gate only fails closed on FIRST boot.
export function RuntimeAuthProvider({ children }: { children: ReactNode }) {
  const meta = useMeta();
  const mode = useAuthMode();

  if (mode !== null) {
    return <>{children}</>;
  }

  if (meta.isError) {
    const err = meta.error;
    const detail =
      err instanceof ApiError ? `${err.code}: ${err.message}` : err instanceof Error ? err.message : null;
    return (
      <div className="auth-viewport">
        <div className="card auth-card" role="alert">
          <div className="brand" style={{ marginBottom: 18 }}>
            <span className="logo" aria-hidden="true" />
            <span>ENTROPIA</span>
          </div>
          <h2 style={{ marginTop: 0, fontSize: 16 }}>Cannot reach the server</h2>
          <p style={{ color: "var(--text-dim)" }}>
            Entropia could not load its runtime configuration, so it cannot choose how to sign you in.
            This is a fail-closed state — no authentication is attempted until configuration loads.
          </p>
          {detail ? (
            <p className="auth-error" style={{ marginBottom: 14 }}>
              {detail}
            </p>
          ) : null}
          <button
            type="button"
            className="btn btn-primary auth-submit"
            onClick={() => void meta.refetch()}
            disabled={meta.isFetching}
          >
            {meta.isFetching ? "Retrying…" : "Retry"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-viewport">
      <div className="card auth-card" aria-busy="true">
        <div className="brand" style={{ marginBottom: 18 }}>
          <span className="logo" aria-hidden="true" />
          <span>ENTROPIA</span>
        </div>
        <p style={{ color: "var(--text-dim)" }}>Starting…</p>
      </div>
    </div>
  );
}
