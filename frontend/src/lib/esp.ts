// Embedded System Packages data access (doc 09 §3, §4.3, §10.1): the role-aware
// resolver-registry catalog (visibility applied SERVER-side — the client never
// hides rows), the resolver detail projection, and the Pre-Check-parity resolve
// probe. The probe POST is transport only: `resolve_embedded_dependency` is a
// pure read that creates nothing and writes no audit row, so it carries no
// Idempotency-Key and invalidates no query key.
//
// The registry has no dedicated SSE event: resolver lifecycle changes ride
// resource.changed (full refresh). Read keys live under ["esp"]. Registry
// mutations are bound here too: create (any authenticated actor proposes a
// CANDIDATE — no OCC / Idempotency-Key), and Admin-only activate / deprecate,
// which carry the registry_version as the X-Registry-Version OCC header (a plain
// int, NOT the If-Match "rv-N" ETag) + a fresh Idempotency-Key per attempt. A
// stale token -> 409 RESOLVER_REGISTRY_CONFLICT; a non-Admin -> 403
// APPROVAL_REQUIRES_ADMIN — both rendered verbatim. Mutations invalidate ["esp"]
// + ["audit"] (each command audits), mirroring lib/marketData.ts.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Taxonomy mirrors — hydration-only copies of domain/esp/enums.py. Selects are
// seeded from these; the SERVER re-validates every filter/runtime value and
// rejects a bad one with the 422 envelope verbatim — never authorization.
// ---------------------------------------------------------------------------

export const RESOLVER_TRUST_STATES = [
  "candidate",
  "trusted_active",
  "deprecated",
  "unavailable",
] as const;

export const RUNTIME_ADAPTERS = ["pine_v5", "python"] as const;

// ESP performance metrics are N/A by nature (doc 09 §14, L4): the server sends
// the availability label for every field — never a fabricated zero. The client
// renders whatever string arrives, in this stable order.
export const ESP_PERFORMANCE_FIELDS = ["net_profit", "backtest_ready", "oos_passed"] as const;

// ---------------------------------------------------------------------------
// Wire types (mirror application/queries/esp.py `_registry_dict` /
// `_contract_dict` / `get_esp_detail` / `resolve_embedded_dependency` verbatim)
// ---------------------------------------------------------------------------

export interface EspRegistryRow {
  registry_id: string;
  canonical_key: string;
  package_entity_id: string;
  trusted_active_revision_id: string | null;
  trust_state: string;
  runtime_adapter: string;
  registry_version: number;
  replacement_revision_id: string | null;
  // Present on list rows; the nested `registry` dict inside EspPackageDetail
  // omits it (null) — the detail view already carries the top-level field.
  visibility_scope: string | null;
  net_profit: string;
  backtest_ready: string;
  oos_passed: string;
}

export interface EspPage {
  data: EspRegistryRow[];
  meta: { cursor: string | null; has_more: boolean };
}

export interface EspContract {
  contract_id: string;
  canonical_key: string;
  signature: Record<string, unknown>;
  runtime_adapter: string;
  warm_up_period: number | null;
  timing_semantics: string | null;
  repaint: boolean;
  evidence: Record<string, unknown> | null;
}

export interface EspPackageDetail {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  package_kind: string;
  visibility_scope: string;
  validation_state: string;
  approval_state: string;
  content_hash: string;
  row_version: number;
  lifecycle_state: string;
  owner_principal_id: string | null;
  contract: EspContract | null;
  registry: EspRegistryRow | null;
  created_at: string | null;
  net_profit: string;
  backtest_ready: string;
  oos_passed: string;
}

// Success projection of POST /embedded-system-packages/resolve (doc 09 §4.3):
// the EXACT pinned revision — never name-only / latest (P4/L5).
export interface ResolveResult {
  resolved: boolean;
  canonical_key: string;
  entity_id: string;
  revision_id: string;
  content_hash: string;
  runtime_adapter: string;
  registry_version: number;
  signature: Record<string, unknown>;
  evidence: Record<string, unknown> | null;
}

// Parsed-call signature payload (domain/esp/resolver.py `signature_matches`):
// ordered param TYPES are identity, names are display-only.
export interface SignatureParam {
  name?: string;
  type: string;
}

export interface ResolveProbeInput {
  key: string;
  params: SignatureParam[];
  returnShape: string;
  target_runtime: string;
}

// Badge tone for the registry trust facet (presentation only).
export function trustTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (state === "trusted_active") return "ok";
  if (state === "deprecated") return "warn";
  if (state === "unavailable") return "down";
  return "neutral";
}

// One signature param per line: "name:type" or a bare "type". Blank lines are
// skipped; the ordered result feeds parsed_call.signature.params verbatim.
export function parseSignatureParams(text: string): SignatureParam[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      const colonAt = line.indexOf(":");
      if (colonAt === -1) return { type: line };
      return { name: line.slice(0, colonAt).trim(), type: line.slice(colonAt + 1).trim() };
    });
}

// ---------------------------------------------------------------------------
// Query hooks — all under the ["esp"] prefix (swept by resource.changed)
// ---------------------------------------------------------------------------

export function useEspRegistry(
  trustState: string | null,
  cursor: string | null,
  visibilityScope: string | null = null,
) {
  return useQuery({
    queryKey: ["esp", "list", trustState, visibilityScope, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      // An empty facet param is NEVER sent (server 422s unknown values).
      if (trustState) params.set("trust_state", trustState);
      if (visibilityScope) params.set("visibility_scope", visibilityScope);
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<EspPage>(`/embedded-system-packages${qs ? `?${qs}` : ""}`);
    },
    // Keep the current table mounted while a page flip is in flight.
    placeholderData: (previous) => previous,
  });
}

export function useEspPackage(entityId: string | null) {
  return useQuery({
    queryKey: ["esp", "detail", entityId],
    queryFn: () =>
      api.get<EspPackageDetail>(
        `/embedded-system-packages/${encodeURIComponent(entityId ?? "")}`,
      ),
    enabled: entityId !== null,
  });
}

// Pre-Check-parity resolve probe (doc 09 §9.1–§9.3, §10.3): a user-triggered
// read over the live registry. Failure surfaces the typed error verbatim
// (RESOLVER_NOT_RESOLVED 404 / RESOLVER_SIGNATURE_MISMATCH 422 /
// RESOLVER_ADAPTER_INCOMPATIBLE 409). Nothing is created — no invalidation.
export function useResolveProbe() {
  return useMutation({
    mutationFn: (input: ResolveProbeInput) =>
      api.post<ResolveResult>("/embedded-system-packages/resolve", {
        parsed_call: {
          key: input.key,
          signature: { params: input.params, return: input.returnShape },
        },
        target_runtime: input.target_runtime,
      }),
  });
}

// ---------------------------------------------------------------------------
// Registry mutation wire types (mirror application/commands/esp.py return dicts
// verbatim) + hooks. create is open to any authenticated actor; activate /
// deprecate are Admin-only server-side (ensure_can_activate/deprecate, CR-02).
// ---------------------------------------------------------------------------

// Visibility facet mirror (domain/lifecycle/enums.py VisibilityScope). Seeds the
// create select; the server re-validates and rejects a bad value with the 422
// envelope — never authorization.
export const VISIBILITY_SCOPES = [
  "private",
  "explicitly_shared",
  "published",
  "system",
] as const;

// create_esp_package return dict — a fresh CANDIDATE proposal (doc 09 §5); not
// trusted until an Admin activates it.
export interface CreateEspResult {
  entity_id: string;
  revision_id: string;
  canonical_key: string;
  trust_state: string;
  runtime_adapter: string;
}

// activate_resolver return dict (candidate -> trusted_active, doc 09 §8/§10.2).
export interface ActivateResolverResult {
  entity_id: string;
  revision_id: string;
  canonical_key: string;
  trust_state: string;
  registry_version: number;
}

// deprecate_resolver return dict (trusted_active -> deprecated, doc 09 §8).
export interface DeprecateResolverResult {
  canonical_key: string;
  entity_id: string;
  trust_state: string;
  replacement_revision_id: string | null;
  registry_version: number;
}

export interface CreateEspInput {
  canonical_key: string;
  signature: { params: SignatureParam[]; return: string };
  runtime_adapter: string;
  visibility_scope: string;
  warm_up_period: number | null;
  timing_semantics: string | null;
  repaint: boolean;
  change_note: string | null;
}

export interface ActivateResolverInput {
  entityId: string;
  registryVersion: number;
  revision_id: string;
  canonical_key: string;
  note?: string | null;
}

export interface DeprecateResolverInput {
  entityId: string;
  registryVersion: number;
  canonical_key: string;
  reason: string;
  replacement_revision_id?: string | null;
}

// UI-hint gating only (domain/esp/state_machine.py): activation is legal from
// `candidate`, deprecation from `trusted_active`. The server re-validates BOTH
// the transition and the Admin gate — an illegal/non-Admin move surfaces verbatim.
export function canActivate(trustState: string): boolean {
  return trustState === "candidate";
}

export function canDeprecate(trustState: string): boolean {
  return trustState === "trusted_active";
}

// Registry OCC travels in the X-Registry-Version header (a plain int, parsed
// server-side as int(strip('"')) — NOT the If-Match "rv-N" ETag) + a fresh
// Idempotency-Key per attempt (a retry after a rejection is a new decision, not a
// replay). A stale token -> 409 RESOLVER_REGISTRY_CONFLICT verbatim.
function postWithRegistryVersion<T>(
  path: string,
  registryVersion: number,
  body: unknown,
): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body,
    headers: {
      "X-Registry-Version": String(registryVersion),
      "Idempotency-Key": crypto.randomUUID(),
    },
  });
}

// Propose a new resolver: any authenticated actor may create a CANDIDATE (doc 09
// §5). No OCC / Idempotency-Key — a create has no head to race. Invalidates
// ["esp"] (the new candidate joins the registry) + ["audit"].
export function useCreateEsp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateEspInput) =>
      api.post<CreateEspResult>("/embedded-system-packages", input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["esp"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Admin-only: activate a CANDIDATE resolver -> TRUSTED_ACTIVE. OCC on the
// registry_version + fresh Idempotency-Key. A non-Admin -> 403 verbatim.
export function useActivateResolver() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, registryVersion, ...body }: ActivateResolverInput) =>
      postWithRegistryVersion<ActivateResolverResult>(
        `/embedded-system-packages/${encodeURIComponent(entityId)}/activate`,
        registryVersion,
        body,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["esp"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Admin-only: deprecate a TRUSTED_ACTIVE resolver -> DEPRECATED. A reason is
// required (doc 09 §6). Historical pins keep reading their exact revision; only
// new-work selection closes. OCC + fresh Idempotency-Key; a non-Admin -> 403.
export function useDeprecateResolver() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, registryVersion, ...body }: DeprecateResolverInput) =>
      postWithRegistryVersion<DeprecateResolverResult>(
        `/embedded-system-packages/${encodeURIComponent(entityId)}/deprecate`,
        registryVersion,
        body,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["esp"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
