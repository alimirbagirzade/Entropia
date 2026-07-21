import type { ReactNode } from "react";

import { useMe } from "@/lib/hooks";

// R2-09 (GAP item 10): presentation-only Admin gating over the /me server-truth
// projection. Fail-closed — while /me is loading, errored or resolves to a
// non-admin principal, an Admin-only control is treated as NOT available; it
// renders only once the server has PROVEN is_admin. Visibility is never
// authorization: every dispatch is re-checked server-side, and a stale-cache
// Admin projection still receives the 403 envelope verbatim.
// eslint-disable-next-line react-refresh/only-export-components
export function useIsAdmin(): boolean {
  const me = useMe();
  return me.data?.is_admin === true;
}

// Read-only replacement for an Admin-only primary control (GAP item 10 fix #3):
// the unauthorized user keeps the surrounding read-only state and sees WHY the
// action is absent instead of a button that can only 403. `detail` extends the
// base sentence with surface-specific read-only context.
export function AdminApprovalNote({ detail }: { detail?: string }) {
  return (
    <p className="page-sub" role="note">
      Admin approval required — this action is available to Admin users only.
      {detail ? ` ${detail}` : ""}
    </p>
  );
}

// Convenience wrapper: children for a server-confirmed Admin, the read-only
// note for everyone else (including the fail-closed unknown state).
export function AdminGate({ detail, children }: { detail?: string; children: ReactNode }) {
  return useIsAdmin() ? <>{children}</> : <AdminApprovalNote detail={detail} />;
}
