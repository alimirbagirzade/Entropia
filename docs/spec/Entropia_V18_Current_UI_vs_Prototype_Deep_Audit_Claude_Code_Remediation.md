# Entropia V18 — Current UI vs Prototype Deep Audit and Binding Claude Code Remediation

**Audit date:** 22 July 2026  
**Audited repository:** `alimirbagirzade/Entropia`  
**Audited local branch:** `main`  
**Audited commit:** `6e3fab979759f31f24b09a6acfc569e0a8cd0e02`  
**Audience:** Claude Code and the engineers responsible for Entropia V18  
**Status:** Open remediation specification. Nothing in this document is product-owner approved merely because the current repository calls it `PASS`, `Complete`, or `PO-APPROVE`.

## 1. The answer to the three audit questions

### 1.1 What you built

Claude, you built a substantial production-oriented application around the V18 material:

- The Mainboard can now create and open Strategy, Trading Signal, and Trade Log editors inline without changing the URL.
- Strategy Details now contains the documented ten numbered areas in a three-column editor.
- Market Data, Research Data, Trading Signal, Trade Log, Create Package, Package Library, Portfolio, Ready Check, Backtest Run, Results History, Analysis Lab, Panel, Trash, User Manual, and capability screens are connected to real backend APIs.
- File selection and upload paths now exist for the major ingest workflows.
- Root/revision, immutable manifest, authorization, audit, outbox, job, lifecycle, Ready Check, and result-history foundations are extensive and should be preserved.
- Real browser E2E coverage, screenshot capture, responsive checks, authentication checks, and accessibility scans now exist.

This is meaningful progress. The remediation must not discard these foundations.

### 1.2 What you should have built

You should have built the production implementation behind the prototype's product interaction model:

`Mainboard → horizontal working-object row → arrow → compact type-specific inline editor → Ready Check modal → RUN → inline latest Result`

The page specifications deliberately separate two concerns:

1. The prototype is the visual, spatial, navigation, and interaction reference.
2. The Master Technical Reference and the 22 page specifications replace prototype-only fake persistence, unsafe terminology, local arrays, display-name identity, and demo financial behavior with real Production V1 semantics.

The required result is therefore not a literal copy of every obsolete prototype label, and it is not a generic administration application that merely exposes the backend. It is the prototype's human-facing workspace, backed by the production domain model.

### 1.3 What you misunderstood

Your largest misunderstanding was treating technical completeness as product-interface fidelity. You repeatedly solved the backend problem by exposing more cards, identifiers, states, separate routes, diagnostic panels, and lifecycle controls. That often made the application technically richer but visually and operationally farther from the intended product.

You also treated an implementation-generated screenshot as evidence that the implementation matches the prototype. It is not. A screenshot regression against the current application only proves that the current application did not change unexpectedly. It cannot prove that the current application is correct.

Finally, you classified visible differences as `PO-APPROVE` before the product owner approved them. The repository's own final-acceptance document has an empty D-1 through D-9 approval record. An unsigned proposed deviation is an open defect, not an approved design decision.

## 2. Source-of-truth and conflict rule

Use the following hierarchy for every remediation item:

1. Financial correctness, security, persistence, authorization, lifecycle, and canonical type boundaries come from the Master Technical Reference and the Production V1 sections of the page specifications.
2. Visual hierarchy, row placement, expand/collapse behavior, information grouping, density, action location, and navigation model come from the V18 prototype and the V18 Interface Behavior sections.
3. A page specification's explicit Production Alignment Note may rename or replace a legacy prototype action without moving the action out of its required visual context.
4. The current implementation is evidence of what exists; it is not a source of product requirements.
5. `PO-APPROVE`, `candidate for approval`, or an unsigned acceptance table is not approval.
6. If two authoritative statements remain genuinely incompatible after applying these rules, stop that specific item and record the exact conflict for the product owner. Do not silently choose the current implementation.

Examples:

- Trading Signal must remain a Mainboard inline working object because that is the required interaction model.
- Trading Signal must not become a Package Library package because the Production V1 type boundary explicitly forbids it.
- Therefore the prototype button `Save As Trading Signal Package` must become a canonical action such as `Save Trading Signal Revision` in the same inline action bar; it must not disappear, move to a generic route, or create `PackageKind=trading_signal`.
- Add Package is correctly strategy-package-only in Production V1. Do not reintroduce Trading Signal or Trade Log package kinds. Instead remove the misleading legacy package menu entries.

## 3. Preserve these completed improvements

Do not regress the following while fixing the remaining defects:

- Mainboard URL remains `/` while the three working-object editors open, save, and close inline.
- Add Strategy creates an inline draft row.
- Add Outsource Signal selects Trading Signal or Trade Log and creates the correct inline draft row.
- Add Package selects an accessible usable Strategy Package revision and derives a Strategy draft.
- Normal users do not type raw root IDs, revision IDs, hashes, object-storage keys, or JSON to complete ordinary workflows.
- File bytes are uploaded through the real ingest paths rather than represented by a fake filename-only state.
- Authorization remains server-side even when an action is hidden or disabled in the UI.
- Ready Check and RUN remain tied to immutable composition/snapshot truth.
- Historical results and pinned revisions remain immutable.
- Mobile overflow fixes, stale-session handling, error envelopes, and loading states remain intact.

## 4. P0 — Acceptance and visual-verification defects

### Finding A-01 — The “inline” visual tests do not render inline editors

**What you built:** `frontend/e2e/specs/11-visual-regression.spec.ts` names screenshots `strategy-inline`, `trading-signal-inline`, and `trade-log-inline`, but navigates directly to `/strategy`, `/trading-signal`, and `/trade-log`. No Mainboard row is created or expanded.

**What you should have built:** The test must open `/`, invoke the same Add action a user invokes, expand the horizontal row, and capture the resulting inline editor inside the Mainboard.

**What you misunderstood:** A component that is also available on a standalone workbench is not visually equivalent to that component hosted inside the Mainboard row.

**Required correction:** Replace these cases with explicit Mainboard journeys. Assert the URL remains `/`, assert the correct row header and arrow state, and screenshot the Mainboard with that row expanded. Keep standalone-route tests separately and do not call them inline tests.

**Acceptance:** A test fails if the inline editor is removed while the standalone route still works.

### Finding A-02 — The visual regression suite protects the current UI, not the prototype

**What you built:** `toHaveScreenshot()` compares the application with snapshots generated from the same application and permits a 2% pixel-difference ratio.

**What you should have built:** A prototype-fidelity gate must compare equivalent current and prototype states, or compare both against an approved visual contract derived from the prototype.

**What you misunderstood:** Regression stability and design correctness are different claims. A stable wrong layout remains wrong.

**Required correction:** Keep the current snapshot suite as a regression layer, but add a separate `prototype-fidelity` layer. For each page/state, define the prototype invocation, current-app journey, viewport, seeded content, masked dynamic regions, measurable layout anchors, and approved tolerance. Require product-owner sign-off for the reference set.

**Acceptance:** The suite independently reports “current regression” and “prototype fidelity”; one cannot substitute for the other.

### Finding A-03 — The compared states are not equivalent

**What you built:** Prototype captures create inline rows, open the Ready Check modal, and add an inline result. Current baseline captures often use standalone draft-manager, Ready Check, or RUN routes. Other pairs compare populated prototype content with empty current content, or inactive current Agent state with an active prototype state.

**What you should have built:** Every pair must represent the same user role, object count, lifecycle state, open/closed state, data values, viewport, and interaction point.

**What you misunderstood:** Matching route names is not matching product state.

**Required correction:** Create deterministic fixtures for empty, one-row collapsed, one-row expanded, validation error, saved revision, Ready PASS modal, running, succeeded inline result, and populated history. Capture both systems at the same state.

**Acceptance:** Every comparison record contains a state manifest and the assertions that prove the current and prototype states are equivalent before the screenshot is taken.

### Finding A-04 — The claimed full visual matrix has missing prototype references

**What you built:** The repository contains 122 current baseline images but only 20 prototype images. The route matrix contains 23 route targets because document 19 is split into Management and Logs. Outsource Signal, Pre-Check, and Future Dev have no prototype-reference captures in that set.

**What you should have built:** The evidence inventory must explicitly map all 22 page documents and every production route/state to either a prototype reference or a documented “no independent prototype screen” rule with the correct host-state reference.

**What you misunderstood:** A count of generated PNG files is not coverage traceability.

**Required correction:** Add `docs/implementation/v18_visual_traceability.md` with one row per document, production route, prototype handler/host state, required fixture, reference image, current image, diff result, exception status, and approval signature.

**Acceptance:** No document or route is silently omitted, double-counted, or represented by the wrong host screen.

### Finding A-05 — `PO-APPROVE` was treated as if the PO had approved it

**What you built:** `docs/implementation/v18_visual_deviations.md` labels large Mainboard and page-structure differences `PO-APPROVE`. `v18_final_acceptance.md` still has an empty approval record for D-1 through D-9.

**What you should have built:** Unapproved differences remain open requirements until the product owner signs a specific exception.

**What you misunderstood:** “Recommend approval” is not “approved.”

**Required correction:** Change every unsigned `PO-APPROVE` item to `OPEN — PO DECISION REQUIRED`. Do not mark its parent requirement complete. Link any future approval to the exact screenshot, behavior, date, approver, and scope.

**Acceptance:** The status system cannot calculate a requirement as complete while it contains an unsigned deviation.

### Finding A-06 — Ten pages were never deeply compared

**What you built:** The final-acceptance document explicitly says documents 03, 07, 09, 10, 12, 17, 18, 19, 21, and 22 received only a first observation rather than a detailed side-by-side review.

**What you should have built:** Every visible component, default state, action, row, field, label, panel, modal, and responsive state must be checked.

**What you misunderstood:** A screenshot existing on disk does not mean anyone evaluated it.

**Required correction:** Complete a component-level comparison for those documents and update the visual traceability matrix with individual findings and evidence.

**Acceptance:** Product-owner review can navigate from each document requirement to current screenshot, prototype screenshot, code, test, and disposition.

### Finding A-07 — Serious accessibility defects are allow-listed instead of fixed

**What you built:** The committed axe report records 228 serious color-contrast nodes across 23 route captures and two serious `link-in-text-block` violations. The test explicitly accepts those rules.

**What you should have built:** V18 fidelity must include readable content and keyboard/screen-reader operability. A theme adaptation may preserve the visual identity while meeting WCAG 2.2 AA.

**What you misunderstood:** Recording a serious violation prevents surprise; it does not close the defect.

**Required correction:** Produce an accessible V18 palette, underline paragraph links, rerun the full matrix, and require zero critical/serious violations unless the product owner signs a narrowly scoped exception.

**Acceptance:** Zero unapproved critical or serious axe nodes.

### Finding A-08 — Manual accessibility verification is far too narrow

**What you built:** Keyboard testing covers login, Mainboard, and the Add menu. The repository states that full per-page keyboard and NVDA/VoiceOver journeys were not performed.

**What you should have built:** The primary flows must work by keyboard and with at least the documented screen-reader coverage: inline editor expansion, complex forms, file upload, modals, tables, errors, lifecycle actions, and results.

**What you misunderstood:** Passing axe and one keyboard smoke path is not end-to-end accessibility.

**Required correction:** Add a manual and automated matrix for keyboard order, focus return, announcements, error association, modal trapping, expandable row semantics, and live job/result updates.

**Acceptance:** Signed keyboard and screen-reader evidence exists for every P0/P1 workflow.

## 5. P0 — Mainboard and inline-editor defects

### Finding M-01 — The Mainboard hierarchy is still not the prototype hierarchy

**What you built:** The current Mainboard adds a `Mainboard` title, `Backtest composition · human_default`, a permanent `+ Add` button, an allocation strip, a large Composition panel, hashes/freeze data, and a Backtest Results card around the central working list.

**What you should have built:** The default visual hierarchy is the prototype's simple workspace: stable top menu, `STRATEGIES`, horizontal rows, the results area, and the Ready Check/RUN controls. Production-only metadata must not compete with the primary editing surface.

**What you misunderstood:** Making server truth visible does not require making infrastructure state visually dominant.

**Required correction:** Keep hashes, workspace version, allocation mode, and freeze diagnostics in an Advanced/Composition disclosure or contextual panel. Restore the prototype's first-glance hierarchy and vertical rhythm. The permanent `+ Add` affordance may remain only if explicitly approved; the menu Add path must remain primary and equivalent.

**Acceptance:** At normal desktop width, the first screen visually reads as working-object rows, not a composition administration dashboard.

### Finding M-02 — Collapsed rows carry too much technical/status decoration

**What you built:** Rows include multiple type/state/share badges such as `Strategy · Unsaved draft` and can display repeated generic labels such as multiple `STRATEGY 1` drafts.

**What you should have built:** A collapsed row is a clean, long horizontal rectangle with a meaningful human label, the minimal necessary production state, delete control where allowed, and the arrow on the right.

**What you misunderstood:** Every backend state does not need a pill in the row's primary reading line.

**Required correction:** Use a deterministic unique temporary label for unsaved rows, use the saved display name after persistence, move secondary status/provenance into the expanded panel or a compact secondary line, and retain the prototype's blue-row visual emphasis.

**Acceptance:** Three unsaved strategies are immediately distinguishable and each row remains visually compact.

### Finding M-03 — Strategy Details is structurally present but visually too coarse

**What you built:** The current CSS uses 16px grid gaps, 14px column gaps, 12×14px card padding, and large card titles. It omits the prototype's vertical column dividers. The result is much taller and more card-like than the compact prototype.

**What you should have built:** The updated prototype uses a compact three-column grid: 12px grid gap, 6px card padding, approximately 10.7px section titles, tight field rows, and visible column separators.

**What you misunderstood:** Matching the number of columns and section names is not matching the layout.

**Required correction:** Rebuild the Strategy editor's spacing and typography from the final prototype CSS tokens in `docs/spec/index_guncellenmis_duzeltilmis_v18.html`. Do not globally shrink unrelated screens. Add component-level visual tests for every Strategy section.

**Acceptance:** At 1440px the ten areas read as one dense editor rather than ten vertically inflated cards, with no awkward button/ID wrapping.

### Finding M-04 — Strategy fields expose technical identity and implementation commentary

**What you built:** The inline editor prominently shows technical root identity, verbose operational explanations, OCC/revision information, and an admin raw-payload disclosure near the normal working flow.

**What you should have built:** The normal editor shows product fields and human provenance. Technical identity may be available in a collapsed Advanced/Diagnostics section for authorized users.

**What you misunderstood:** “The user can understand the ID” is not the same as “the user needs the ID to configure the strategy.”

**Required correction:** Replace root/revision IDs with human labels in the default view, preserve IDs only as copyable advanced metadata, and shorten persistent helper text by moving long explanations behind the documented information controls.

**Acceptance:** A normal user can complete all ten areas without reading or copying any infrastructure identifier.

### Finding M-05 — The Strategy form offers settings the engine cannot execute

**What you built:** The UI allows several custom-formula, filter, trend/divergence, order, scaling, conflict, and execution combinations while helper text or Ready Check later says the V1 engine does not model them.

**What you should have built:** Every selectable and savable financial setting must either execute exactly as documented or be visibly unavailable before the user builds a strategy around it.

**What you misunderstood:** Failing closed at Ready Check protects financial correctness, but it does not complete the product workflow.

**Required correction:** Implement each documented active Production V1 behavior end to end. Until implemented, mark the option `Not available in this build`, disable it, and explain the dependency. Do not allow a normal draft to proceed deep into the workflow only to discover a hidden engine boundary.

**Acceptance:** Every enabled option has form, schema, revision, readiness, engine, trace, result, and test coverage.

### Finding M-06 — Trading Signal is inline but not the compact two-column product panel

**What you built:** The inline panel contains an import region followed by a second large full-width `Create Trading Signal` form, repeated identity/binding concepts, long operational prose, and an attached-signals registry. It is far longer than the prototype.

**What you should have built:** One compact two-column expanded panel: identity/source/data fields grouped on the left, upload/format/mapping on the right, and one bottom action bar.

**What you misunderstood:** Reusing a complete standalone workbench inside the row is not the same as designing the row's inline editor.

**Required correction:** Compose an inline-specific presentation over the same hooks and commands. Remove duplicate controls, move revision history/attached registry to Advanced or the standalone management route, preserve one source of form state, and use canonical Production labels.

**Acceptance:** The common create/import/save journey is visible without scrolling through a second workbench inside the row.

### Finding M-07 — Trade Log repeats the same inline composition error

**What you built:** Trade Log uses the same oversized import-plus-create workbench pattern and includes management content inside the Mainboard editor.

**What you should have built:** The compact two-column Trade Log panel defined by page 05, with identity/source and time/price policy grouped clearly, file import and format guidance opposite, and a single action bar.

**What you misunderstood:** Shared code between Trading Signal and Trade Log should share primitives, not force both into the same oversized page composition.

**Required correction:** Create a shared compact inline shell with type-specific field groups. Keep standalone workbenches for deep revision/import history only.

**Acceptance:** Trading Signal and Trade Log look related but preserve their different field semantics and remain compact inside their rows.

### Finding M-08 — Trading Signal and Trade Log actions are incomplete in the inline panel

**What you built:** The visible toolbar emphasizes Validate, Save, Cancel, and Close. The documented source-bundle/mapping export is not represented as a complete normal action, and Clear/reset semantics are not presented like the prototype flow.

**What you should have built:** Production-canonical equivalents of Save Revision, Clear Draft, and Export Signal Events/Source Bundle or Export Trade Log Source Mapping, in the same bottom action location.

**What you misunderstood:** The page specs remove the word `Package`; they do not remove the export intent.

**Required correction:** Implement the real authorized export job/artifact, expose it only when a normalized revision exists, add correct pending/error/success states, and implement Clear as draft reset rather than deletion.

**Acceptance:** Export produces an external-object artifact and never creates a Package Library package.

### Finding M-09 — Primary-flow and deep-management surfaces are not separated

**What you built:** Inline rows and standalone routes frequently render nearly the same full workbench. Visual tests then use the standalone route as a proxy for the inline product flow.

**What you should have built:** A compact primary Mainboard editor and an optional deep-management route for revision history, import artifacts, and diagnostics, both using the same domain commands.

**What you misunderstood:** Code reuse does not require presentation reuse at the wrong scale.

**Required correction:** Separate `InlineEditor` composition from `ManagementWorkbench` composition while sharing field primitives, validation, mutations, and query state.

**Acceptance:** Removing the deep route would not break the core Mainboard journey; removing the inline editor would fail P0 acceptance.

### Finding M-10 — Ready Check acceptance uses the wrong visual surface

**What you built:** Mainboard has a Ready Check interaction, but the screenshot matrix and critical visual regression use `/backtest/ready-check`, a technical composition/report page with identifiers and hashes.

**What you should have built:** The primary visual reference is the Mainboard `Backtest Ready Check` modal/drawer with Passed, Failed, and Warnings columns/cards. The standalone report may remain a secondary diagnostic route.

**What you misunderstood:** Backend report completeness and prototype interaction placement are separate requirements.

**Required correction:** Capture and test the Mainboard modal as the P0 surface. Keep raw report identity in Advanced details.

**Acceptance:** A product user can understand readiness and the exact remediation without leaving the Mainboard.

### Finding M-11 — RUN/Result acceptance also uses the wrong visual surface

**What you built:** The regression capture uses `/backtest/run`, while the prototype and page contracts make RUN originate on Mainboard and place the latest succeeded result beneath the working composition.

**What you should have built:** Test and visually approve request, queued/running state, success, failure, and the latest inline result in the Mainboard context.

**What you misunderstood:** A functional standalone run controller does not prove the product's central loop.

**Required correction:** Make the Mainboard journey the authoritative E2E and visual test. Keep the standalone route as full result/run diagnostics.

**Acceptance:** Ready PASS enables RUN; RUN produces one immutable result; the latest succeeded result appears inline without navigation.

### Finding M-12 — The navigation still advertises forbidden package kinds

**What you built:** The Edit → Package Library submenu still contains `Trading Signal Packages` and `Trade Log Packages`, and both silently open an unfiltered Package Library because those backend package kinds do not exist.

**What you should have built:** The Production V1 library contains only Strategy, Indicator, Condition, and Embedded System package kinds. Trading Signal and Trade Log belong under Add Outsource Signal and external working-object management.

**What you misunderstood:** Preserving a legacy prototype menu label while pointing it somewhere else is not backward compatibility; it is misleading navigation.

**Required correction:** Remove the two package entries. Provide external-object access through the Mainboard and, if needed, clearly named Trading Signal/Trade Log management routes outside Package Library.

**Acceptance:** No visible menu or API contract implies `PackageKind=trading_signal|trade_log`.

## 6. P1 — Page-by-page visual and information-architecture defects

### Finding P-01 — Add Outsource Signal is tested as a separate page instead of a Mainboard action

**What you built:** The Mainboard Add submenu is now correct, but the visual matrix treats `/outsource-signal` as a normal page target and the deep-link page contains a large explanatory chooser/workbench.

**What you should have built:** Primary acceptance covers Add → Add Outsource Signal → Trading Signal/Trade Log inside Mainboard. The route may remain only as a compact recovery/deep-link chooser.

**What you misunderstood:** A valid deep link is not a primary product screen.

**Required correction:** Reclassify the route and remove it from the claim that it represents the prototype's primary flow.

**Acceptance:** All navigation menus use the Mainboard action model; the deep link clearly returns the user to the Mainboard workflow.

### Finding P-02 — Pre-Check's primary and secondary surfaces are confused

**What you built:** Create Package includes the correct Pre-Check action/status/overlay, but the route matrix emphasizes a separate `/packages/pre-check` request-ID table and scan-artifact page.

**What you should have built:** The Create Package compose area, status card, and Pre-Check result overlay are the normal user experience. A separate artifact viewer may exist for detailed immutable scan evidence.

**What you misunderstood:** A full scan administration screen is not the prototype placement.

**Required correction:** Make the overlay complete enough for the normal resolution journey and label the standalone route as `Pre-Check Artifacts` or advanced diagnostics. Use human request names in the default list, not raw IDs.

**Acceptance:** A user completes Pre-Check, sees resolved/missing dependencies, and continues without leaving Create Package.

### Finding P-03 — Create Package still exposes machine values as product labels

**What you built:** Dropdowns, badges, and request summaries display values such as `indicator`, `translate_existing_code`, `pinescript`, `directional_signal`, and raw request IDs.

**What you should have built:** Human labels such as `Indicator Package`, `Translate Existing Code`, `PineScript`, and `Directional Signal`, while preserving machine enums in API payloads.

**What you misunderstood:** Type safety in the API does not require machine vocabulary in the UI.

**Required correction:** Introduce centralized display-label maps and human request titles. Put IDs in an optional Advanced detail.

**Acceptance:** No normal Create Package field or chip exposes an underscore-delimited enum or opaque ID as its primary label.

### Finding P-04 — Create Package's source/dependency area does not match the prototype composition

**What you built:** Source code and declared dependencies are narrow textareas embedded in a dense field grid; request chips consume prominent space; right-side lifecycle panels remain hidden until a request exists.

**What you should have built:** The source/prompt is the dominant left-side compose area; status and lifecycle stages remain spatially stable on the right, including honest empty states.

**What you misunderstood:** Progressive disclosure should not destroy the page's stable mental model.

**Required correction:** Restore the prototype's two-column proportions, large source area, action row, and persistent status skeleton. Move `My requests` to a compact selector/history drawer.

**Acceptance:** The page's geometry does not jump substantially after Send, and the user can predict the full pipeline before submitting.

### Finding P-05 — Create Package visibly admits fields are not persisted

**What you built:** The page states that Compatible Family and explicit Indicator Link follow the layout but “are not yet sent to the backend (V1).”

**What you should have built:** Every visible, editable semantic field must be included in the typed request, validated, persisted, returned, and used by downstream candidate/dependency logic.

**What you misunderstood:** A field that appears in the correct place but has no domain effect is not implemented.

**Required correction:** Extend the request schema and command path for these fields, or remove/disable them with a clear build-boundary label until implementation. Never present them as working controls.

**Acceptance:** Save, reload, candidate generation, draft creation, and audit preserve the selected values.

### Finding P-06 — Package Library omits required Market and Timeframe facets

**What you built:** The code explicitly says Market and Timeframe are absent “by design” because the current projection lacks those fields.

**What you should have built:** The page 08 Production contract includes server-queryable market and timeframe scope. The UI must retain the prototype's filter toolbar while using canonical server fields.

**What you misunderstood:** A missing backend projection is an integration gap, not a reason to remove a required filter.

**Required correction:** Add market/timeframe scope to package revision/catalog DTOs, indexed query filters, human display, and tests. Use `System/Not applicable` semantics for Embedded System packages.

**Acceptance:** A user can perform the documented Type + Market + Timeframe + Rationale query and receive server-filtered results.

### Finding P-07 — Package Library hides the prototype category structure and shows machine states

**What you built:** Empty package sections are omitted; rows show raw package-kind/lifecycle/validation/approval/visibility tokens; the Import Package JSON area occupies a large part of the page.

**What you should have built:** The stable category structure and compact expandable rows remain visually recognizable. Production lifecycle detail and import can live in secondary panels.

**What you misunderstood:** Adding production capabilities does not require replacing the catalog's information architecture.

**Required correction:** Show all canonical sections with meaningful empty states, map enums to human labels, keep import in a collapsed advanced card or dedicated route, and prevent raw JSON from dominating the normal catalog.

**Acceptance:** The default page reads first as a reusable-logic catalog, not a manifest import console.

### Finding P-08 — Embedded System Packages lost the scoped Package Library presentation

**What you built:** `/packages/embedded` is a dedicated technical resolver registry with function keys, trust states, revision IDs, probes, and proposal controls.

**What you should have built:** The normal entry should preserve the generic Package Library layout scoped to `embedded_system`, with System/Not applicable facets and expandable human-readable rows. Deep resolver administration may be a secondary authorized detail.

**What you misunderstood:** The Production resolver model changes the content behind the row; it does not eliminate the documented catalog surface.

**Required correction:** Add a scoped catalog view as the primary screen and move resolver probes/contracts/evidence to row details or an Advanced Resolver Management route.

**Acceptance:** Edit → Package Library → Embedded System Packages opens a recognizable scoped library, not an unrelated administration product.

### Finding P-09 — Market Data registry columns do not satisfy the visual/data contract

**What you built:** The current table emphasizes Revision state, Validation, revision number, and Created date. It omits Source, Coverage, and Resolution and renders values such as `ohlcv` as machine text.

**What you should have built:** The prototype/production-facing digest includes Dataset, Type, Source, Instrument, Coverage, Resolution, Status, Version, and Action, backed by server truth.

**What you misunderstood:** Lifecycle columns are useful, but they do not replace data-quality and data-scope information.

**Required correction:** Extend the list projection with provider/source, coverage summary, and resolution; map types such as `ohlcv` to `OHLCV`; keep deeper validation/revision state in expanded detail.

**Acceptance:** A user can decide which dataset to open from the registry without opening every row.

### Finding P-10 — Research Data is not registry-first

**What you built:** The default screen immediately displays workflow/status material and a large Dataset Setup form before the registry. The expected Search, Category, and Source toolbar is not the dominant default surface.

**What you should have built:** Default view: workflow strip, registry toolbar, registry table, and `+ Add Research Dataset`. The setup form appears only after Add and closes back to the registry.

**What you misunderstood:** Implementing the form fields is not enough; the open/closed state and page hierarchy are requirements.

**Required correction:** Make setup closed by default, restore server-backed search/category/source filters, preserve registry context while editing, and implement unsaved-change confirmation.

**Acceptance:** A returning user can search and open existing research datasets without scrolling past a creation form.

### Finding P-11 — Portfolio exposes wire identities instead of working-object names

**What you built:** Composition and allocation tables prominently show `workspace_id` and `composition_item_id` values such as `mbi_...`; add-candidate and preview lists use those IDs as primary labels.

**What you should have built:** Human Strategy/Trading Signal/Trade Log names and types are primary. IDs remain hidden binding keys.

**What you misunderstood:** Stable IDs are required for persistence, not for the user's mental model.

**Required correction:** Extend the allocation projection with display labels and revision summaries; keep IDs in data attributes/advanced detail only. Retain all four numbered cards and their disabled/faded skeleton when allocation is off.

**Acceptance:** The user can allocate capital without matching `mbi_...` values to another screen.

### Finding P-12 — Results History collapsed rows omit the required metric digest

**What you built:** Collapsed rows show raw result ID, date, timeframe, symbol, and several controls. Net Profit, ROMAD, Drawdown, and Win Rate appear only after expansion or elsewhere.

**What you should have built:** The collapsed summary format includes a human result label/title and the fixed key-metric digest: Net, ROMAD, DD, and Win Rate.

**What you misunderstood:** The expanded panel does not replace the summary contract.

**Required correction:** Render human-short result identity and key metrics directly in the row. Keep compare/delete/view actions visually secondary and policy-driven. Do not recalculate metrics in the browser.

**Acceptance:** Users can scan and rank history at a glance before expanding any card.

### Finding P-13 — Result detail is visibly incomplete

**What you built:** `ResultDetail.tsx` explicitly says the price chart, equity curve, drawdown, exposure, and AI Review are not rendered/generated in V1.

**What you should have built:** The documented Result viewer includes real immutable result artifacts and visualizations where required. If AI Review is outside V1, it must not be presented as a nearly complete active section.

**What you misunderstood:** An honest placeholder is better than fabricated data, but it is still incomplete product functionality.

**Required correction:** Implement chart rendering from immutable artifact endpoints, with loading/error/empty states and no client recomputation. Gate AI Review behind the capability system and hide or clearly label it as Future Dev until activated.

**Acceptance:** Charts reflect the exact result manifest and ledger; a disabled future capability is not counted as V1 completion.

### Finding P-14 — Panel Logs does not preserve the required backtest-log primary view

**What you built:** The page is primarily a generic event projection plus a raw audit stream with event kinds, principal IDs, resource IDs, and correlation data.

**What you should have built:** Preserve the V18 `All User Backtest Logs` primary table with User, Date, Backtest, Net Profit, ROMAD, and Trades. Production event/audit exploration may be an additional tab/card/drawer.

**What you misunderstood:** The audit log is a richer technical data source, but it is not a replacement for the admin's backtest-history question.

**Required correction:** Add a server-side admin backtest-log projection and make it the first view. Place event filters and raw audit stream in a clearly separated technical view.

**Acceptance:** An Admin can answer “which user ran which backtest and what were its headline metrics?” without decoding domain events.

### Finding P-15 — Panel Management displays machine policy strings

**What you built:** Role matrices and user tables expose values such as `shared_and_published` and `own_system_outputs`, along with test-like account names and extensive operational detail.

**What you should have built:** Human-readable role/capability descriptions with technical keys available only in advanced detail.

**What you misunderstood:** A policy enum is not final UI copy.

**Required correction:** Add a display vocabulary, group permissions by human task, keep the compact management table primary, and move operator recovery/technical actors into separate admin disclosures.

**Acceptance:** A product administrator can understand permissions without knowing backend enum names.

### Finding P-16 — Rationale assignments expose raw package identities

**What you built:** Assignment rows can display `pkg_...` IDs, raw package kind values, or `—` when seeded package names are missing.

**What you should have built:** Human package name, package type label, current revision, and family name, while using IDs only for binding.

**What you misunderstood:** Server-truth identity and human-readable identity must coexist.

**Required correction:** Fix seed/projection display names, add label mapping, and reserve raw IDs for an advanced detail.

**Acceptance:** Every visible assignment row identifies the package unambiguously in product language.

### Finding P-17 — Page-title, spacing, and token differences were globally accepted without approval

**What you built:** Many prototype all-caps titles became title case; spacing, borders, colors, card radii, typography, and status-chip usage were normalized into the current design system.

**What you should have built:** A documented V18 token layer derived from the final prototype, with intentional Production additions specified separately.

**What you misunderstood:** Internal visual consistency does not automatically equal prototype fidelity.

**Required correction:** Extract prototype tokens for shell height, menu, page title, row height, card borders, typography, spacing, and action placement. Apply them page by page. Submit any deliberate global change for explicit approval with side-by-side evidence.

**Acceptance:** No global visual deviation is closed by “consistent everywhere”; it is either matched or signed off.

### Finding P-18 — Long permanent explanatory copy overwhelms the workspace

**What you built:** Several screens render extensive implementation, lifecycle, server-truth, or safety explanations directly in normal view.

**What you should have built:** Concise task guidance in the page, with the full documented information catalog behind accessible information controls, help drawers, or advanced sections.

**What you misunderstood:** Including all documentation text on screen is not the same as good contextual help.

**Required correction:** Classify copy as label, helper, warning, empty state, info content, or advanced diagnostics. Keep only task-critical text permanently visible.

**Acceptance:** Primary actions and fields dominate the visual hierarchy; help remains fully accessible on demand.

## 7. P0/P1 — Functional and backend-integration defects that invalidate UI completeness

### Finding F-01 — Several Create Package “jobs” are completed synchronously as stubs

**What you built:** `_enqueue_stub_job()` inserts a durable job row and immediately marks it succeeded in the request transaction. Pre-Check/candidate documentation in the command file still calls this a V1 stub even though deterministic generator modules now exist.

**What you should have built:** A real queued worker lifecycle for work presented as asynchronous: queued, running, succeeded/failed/cancelled, durable diagnostics, retry, and reconnect-safe UI.

**What you misunderstood:** Persisting a succeeded job record is not executing a durable job.

**Required correction:** Route expensive Pre-Check, generation, validation, baseline, import/export, and other advertised asynchronous work through real workers. Remove stale stub comments only after the real path is active.

**Acceptance:** Closing the browser does not affect execution; worker failure creates a durable failed state; the UI never displays success before work actually completes.

### Finding F-02 — Natural-language package generation remains a skeleton boundary

**What you built:** The generator states that description-based work can produce a deterministic skeleton and may remain non-executable when no native primitive is resolved; a real arbitrary-code/LLM generator is Future Dev.

**What you should have built:** The product must clearly distinguish a validated executable package candidate from a design skeleton. It must not market both as equivalent Create Package success.

**What you misunderstood:** A reproducible manifest/hash and a loadable executable implementation are different completion levels.

**Required correction:** Represent `design_skeleton`, `generated_candidate`, `validated_executable`, and `published` as distinct states. Block C.D.P/approval when executable evidence is missing and communicate the next action.

**Acceptance:** No non-executable skeleton can be published or used by Ready Check.

### Finding F-03 — Multi-item portfolio execution is not a genuine unified-clock simulation

**What you built:** The engine composes independently replayed strategies in deterministic pin order and explicitly warns that the portfolio curve is sequential, not a unified-clock valuation. NET conflict behavior is conservatively substituted because genuine co-simulation is deferred.

**What you should have built:** Shared-capital allocation, exposure caps, cross-item conflicts, hedging, contribution, and portfolio equity require one event clock across all participating data sources.

**What you misunderstood:** Combining completed per-strategy PnL streams is not the same as executing a portfolio.

**Required correction:** Implement a unified-clock scheduler with deterministic event ordering, shared cash/equity, simultaneous exposure, cross-item rules, and full trace. Until then, block modes whose semantics require it rather than presenting an approximate portfolio result as complete.

**Acceptance:** A multi-strategy scenario with overlapping positions produces results from shared chronological state, not concatenated independent runs.

### Finding F-04 — Breakout-proxy code and truth statements remain contradictory

**What you built:** The worker now rejects an unresolved/empty indicator plan, but the domain-engine header, fallback branch, diagnostics, frontend warning mapper, and tests still describe and support `deterministic_bar_breakout_proxy_v1` under some call paths.

**What you should have built:** No production-callable path may silently or accidentally produce metrics from a strategy the user did not define.

**What you misunderstood:** Adding a worker guard does not make contradictory engine behavior and documentation harmless.

**Required correction:** Trace every engine caller. Remove the fallback from production paths or make it an explicit test-only fixture. Replace stale engine documentation and tests with fail-closed assertions. Preserve an explicit built-in breakout strategy only if the user selects it as a real strategy type.

**Acceptance:** An unresolved or empty trigger plan cannot materialize a Result.

### Finding F-05 — Unsupported financial options remain part of the editable contract

**What you built:** Ready Check and engine warnings still reference unsupported sizing, leverage, filters, conflict handling, best-bid/ask, partial-fill, trailing-stop, and other modes.

**What you should have built:** The form contract and executable engine contract must be the same for active Production V1 options.

**What you misunderstood:** A blocker is a safe temporary boundary, not completion of the documented feature.

**Required correction:** Maintain a machine-readable capability matrix consumed by the UI, Ready Check, and tests. Implement required V1 modes; visibly disable future modes.

**Acceptance:** There is no enabled option that only fails later with “not modelled.”

### Finding F-06 — Result artifacts are not complete enough for the promised analysis UI

**What you built:** The backend can produce summary, ledger, and diagnostics artifacts, but the UI explicitly lacks the price/marker chart and equity/drawdown/exposure visualizations.

**What you should have built:** Immutable artifact endpoints and paginated/lazy visual renderers aligned to the result manifest.

**What you misunderstood:** Exportable data does not complete an on-screen analysis requirement.

**Required correction:** Define chart artifact schemas, timestamps, downsampling policy, marker linkage, null behavior, and renderer tests. Do not recompute canonical financial metrics in the browser.

**Acceptance:** The same result ID renders the same curves and markers after reload.

### Finding F-07 — Raw IDs are still normal presentation data on several pages

**What you built:** Results History, Pre-Check, Portfolio, Package Library, Rationale assignments, Panel Logs, and advanced Mainboard surfaces use raw IDs as primary visible values.

**What you should have built:** Each query DTO needs both stable identity and a policy-safe human display summary.

**What you misunderstood:** Removing editable ID inputs did not finish the humanization task.

**Required correction:** Add display DTOs at query boundaries; never reconstruct names from IDs in the browser. Keep copyable IDs in advanced detail for support/audit.

**Acceptance:** No common task requires recognizing an opaque identifier.

### Finding F-08 — The web container health check is unreliable on the local stack

**What you built:** The web service health check uses `http://localhost:80/`. In the current container this can resolve to IPv6 while nginx serves IPv4, marking the container unhealthy even though the host page works.

**What you should have built:** A deterministic container-local health probe.

**What you misunderstood:** Host reachability and Docker health status can disagree because of address-family resolution.

**Required correction:** Use `http://127.0.0.1:80/` or configure nginx/listener resolution consistently. Add the health state to CI acceptance.

**Acceptance:** `docker compose ps` reports the web container healthy on the documented Windows local setup.

### Finding F-09 — Acceptance and README claims are stronger than the implementation evidence

**What you built:** README and acceptance materials describe a full 24-screen app and near-closed acceptance while the same repository records missing deep visual review, accessibility defects, placeholders, synchronous stub jobs, sequential portfolio composition, and missing result renderers.

**What you should have built:** Status documents that distinguish route existence, UI binding, functional completion, prototype fidelity, financial correctness, accessibility, and product-owner acceptance.

**What you misunderstood:** “Implemented” is not a single binary state for a system of this complexity.

**Required correction:** Replace broad completion claims with a requirement matrix and honest boundaries. Do not count Future Dev placeholders as active capability completion.

**Acceptance:** Every completion percentage or claim can be recomputed from signed requirements and test evidence.

## 8. Complete page-document coverage matrix

This table prevents a partially reviewed page from being silently treated as approved. `Preserve` means the current production behavior is valuable; it does not waive the remaining visual-fidelity evidence.

| Page document | Current audit disposition | Binding next action |
|---|---|---|
| 01 Mainboard | Core inline behavior now exists, but hierarchy and row presentation still diverge materially. | Implement M-01, M-02, M-10, and M-11; obtain signed shell screenshots. |
| 02 Strategy Details | Ten-area/three-column structure exists, but density, technical content, and executable-option parity remain incomplete. | Implement M-03 through M-05; preserve immutable revision/pin logic. |
| 03 Add Outsource Signal | Mainboard action is substantially corrected; the standalone chooser is over-weighted in acceptance. | Preserve inline dispatch; reclassify the route and tests under P-01. |
| 04 Trading Signal | Inline host and real ingest exist, but the panel is an oversized workbench and lacks the complete canonical action set. | Implement M-06, M-08, and M-09. |
| 05 Trade Log | Inline host and real ingest exist, with the same composition problem as Trading Signal. | Implement M-07 through M-09. |
| 06 Add Package / Create Package | Strategy-only Add Package is correct; Create Package layout, display vocabulary, persistence, and worker truth remain incomplete. | Preserve the package-kind boundary; implement M-12, P-03 through P-05, F-01, and F-02. |
| 07 Pre-Check | Real immutable scan logic and the Create Package overlay exist; acceptance emphasizes the wrong standalone surface. | Implement P-02 and real worker lifecycle where the operation is asynchronous. |
| 08 Package Library | Strong lifecycle/query foundation; required catalog facets, stable visual sections, and human vocabulary remain incomplete. | Implement P-06 and P-07. |
| 09 Embedded System Packages | Resolver semantics are substantial, but the primary scoped Package Library presentation is missing. | Implement P-08; preserve trust/evidence/deprecation behavior as advanced detail. |
| 10 Rationale Families | Card/editor model is broadly aligned; assignment rows and seeded display identity remain technical. | Implement P-16 and complete equivalent-state visual approval. |
| 11 Market Data | Real add/upload/analyze/lifecycle workflow now exists; registry digest and display labels are incomplete. | Implement P-09; preserve the real file path and approved-revision semantics. |
| 12 Research Data | Backend dependency, timing, upload, and approval foundations are meaningful; default screen hierarchy is wrong. | Implement P-10; keep server-backed Approved Market Data binding. |
| 13 Portfolio / Equity Allocation | Four-card editor exists; raw identities and non-unified execution undermine the intended experience and semantics. | Implement P-11 and F-03. |
| 14 Backtest Ready Check | Real readiness report exists; prototype acceptance is performed against the technical standalone route. | Implement M-10 and equivalent-state Mainboard modal tests. |
| 15 RUN and Backtest Results | Real async run/result foundations and inline summary exist; primary capture is wrong and detail visualization is incomplete. | Implement M-11, P-13, F-04, F-05, and F-06. |
| 16 Results History | Immutable server history, sort, compare, pagination, and soft-delete support are substantial; collapsed summary is not the specified digest. | Implement P-12; preserve server-side sorting and immutable metrics. |
| 17 Arrange Metrics | Apply, Lock, and Unlock behavior is present and correctly presentation-only. | Preserve semantics; perform equivalent populated/locked prototype comparison and reduce unapproved copy/layout drift. |
| 18 Analysis Lab | Production task/control/history capability is richer than the prototype, but current visual comparison uses non-equivalent empty/inactive state. | Preserve durable Agent controls; compare an equivalent active task and move technical history behind secondary hierarchy where needed. |
| 19 Panel Management / Logs | Management is technically extensive; machine vocabulary remains. Logs replaced the primary backtest-log question with an event/audit console. | Implement P-14 and P-15; preserve immutable audit as a secondary technical view. |
| 20 Trash | Restore/purge/OCC/re-auth foundations are close to the Production contract. | Preserve lifecycle behavior; complete exact row/filter/action visual review and accessibility remediation. |
| 21 User Manual | Two-column reader, stream, search, and Admin publishing foundations are present. | Preserve canonical server content; verify baseline completeness, equivalent prototype layout, anchors, and accessibility. Do not restore obsolete package terminology. |
| 22 Future Dev | Placeholder/capability gating is largely correct for inactive capabilities. | Do not count placeholders as active feature completion; add missing prototype/state evidence and keep operational controls gated. |

Additional production routes such as Instrument Registry, Admin Provisioning, and System Metrics are legitimate production additions, but they are outside the 22-page prototype. Keep them secondary, use the same shell/tokens, test them independently, and never use them to inflate prototype-completion claims.

## 9. Evidence index Claude must use

| Evidence | Why it matters |
|---|---|
| `docs/spec/index_guncellenmis_duzeltilmis_v18.html` | Final prototype geometry, handlers, visible labels, row expansion, modals, and page compositions. |
| `docs/spec/01_...md` through `docs/spec/22_...md` | Production V1 corrections to prototype-only persistence, terminology, policy, and domain behavior. |
| `docs/implementation/v18_visual_deviations.md` | Repository-authored list of known visual differences; `PO-APPROVE` entries remain unsigned. |
| `docs/implementation/v18_final_acceptance.md` | Explicit evidence that D-1 through D-9 are unsigned, ten pages lack deep review, serious accessibility findings remain, and manual accessibility is incomplete. |
| `frontend/e2e/screenshots/prototype/*--1440.png` | Twenty captured prototype states. These are references, not complete traceability by themselves. |
| `frontend/e2e/screenshots/baseline/*/normal--1440.png` | Current application captures. Several are not state-equivalent to the prototype reference. |
| `frontend/e2e/utils/screenshotMatrix.ts` | Proof that documents 02/04/05 are mapped to standalone routes and the route target count is 23. |
| `frontend/e2e/specs/11-visual-regression.spec.ts` | Proof that the tests named `*-inline` navigate to standalone routes and compare against current-app snapshots. |
| `frontend/e2e/specs/12-prototype-capture.spec.ts` | Correct prototype invocations for inline Strategy/Signal/Log, Ready modal, and inline Run result. Use these to build equivalent current journeys. |
| `frontend/e2e/a11y-report/axe-summary.txt` | Page-by-page serious accessibility evidence. |
| `frontend/src/styles/global.css` and the final prototype CSS | Direct evidence of Strategy editor density, spacing, dividers, typography, and responsive differences. |
| `frontend/src/pages/Mainboard.tsx` | Current inline rows, Add model, technical composition UI, Ready/RUN integration, and transient external drafts. |
| `frontend/src/components/AddPackagePopover.tsx` | Correct Production V1 strategy-only package derivation boundary. |
| `frontend/src/app/nav.ts` | Misleading legacy Trading Signal/Trade Log Package Library entries and Future Dev routing. |
| `frontend/src/pages/CreatePackage.tsx` | Current layout and explicit statement that visible compatibility/link fields are not sent to the backend. |
| `frontend/src/pages/Library.tsx` | Explicit omission of Market/Timeframe facets and current machine-value presentation. |
| `frontend/src/pages/Portfolio.tsx` | Primary rendering of workspace/composition item IDs. |
| `frontend/src/pages/ResultsHistory.tsx` | Current collapsed-row identity/actions and expanded-only metric details. |
| `frontend/src/pages/PanelLogs.tsx` | Generic event projection and raw audit stream that currently replace the primary backtest-log view. |
| `frontend/src/components/ResultDetail.tsx` | Explicit missing chart and AI Review renderers. |
| `backend/src/entropia/application/commands/create_package.py` | `_enqueue_stub_job()` and synchronous succeeded-job behavior. |
| `backend/src/entropia/domain/create_package/generator.py` | Deterministic generator strengths and the honest description/arbitrary-generation boundary. |
| `backend/src/entropia/application/jobs/backtest_engine.py` | Current worker guard against unresolved indicator plans and per-strategy replay/composition flow. |
| `backend/src/entropia/domain/backtest/engine.py` | Remaining proxy branches, unsupported behavior, sequential composition, and unified-clock warning. |
| `docker-compose.yml` | Current localhost-based web health probe. |

## 10. Required implementation order

The order matters. Do not start by polishing isolated pages while the acceptance system still validates the wrong screens.

### Phase 0 — Repair the truth system

1. Create the visual traceability matrix.
2. Reclassify unsigned `PO-APPROVE` items as open.
3. Fix equivalent-state fixtures and screenshot journeys.
4. Separate current-regression tests from prototype-fidelity tests.
5. Establish an approved V18 token set and screenshot reference set.

**Exit gate:** The test suite can detect the difference between a standalone Strategy page and an expanded Strategy row on Mainboard.

### Phase 1 — Lock the Mainboard product shell

1. Restore the prototype's primary visual hierarchy.
2. Compact collapsed rows and humanize their identity.
3. Move composition metadata into advanced disclosure.
4. Approve desktop and mobile empty/collapsed states.

**Exit gate:** Product owner approves the shell before inner forms are polished.

### Phase 2 — Finish Strategy Details

1. Match compact three-column geometry and ten-section organization.
2. Remove primary-view technical identity.
3. Reconcile every visible option with engine capability.
4. Approve default, populated, validation-error, and saved states.

**Exit gate:** Every selectable active option is executable and traced.

### Phase 3 — Finish Trading Signal and Trade Log inline editors

1. Build compact inline compositions rather than embedding whole workbenches.
2. Remove duplicated field/registry regions.
3. Add canonical Save/Clear/Export actions.
4. Preserve event-time/available-time, import, validation, revision, and Mainboard pin semantics.

**Exit gate:** Both end-to-end journeys complete on `/` and visually match their prototype grouping.

### Phase 4 — Correct package and data information architecture

1. Create Package layout, human labels, and missing persisted fields.
2. Pre-Check overlay as primary, artifact route as secondary.
3. Package Library market/timeframe projection and stable categories.
4. Scoped Embedded System catalog plus advanced resolver management.
5. Market Data list digest and Research Data registry-first flow.

**Exit gate:** No normal package/data workflow exposes machine values or loses a prototype-required filter/column.

### Phase 5 — Correct Portfolio, Ready/RUN, Results, and admin pages

1. Humanize Portfolio items and complete unified-clock behavior or block unsupported modes.
2. Approve Ready modal and Mainboard RUN/result states.
3. Add history metric digest and real result charts.
4. Restore backtest-log primary view in Panel Logs.
5. Humanize management/rationale tables.

**Exit gate:** The complete product loop is understandable without visiting a technical route.

### Phase 6 — Close quality and operational gaps

1. Replace synchronous stub jobs with real workers.
2. Eliminate contradictory proxy behavior.
3. Resolve serious accessibility findings and complete manual audits.
4. Fix Docker web health.
5. Rewrite status/README claims to match evidence.

**Exit gate:** No P0/P1 finding remains open and all signed acceptance evidence is reproducible from a clean stack.

## 11. Required per-finding completion report from Claude Code

For every finding above, Claude Code must return:

```text
Finding ID:
Status: Not Started | In Progress | Blocked | Complete
Files changed:
Database/API changes:
Migration/backfill:
Unit tests:
Integration tests:
Browser E2E journey:
Prototype/current screenshots:
Accessibility evidence:
Known limitations:
Approved deviation reference:
```

`Complete` is prohibited when any field is omitted for a requirement that needs it.

## 12. Definition of done

The remediation is done only when all of the following are true:

- The Mainboard is visibly the central working surface.
- Strategy, Trading Signal, and Trade Log are compact horizontal rows that expand inline.
- Strategy Details contains all ten documented areas in the approved compact three-column design.
- Trading Signal and Trade Log remain external working objects, not Package Library package kinds.
- Add Package remains a real Strategy Package selector.
- Ready Check opens in the Mainboard context and produces an understandable Passed/Failed/Warnings report.
- RUN uses the validated immutable snapshot and the latest succeeded result appears inline.
- Every active saved financial option is actually executed and represented in decision trace and result artifacts.
- Multi-item portfolio behavior is either genuine unified-clock execution or visibly blocked for modes requiring it.
- Market/Research ingest and package workflows are usable without raw IDs, hashes, object keys, machine enums, or JSON.
- Package Library, Embedded System Packages, Market Data, Research Data, Results History, and Panel Logs preserve their documented visual information architecture.
- Result charts use immutable backend artifacts and no fake data.
- Prototype-fidelity tests compare equivalent states and have signed references.
- All unapproved serious accessibility findings are closed.
- No unsigned deviation is counted as accepted.
- README and project status describe the remaining boundaries honestly.

## 13. Final direction to Claude

Do not restart the repository from zero. The backend, domain, revision, audit, job, authorization, and E2E foundations contain substantial reusable work. Refactor the presentation composition and complete the missing integrations on top of those foundations.

Do not solve this by merely restyling the standalone pages. The central correction is architectural at the UI-composition level: the production capabilities must be presented through the prototype's Mainboard-centered product model.

For every proposed completion, answer these questions before writing `Complete`:

1. Did you implement the same user intent in the same visual context as the prototype?
2. Did you apply the Production V1 canonical correction without losing that visual context?
3. Can a normal user complete the task without technical IDs, machine enums, raw JSON, or a separate administration route?
4. Does the backend execute exactly what the UI allows the user to save?
5. Does an equivalent-state browser test and an approved side-by-side screenshot prove it?

If any answer is no, the item is not complete.
