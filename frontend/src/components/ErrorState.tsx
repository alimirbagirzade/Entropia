import { Link } from "react-router-dom";

import { ApiError } from "@/lib/apiClient";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  // R2-10 (GAP madde 14): a 401 is not a generic failure — in AUTH_MODE=session
  // an anonymous visitor hitting a protected read must land on a real
  // UNAUTHENTICATED state with a Login action, never a spinner or a raw error.
  if (error instanceof ApiError && error.status === 401) {
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
