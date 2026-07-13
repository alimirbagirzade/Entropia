// Explicit package sharing (GAP-17; Master Reference §6, §6.4). The owner (or an
// Admin) grants a specific user explicit view/use access to a private package;
// the backend flips PRIVATE <-> EXPLICITLY_SHARED as the first/last grant is
// added/removed. Grant + revoke carry the package root row_version as the
// If-Match "rv-N" OCC token (the /library/{id} detail returns it) + a fresh
// Idempotency-Key — mirroring the sibling Move-to-Trash mutation. Listing the
// grantees is owner/Admin-only. "Shared with me" is the grantee's inbox. All
// read keys live under ["library"] (swept by resource.changed); mutations also
// sweep ["audit"].

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";
import type { LibraryPage } from "./library";

// ---------------------------------------------------------------------------
// Wire types (mirror application/queries/sharing.py + commands/sharing.py)
// ---------------------------------------------------------------------------

export interface PackageShare {
  share_id: string;
  grantee_principal_id: string;
  grantee_email: string | null;
  grantee_display_name: string | null;
  granted_by_principal_id: string | null;
  created_at: string | null;
}

export interface PackageSharesResult {
  entity_id: string;
  visibility_scope: string;
  row_version: number;
  shares: PackageShare[];
}

export interface ShareResult {
  entity_id: string;
  share_id: string;
  grantee_principal_id: string;
  grantee_email: string | null;
  grantee_display_name: string | null;
  visibility_scope: string;
  active_share_count: number;
  row_version: number;
}

export interface RevokeShareResult {
  entity_id: string;
  share_id: string;
  revoked: boolean;
  visibility_scope: string;
  active_share_count: number;
  row_version: number;
}

// ---------------------------------------------------------------------------
// Read hooks (["library"] prefix)
// ---------------------------------------------------------------------------

// The active grantees of a package. Owner/Admin-only server-side (a grantee
// gets 403 SHARE_MANAGEMENT_FORBIDDEN, rendered verbatim); the client enables
// the query only where the server marks `can_share`, but that is never the
// authority — the server re-validates.
export function usePackageShares(entityId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["library", "shares", entityId],
    queryFn: () =>
      api.get<PackageSharesResult>(
        `/library/${encodeURIComponent(entityId ?? "")}/shares`,
      ),
    enabled: entityId !== null && enabled,
  });
}

// The caller's inbox of packages explicitly shared WITH them (GAP-17).
export function useSharedPackages() {
  return useQuery({
    queryKey: ["library", "shared-with-me"],
    queryFn: () => api.get<LibraryPage>("/library-shared-with-me"),
  });
}

// ---------------------------------------------------------------------------
// Mutations — OCC via If-Match "rv-N" + a fresh Idempotency-Key per attempt.
// The client never pre-gates on permissions; the server renders 403/409/422
// verbatim.
// ---------------------------------------------------------------------------

function invalidateSharing(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["library"] });
  void queryClient.invalidateQueries({ queryKey: ["audit"] });
}

export function useSharePackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entityId: string; rowVersion: number; granteeEmail: string }) =>
      apiRequest<ShareResult>(`/library/${encodeURIComponent(input.entityId)}/shares`, {
        method: "POST",
        headers: {
          "If-Match": `"rv-${input.rowVersion}"`,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: { grantee_email: input.granteeEmail },
      }),
    onSuccess: () => invalidateSharing(queryClient),
  });
}

export function useRevokeShare() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entityId: string; shareId: string; rowVersion: number }) =>
      apiRequest<RevokeShareResult>(
        `/library/${encodeURIComponent(input.entityId)}/shares/${encodeURIComponent(input.shareId)}`,
        {
          method: "DELETE",
          headers: {
            "If-Match": `"rv-${input.rowVersion}"`,
            "Idempotency-Key": crypto.randomUUID(),
          },
        },
      ),
    onSuccess: () => invalidateSharing(queryClient),
  });
}
