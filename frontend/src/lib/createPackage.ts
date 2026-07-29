// Create Package data access (doc 06 §4/§5/§7/§9, doc 07 §8/§10): compose an
// immutable create-package request, list the actor's own requests, open the
// read-only request projection (flow state + current Pre-Check scan), and drive
// the request lifecycle ACTIONS — run Pre-Check, generate candidate, create
// draft, approve & publish — plus the immutable dependency-scan artifact viewer.
//
// Concurrency contract: pre-check / generate-candidate carry the request
// row_version as an X-Request-Version OCC header (stale tab -> 409 verbatim);
// draft carries the expected_candidate_hash body token; approve carries the
// draft head as expected_head_revision_id. Every action sends a FRESH
// Idempotency-Key per attempt (a retry after a rejection is a new decision,
// not a replay). Approve is Admin-only server-side (CR-02) — the UI never
// role-gates the button; a non-Admin sees the 403 envelope verbatim.
//
// Create Package has no dedicated SSE event: a new request / state move changes
// an entity's lifecycle, swept by resource.changed (full refresh). Read keys live
// under ["package-requests"]; mutations invalidate that prefix (+ ["audit"] —
// every action writes audit rows the Panel Logs page binds). The Rationale
// Family selector reads the shared ["rationale-families"] list.

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";
import { uploadFile } from "./upload";

// ---------------------------------------------------------------------------
// Enums mirrored from backend domain/create_package/enums.py (CR-04: the wire
// values are lowercase snake_case, returned verbatim).
// ---------------------------------------------------------------------------

export type CreatePackageKind = "indicator" | "condition" | "embedded_system";

export type CreationMode =
  | "translate_existing_code"
  | "generate_from_description"
  | "repair_existing_code"
  | "review_existing_code";

export type SourceKind = "code" | "description";

export type SourceLanguage = "pinescript" | "python" | "cpp" | "other";

// V1 fixes the target runtime to the registered Python adapter
// (value_objects.SUPPORTED_TARGET_RUNTIMES); pine_v5 exists in the enum but the
// backend rejects it with RuntimeUnavailable, so the form only offers python.
export const SUPPORTED_TARGET_RUNTIME = "python";

export const CREATE_PACKAGE_KINDS: CreatePackageKind[] = [
  "indicator",
  "condition",
  "embedded_system",
];

export const CREATION_MODES: CreationMode[] = [
  "translate_existing_code",
  "generate_from_description",
  "repair_existing_code",
  "review_existing_code",
];

export const SOURCE_LANGUAGES: SourceLanguage[] = ["pinescript", "python", "cpp", "other"];

// Code modes carry supplied code (source_language required); Generate From
// Description carries a description (source_language forbidden). Mirrors
// value_objects.source_kind_for_mode / _CODE_MODES.
const CODE_MODES: ReadonlySet<CreationMode> = new Set<CreationMode>([
  "translate_existing_code",
  "repair_existing_code",
  "review_existing_code",
]);

export function sourceKindForMode(mode: CreationMode): SourceKind {
  return CODE_MODES.has(mode) ? "code" : "description";
}

// Output-contract `kind` values allowed per package type (doc 06 §4.3; mirrors
// value_objects._OUTPUT_KINDS_BY_KIND). The server re-validates on submit.
export const OUTPUT_KINDS_BY_KIND: Record<CreatePackageKind, string[]> = {
  indicator: ["directional_signal", "numeric_series", "state_series", "boolean_event"],
  condition: ["boolean_condition"],
  embedded_system: [
    "directional_signal",
    "numeric_series",
    "state_series",
    "boolean_event",
    "resolver_output",
  ],
};

export function outputKindsFor(kind: CreatePackageKind): string[] {
  return OUTPUT_KINDS_BY_KIND[kind] ?? [];
}

// D-2 (audit P-03, PO 22-Jul): human display labels for the Create Package
// enums. The machine enum stays the option `value` (and therefore the request
// payload — the server contract is unchanged); only the visible text is
// humanized. Any value missing from a map falls back to a title-cased render
// via `createPackageEnumLabel`, so a new backend enum never surfaces raw.
export const CREATE_PACKAGE_KIND_LABELS: Record<string, string> = {
  indicator: "Indicator Package",
  condition: "Condition Package",
  embedded_system: "Embedded System Package",
};

export const CREATION_MODE_LABELS: Record<string, string> = {
  translate_existing_code: "Translate Existing Code",
  generate_from_description: "Generate From Description",
  repair_existing_code: "Repair Existing Code",
  review_existing_code: "Review Existing Code",
};

export const SOURCE_LANGUAGE_LABELS: Record<string, string> = {
  pinescript: "PineScript",
  python: "Python",
  cpp: "C++",
  other: "Other",
};

export const TARGET_RUNTIME_LABELS: Record<string, string> = {
  python: "Python",
  pine_v5: "PineScript v5",
};

export const OUTPUT_KIND_LABELS: Record<string, string> = {
  directional_signal: "Directional Signal",
  numeric_series: "Numeric Series",
  state_series: "State Series",
  boolean_event: "Boolean Event",
  boolean_condition: "Boolean Condition",
  resolver_output: "Resolver Output",
};

// Title-case fallback for any enum value not present in a label map above
// (e.g. "some_new_kind" → "Some New Kind"). Never renders a raw underscore enum.
export function createPackageEnumLabel(map: Record<string, string>, value: string): string {
  const known = map[value];
  if (known !== undefined) return known;
  return value
    .split("_")
    .map((part) => (part.length > 0 ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

// Presentation-only badge tone for the read-only flow state (the wire state
// stays a plain string). Blocked/failed/rejected are down; the passed/ready/
// approved milestones are ok; stale warns; the rest are neutral in-flight.
const DOWN_STATES: ReadonlySet<string> = new Set([
  "precheck_blocked",
  "precheck_failed",
  "candidate_failed",
  "rejected",
  "revision_required",
]);
const OK_STATES: ReadonlySet<string> = new Set([
  "precheck_passed",
  "precheck_not_applicable",
  "candidate_ready",
  "eligible_for_approval",
  "approved",
]);

export function requestStateTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (DOWN_STATES.has(state)) return "down";
  if (state === "precheck_stale") return "warn";
  if (OK_STATES.has(state)) return "ok";
  return "neutral";
}

// Presentation-only badge tone for the Pre-Check scan status (PrecheckScanStatus
// wire values verbatim; stale is computed on read server-side).
export function scanStatusTone(status: string): "ok" | "warn" | "down" | "neutral" {
  if (status === "passed" || status === "not_applicable") return "ok";
  if (status === "blocked" || status === "failed") return "down";
  if (status === "stale") return "warn";
  return "neutral";
}

// Presentation-only badge tone for the immutable validation-run status
// (ValidationRunStatus wire values verbatim: queued/running/passed/failed/stale).
export function validationRunTone(status: string): "ok" | "warn" | "down" | "neutral" {
  if (status === "passed") return "ok";
  if (status === "failed") return "down";
  if (status === "stale") return "warn";
  return "neutral";
}

// Presentation-only badge tone for the baseline parse status
// (BaselineParseStatus wire values verbatim: uploaded/parsing/passed/failed).
// `parsing` is the durable worker's in-flight state (F-01c) — an in-flight parse is
// NOT proof of equivalence, so it shares the not-yet-proven tone with `uploaded`.
export function baselineParseTone(status: string): "ok" | "warn" | "down" | "neutral" {
  if (status === "passed") return "ok";
  if (status === "failed") return "down";
  if (status === "uploaded" || status === "parsing") return "warn";
  return "neutral";
}

// Narrow an unknown scan payload member (detected/resolved/missing/unsupported
// are JSONB lists on the wire) to a safe record array for row rendering.
export function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
  );
}

// ---------------------------------------------------------------------------
// Wire types (mirror queries/create_package.py projections verbatim)
// ---------------------------------------------------------------------------

export interface ScanSummary {
  scan_id: string;
  attempt_no: number;
  status: string;
  detected: unknown;
  resolved: unknown;
  missing: unknown;
  scanner_version: string | null;
  registry_fingerprint: string | null;
  context_hash: string | null;
}

// Immutable validation-run evidence summary embedded in the request projection
// (queries/create_package.py::_validation_summary). ``checks`` is a JSONB list of
// per-conformance rows; ``candidate_hash`` pins the exact candidate this run
// certified (validation_fresh goes false once the candidate is regenerated).
export interface ValidationSummary {
  validation_run_id: string;
  attempt_no: number;
  status: string;
  validator_version: string | null;
  checks: Array<Record<string, unknown>>;
  candidate_hash: string | null;
  draft_revision_id: string | null;
}

// Current baseline-asset summary embedded in the request projection
// (queries/create_package.py::_baseline_summary). The bytes never travel through
// the projection — only the content-addressed digest + parse evidence.
export interface BaselineSummary {
  baseline_asset_id: string;
  attempt_no: number;
  parse_status: string;
  content_digest: string | null;
  size_bytes: number | null;
  original_filename: string | null;
  baseline_metadata: Record<string, unknown>;
  parse_report: Record<string, unknown> | null;
  parser_version: string | null;
}

export interface PackageRequestSummary {
  request_id: string;
  package_type: string;
  state: string;
  source_kind: string;
  package_root_id: string | null;
}

export interface PackageRequestsPage {
  data: PackageRequestSummary[];
  meta: { cursor: string | null; has_more: boolean };
}

export interface PackageRequestDetail {
  request_id: string;
  package_type: string;
  creation_mode: string;
  source_kind: string;
  source_language: string | null;
  target_runtime: string;
  output_contract: Record<string, unknown>;
  rationale_family_id: string | null;
  compatible_rationale_family_ids: string[];
  // Explicit Indicator Link (doc 06 §4): the persisted indicator root+revision pins
  // (Condition packages), or null when the package declares no explicit link.
  linked_indicator: Record<string, unknown> | null;
  declared_dependencies: Array<Record<string, unknown>>;
  state: string;
  context_hash: string;
  request_version: number;
  owner_principal_id: string | null;
  current_scan: ScanSummary | null;
  precheck_fresh: boolean;
  package_root_id: string | null;
  draft_revision_id: string | null;
  // The candidate the durable generation worker pinned (F-01b). The admission POST no
  // longer returns a hash — it does not exist yet — so this is the staleness token the
  // Create-Draft step sends. Null until a candidate exists.
  candidate_hash: string | null;
  can_generate_candidate: boolean;
  // Validation evidence (doc 06 §4.4/§7): the current immutable run + whether it
  // still certifies THIS draft's candidate (false once the candidate regenerates).
  current_validation_run: ValidationSummary | null;
  validation_fresh: boolean;
  // Mode-aware baseline projection (doc 06 §4.4): whether the package claims
  // equivalence, its current baseline, and whether the approval baseline gate is
  // satisfied (a claiming package needs baseline_ready; a non-claiming one never
  // requires it — baseline_required mirrors claims_equivalence server-side).
  claims_equivalence: boolean;
  current_baseline: BaselineSummary | null;
  baseline_ready: boolean;
  baseline_required: boolean;
  // Revision chain (doc 06 §7/§15). Request Revision clears the draft head to build a
  // fresh attempt, so these server pins are the ONLY place the prior attempt survives:
  // the attempt number (1 = original), the parent draft revision and the prior
  // validation run, plus the append-only chain of every earlier attempt.
  revision_attempt_no: number;
  revision_total_attempts: number;
  parent_revision_ref: string | null;
  prior_validation_run_ref: string | null;
  revision_chain: RevisionLinkSummary[];
  created_at: string | null;
}

// One immutable link in the Request-Revision chain: the attempt it OPENS and the
// prior attempt (draft revision + root) plus that attempt's validation summary
// reference it descends from.
export interface RevisionLinkSummary {
  revision_link_id: string;
  attempt_no: number;
  parent_package_root_id: string | null;
  parent_revision_ref: string | null;
  prior_validation_run_ref: string | null;
  prior_candidate_hash: string | null;
  prior_state: string;
  created_at: string | null;
}

export interface CreateRequestResult {
  request_id: string;
  package_type: string;
  source_kind: string;
  state: string;
  context_hash: string;
  request_version: number;
}

export interface CreateRequestInput {
  package_type: CreatePackageKind;
  creation_mode: CreationMode;
  target_runtime: string;
  request_body: string;
  output_contract: Record<string, unknown>;
  source_language: SourceLanguage | null;
  other_language_label: string | null;
  rationale_family_id: string | null;
  // Compatibility declarations (doc 06 §4). The server re-validates both: each
  // compatible family must be an ACTIVE Rationale Family, and the linked indicator
  // must resolve to a real indicator root+revision (name-only selection prohibited).
  compatible_rationale_family_ids: string[];
  linked_indicator: LinkedIndicator | null;
  declared_dependencies: DeclaredDependency[];
}

// The Explicit Indicator Link wire shape (doc 06 §4): the saved dependency is the
// indicator ROOT + REVISION identifier — the machine pins, never a display name.
export interface LinkedIndicator {
  linked_indicator_package_root_id: string;
  linked_indicator_package_revision_id: string;
}

// Resolved/missing row shapes (commands/create_package.py::_resolve_declared):
// each resolved ref pins the exact ESP revision (never name-only/latest, P4/L5);
// a typed resolver error becomes a missing call with its precise code.
export interface ResolvedRef {
  call?: string;
  canonical_key?: string;
  embedded_entity_id?: string;
  embedded_revision_id?: string;
  content_hash?: string;
  runtime_adapter?: string;
  registry_version?: number;
}

export interface MissingCall {
  call?: string;
  code?: string;
  message?: string;
}

// Immutable scan artifact detail (queries/create_package.py::get_dependency_scan).
export interface DependencyScanDetail extends ScanSummary {
  request_id: string;
  unsupported: unknown;
  source_hash: string | null;
  language: string | null;
  job_id: string | null;
  completed_at: string | null;
}

// Action results (mirror commands/create_package.py return dicts verbatim).
export interface PrecheckActionResult {
  request_id: string;
  scan_id: string;
  attempt_no: number;
  status: string;
  state: string;
  resolved: number;
  missing: Array<Record<string, unknown>>;
  registry_fingerprint: string;
  job_id: string;
}

// Generate Candidate (commands/create_package.py::submit_candidate_generation): an
// ADMISSION (F-01b). The Pre-Check gate still fails fast with its typed 409, but past
// it the POST only enqueues the durable job and returns `candidate_generating` with an
// EMPTY candidate_hash — the real hash lands on the request projection when the worker
// finishes, so a draft can never be chained against a candidate that does not exist.
export interface CandidateActionResult {
  request_id: string;
  state: string;
  candidate_hash: string;
  job_id: string;
  request_version: number;
}

export interface DraftActionResult {
  request_id: string;
  package_root_id: string | null;
  draft_revision_id: string | null;
  state: string;
}

export interface ApproveActionResult {
  request_id: string;
  package_root_id: string | null;
  revision_id: string | null;
  approval_state: string;
  visibility_scope: string;
  state: string;
}

// Run Validation Tests (commands/create_package.py::start_package_validation_run): an
// ADMISSION (F-01b). It appends the immutable run in its `queued` state and enqueues the
// durable job, returning `validation_running` with EMPTY checks; the seven mandatory
// checks and the terminal verdict (eligible_for_approval / revision_required) land on
// the projection when the worker finishes.
export interface ValidationActionResult {
  request_id: string;
  validation_run_id: string;
  attempt_no: number;
  status: string;
  state: string;
  checks: Array<Record<string, unknown>>;
  job_id: string;
  request_version: number;
}

// Request Revision (commands/create_package.py::request_package_revision): reopen
// a failed/rejected draft, regenerating a fresh deterministic candidate. The new
// attempt is parent-linked (doc 06 §7): the response names the attempt it opened and
// the prior attempt's draft revision + validation run it descends from.
export interface RevisionActionResult {
  request_id: string;
  state: string;
  candidate_hash: string;
  revision_attempt_no: number;
  parent_revision_ref: string | null;
  prior_validation_run_ref: string | null;
  request_version: number;
}

// Upload Baseline (commands/create_package.py::upload_baseline_asset): store an
// immutable content-addressed CSV + metadata; a fresh upload is a new attempt.
export interface BaselineUploadResult {
  request_id: string;
  baseline_asset_id: string;
  attempt_no: number;
  parse_status: string;
  content_digest: string;
  size_bytes: number;
}

// Parse Baseline (commands/create_package.py::start_baseline_parse): an ADMISSION —
// the head baseline flips uploaded -> parsing and a durable job is enqueued (F-01c).
// `parser_version` / `parse_report` are EMPTY here on purpose: the CSV has not been
// read yet, so the real verdict is only ever read from the request projection
// (`current_baseline`) once the worker lands it.
export interface BaselineParseResult {
  request_id: string;
  baseline_asset_id: string;
  attempt_no: number;
  parse_status: string;
  parser_version: string;
  parse_report: Record<string, unknown>;
  job_id: string;
  request_version: number;
}

// Baseline upload input (F-03) — the real chosen TradingView CSV is transferred
// as multipart; the server derives content type + digest + filename from the
// bytes. The structured metadata the parse gate re-validates
// (REQUIRED_BASELINE_METADATA_FIELDS) rides a JSON form field.
export interface BaselineUploadInput {
  request_id: string;
  request_version: number;
  file: File;
  baseline_metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Declared dependencies (R2-12) — the ESP resolver matches EXACT ordered
// parameter types + return shape (domain/esp/resolver.py signature_matches;
// doc 09 §4.2 "ordered types are identity"). A bare key therefore carries an
// EMPTY signature and can never match a parameterised resolver contract, so
// the compose input accepts an optional signature per line:
//   ta.sma(series,int)->series
// A plain `key` line still travels as {key, signature:{}} (backend contract
// unchanged — clean_declared_dependencies already accepts both).
// ---------------------------------------------------------------------------

export interface DeclaredDependency {
  key: string;
  signature: Record<string, unknown>;
}

export function parseDeclaredDependencyLine(line: string): DeclaredDependency {
  const trimmed = line.trim();
  const match = /^([^()\s]+)\(([^()]*)\)\s*(?:->\s*(\S+))?$/.exec(trimmed);
  if (!match) return { key: trimmed, signature: {} };
  const [, key, paramList, returnType] = match;
  const params = paramList
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .map((type) => ({ type }));
  const signature: Record<string, unknown> = { params };
  if (returnType) signature.return = returnType;
  return { key, signature };
}

export function parseDeclaredDependencies(text: string): DeclaredDependency[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map(parseDeclaredDependencyLine);
}

// ---------------------------------------------------------------------------
// Baseline metadata (R2-12, GAP item 11) — the parse gate requires these keys
// (domain/create_package/baseline.py REQUIRED_BASELINE_METADATA_FIELDS
// verbatim). The UI collects them as typed product fields; the server remains
// the authority (missing/empty keys → BASELINE_METADATA_INVALID verbatim).
// ---------------------------------------------------------------------------

export const REQUIRED_BASELINE_METADATA_FIELDS = [
  "provider",
  "symbol",
  "timeframe",
  "range",
  "timezone",
  "settings",
  "source_revision_context",
] as const;

export interface BaselineMetadataFields {
  provider: string;
  symbol: string;
  timeframe: string;
  rangeStart: string;
  rangeEnd: string;
  timezone: string;
  settings: string;
  sourceRevisionContext: string;
}

// Compose the wire baseline_metadata object from the typed fields + the
// Admin-only Advanced extras. Typed descriptors win over extras on key
// collision; empty typed fields are omitted so the wire object matches what was
// actually filled in (the server's presence check treats "" as absent anyway).
// `range` becomes a {start, end} object from the two typed inputs.
export function buildBaselineMetadata(
  fields: BaselineMetadataFields,
  extras: Record<string, unknown>,
): Record<string, unknown> {
  const metadata: Record<string, unknown> = { ...extras };
  if (fields.provider.trim()) metadata.provider = fields.provider.trim();
  if (fields.symbol.trim()) metadata.symbol = fields.symbol.trim();
  if (fields.timeframe.trim()) metadata.timeframe = fields.timeframe.trim();
  const range: Record<string, string> = {};
  if (fields.rangeStart.trim()) range.start = fields.rangeStart.trim();
  if (fields.rangeEnd.trim()) range.end = fields.rangeEnd.trim();
  if (Object.keys(range).length > 0) metadata.range = range;
  if (fields.timezone.trim()) metadata.timezone = fields.timezone.trim();
  if (fields.settings.trim()) metadata.settings = fields.settings.trim();
  if (fields.sourceRevisionContext.trim())
    metadata.source_revision_context = fields.sourceRevisionContext.trim();
  return metadata;
}

export interface RationaleFamily {
  entity_id: string;
  display_name: string;
  normalized_name?: string;
  display_color?: string | null;
}

export interface RationaleFamiliesPage {
  data: RationaleFamily[];
  meta: { cursor: string | null; has_more: boolean };
}

// GET /rationale-families:suggest (master ref Module 6 §11). Mirrors
// application/queries/rationale.py::suggest_families verbatim. Not cursor-paginated:
// a suggestion list is bounded by design, so `meta` carries the normalized query and
// a has_more flag instead of a cursor.
export interface RationaleFamilySuggestion {
  entity_id: string;
  current_revision_id: string;
  display_name: string;
  normalized_name: string;
  subfamilies: string[];
}

export interface RationaleFamilySuggestions {
  data: RationaleFamilySuggestion[];
  meta: { q: string; has_more: boolean };
}

// ---------------------------------------------------------------------------
// Lifecycle-action availability (F-12) — a single, testable source of truth that
// mirrors the backend request state machine (domain/create_package/state_machine.py
// _REQUEST_ALLOWED + the per-command gates in commands/create_package.py). The UI
// exposes ONLY the actions the current flow state permits; the server re-validates
// every transition, so this is presentation gating, never authorization. Deriving
// availability here (not ad-hoc per button) is what makes the F-12 acceptance —
// "buttons/status/disabled follow the backend state machine" and "a draft cannot
// call approval directly" — a property of one function with unit coverage.
// ---------------------------------------------------------------------------

// States from which run_precheck can (re)scan dependencies: the pre-candidate
// states that _REQUEST_ALLOWED lets transition into a PRECHECK_* result. Once a
// candidate/draft exists the scan is frozen (no PRECHECK edge), so Pre-Check is off.
const PRECHECK_STATES: ReadonlySet<string> = new Set([
  "requested",
  "precheck_passed",
  "precheck_blocked",
  "precheck_not_applicable",
  "precheck_stale",
  "precheck_failed",
]);

// Legal only from revision_required / rejected (request_package_revision docstring).
const REVISION_STATES: ReadonlySet<string> = new Set(["revision_required", "rejected"]);

export interface PackageActionAvailability {
  precheck: boolean;
  generateDraft: boolean;
  runValidation: boolean;
  requestRevision: boolean;
  approve: boolean;
  uploadBaseline: boolean;
  parseBaseline: boolean;
  // A one-line guide to the next legal step, so a user never hits an unexpected
  // VALIDATION_REQUIRED dead end (F-12 acceptance #3).
  nextStepHint: string;
  // R2-12 (GAP item 11): WHY each locked action is locked, rendered directly
  // next to its control. Derived from the server projection alone (state /
  // scan / freshness flags) — null when the action is available.
  reasons: PackageActionReasons;
}

export interface PackageActionReasons {
  precheck: string | null;
  generateDraft: string | null;
  runValidation: string | null;
  approve: string | null;
  parseBaseline: string | null;
}

const NO_REASONS: PackageActionReasons = {
  precheck: null,
  generateDraft: null,
  runValidation: null,
  approve: null,
  parseBaseline: null,
};

// The lock reason for C.D.P (generate candidate → draft), read off the server
// projection: a present draft, an absent/blocked/stale Pre-Check, or a server
// that has simply not flagged can_generate_candidate yet.
function generateDraftReason(detail: PackageRequestDetail): string | null {
  if (detail.draft_revision_id !== null) return "A draft package already exists for this request.";
  // F-01b: generation runs in a durable background worker. While it runs the action is
  // locked — the result arrives on the projection, not from a second click.
  if (detail.state === "candidate_generating")
    return "Candidate generation is running in the background — closing this browser does not cancel it.";
  if (detail.can_generate_candidate || detail.state === "candidate_ready") return null;
  if (detail.current_scan === null) return "Pre-Check has not run — resolve dependencies first.";
  if (
    detail.current_scan.status !== "passed" &&
    detail.current_scan.status !== "not_applicable"
  )
    return `Pre-Check has not PASSED (${detail.current_scan.status}).`;
  if (!detail.precheck_fresh) return "The Pre-Check is stale — re-run it before drafting.";
  return "The server has not cleared candidate generation yet.";
}

function runValidationReason(detail: PackageRequestDetail): string | null {
  if (detail.state === "draft_created") return null;
  if (detail.draft_revision_id === null)
    return "No draft package yet — create one first (C.D.P).";
  switch (detail.state) {
    case "validation_running":
      return "Validation is already running.";
    case "eligible_for_approval":
      return "Validation already PASSED — the request is eligible for approval.";
    case "revision_required":
      return "Validation failed — Request Revision to regenerate the candidate.";
    case "approved":
      return "The request is approved — validation evidence is frozen.";
    default:
      return `Validation is not available in state ${detail.state}.`;
  }
}

// The head baseline's parse is running in the durable worker (F-01c). While this is
// true the UI shows in-flight and never a verdict — the terminal status arrives with
// the projection refetch the worker's resource.changed event triggers.
export function baselineParseRunning(detail: PackageRequestDetail | null): boolean {
  return detail?.current_baseline?.parse_status === "parsing";
}

function parseBaselineReason(detail: PackageRequestDetail, mutable: boolean): string | null {
  if (!mutable) return "The request is approved — the baseline is frozen.";
  if (detail.current_baseline === null) return "Upload a baseline CSV first.";
  if (baselineParseRunning(detail))
    return "The baseline parse is running in the background — it finishes even if you close this tab.";
  return null;
}

function approveReason(detail: PackageRequestDetail): string | null {
  if (detail.state === "approved") return "Already approved & published.";
  if (detail.state !== "eligible_for_approval")
    return "Validation has not PASSED yet — the request is not eligible for approval.";
  return approvalBlockReason(detail);
}

// The reason approve is unavailable while eligible_for_approval — kept separate so
// the panel can explain the gate (stale evidence / missing baseline) verbatim.
export function approvalBlockReason(detail: PackageRequestDetail): string | null {
  if (detail.state !== "eligible_for_approval") return null;
  if (!detail.validation_fresh)
    return "The passed validation no longer certifies the current candidate — re-run validation.";
  if (detail.baseline_required && !detail.baseline_ready)
    return "This request claims equivalence — upload and parse a PASSED baseline before approval.";
  return null;
}

function nextStepHint(detail: PackageRequestDetail): string {
  switch (detail.state) {
    case "requested":
      return detail.current_scan === null
        ? "Run Pre-Check to resolve code dependencies."
        : "Pre-Check done — generate a draft package (C.D.P).";
    case "precheck_passed":
    case "precheck_not_applicable":
      return "Dependencies resolved — generate a draft package (C.D.P).";
    case "precheck_blocked":
    case "precheck_failed":
      return "Create the missing Embedded System Packages, then re-run Pre-Check.";
    case "precheck_stale":
      return "The Pre-Check is stale — re-run it before drafting.";
    case "candidate_generating":
      return "Generating the candidate…";
    case "candidate_ready":
      return "Candidate ready — create the draft package (C.D.P).";
    case "candidate_failed":
      return "Candidate generation failed — request a revision to retry.";
    case "draft_created":
      return "Run Validation Tests to become eligible for approval.";
    case "validation_running":
      return "Validation is running…";
    case "eligible_for_approval":
      return approvalBlockReason(detail) ?? "Ready — Approve & publish the package.";
    case "revision_required":
      return "Validation failed — Request Revision to regenerate the candidate.";
    case "rejected":
      return "Rejected — Request Revision to start a fresh attempt.";
    case "approved":
      return "Approved & published to the Package Library.";
    default:
      return "";
  }
}

// Derive, from the read-only request projection alone, which lifecycle actions the
// UI should enable. Never inferred from a button click — the flow state is server
// truth. A null detail (no request selected) disables everything.
export function packageActionAvailability(
  detail: PackageRequestDetail | null,
): PackageActionAvailability {
  if (detail === null) {
    return {
      precheck: false,
      generateDraft: false,
      runValidation: false,
      requestRevision: false,
      approve: false,
      uploadBaseline: false,
      parseBaseline: false,
      nextStepHint: "",
      reasons: NO_REASONS,
    };
  }
  const state = detail.state;
  // A published request is terminal — its baseline/candidate are frozen.
  const mutable = state !== "approved";
  return {
    precheck: PRECHECK_STATES.has(state),
    // Draft only before one exists, once the server says a candidate can be built —
    // and never while the durable generation worker is still running (F-01b).
    generateDraft:
      detail.draft_revision_id === null &&
      state !== "candidate_generating" &&
      (detail.can_generate_candidate || state === "candidate_ready"),
    // VALIDATION_RUNNING has exactly one inbound edge: draft_created.
    runValidation: state === "draft_created",
    requestRevision: REVISION_STATES.has(state),
    // Approve mirrors approve_and_publish's gate: eligible_for_approval + fresh
    // passing evidence + (baseline parsed when equivalence is claimed).
    approve: state === "eligible_for_approval" && approvalBlockReason(detail) === null,
    uploadBaseline: mutable,
    // Never re-admit a parse the durable worker is still running (F-01c) — the head
    // asset's own `parsing` status is server truth, not a client-side pending flag.
    parseBaseline: mutable && detail.current_baseline !== null && !baselineParseRunning(detail),
    nextStepHint: nextStepHint(detail),
    reasons: {
      precheck: PRECHECK_STATES.has(state)
        ? null
        : "The dependency scan is frozen — a candidate or draft already exists.",
      generateDraft: generateDraftReason(detail),
      runValidation: runValidationReason(detail),
      approve: approveReason(detail),
      parseBaseline: parseBaselineReason(detail, mutable),
    },
  };
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// The Rationale Family selector for the create form (indicator/condition require
// an ACTIVE family). Shared read under ["rationale-families"]; first page only.
export function useRationaleFamilies(cursor: string | null) {
  return useQuery({
    queryKey: ["rationale-families", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<RationaleFamiliesPage>(`/rationale-families${qs ? `?${qs}` : ""}`);
    },
    staleTime: 5 * 60 * 1000,
  });
}

// Read-only Family suggestions for the composer (master ref Module 6 §11). A GET
// with no mutation: no Idempotency-Key, no OCC token. Applying a suggestion stays a
// separate explicit action — picking a chip only fills the existing selector, it
// never creates a Family (§9.3: a suggestion is an inference, never a silent write).
// Nested under the ["rationale-families"] prefix so the same invalidation sweeps it.
export function useRationaleFamilySuggestions(q: string) {
  const needle = q.trim();
  return useQuery({
    queryKey: ["rationale-families", "suggest", needle],
    queryFn: () =>
      api.get<RationaleFamilySuggestions>(
        `/rationale-families:suggest?q=${encodeURIComponent(needle)}`,
      ),
    // Below 2 characters the server returns [] anyway; skip the round trip.
    enabled: needle.length >= 2,
    staleTime: 5 * 60 * 1000,
  });
}

export function usePackageRequests(cursor: string | null) {
  return useQuery({
    queryKey: ["package-requests", "list", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<PackageRequestsPage>(`/create-package/requests${qs ? `?${qs}` : ""}`);
    },
    // Keep the current table mounted while a page flip is in flight.
    placeholderData: (previous) => previous,
  });
}

export function usePackageRequest(requestId: string | null) {
  return useQuery({
    queryKey: ["package-requests", "detail", requestId],
    queryFn: () =>
      api.get<PackageRequestDetail>(
        `/create-package/requests/${encodeURIComponent(requestId ?? "")}`,
      ),
    enabled: requestId !== null,
  });
}

// The immutable dependency-scan artifact (doc 07 §10): evidence never mutates
// once written, so a long staleTime is safe; the key stays under
// ["package-requests"] so the resource.changed sweep is harmless.
export function useDependencyScan(scanId: string | null) {
  return useQuery({
    queryKey: ["package-requests", "scan", scanId],
    queryFn: () =>
      api.get<DependencyScanDetail>(`/dependency-scans/${encodeURIComponent(scanId ?? "")}`),
    enabled: scanId !== null,
    staleTime: 5 * 60 * 1000,
  });
}

// Immutable validation-run evidence detail (queries/create_package.py::
// get_validation_run). Like the scan artifact it never mutates once written.
export function useValidationRun(validationRunId: string | null) {
  return useQuery({
    queryKey: ["package-requests", "validation-run", validationRunId],
    queryFn: () =>
      api.get<
        ValidationSummary & { request_id: string; job_id: string; completed_at: string | null }
      >(`/validation-runs/${encodeURIComponent(validationRunId ?? "")}`),
    enabled: validationRunId !== null,
    staleTime: 5 * 60 * 1000,
  });
}

// Immutable baseline-asset detail + parse report (queries/create_package.py::
// get_baseline_asset). Once parsed the evidence is fixed; a fresh upload is a new id.
export function useBaselineAsset(baselineAssetId: string | null) {
  return useQuery({
    queryKey: ["package-requests", "baseline-asset", baselineAssetId],
    queryFn: () =>
      api.get<BaselineSummary & { request_id: string; parsed_at: string | null }>(
        `/baseline-assets/${encodeURIComponent(baselineAssetId ?? "")}`,
      ),
    enabled: baselineAssetId !== null,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Mutation — create a request (POST /create-package/requests)
// ---------------------------------------------------------------------------

// A fresh Idempotency-Key per submit keeps a retry after a rejection a new
// decision, not a replay; the submit button stays disabled while pending so a
// double-click never creates two requests. On success the ["package-requests"]
// list is invalidated. The server re-validates every field and returns the
// canonical error envelope verbatim (the client never invents CP messages).
export function useCreatePackageRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateRequestInput) =>
      apiRequest<CreateRequestResult>("/create-package/requests", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: input,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["package-requests"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations — request lifecycle actions (doc 06 §7, doc 07 §8)
// ---------------------------------------------------------------------------

// Every action moves the request projection and writes audit rows; refetch both.
function invalidateActions(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["package-requests"] });
  void queryClient.invalidateQueries({ queryKey: ["audit"] });
}

// Pre-check / generate-candidate carry the request row_version as an
// X-Request-Version OCC header so a stale tab gets the 409 verbatim instead of
// silently racing a concurrent edit (mirrors agentLab postWithIfMatch), plus a
// fresh Idempotency-Key per attempt (doc 07 §8.1).
function postWithRequestVersion<T>(path: string, requestVersion: number): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: {
      "X-Request-Version": String(requestVersion),
      "Idempotency-Key": crypto.randomUUID(),
    },
  });
}

export function useRunPrecheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; request_version: number }) =>
      postWithRequestVersion<PrecheckActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/pre-check`,
        input.request_version,
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

export function useGenerateCandidate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; request_version: number }) =>
      postWithRequestVersion<CandidateActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/generate-candidate`,
        input.request_version,
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Draft races the CANDIDATE, not the request head: the expected_candidate_hash
// body token (from the accepted generate result) rejects a stale candidate with
// the typed error verbatim. Idempotent server-side: an existing draft replays
// the SAME root + revision.
export function useCreateDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; expected_candidate_hash: string | null }) =>
      apiRequest<DraftActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/draft`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: { expected_candidate_hash: input.expected_candidate_hash },
        },
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Admin-only server-side (CR-02); expected_head_revision_id pins the draft head
// so a concurrent revision move gets the conflict verbatim. UI visibility is
// never authorization — a non-Admin click surfaces the 403 envelope verbatim.
export function useApproveRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      request_id: string;
      expected_head_revision_id: string | null;
      note: string | null;
    }) =>
      apiRequest<ApproveActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/approve`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            expected_head_revision_id: input.expected_head_revision_id,
            note: input.note,
          },
        },
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Run Validation Tests: the request row_version guards the transition
// (X-Request-Version) + a fresh Idempotency-Key per attempt. The server enforces
// the draft-present gate (CandidateNotReady verbatim); a passed run moves the
// request to eligible_for_approval, a failed run to revision_required.
export function useRunValidation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; request_version: number }) =>
      postWithRequestVersion<ValidationActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/validate`,
        input.request_version,
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Request Revision: reopen a failed/rejected draft. Legal only from
// revision_required / rejected (state machine) — the server rejects an illegal
// state verbatim; the UI never pre-judges the state.
export function useRequestRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; request_version: number }) =>
      postWithRequestVersion<RevisionActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/request-revision`,
        input.request_version,
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Upload Baseline: an immutable content-addressed CSV upload (doc 06 §8.3). The
// row_version guards concurrency + a fresh Idempotency-Key per attempt. The file
// type / size / emptiness gates run server-side (FILE_TYPE_NOT_ALLOWED / 422
// verbatim) — the UI submits the composed body and renders the envelope.
export function useUploadBaseline() {
  const queryClient = useQueryClient();
  return useMutation({
    // F-03: real native CSV transfer (multipart). The X-Request-Version OCC token
    // rides a header (stale tab -> 409 verbatim) and the structured baseline
    // metadata rides a JSON form field; a fresh Idempotency-Key per attempt.
    mutationFn: (input: BaselineUploadInput) =>
      uploadFile<BaselineUploadResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/baseline`,
        input.file,
        {
          idempotencyKey: crypto.randomUUID(),
          headers: { "X-Request-Version": String(input.request_version) },
          fields: { baseline_metadata: JSON.stringify(input.baseline_metadata) },
        },
      ).promise,
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Parse Baseline: ADMIT the head baseline's parse (doc 06 §8.3; F-01c). The
// metadata-complete gate still runs server-side at admission
// (BASELINE_METADATA_INVALID verbatim); reading the CSV happens in the durable
// worker, so the response says `parsing` and the terminal passed/failed status
// arrives via the projection refetch — closing the tab never cancels the parse.
export function useStartBaselineParse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; request_version: number }) =>
      postWithRequestVersion<BaselineParseResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/baseline-parse`,
        input.request_version,
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}
