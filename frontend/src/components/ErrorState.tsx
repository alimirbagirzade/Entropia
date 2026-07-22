import { Link } from "react-router-dom";

import { ApiError, SESSION_INVALID } from "@/lib/apiClient";
import { getAuthMode } from "@/lib/authMode";

// A denied ACTION is not a lost session. These codes (and any 403) mean "this
// identity may not do this"; the session is valid and must survive, so this
// surface never routes to /login (re-authenticating cannot grant a permission
// you lack) and — like the whole component — never clears anything.
const ACCESS_DENIED_CODES = new Set(["ACCESS_DENIED", "FORBIDDEN"]);

// AUTH-09: classify by the backend's canonical error CODE, not the bare HTTP
// status. Not every 401 means "destroy the browser session and go to login" —
// missing auth, an invalid session, denied credentials, and a forbidden action
// are four different outcomes that a status-only branch collapsed into one.
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (error instanceof ApiError) {
    // The server pulled the session out from under us (expired / revoked /
    // unknown token). The apiClient already cleared it exactly once and the shell
    // owns the single redirect — this surface only reassures. It deliberately
    // offers no Retry: retrying would re-fire with a token that is already gone.
    if (error.code === SESSION_INVALID) {
      return (
        <div className="state" role="alert">
          <div className="glyph" aria-hidden="true">🔒</div>
          <h3>Session ended</h3>
          <p>Your session is no longer valid. Returning you to sign in…</p>
          <Link to="/login" className="page-button">
            Login
          </Link>
        </div>
      );
    }

    // Authentication was never established. In session mode the fix is to sign in;
    // in dev mode there is no session to establish — the API resolves identity
    // from the “act as” field (X-Actor-Id) and ignores session tokens, so a Login
    // link would point at a page the backend disregards. The runtime mode is the
    // source of truth here, exactly as it is for the shell's auth controls.
    if (error.code === "UNAUTHENTICATED") {
      if (getAuthMode() === "dev") {
        return (
          <div className="state" role="alert">
            <div className="glyph" aria-hidden="true">🔒</div>
            <h3>UNAUTHENTICATED</h3>
            <p>Select a dev actor in the “act as” field to identify yourself.</p>
          </div>
        );
      }
      return (
        <div className="state" role="alert">
          <div className="glyph" aria-hidden="true">🔒</div>
          <h3>UNAUTHENTICATED</h3>
          <p>Sign in to access this page.</p>
          <Link to="/login" className="page-button">
            Login
          </Link>
        </div>
      );
    }

    // A forbidden action keeps the user exactly where they are: no Login route
    // (it cannot help) and no session teardown. Retry stays available for the
    // cases where the caller can legitimately retry a different way.
    if (error.status === 403 || ACCESS_DENIED_CODES.has(error.code)) {
      return (
        <div className="state" role="alert">
          <div className="glyph" aria-hidden="true">⛔</div>
          <h3>Access denied</h3>
          <p>{error.message}</p>
          {onRetry ? (
            <button type="button" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      );
    }
  }

  // Everything else — INVALID_CREDENTIALS (which stays local to its own form and
  // must never destroy another valid session), other canonical codes, and any
  // non-ApiError — renders the verbatim envelope with a retry affordance. This
  // surface is display-only; it classifies but never mutates session state.
  const message =
    error instanceof ApiError
      ? `${error.code}: ${error.message}`
      : error instanceof Error
        ? error.message
        : "Something went wrong.";
  return (
    <div className="state" role="alert">
      <div className="glyph" aria-hidden="true">⚠</div>
      <h3>Unable to load</h3>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
