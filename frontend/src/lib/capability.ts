// Future Dev capability registry data access (doc 22): the read-only registry
// list/detail and Graphic View overview projections open to any authenticated
// principal, plus the Admin-only lifecycle transition. The registry is the
// SERVER-SIDE source of truth for what Future Dev may do — never a frontend
// feature flag (doc 22 §2, §15); UI visibility is never authorization (§3):
// the route re-checks Admin and the command re-checks it at the service.
//
// Query keys live under ["capabilities"] — the registry has no dedicated SSE
// event; rows refresh via this page's own mutations and the `resource.changed`
// full sweep (lib/sse.ts EVENT_QUERY_KEYS catch-all).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/queries/capability.py and
// application/commands/capability.py verbatim)
// ---------------------------------------------------------------------------

export interface Capability {
  capability_key: string;
  title: string;
  menu_path: string;
  lifecycle_state: string;
  is_operational: boolean;
  ui_surface_version: string;
  domain_contract_version: string | null;
  registry_version: number;
  enabled_at: string | null;
  retirement_at: string | null;
  status_message: string;
}

export interface CapabilityListResponse {
  capabilities: Capability[];
  count: number;
}

// A gate entry is a plain boolean or an object carrying `complete` plus
// free-form server-side fields (notes); anything else counts as incomplete
// (domain/capability/lifecycle.py `_gate_complete`).
export type GateEntry = boolean | { complete?: boolean; [key: string]: unknown };

export interface DependencySnapshot {
  gates?: Record<string, GateEntry>;
  [key: string]: unknown;
}

export interface CapabilityDetail extends Capability {
  dependency_snapshot: DependencySnapshot;
  changed_by_actor_id: string | null;
  change_reason: string | null;
}

export interface GraphicViewCard {
  title: string;
  text: string;
}

export interface GraphicViewOverview {
  capability_key: string;
  title: string;
  lifecycle_state: string;
  is_operational: boolean;
  registry_version: number;
  intro: string;
  cards: GraphicViewCard[];
  status_message: string;
}

export interface CapabilityTransitionResult {
  capability_id: string;
  capability_key: string;
  title: string;
  menu_path: string;
  lifecycle_state: string;
  ui_surface_version: string;
  domain_contract_version: string | null;
  registry_version: number;
  enabled_at: string | null;
  retirement_at: string | null;
  activation_event_id: string;
  correlation_id: string | null;
}

// ---------------------------------------------------------------------------
// Server-owned lifecycle taxonomy (domain/capability/{enums,lifecycle}.py,
// doc 22 §9.1/§9.2) mirrored for the composer option lists. The server
// re-validates every edge and every gate on dispatch — these constants
// hydrate <select>s/checklists and are never client authority.
// ---------------------------------------------------------------------------

export const CAPABILITY_STATES = [
  "placeholder",
  "designed",
  "internal",
  "shadow",
  "limited",
  "active",
  "retired",
] as const;
export type CapabilityStateKey = (typeof CAPABILITY_STATES)[number];

// Legal edges (doc 22 §9.1): staged forward progression, explicit rollback
// downgrades, retirement only from an operational state. Retired is terminal.
export const ALLOWED_TRANSITIONS: Record<CapabilityStateKey, readonly CapabilityStateKey[]> = {
  placeholder: ["designed"],
  designed: ["internal"],
  internal: ["shadow"],
  shadow: ["limited"],
  limited: ["active", "shadow", "retired"],
  active: ["limited", "retired"],
  retired: [],
};

export function allowedTargets(state: string): readonly CapabilityStateKey[] {
  return ALLOWED_TRANSITIONS[state as CapabilityStateKey] ?? [];
}

// The seven activation gates (doc 22 §9.2) recorded in dependency_snapshot.
export const ACTIVATION_GATES = [
  "domain",
  "data",
  "policy",
  "ui",
  "backend",
  "verification",
  "rollback",
] as const;

// Badge tones only — the wire state stays a plain string.
export const STATE_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  active: "ok",
  limited: "warn",
  retired: "down",
};

// Mirrors the server's completeness reading: true, or an object whose
// `complete` is exactly true.
export function gateComplete(entry: GateEntry | undefined): boolean {
  if (entry === true) return true;
  return typeof entry === "object" && entry !== null && entry.complete === true;
}

// Merge an Admin's gate checklist back into the stored snapshot WITHOUT
// clobbering server-side note objects: object entries keep their fields and
// only `complete` flips; plain entries become booleans.
export function buildGatesSnapshot(
  original: DependencySnapshot,
  draft: Record<string, boolean>,
): DependencySnapshot {
  const originalGates = original.gates ?? {};
  // Start from the stored record so non-canonical server-side keys survive.
  const gates: Record<string, GateEntry> = { ...originalGates };
  for (const gate of ACTIVATION_GATES) {
    const entry = originalGates[gate];
    const complete = draft[gate] ?? gateComplete(entry);
    gates[gate] = typeof entry === "object" && entry !== null ? { ...entry, complete } : complete;
  }
  return { ...original, gates };
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useCapabilities() {
  return useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilityListResponse>("/capabilities"),
  });
}

export function useCapability(capabilityKey: string | null) {
  return useQuery({
    queryKey: ["capabilities", "detail", capabilityKey],
    queryFn: () =>
      api.get<CapabilityDetail>(`/capabilities/${encodeURIComponent(capabilityKey ?? "")}`),
    enabled: capabilityKey !== null,
  });
}

export function useGraphicViewOverview() {
  return useQuery({
    queryKey: ["capabilities", "graphic-view-overview"],
    queryFn: () => api.get<GraphicViewOverview>("/future-dev/graphic_view/overview"),
  });
}

// ---------------------------------------------------------------------------
// Mutation — Admin lifecycle transition (POST .../lifecycle-transitions)
// ---------------------------------------------------------------------------

export interface TransitionInput {
  capability_key: string;
  to_state: string;
  reason: string;
  expected_registry_version: number;
  dependency_snapshot?: DependencySnapshot;
}

// OCC: expected_registry_version carries the projection's registry_version so
// a stale tab gets the 409 envelope verbatim instead of clobbering a
// concurrent change. The command REQUIRES an Idempotency-Key — one fresh UUID
// per attempt (a retry after a rejection is a new decision, not a replay).
// Omitting dependency_snapshot keeps the server-stored gate record untouched.
export function useTransitionCapability() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TransitionInput) =>
      apiRequest<CapabilityTransitionResult>(
        `/capabilities/${encodeURIComponent(input.capability_key)}/lifecycle-transitions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            to_state: input.to_state,
            reason: input.reason,
            expected_registry_version: input.expected_registry_version,
            ...(input.dependency_snapshot !== undefined
              ? { dependency_snapshot: input.dependency_snapshot }
              : {}),
          },
        },
      ),
    onSuccess: () => {
      // The registry row changed AND the command emitted an audit event.
      void queryClient.invalidateQueries({ queryKey: ["capabilities"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
