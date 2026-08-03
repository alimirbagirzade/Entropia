# High-risk API contract audit — ESP / Package Library / Agent Tool Gateway

**Base:** `origin/main` @ `870cc1a` (2026-08-03) · **Branch:** `refactor/typed-contracts-esp-library-agent`
**Scope:** the public payloads touched by ADIM 2–7 — ESP resolve/lifecycle/validation/export,
Package Library detail/request-validation/run-read/export, Agent Tool Gateway history and the
Strategy / Trading Signal results those calls carry.

Everything below was re-derived from the code on this base, not from a prior handoff. Where a
research finding disagreed with the source, the source won and the disagreement is recorded.

---

## 1. Endpoint audit

`Body` = the shape the handler actually returned before this slice. `Replay` = what an
`Idempotency-Key` repeat serves. `OpenAPI before` was `<untyped object>` for every row marked
`dict`, i.e. the body was **invisible in `docs/openapi.json` while the drift guard stayed green**
— the trap O-30 closed for the purge 202 and G-02 closed for the package export.

### 1.1 Embedded System Packages (`routes/esp.py`)

| Method / path | Request | Body before | Keys | Replay | Errors | Frontend | OpenAPI now |
|---|---|---|---|---|---|---|---|
| `POST /embedded-system-packages` (201) | `CreateEspRequest` + `Idempotency-Key` | `dict` | 5 | `run_idempotent`, verbatim | 401/403/422 | `CreateEspResult` | `CreateEspResponse` |
| `GET /embedded-system-packages` | cursor/limit/trust_state/visibility_scope | `dict` | `data[12]` + `meta{2}` | n/a (read) | 401 | `EspPage` / `EspRegistryRow` | `EspRegistryPageResponse` |
| `GET /embedded-system-packages/{id}` | — (ETag out) | `dict` | 18 (+3 nested) | n/a (read) | 401/403/404 | `EspPackageDetail` | `EspPackageDetailResponse` |
| `POST /{id}/validate` | `ValidateRequest` + `Idempotency-Key` | `dict` | 6 (`checks` = **list**) | `run_idempotent`, verbatim | 403/404/422 | *(unbound)* | `EspValidationRunResponse` |
| `POST /{id}/activate` | `ActivateRequest` + `X-Registry-Version` + `Idempotency-Key` | `dict` | 5 | `run_idempotent`, verbatim | 403/409 | `ActivateResolverResult` | `ActivateResolverResponse` |
| `POST /{id}/deprecate` | `DeprecateRequest` + `X-Registry-Version` + `Idempotency-Key` | `dict` | 5 | `run_idempotent`, verbatim | 403/409 | `DeprecateResolverResult` | `DeprecateResolverResponse` |
| `POST /embedded-system-packages/resolve` | `ResolveRequest` | `dict` | 9 | n/a (read, no key) | 404/409/422 | `ResolveResult` | `ResolveDependencyResponse` |

### 1.2 Package Library (`routes/library.py`)

| Method / path | Request | Body before | Keys | Replay | Errors | Frontend | OpenAPI now |
|---|---|---|---|---|---|---|---|
| `GET /library` | 9 facets + cursor/limit | `dict` | `data[20]` + `meta{2}` | n/a (read) | 401 | `LibraryPage` | `LibraryPageResponse` |
| `GET /library/{id}` | — (ETag out) | `dict` | 27 | n/a (read) | 401/403/404 | `LibraryPackageDetail` | `LibraryPackageDetailResponse` |
| `POST /{id}/deprecate` | `DeprecatePackageRequest` + `Idempotency-Key` | `dict` | 2 | **unreachable** — the lifecycle guard sits OUTSIDE `run_idempotent`, so a repeat is 409 `LIFECYCLE_BLOCKED` before idempotency is consulted | 403/409 | `DeprecatePackageResult` | `DeprecatePackageResponse` |
| `DELETE /library/{id}` (204) | `If-Match "rv-N"` | no body | — | idempotent no-op | 403/409 | `void` | unchanged |
| `POST /{id}/derive` (201) | `DerivePackageRequest` + `Idempotency-Key` | `dict` | 6 | `run_idempotent`, verbatim | 403/422 | `DerivePackageResult` | `DerivePackageResponse` |
| `POST /{id}/revisions` (201) | `CreateRevisionRequest` (body OCC) + `Idempotency-Key` | `dict` | 5 | `run_idempotent`, verbatim | 403/409 | `CreateRevisionResult` | `CreatePackageRevisionResponse` |
| `POST /{id}/validation-runs` (201) | `RequestValidationRequest` (body OCC) + `Idempotency-Key` | **already typed** | 8 | inner CP command is idempotent; the outer envelope is **re-projected every call** | 403/409/422 | `RequestValidationResult` | `PackageValidationRunAcceptedResponse` *(unchanged)* |
| `POST /{id}/request-approval` | `RequestApprovalRequest` (body OCC) + `Idempotency-Key` | `dict` | 3 | `run_idempotent`, verbatim | 403/409 | `RequestApprovalResult` | `RequestPackageApprovalResponse` |
| `POST /{id}/approve` | `ApprovePackageRequest` (body OCC) + `Idempotency-Key` | `dict` | 4 | `run_idempotent`, verbatim | 403/409 | `ApprovePackageResult` | `ApprovePackageResponse` |
| `POST /{id}/export` | `ExportPackageRequest` + `Idempotency-Key` | **already typed** | 6 | `run_idempotent` + **legacy back-fill** (`_with_export_envelope_defaults`) | 403/404 | `ExportPackageResult` | `PackageExportResponse` *(tightened)* |

### 1.3 Agent Tool Gateway (`routes/agent_lab.py`)

| Method / path | Request | Body before | Keys | Replay | Errors | Frontend | OpenAPI now |
|---|---|---|---|---|---|---|---|
| `GET /agent-tasks/{task_id}/tool-calls` | `limit` | `dict` | `tool_calls[13]` | n/a (read) | 403/404 | `AgentToolCallList` | `AgentToolCallListResponse` |
| `GET /agent-tool-calls/{id}` | — | `dict` | 19 | n/a (read) | 403/404 | `AgentToolCallDetail` | `AgentToolCallDetailResponse` |

**Enqueue has no HTTP surface.** `dispatch_tool_call` and `enqueue_tool_call`
(`application/jobs/agent_tools.py`) are worker-plane functions; nothing under
`apps/api/routes/` imports `agent_tools`, and the only production callers are the agent
executor (`apps/agent_coordinator` → `run_agent_executor`) and the dramatiq actors
`run_agent_tool` / `run_agent_tool_high`. There is therefore **no enqueue request contract to
publish** — the gateway's public contract is the two history reads, which is what was typed.
The Strategy / Trading Signal results from ADIM 6–7 reach HTTP only as `response_ref` on the
detail read (see §4).

---

## 2. What changed

* **16 endpoints** moved from an untyped `object` 2xx body to a named, published component.
* **30 new schema components**; **0 removed**; **196 operations before and after** (no route added,
  renamed, or dropped).
* **2 existing components changed**: `PackageValidationRunAcceptedResponse` (description only —
  the model moved modules verbatim) and `PackageExportResponse` (see §5).
* Response models live in a new `apps/api/schemas/` package rather than inline in the route
  modules. The three pre-existing models (O-30 purge, G-02 export, validation-run) set the
  inline precedent, but those route modules describe themselves as **thin handlers**; ~40 models
  inline would have pushed `routes/library.py` past 550 lines and buried the handlers.
  `PackageExportResponse` and `PackageValidationRunAcceptedResponse` moved into
  `schemas/library.py` under their **existing class names**, so no published component key moved.
  `routes/trash.py::PurgeAcceptedResponse` was left where it is — out of this slice's scope.
* Handlers still return `dict[str, Any]`; only `response_model=` was added. That is the
  established pattern (`trash.py:191`, `library.py:338`) and it keeps the route-level subscripts
  that run **before** serialization working — `int(detail["row_version"])` for the two ETags and
  `dispatch_create_package_job(result["job_id"])` for the validation-run broker hand-off.

---

## 3. Design rules applied

**Every field is REQUIRED; nullability lives in the type.** `x: str | None` with no default keeps
the key in `required` and lets the value be `null`. A `= None` default would advertise an
omittable key that is never omitted. Asserted for all 17 top-level and 14 nested components.

**Enums publish as `string`, never a closed enum.** The serializers already emit the lowercase
`StrEnum` value via `str(x)`. Publishing a closed enum in a *response* would turn a value the
server legitimately produced into a client-side validation failure the day a member is added —
and would 500 the server first, since `response_model` validates on the way out. Asserted for 14
state fields.

**Timestamps publish as `string`, never `format: date-time`.** The serializers emit
`.isoformat()` on `DateTime(timezone=True)` columns. Declaring `datetime` would re-parse and
re-render the value. Asserted for 6 timestamp fields.

**Two shapes that share a name are two models.** `checks` is a per-check **list** on the validate
command and the stored **report envelope dict** on the detail read; `rationale_family` is
`{id, name}` on a list row and `{id, name, pinned_name, family_active}` on the detail. Merging
either pair would have forced optional fields and hidden which endpoint returns which.
`ActivateResolverResponse` / `DeprecateResolverResponse` stayed separate for the same reason —
activate carries `revision_id`, deprecate carries `replacement_revision_id`.

**Supersets are structural, not asserted.** `LibraryPackageDetailResponse` and
`LibraryPackageRow` share a private base (`_LibraryPackageFields`) so the detail cannot fall out
of superset with the list; `AgentToolCallDetailResponse` inherits `AgentToolCallCard`. The
library pair uses a shared base rather than an override because mypy strict rejects narrowing a
field type in a subclass as a Liskov violation.

---

## 4. What deliberately stayed open

| Field | Why it must not be closed |
|---|---|
| `PackageExportResponse.manifest` | Versioned content-addressed artifact that states its own field set via `export_schema_version`, and is round-tripped **verbatim** into `POST /package-imports`. A dropped key would silently corrupt the import and desynchronise `manifest_hash`. |
| `input_contract`, `output_contract`, `dependency_snapshot`, `validation_summary` | Caller-authored JSONB; the UI renders them verbatim **and** reads arbitrary keys (`input_contract.market` / `.timeframe` in `AddPackagePopover`). |
| `EspResolverContract.signature` / `.evidence`, `ResolveDependencyResponse.signature` / `.evidence` | Caller-authored JSONB rendered verbatim. |
| `EspValidationRunSummary.checks` | Raw JSONB read; the shape is namespaced by `validator_version`, so old rows may differ. |
| `PackageProvenanceScan.resolved_refs` / `missing_calls` / `unsupported_calls` | Per-call rows owned by the Pre-Check plane. |
| `LibraryPackageRow.performance` | `dict[str, str]`. The six metrics come from a module constant; a closed model would silently drop a seventh the day one is added. Matches the frontend's `Record<string, string>`, which index-reads it. |
| `AgentToolCallDetailResponse.request` / `.response_ref` | **The gateway envelope/payload split.** `response_ref` is discriminated by `tool_name` across 33 registered tools and stores the backing command's return verbatim — including every Strategy and Trading Signal result from ADIM 6–7. It is also a three-way union: the tool's own payload on `succeeded` (with **no** `status` key — read the sibling column), `{status, reason_code, reason}` on `rejected`, `{status, failure_code, failure_reason, details}` on `failed`. A closed discriminated union would need re-cutting on every registry addition and would drop fields from any tool it did not yet know. Everything the *gateway* owns — identity, provenance, policy, terminal status, failure pointers, timestamps — **is** typed. |

`LibraryPackageRow.permissions` went the other way: it is closed (11 named booleans) because a
dropped flag silently **hides a UI action** instead of failing loudly. The regression test pins
it against `dataclasses.fields(PackagePermissions)`, so adding a flag without updating the model
fails the suite rather than the UI.

---

## 5. Compatibility matrix

| Change | Kind | Client impact |
|---|---|---|
| 16 bodies now publish a named component | **Additive** | The wire bytes are unchanged; a client that ignored the schema is unaffected, one that reads it gains a contract. |
| 30 new components | **Additive** | New names only. |
| `PackageExportResponse.registry_observation`: `object` → `$ref PackageRegistryObservation` | **Tightening (response)** | Strictly more guarantee. The 6 keys were already sent; they are now named. |
| `PackageExportResponse.registry_observation`: optional → `required` | **Tightening (response)** | The key was already always present — `_with_export_envelope_defaults` back-fills it on a pre-G-02 replay. The old `= None` default advertised an omission that never happened. |
| `PackageValidationRunAcceptedResponse` description | **Cosmetic** | Model moved modules verbatim; properties and `required` are byte-identical. |
| No field removed, renamed, or made optional anywhere | — | **No breaking removal in this slice**, so no alias or deprecation window is needed. |
| `ErrorBody` / `ErrorResponse` | **Untouched** | O-02 envelope names unchanged; pinned by a test. |
| 201/202 statuses, OCC tokens (`If-Match`, `expected_*`, `X-Registry-Version`), `Idempotency-Key` | **Untouched** | No request contract was modified. |

### Frontend wire parity

`docs/openapi.json` and `frontend/src/lib/{esp,library,agentLab}.ts` are now compared
field-by-field, including nullability, by `tests/contract/test_wire_contract_parity.py` (27
pairs). Four drifts existed on `origin/main` and are fixed:

| Drift found | Direction | Fix |
|---|---|---|
| `EspPackageDetail` never declared `latest_validation_run` | client blind to a field the server has sent **since R8** | added `EspValidationRunSummary` + the field. The Embedded page still does not render it — declaring the wire type is not the same as building the UI, and that stays an honest open item. |
| `EspPackageDetail.lifecycle_state: string` | TS **narrower** than the server (`entity_registry.lifecycle_state` is a nullable free-form column) — a latent runtime bug | widened to `string \| null` |
| `LibraryPackageRow.lifecycle_state: string` | same | widened to `string \| null` |
| `ProvenanceScan.registry_fingerprint` / `context_hash: string \| null` | TS **wider** than the server (both NOT NULL) — a dead branch | tightened to `string` |

The two widenings made three render sites null-unsafe. `lifecycleTone` now accepts
`string | null` and the labels fall back to a new `UNSTATED_LIFECYCLE_LABEL` (`"unstated"`) —
an honest label, never a fabricated `"active"`. No route path, react-query key, hook, OCC token,
Idempotency-Key, SSE mapping or `lib/*.ts` data logic was touched.

---

## 6. Tests

| File | Guards |
|---|---|
| `tests/contract/test_typed_contract_no_field_drop.py` (17) | Every model pinned against the **real serializer** that feeds it (`_registry_dict`, `_contract_dict`, `_validation_run_dict`, `_package_row`, `_scan_summary`, `_pinned_family`, `_live_family`, `_tool_call_card`, `_tool_call_detail`, `ResolverCheck.as_dict`, `build_registry_observation`, `dataclasses.fields(PackagePermissions)`). Pure functions over ORM stubs — no DB. Plus the poisoned-snapshot guard from §7. |
| `tests/contract/test_typed_contract_openapi.py` (11, mostly parametrized) | Each surface publishes the right component; **all fields required**; the open payloads stay unconstrained; `ErrorBody`/`ErrorResponse` untouched. The "no closed enum" and "timestamps are plain strings" rules are **blanket walks over every component transitively reachable from a 2xx body**, not a hand-listed field set — a list stops covering the field somebody adds next. A separate test asserts the walk actually reaches the nested models, so the two blanket tests cannot pass vacuously. |
| `tests/contract/test_wire_contract_parity.py` (3, 27 parametrized pairs) | OpenAPI ↔ TypeScript field-set and nullability parity; a missing interface raises; both sides of every pair are asserted non-empty so the comparison can never be vacuous. |
| `tests/integration/test_typed_contract_replay_parity.py` (16) | HTTP body `==` the **stored idempotency envelope** (the dict before `response_model`) for every idempotent surface; end-to-end replay equality where a second call is reachable; ESP/Library/Gateway reads `==` the query's unfiltered return; a **pre-G-02 export record** replays under the now-strict model; a resolve failure still renders `ErrorBody`; a **rejected** ToolCall renders through the typed detail. |

Two surfaces have no stored envelope to compare against and needed their own technique:

* **`POST /library/{id}/validation-runs`** is not `run_idempotent`-wrapped — the outer envelope is
  re-projected on every call. The test **spies on the command** (`monkeypatch` around
  `pkg_cmd.request_package_validation`) so the comparison is the real pre-model dict against the
  post-model body. Pinning it against a hand-written key set — which is what the pre-existing
  `test_library_validation_run_route.py` does — would agree with the model by construction and
  stay green if the command grew a ninth key.
* **`provenance` / `rationale_family`** are `null` on a package built straight through
  `pkg_repo.create_package`, so `PackageProvenance`, `PackageProvenanceScan`,
  `PinnedRationaleFamilyRef` and `LiveRationaleFamilyRef` would be *declared but never applied*.
  The fixture now pins a family snapshot, and a second test drives a CreatePackage-plane package
  so the provenance block is populated.

**Two pre-existing contract stubs had to be re-aligned.**
`tests/contract/test_library_contract.py` faked the list and detail queries with
`{"entity_id": "pkg_1"}` and `{"entity_id": …, "row_version": 3, "name": "X"}` — shapes the
projection never produces, which the untyped route passed through happily. Under
`LibraryPageResponse` / `LibraryPackageDetailResponse` those are a 500, which is the correct
outcome: a contract test asserting on a body the server cannot produce was testing nothing. The
stubs now mirror `_package_row` key-for-key; what the tests actually check (filter-alias
pass-through, the ETag header) is unchanged.

---

## 7. A defect this slice had to fix before it could land

**A typed contract turns a latent data problem into a 500.** `response_model` validates on the
way out, so a value that violates the declared type now fails the whole response instead of
shipping a wrong-typed field. Every nullable/non-null decision in §1–§4 was taken from the
**column definition**, not from observed data, and the nullable side was chosen wherever the DB
allows null — which left exactly one reachable hole, found by adversarial review of this diff:

* `package_revision.rationale_family_snapshot` is JSONB, and `POST /package-imports` writes a
  **caller-supplied manifest** into it behind a container-level `isinstance(dict)` guard only
  (`application/jobs/package_import.py:210`). The two projections that read it,
  `_pinned_family` and `_live_family`, screened the id with a bare truthiness test and passed
  `display_name` through raw.
* So an authenticated import of
  `{"rationale_family_snapshot": {"rationale_family_id": 7, "display_name": 42}}` produced a
  catalog row whose `rationale_family` was `{"id": 7, "name": 42}`. Before this slice that
  rendered as garbage; under `PinnedRationaleFamilyRef` it would have been a **500 on the whole
  `GET /library` page** for every viewer of that row, not just on one field.
* Fixed at the serializer, matching the module's own precedent (`_package_name` isinstance-guards,
  `_output_kinds` and `derive_catalog_scope` coerce): `_snapshot_family_id` requires a non-empty
  **string** id — a non-string is not a family reference, so the row reports *no* pinned family —
  and `_snapshot_display_name` drops a non-string name rather than rendering `42` as a label the
  system never assigned. The guard also runs **before** the id reaches
  `rationale_repo.get_family_root`, which was being handed a non-string lookup key.
* Valid data is byte-identical. Pinned by
  `test_a_poisoned_family_snapshot_cannot_break_the_typed_projection` and
  `test_the_detail_family_projection_screens_the_same_poison`.

The write path itself is left alone on purpose: hardening `POST /package-imports` against
arbitrary manifest content is a different slice, and the projection must be safe regardless of
what is already stored.

## 8. Residual risk
* **`registry_observation` is now a closed model.** If `build_registry_observation` gains a key
  without the model gaining it, the key is dropped — the regression test in
  `test_typed_contract_no_field_drop.py` is what catches that, not the type system.
* **Nine of the command envelopes are guarded only by an integration module.**
  `tests/integration/conftest.py` skips the whole module when no PostgreSQL is reachable, so a
  developer running without a database gets **no field-level protection** on the ESP
  create/validate/activate/deprecate and Library derive/revisions/approve/deprecate/export
  bodies — only the contract modules' model-vs-serializer pins, which do not exercise the
  commands. CI runs with Postgres, so the gate itself is intact; this is a local-run caveat,
  not a coverage gap in the pipeline.
* **`response_ref` remains unmodelled by design** (§4). Consumers must read the sibling `status`
  column rather than looking for a `status` key inside a successful payload.
* **`GET /library-shared-with-me`** (`routes/sharing.py`) returns the identical `LibraryPage`
  envelope and is still untyped. It is outside this slice's scope; `LibraryPageResponse` is
  reusable for it verbatim when that surface is next touched.
* The remaining ~161 `dict[str, Any]` route returns elsewhere in the API are **untouched** — this
  slice is deliberately not a repository-wide DTO rewrite.
