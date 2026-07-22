import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ErrorState } from "@/components/ErrorState";
import { ApiError, SESSION_INVALID } from "@/lib/apiClient";
import { resetAuthMode, setAuthMode } from "@/lib/authMode";

// AUTH-09 / audit §5 — ErrorState classifies by the backend's canonical error
// CODE, not the bare HTTP status. The old status-only branch treated EVERY 401 as
// "destroy the session and go to login". These pin the four distinct outcomes —
// invalid session, missing auth (mode-aware), a forbidden action, and a
// credential failure — and prove a denied action never routes to login.

function renderError(error: unknown) {
  return render(
    <MemoryRouter>
      <ErrorState error={error} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  resetAuthMode();
});

afterEach(() => {
  cleanup();
  resetAuthMode();
});

describe("ErrorState canonical-code classification (AUTH-09)", () => {
  it("SESSION_INVALID shows the ended-session state and offers no competing Retry", () => {
    // The apiClient already cleared the token and the shell owns the single
    // redirect; this surface only reassures and must not re-fire the read.
    renderError(new ApiError(401, SESSION_INVALID, "Session is not valid."));

    expect(screen.getByText("Session ended")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("UNAUTHENTICATED in session mode offers a Login action", () => {
    setAuthMode("session");
    renderError(new ApiError(401, "UNAUTHENTICATED", "Authentication is required."));

    expect(screen.getByText("UNAUTHENTICATED")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Login" })).toHaveAttribute("href", "/login");
  });

  it("UNAUTHENTICATED in dev mode points at the dev actor, never a Login link", () => {
    // Dev mode resolves identity from X-Actor-Id; a Login link would point at a
    // page the backend ignores, so the message names the real control instead.
    setAuthMode("dev");
    renderError(new ApiError(401, "UNAUTHENTICATED", "Authentication is required."));

    expect(screen.getByText(/Select a dev actor/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();
  });

  it("a 403 ACCESS_DENIED renders access-denied and never routes to login", () => {
    // A forbidden action is not a lost session — re-authenticating cannot grant a
    // permission you lack, so there is deliberately no Login link here.
    setAuthMode("session");
    renderError(new ApiError(403, "ACCESS_DENIED", "Admin only."));

    expect(screen.getByText("Access denied")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();
  });

  it("a FORBIDDEN code is treated as access-denied even without a 403 status", () => {
    renderError(new ApiError(401, "FORBIDDEN", "Admin only."));

    expect(screen.getByText("Access denied")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();
  });

  it("INVALID_CREDENTIALS stays a local, verbatim error with no global Login action", () => {
    // Even with a valid session elsewhere, a login/reauth credential failure is
    // form-local: ErrorState never routes to login and (being display-only) never
    // clears the session.
    setAuthMode("session");
    renderError(new ApiError(401, "INVALID_CREDENTIALS", "Invalid username or password."));

    expect(screen.getByText("INVALID_CREDENTIALS: Invalid username or password.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();
  });
});
