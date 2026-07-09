// Embedded System Packages data access (doc 09 §3, §4.3, §10.1): the role-aware
// resolver-registry catalog (visibility applied SERVER-side — the client never
// hides rows), the resolver detail projection, and the Pre-Check-parity resolve
// probe. The probe POST is transport only: `resolve_embedded_dependency` is a
// pure read that creates nothing and writes no audit row, so it carries no
// Idempotency-Key and invalidates no query key.
//
// The registry has no dedicated SSE event: resolver lifecycle changes ride
// resource.changed (full refresh). Read keys live under ["esp"]. Registry
// mutations (create / activate / deprecate — Admin-only, X-Registry-Version
// OCC header) stay OUT of this slice; the detail row_version / registry_version
// tokens are ready for those later slices.

import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "./apiClient";

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

export function useEspRegistry(trustState: string | null, cursor: string | null) {
  return useQuery({
    queryKey: ["esp", "list", trustState, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      // An empty facet param is NEVER sent (server 422s unknown values).
      if (trustState) params.set("trust_state", trustState);
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
