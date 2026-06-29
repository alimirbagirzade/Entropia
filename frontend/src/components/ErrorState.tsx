import { ApiError } from "@/lib/apiClient";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
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
