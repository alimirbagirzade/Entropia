// Canonical Instrument Registry data access (GAP-16; Master Reference §8.1, §9.1).
// The registry is shared reference data: any authenticated actor may list/read it
// and register a new canonical instrument. A free-text UI scope ("BTCUSDT
// Perpetual", or a venue/symbol/contract triple) is resolved SERVER-side to a
// canonical instrument_id — an unresolvable scope fails closed
// (INSTRUMENT_SCOPE_UNRESOLVABLE), never a silent free-text assumption.
//
// The registry has no dedicated SSE event: instrument changes ride
// resource.changed (full refresh). Read keys live under ["instruments"].
// Deprecation is Admin-only and carries the registry_version as the
// X-Registry-Version OCC header (a plain int, NOT the If-Match "rv-N" ETag) + a
// fresh Idempotency-Key. A stale token -> 409 INSTRUMENT_REGISTRY_CONFLICT; a
// non-Admin -> 403 INSTRUMENT_DEPRECATE_REQUIRES_ADMIN — both rendered verbatim.
// Mutations invalidate ["instruments"] + ["audit"], mirroring lib/esp.ts.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// Taxonomy mirrors of domain/instrument/enums.py — hydration only. The server
// re-validates every value and rejects a bad one with the 422 envelope verbatim.
export const CONTRACT_TYPES = [
  "spot",
  "perpetual",
  "future",
  "option",
  "index",
  "other",
] as const;

export const INSTRUMENT_STATES = ["active", "deprecated"] as const;

// Wire types mirror application/queries/instrument.py `_instrument_dict` /
// `_alias_dict` / `get_instrument_detail` / `resolve_scope` verbatim.
export interface InstrumentRow {
  instrument_id: string;
  resolution_key: string;
  venue_id: string;
  symbol: string;
  contract_type: string;
  display_name: string;
  base_asset: string | null;
  quote_asset: string | null;
  settlement_asset: string | null;
  multiplier: string | null;
  market_class: string | null;
  state: string;
  registry_version: number;
  deprecation_reason: string | null;
}

export interface InstrumentPage {
  data: InstrumentRow[];
  meta: { cursor: string | null; has_more: boolean };
}

export interface InstrumentAlias {
  alias_id: string;
  alias_norm: string;
  alias_text: string;
}

export interface InstrumentDetail extends InstrumentRow {
  row_version: number;
  aliases: InstrumentAlias[];
}

// Success projection of POST /instruments/resolve (Master §8.1): the exact
// canonical instrument the free-text scope resolves to.
export interface ResolveResult extends InstrumentRow {
  resolved: boolean;
}

// Badge tone for the registry state facet (presentation only).
export function stateTone(state: string): "ok" | "warn" | "neutral" {
  if (state === "active") return "ok";
  if (state === "deprecated") return "warn";
  return "neutral";
}

// UI-hint gating only: deprecation is legal from `active`. The server
// re-validates both the transition and the Admin gate.
export function canDeprecate(state: string): boolean {
  return state === "active";
}

// One alias per line; blanks skipped. Feeds the register/alias payloads verbatim.
export function parseAliases(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

// ---------------------------------------------------------------------------
// Query hooks — all under the ["instruments"] prefix (swept by resource.changed)
// ---------------------------------------------------------------------------

export function useInstruments(state: string | null, cursor: string | null) {
  return useQuery({
    queryKey: ["instruments", "list", state, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      // An empty facet param is NEVER sent (server 422s an unknown value).
      if (state) params.set("state", state);
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<InstrumentPage>(`/instruments${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

export function useInstrument(instrumentId: string | null) {
  return useQuery({
    queryKey: ["instruments", "detail", instrumentId],
    queryFn: () =>
      api.get<InstrumentDetail>(`/instruments/${encodeURIComponent(instrumentId ?? "")}`),
    enabled: instrumentId !== null,
  });
}

export interface ResolveScopeInput {
  venue_id?: string | null;
  symbol?: string | null;
  contract_type?: string | null;
  alias?: string | null;
}

// A pure read over the registry. Failure surfaces the typed error verbatim
// (INSTRUMENT_SCOPE_UNRESOLVABLE 422 / INSTRUMENT_SCOPE_INVALID 422). Nothing is
// created — no invalidation.
export function useResolveScope() {
  return useMutation({
    mutationFn: (input: ResolveScopeInput) =>
      api.post<ResolveResult>("/instruments/resolve", input),
  });
}

// ---------------------------------------------------------------------------
// Mutations. register + add-alias are open to any authenticated actor; deprecate
// is Admin-only server-side. All carry a fresh Idempotency-Key per attempt.
// ---------------------------------------------------------------------------

export interface RegisterInstrumentInput {
  venue_id: string;
  symbol: string;
  contract_type: string;
  display_name: string;
  base_asset?: string | null;
  quote_asset?: string | null;
  settlement_asset?: string | null;
  multiplier?: string | null;
  market_class?: string | null;
  aliases: string[];
}

export interface RegisterInstrumentResult {
  instrument_id: string;
  resolution_key: string;
  display_name: string;
  state: string;
  registry_version: number;
  alias_count: number;
}

export interface AddAliasResult {
  instrument_id: string;
  alias_norm: string;
  alias_text: string;
}

export interface DeprecateInstrumentResult {
  instrument_id: string;
  state: string;
  registry_version: number;
}

function postWithIdempotency<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body,
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}

// Registry OCC travels in the X-Registry-Version header (a plain int) + a fresh
// Idempotency-Key. A stale token -> 409 INSTRUMENT_REGISTRY_CONFLICT verbatim.
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

export function useRegisterInstrument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RegisterInstrumentInput) =>
      postWithIdempotency<RegisterInstrumentResult>("/instruments", input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["instruments"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export function useAddInstrumentAlias(instrumentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alias: string) =>
      postWithIdempotency<AddAliasResult>(
        `/instruments/${encodeURIComponent(instrumentId)}/aliases`,
        { alias },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["instruments"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export interface DeprecateInstrumentInput {
  registryVersion: number;
  reason: string;
}

export function useDeprecateInstrument(instrumentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ registryVersion, reason }: DeprecateInstrumentInput) =>
      postWithRegistryVersion<DeprecateInstrumentResult>(
        `/instruments/${encodeURIComponent(instrumentId)}/deprecate`,
        registryVersion,
        { reason },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["instruments"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
