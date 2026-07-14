# Entropia V18 - Claude Code Implementation Specification

**Document type:** Binding implementation and acceptance specification  
**Version:** 1.0  
**Date:** 14 July 2026  
**Audience:** Claude Code and the engineering team responsible for implementing Entropia V18  
**Status:** Every requirement in this document is required unless the product owner explicitly approves a written exception.

## 1. Primary objective

Bring the current Entropia codebase into full functional, technical, visual, and interaction-level compliance with the V18 product documentation and prototype.

This is not a cosmetic refactor. The current application contains strong infrastructure, data-model, revision, audit, lifecycle, job, and API foundations, but several core product workflows and financial-engine behaviors do not match the required product. The implementation must correct the underlying architecture and behavior, not merely make the current screens look similar.

The target product model is:

`Mainboard -> horizontal object row -> type-specific inline editor -> Ready Check -> RUN -> inline Result`

The target must not be replaced by:

`Separate route -> generic CRUD cards -> infrastructure identifiers/raw JSON -> separate control pages`

## 2. Mandatory source material

Before changing code, read the following material in full:

1. `Entropia_V18_Master_Technical_Reference_v1_0.docx`
2. `Entropia_V18_Sayfa_Bazli_Dokumantasyon_Handoff_ve_Calisma_Standardi_v1_1.docx`
3. `2.3. POSITION ENTRY LOGIC.docx`
4. All 22 page specifications under `docs/spec/`
5. The V18 prototype HTML stored with the specifications
6. This implementation specification

Do not infer requirements only from the current code. The existing implementation is the subject of remediation and is not the source of truth.

If two authoritative documents conflict in a way that changes financial results, data semantics, security, workflow, or information architecture, stop that specific task and record the conflict for product-owner resolution. Do not invent a behavior silently.

## 3. Claude Code execution rules

1. Work by requirement ID. The required inventory is F-01 through F-25 and UI-01 through UI-22.
2. Create and maintain a traceability file at `docs/implementation/entropia_v18_remediation_status.md`. For every requirement, record:
   - Status: Not Started, In Progress, Blocked, or Complete
   - Files changed
   - Migrations or data transformations
   - Tests added or updated
   - Acceptance evidence
   - Any approved deviation
3. Do not mark a requirement complete because a component, route, button, API, schema field, or placeholder exists. Completion requires working end-to-end behavior and passing acceptance tests.
4. Do not implement fake success states, placeholder business logic, hard-coded production values, silent fallbacks, or test-only shortcuts.
5. Do not ask normal users to provide infrastructure data such as root IDs, revision IDs, content hashes, object keys, SHA digests, byte sizes, or raw JSON.
6. Unsupported or unresolved financial behavior must fail closed. Never substitute a different strategy, order model, sizing model, dataset, or risk rule.
7. Every setting that can be saved and that affects a financial result must be executed by the engine and represented in the decision trace.
8. Preserve the valid existing foundations: root/revision/snapshot semantics, immutable manifests, audit/outbox records, durable jobs, lifecycle history, role/policy enforcement, result history, comparison, and export artifacts.
9. Use repository-relative paths in code, tests, documentation, and reports. Do not introduce machine-specific absolute paths.
10. Preserve backward compatibility only where it does not contradict the V18 contract. If migration is required, add an explicit migration and document the transformation.
11. After each requirement or tightly coupled requirement group:
    - Run focused unit tests.
    - Run relevant integration tests.
    - Run the affected browser E2E journey.
    - Update the traceability file.
12. Do not rewrite or weaken tests merely to make the suite green. Tests that currently protect incorrect behavior must be replaced with tests for the documented behavior.

## 4. Priority definitions

- **P0 - Blocker:** Financial correctness, data ingestion, core Mainboard workflow, security, or a required end-to-end journey is broken.
- **P1 - Critical:** The primary product interaction model is violated or a major screen cannot be used correctly by a normal user.
- **P2 - Major:** The screen is partly usable but its required layout, interaction, or important information is missing.
- **P3 - Completion:** Testing, documentation, consistency, and product-readiness work required before final acceptance.

# PART I - FUNCTIONAL AND TECHNICAL REMEDIATION

## F-01 - Implement real Market Data file upload - P0

### Required implementation

- Add a native file chooser to `frontend/src/pages/MarketData.tsx` and implement the upload workflow defined by the Market Data specification.
- Transfer the actual file bytes through the API/upload service into object storage.
- Generate object key, SHA-256 digest, byte size, and content type automatically. Do not request these values from the user.
- Show progress, cancellation, retry, failure, and successful-completion states.
- Persist the dataset metadata only after object-storage write and integrity verification succeed.
- Make the upload idempotent and safe to retry.

### Acceptance criteria

- A user can select a supported file from the local machine and upload it without entering storage metadata.
- The exact bytes exist in object storage, the digest is verified, and the dataset revision points to the correct object.
- Unsupported type, excessive size, interrupted connection, storage failure, and digest mismatch produce clear user-facing errors.
- Unit, API integration, object-storage integration, and browser E2E tests pass.

### Relevant code

- `frontend/src/pages/MarketData.tsx`
- `backend/src/entropia/application/commands/market_data.py`
- Market Data page specification under `docs/spec/`

## F-02 - Implement real Research Data file upload - P0

### Required implementation

- Replace the pre-uploaded-object-key workflow in `frontend/src/pages/ResearchData.tsx` with native file selection and real upload.
- Integrate Approved Market Data dependency selection, time-alignment metadata, provenance, available-time semantics, and validation.
- Generate all object-storage metadata internally.

### Acceptance criteria

- A normal user can create Research Data from a local file without knowing a MinIO key or hash.
- File bytes, provenance, available-time fields, and the linked Market Data revision are stored correctly.
- Invalid dependency, schema, alignment, or upload state blocks completion with a clear explanation.

## F-03 - Replace all simulated file inputs with real file choosers - P0

### Required implementation

- Replace TXT/CSV content textareas in Trading Signal and Trade Log with real file selection.
- Replace manual filename/content entry in User Manual upload with real document selection.
- Add real TradingView baseline CSV selection to Create Package.
- Validate extension, MIME type, encoding, size, and schema on the backend as well as the frontend.

### Acceptance criteria

- Trading Signal, Trade Log, User Manual, and Create Package baseline ingestion all use native file selection.
- Selection, upload, parsing, validation, error handling, and persistence are verified in browser E2E tests.
- Pasting an entire file into a textarea is not a required workflow.

## F-04 - Execute the complete Mainboard composition in backtests - P0

### Required implementation

- Stop selecting only the first enabled Strategy.
- Execute every enabled Strategy, Trading Signal, and Trade Log in the immutable Mainboard snapshot according to the documented ordering and conflict rules.
- Pin every participating revision in the run manifest.
- Make the contribution of every object traceable in decisions and results.

### Acceptance criteria

- A Mainboard containing multiple enabled strategies includes all of them in the simulation and financial result.
- Enabled Trading Signal and Trade Log objects affect execution where defined.
- Disabled objects do not affect results.
- Ordering and conflict resolution are deterministic and covered by integration tests.

### Relevant code

- `backend/src/entropia/application/jobs/backtest_engine.py`
- `backend/src/entropia/domain/backtest/engine.py`
- RUN and Backtest Results specification under `docs/spec/`

## F-05 - Apply the selected date range and instrument to engine input - P0

### Required implementation

- Pass `backtest_range` into the worker and engine.
- Physically filter the bar stream by start time, end time, and `instrument_id`.
- In multi-instrument datasets, process only the selected instrument.
- Implement documented timezone and boundary-bar semantics.
- Reject an empty or invalid filtered range explicitly.

### Acceptance criteria

- Different selected ranges over the same dataset process only their respective bars.
- Bars from unselected instruments never enter decisions, positions, metrics, or artifacts.
- Manifest range/instrument values match the data actually processed.

## F-06 - Remove the unresolved-indicator breakout fallback - P0

### Required implementation

- Remove any silent substitution with `deterministic_bar_breakout_proxy_v1` or another proxy when an Indicator Package or dependency cannot be resolved.
- Make unresolved dependencies Ready Check blockers.
- Make the engine fail fast even if a stale or bypassed readiness state reaches the worker.

### Acceptance criteria

- RUN cannot start with an unresolved required package.
- Metrics from a strategy the user did not select can never be produced.
- The blocker identifies the missing package/revision and the required resolution action.

## F-07 - Execute every saved Strategy Details setting - P0

### Required implementation

Implement the documented engine behavior for all saved settings, including:

- Limit orders, order validity, and unfilled policy
- Partial fills
- Entry and exit execution timing
- Funding and Research Data available-time behavior
- Scaling Logic
- Restrictions and Filters
- Overlap, stacking, and hedge rules
- `close_percentage` and partial-close aftermath
- Signal-strength adjustment
- Leverage mode
- Trailing-stop `lock_in_percentage`

Remove the current assumptions that entries always occur at the current candle close and exits are normally full closes.

### Acceptance criteria

- Every setting has at least one positive and one negative engine test.
- The saved revision value, immutable manifest, engine behavior, result artifact, and decision trace agree.
- An unsupported value is a blocker, not an ignored field.

## F-08 - Implement Logic-Based Stop end to end - P0

### Required implementation

- Add documented `logic_blocks` and stop-combination mode fields to the backend strategy schema.
- Use the same model in the frontend form, validation, revision serialization, readiness checks, and engine.
- Implement AND/OR, priority, and interaction behavior in the canonical order defined by the technical reference.

### Acceptance criteria

- A user can create, save, reopen, edit, and execute a Logic-Based Stop.
- Multiple stop types combine exactly as documented.
- No “backend does not implement this” placeholder remains.

## F-09 - Fail closed for unsupported position sizing - P0

### Required implementation

- Block RUN when `custom_formula`, Kelly, or another sizing model is unsupported or invalid.
- Never convert an unsupported setting into all-in notional by dividing all available equity by price.
- Implement valid Kelly/custom-formula behavior according to the reference, or expose a Ready Check blocker until it is implemented.

### Acceptance criteria

- An unsupported sizing setting cannot open a position.
- Existing tests that expect all-in fallback behavior are replaced with fail-closed tests.
- Error and blocker output identify the invalid sizing configuration.

## F-10 - Produce a complete decision trace - P1

### Required implementation

- Expand trace output beyond `entry_signal` and aggregated `filtered_no_entry` records.
- Record entry, exit, stop, scaling, evaluated rule ID, every condition result, restriction, conflict decision, fill, partial fill, and partial-close step.
- Link trace entries to object revisions, bar/event time, position, order, and run manifest.

### Acceptance criteria

- A reviewer can reconstruct why every position was opened, not opened, modified, and closed.
- The same manifest produces a deterministic decision sequence.
- Trace export and UI diagnostics preserve the same information.

## F-11 - Use Research Data and Funding in the backtest engine - P0

### Required implementation

- Read and use Research Data revisions during the backtest instead of storing them only as provenance.
- Implement available-time joins and prevent future leakage.
- Apply Funding data to position cost and every documented rule that depends on it.

### Acceptance criteria

- Research-dependent conditions cannot use information before its available time.
- Funding-enabled and funding-disabled scenarios produce different, verifiable results where expected.
- Every used data revision is pinned in the run manifest.

## F-12 - Complete the Create Package frontend lifecycle - P0

### Required implementation

Connect the frontend to all required backend transitions:

- Run Validation Tests
- Upload baseline CSV
- Parse baseline
- View validation report
- Request Revision
- Confirm eligibility for approval
- Approve and publish

The UI must expose only actions allowed by the current lifecycle state.

### Acceptance criteria

- A draft cannot call approval directly.
- Buttons, status indicators, and disabled states follow the backend state machine.
- A user can complete the full lifecycle without an unexpected `VALIDATION_REQUIRED` dead end.

## F-13 - Execute every required package validation - P0

### Required implementation

- Implement real syntax, runtime, Market Data, repaint/future-leak, baseline comparison, and all other required validation checks in durable workers.
- Do not treat `not_executed` as passed.
- Do not allow `eligible_for_approval` until every mandatory check has completed successfully.

### Acceptance criteria

- All seven mandatory checks produce real output, logs, status, and artifacts.
- Any failed, blocked, or not-executed mandatory check prevents an overall passed result.
- Repaint/future-leak and baseline differences are visible in the validation report.

## F-14 - Implement real candidate/package generation - P1

### Required implementation

- Replace the V1 stub that generates only a manifest/hash.
- Produce a loadable package implementation, contract, dependency list, test draft, and validation inputs from the approved request.
- Store the generated candidate as an immutable revision and submit it to validation.
- Sandbox code generation and execution appropriately.

### Acceptance criteria

- The generated candidate can be loaded by the resolver and executed in the validation sandbox.
- Generation inputs, outputs, dependencies, and provenance are traceable.
- Empty skeletons, hashes without implementation, or non-executable output cannot enter approval.

## F-15 - Replace the Mainboard technical JSON editor with the product workflow - P0

### Required implementation

- Remove generic “Add work object,” object kind, and raw JSON payload from the normal user flow.
- Provide separate Add Strategy, Add Package, and Add Outsource Signal actions as defined by the prototype.
- Use user-facing selectors for revision selection. Never require manual `wor_...` IDs.

### Acceptance criteria

- A user can add and edit a Strategy without understanding JSON, root IDs, or revision IDs.
- The new object appears as a horizontal Mainboard row and opens its type-specific inline editor.

## F-16 - Bind RUN availability to real readiness - P0

### Required implementation

- Render RUN as genuinely disabled/locked until a current Ready Check passes.
- Use the same readiness projection for visual state, keyboard interaction, and backend authorization.
- Do not navigate to a RUN route when the action is unavailable.

### Acceptance criteria

- RUN cannot be triggered while unchecked, stale, failed, or blocked.
- RUN unlocks automatically after a valid readiness result and relocks when relevant inputs change.

## F-17 - Show required headline metrics on Mainboard - P1

### Required implementation

- Consume the backend `headline` projection in the frontend.
- Show Net Profit, Max Drawdown, Win Rate, Profit Factor, and ROMAD in the inline result summary.
- Preserve symbol, timeframe, trade count, and date information.

### Acceptance criteria

- Values match the result detail and exported artifact.
- Missing values render an explicit `N/A` state rather than disappearing.

## F-18 - Make Strategy drafts durable and discoverable - P1

### Required implementation

- Remove dependence on retaining a `?draft=` URL.
- Add a query and UI for listing, opening, attaching, and deleting unattached drafts.
- Preserve ownership, permissions, revision history, and audit records.

### Acceptance criteria

- A user can close the browser, sign in again, and find an unattached draft.
- Drafts cannot leak across users or roles.

## F-19 - Remove infrastructure IDs and raw JSON from Strategy Details - P1

### Required implementation

- Replace Market, Research, and Funding root/revision/hash entry with user-facing pickers.
- Implement documented forms for parameter overrides, reference chains, and restrictions.
- Raw JSON may exist only as an optional, validated advanced view for authorized technical users; it cannot be the primary workflow.

### Acceptance criteria

- A normal user can create a valid Strategy without entering any raw ID or JSON.
- Picker selections correctly pin immutable revisions.

## F-20 - Implement a real autonomous Alpha Agent executor - P1

### Required implementation

- Add a durable executor that claims `QUEUED` tasks created by the coordinator.
- Implement planning, safe tool selection, tool execution, backtest execution, result evaluation, hypothesis/output creation, and lifecycle transitions.
- Add retry, idempotency, timeout, cancellation, audit, and permission boundaries.

### Acceptance criteria

- A directive completes end to end without test code manually calling `dispatch_tool_call` for each step.
- Every step, tool call, result, failure, and state transition is visible in Analysis Lab and audit history.

## F-21 - Implement real Trash re-authentication - P0

### Required implementation

- Do not accept any non-empty string as re-authentication proof.
- Re-verify the active user through the configured identity provider or authentication backend.
- Bind proof to user, action, and a short expiration period. Prevent replay.

### Acceptance criteria

- An incorrect password or arbitrary text cannot authorize permanent deletion.
- Successful re-authentication, failure, expiration, lockout, replay, and audit scenarios are tested.

## F-22 - Complete the production authentication profile - P0

### Required implementation

- Restrict `AUTH_MODE=dev` to an explicitly named development profile.
- Production and production-like test profiles must use real login, session/token validation, role, and policy enforcement.
- Reject user-controlled `X-Actor-Id` identity spoofing in production profiles.

### Acceptance criteria

- Production configuration cannot impersonate an actor through the development header.
- Login, logout, session expiration, role denial, and audit are verified through browser E2E tests.

## F-23 - Add a real browser E2E suite - P0

### Required implementation

- Add Playwright or an equivalent real-browser framework.
- Run against the Docker stack with the real API, database, workers, and test object storage.
- Cover at minimum: authentication, Market Data upload, Research Data upload, Strategy creation, Mainboard attachment, Ready Check, RUN, inline result, Create Package lifecycle, and Trash re-authentication.

### Acceptance criteria

- The suite does not depend only on mocked `fetch` calls.
- CI runs are repeatable and publish screenshot, video, or trace artifacts for failures.

## F-24 - Replace tests that approve incorrect behavior - P0

### Required implementation

- Remove or rewrite tests that assert breakout fallback or `custom_formula -> all-in notional` as expected behavior.
- Name tests after the documented business rule.
- Add regression tests for every P0 engine correction.

### Acceptance criteria

- The test suite no longer acts as a regression lock for known incorrect behavior.
- Each P0 correction includes a test that fails before the fix and passes after it.

## F-25 - Make README and status documentation truthful - P3

### Required implementation

- Do not claim “Production V1 is complete” until all mandatory requirements and acceptance journeys are complete.
- Update test counts, migration level, supported workflows, and known limitations from verifiable sources.
- Align README status with CI output and the actual migration directory.

### Acceptance criteria

- README, CI, and migration files contain no contradictory counts or status claims.
- Every incomplete feature is explicitly marked as not implemented or blocked.

# PART II - PAGE-BY-PAGE UI AND INTERACTION REMEDIATION

## UI-01 - Mainboard - P0

### Required implementation

- Render every Strategy, Trading Signal, and Trade Log as a long horizontal object row.
- Put an expand/collapse arrow on the right side of the row.
- Expanding a row must render the real type-specific editor, not a technical panel dominated by revision ID, row version, enable/disable, movement, and label fields.
- Implement the prototype Add menu with Strategy, Package, and nested Add Outsource Signal actions.
- Keep Strategy editing, Ready Check, RUN, and Result within the Mainboard working context.

### Acceptance criteria

- A user can expand, edit, validate, save, and collapse an object without changing routes.
- Multiple row states behave predictably.
- Keyboard focus, `aria-expanded`, screen-reader naming, and responsive behavior are tested.

## UI-02 - Strategy Details - P0

### Required implementation

- Make Strategy Details open inside the Strategy row instead of using a separate `/strategy` page as the primary workflow.
- Implement the three-column layout: `SETUP & DATA / DECISION LOGIC / RISK MANAGEMENT`.
- Render all 10 documented subsections in their specified names, order, and grouping inside one large panel.
- Put Save, Cancel, validation, and revision actions in the panel's bottom toolbar.
- Do not replace the documented fields with generic cards or a raw JSON editor.

### Acceptance criteria

- All 10 sections are accessible inside the same expanded panel.
- The panel can be used at the target desktop widths without clipped fields or horizontal page overflow.
- Side-by-side screenshot comparison with the V18 prototype passes product-owner review.

## UI-03 - Add Outsource Signal - P1

### Required implementation

- Do not use a standalone Add Outsource Signal page.
- Implement it as the documented two-option nested submenu in the Mainboard Add/hover menu.
- A choice must create a new Trading Signal or Trade Log row and open it inline.
- Remove the standalone `/outsource-signal` chooser from the primary workflow.

### Acceptance criteria

- The correct new row is created without leaving Mainboard.

## UI-04 - Trading Signal - P1

### Required implementation

- Render the editor as a two-column Mainboard inline panel instead of a long standalone card page.
- Group identity, source data, and bulk import according to the prototype.
- Add a sticky bottom action toolbar and real TXT/CSV file selection.

### Acceptance criteria

- File selection, validation, save, cancel, and panel close all work inside the inline editor.
- Pasting file content into a textarea is not required.

## UI-05 - Trade Log - P1

### Required implementation

- Implement the horizontal Trade Log row and expandable two-column inline workspace.
- Place the real file chooser, monospaced format guide, and bottom action toolbar together as shown in the prototype.
- Remove the standalone vertical card stack and “File content” textarea from the primary flow.

### Acceptance criteria

- A user can upload, validate, and save a Trade Log without leaving Mainboard.

## UI-06 - Add Package and Create Package - P0

### Required implementation

- Implement the small Add Package popover on Mainboard.
- Rebuild Create Package as a two-column CP Agent workspace.
- Left column: request/chat board and draft-file list.
- Right column: Package Status, Baseline, Resolver, Validation Tests, and Library Target.
- Do not substitute a generic “New request / My requests / detail” management layout for the required composition.
- Add real TradingView baseline CSV selection.

### Acceptance criteria

- The complete request, generation, baseline, validation, revision, and publish lifecycle is visible and operable in one coherent workspace.

## UI-07 - Pre-Check - P0

### Required implementation

- Implement Pre-Check as a button, status pill, and accessible overlay modal inside Create Package.
- Do not make a separate route the primary workflow.
- Show passed, blocked, failed, and warning states in direct visual connection with Package Status.

### Acceptance criteria

- The button opens a real keyboard-accessible dialog.
- The user does not need to navigate to a request table and reselect the package.

## UI-08 - Package Library - P2

### Required implementation

- Preserve horizontal package rows and inline expansion.
- Implement the complete six-field filter bar, including Market, Timeframe, and Sort controls.
- Present packages in visually distinct type sections.
- Keep the expanded detail compact; do not turn it into a long technical administration page.

### Acceptance criteria

- Every filter combination works, has defined URL/state behavior, and has an empty-results state.

## UI-09 - Embedded System Packages - P2

### Required implementation

- Complete the dedicated heading, System-scope filters/facets, and expandable resolver rows.
- Move “Propose Resolver” and “Resolve Probe” into a modal, drawer, or controlled secondary action so they do not dominate the catalog.
- Present the resolver catalog before operational forms.

### Acceptance criteria

- Operational forms open only after a user action and do not destroy the catalog/detail hierarchy.

## UI-10 - Rationale Families - P2

### Required implementation

- Build the two-column `Family List / Package Assignment` layout.
- Make the pastel family cards the primary workspace.
- Replace the permanently open large family form with a compact Add row that becomes an inline editor/card.

### Acceptance criteria

- Selecting a family updates the assignment context on the right.
- The two columns stack intentionally on narrow screens.

## UI-11 - Market Data - P0

### Required implementation

- Add the process guide, four-step workflow ribbon, and three summary cards defined by the page specification.
- Make Dataset Setup expandable/collapsible instead of permanently open.
- Integrate the real file upload from F-01.
- Remove object key, digest, and byte-size fields from the user flow.
- Fix responsive layout so fields never extend outside the viewport.

### Acceptance criteria

- No horizontal overflow at 1280, 1440, or 1920 pixel desktop widths.
- Active, complete, blocked, and error states in the four-step ribbon reflect real backend state.

## UI-12 - Research Data - P0

### Required implementation

- Add the five-step workflow strip, Approved Market Data dependency alert, and status legend.
- Build the three-column setup area: `SOURCE & MEANING / TIME & ALIGNMENT / VALIDATION & USE`.
- Integrate the real file upload from F-02.
- Replace the generic “create dataset + registry” presentation with the documented workflow context.

### Acceptance criteria

- A missing or invalid Market Data dependency clearly explains the required action and locks invalid later steps.

## UI-13 - Portfolio / Equity Allocation - P2

### Required implementation

- When the toggle is off, disable the workspace using opacity, grayscale, pointer-event prevention, and correct keyboard behavior.
- Present Calculation Preview and Allocation Check as the documented four-card workspace.
- Add the Add Item picker and Sync confirmation flow.
- Replace endless Composition loading with explicit empty and error states.

### Acceptance criteria

- Allocation controls cannot be changed while disabled.
- Re-enabling restores valid focus and state.

## UI-14 - Backtest Ready Check - P0

### Required implementation

- Keep the fixed lower-right Ready Check/RUN shell.
- Open Ready Check as a modal, not a separate route.
- Use the documented three-column `Passed / Failed / Warnings` layout.
- Bind the status strip to the real readiness result rather than static decoration.

### Acceptance criteria

- The modal updates from the real readiness projection.
- Failed, blocked, or stale readiness keeps RUN locked.

## UI-15 - RUN and Backtest Results - P0

### Required implementation

- Lock/unlock RUN from real readiness state.
- Open progress and results inline below Mainboard rather than making `/backtest/run` the main flow.
- Preserve and integrate the existing useful Metrics, chart areas, Trade List, Diagnostics, and Export sections.

### Acceptance criteria

- `Ready Check -> RUN -> progress -> Result` completes without leaving Mainboard.
- Failure, cancellation, retry, and reopening a historical result are supported in the same work context.

## UI-16 - Results History - P2

### Required implementation

- Preserve blue horizontal result cards, expansion arrows, sorting, pagination, and comparison.
- Add Strategies, Parameters, Data, date information, and immutable manifest summary to the inline expanded panel.
- Do not hide essential provenance only behind a separate View page.

### Acceptance criteria

- A user can verify result identity and production inputs from the inline panel.

## UI-17 - Arrange Metrics - P2

### Required implementation

- Add the always-visible 18-item `Future Version Metrics` reference panel.
- Visually distinguish currently available metrics from future metrics.
- Preserve metric checklist, lock, and profile behavior.

### Acceptance criteria

- A user can understand current and planned metric coverage on the same screen.

## UI-18 - Analysis Lab - P2

### Required implementation

- Preserve the top status bar, Lab Context, Lab Conversation, Work Queue, and Hypothesis/Output Board three-column structure.
- Use the documented title `AGENT WORKSPACE / ANALYSIS LAB`.
- Bind the executor states from F-20 to Work Queue and output updates.

### Acceptance criteria

- Desktop three-column, narrow-screen stacking, and live task updates pass visual and browser tests.

## UI-19 - Panel / Management / Logs - P2

### Required implementation

- Do not route Logs and Management to the same long page.
- Create separate `PANEL / LOGS` and `PANEL / MANAGEMENT` work contexts.
- Place Registered Users, System Actors, and Role Matrix in Management.
- Place Logs, Raw Audit, and relevant filters in Logs.
- Put Operator Recovery behind appropriate permission and a controlled secondary flow.

### Acceptance criteria

- Menu entries have distinct valid destinations.
- Unauthorized roles cannot access restricted data or actions.

## UI-20 - Trash - P2

### Required implementation

- Use the documented `PANEL / TRASH` title and hierarchy.
- Preserve search, type filter, table, restore, and permanent-delete controls.
- Present snapshot content in the documented upper JSON snapshot panel rather than only a generic entry-detail view.
- Use the real re-authentication implementation from F-21.

### Acceptance criteria

- Restore and permanent deletion update list state, snapshot state, lifecycle records, and audit consistently.

## UI-21 - User Manual - P1

### Required implementation

- Build the sticky left `MANUAL DOCUMENTS` sidebar and continuous reader on the right.
- Keep search and section navigation as the primary information architecture.
- Move Publish, Add Text, Upload, and Restore into modal, drawer, or inline tools that do not break the reader layout.
- Use a real document chooser for upload.

### Acceptance criteria

- A user can select sections and continue reading in the same reader.
- Manual filename and full-content entry are not required.

## UI-22 - Future Dev - P1

### Required implementation

- Connect `Graphic View`, `Backtest Review`, `Signal Intelligence`, and Research submenu targets to valid routes.
- Implement Graphic View as the documented introduction plus six static placeholder cards.
- In placeholder state, render no input, table, lifecycle control, or operational form.
- Move Capability Registry, Prepare View Dataset, and Analysis Artifact operations out of the placeholder view. Expose them only when the capability is active and the user has permission.

### Acceptance criteria

- No menu target produces Page Not Found.
- An inactive capability exposes no usable operational control.

# PART III - REQUIRED IMPLEMENTATION ORDER

## Phase 0 - Baseline and traceability

1. Read all mandatory source material.
2. Create `docs/implementation/entropia_v18_remediation_status.md` with every F and UI requirement.
3. Record the current test baseline without modifying expectations.
4. Capture current screenshots of all 22 pages for comparison.
5. Identify schema/data migrations before changing persisted structures.

## Phase 1 - Security and acceptance-test foundation

1. Implement F-21 and F-22.
2. Add the real browser E2E environment in F-23.
3. Correct invalid regression expectations in F-24.

## Phase 2 - Core Mainboard work model

1. Implement UI-01, UI-02, UI-03, UI-04, and UI-05.
2. Complete F-15, F-16, F-17, F-18, and F-19.
3. Implement UI-14 and UI-15 so readiness and result execution remain inline.

## Phase 3 - Data ingestion and temporal correctness

1. Implement F-01, F-02, and F-03.
2. Complete UI-11, UI-12, and UI-21 upload behavior.
3. Implement F-05 and F-11.

## Phase 4 - Backtest engine correctness

1. Implement F-04 and F-06.
2. Implement F-07, F-08, and F-09.
3. Implement F-10 and verify complete traceability.

## Phase 5 - Create Package

1. Implement UI-06 and UI-07.
2. Complete F-12, F-13, and F-14.

## Phase 6 - Agent and supporting pages

1. Implement F-20 and integrate it with UI-18.
2. Complete UI-08, UI-09, UI-10, UI-13, UI-16, UI-17, UI-19, UI-20, and UI-22.

## Phase 7 - Final verification and documentation

1. Run all unit, integration, worker, API, and browser E2E tests.
2. Capture final screenshots for all 22 pages at required desktop and responsive sizes.
3. Compare the final UI with the V18 prototype and page specifications.
4. Complete F-25 only after the implementation and evidence are accurate.

# PART IV - REQUIRED TEST STRATEGY

## Unit tests

- Domain rules, schema validation, state transitions, sizing, order/fill behavior, stop logic, conflict rules, temporal joins, and trace generation.
- Frontend state reducers, component interaction, validation, and accessibility behavior.

## Integration tests

- API plus database revision and lifecycle behavior.
- Worker plus object storage plus manifest behavior.
- Complete backtest runs with multiple Mainboard items, multiple instruments, bounded dates, Research Data, Funding, and all required Strategy settings.
- Create Package generation, baseline parsing, all seven validations, revision requests, approval, and publication.
- Authentication, authorization, Trash re-authentication, and audit.

## Browser E2E tests

At minimum, implement these real-browser journeys:

1. Sign in, session expiration, sign out, and role denial.
2. Upload Market Data and observe progress, processing, validation, and registry state.
3. Upload Research Data and link it to Approved Market Data.
4. Create a Strategy, complete all 10 sections, save it, close the browser, and rediscover the draft.
5. Add Strategy, Trading Signal, and Trade Log rows to Mainboard and edit them inline.
6. Run Ready Check, inspect Passed/Failed/Warnings, and verify RUN locking.
7. Execute a multi-item backtest and inspect the inline result, decision trace, history, comparison, and export.
8. Complete the Create Package request, generation, baseline, validation, revision, approval, and publish lifecycle.
9. Create an Agent directive and observe automatic execution through output creation.
10. Restore a Trash item and permanently delete another item using real re-authentication.
11. Navigate every menu target and verify that no route returns Page Not Found.

## Visual regression and responsive coverage

- Capture all 22 target pages at 1280, 1440, and 1920 pixel desktop widths.
- Add the responsive widths required by the page specifications.
- Compare Mainboard, Strategy Details, Trading Signal, Trade Log, Create Package, Ready Check, RUN/Result, Market Data, and Research Data directly against the prototype.
- Fail tests for clipped controls, horizontal page overflow, overlapping layers, inaccessible dialogs, missing sticky toolbars, or broken inline expansion.

# PART V - DEFINITION OF DONE

The remediation is not complete until all of the following are true:

- Every requirement F-01 through F-25 and UI-01 through UI-22 is marked Complete in the traceability file with code and test evidence.
- No required page has a broken route, Page Not Found response, horizontal overflow, clipped control, or unreachable primary action.
- `Mainboard -> inline object editor -> Ready Check -> RUN -> inline Result` works in a real browser against the full stack.
- Every specified upload flow accepts a real local file and completes storage, validation, and persistence end to end.
- The financial engine applies the selected date, instrument, every enabled Mainboard object, every supported Strategy setting, Research Data available-time, and Funding correctly.
- No silent proxy strategy, ignored financial setting, unsupported-model substitution, or all-in fallback remains.
- Decision trace is sufficient to reconstruct every material trading decision.
- Production authentication and permanent-delete re-authentication perform real verification.
- No mandatory package validation can remain `not_executed` while the package is considered passed or eligible for approval.
- All unit, integration, worker, API, and browser E2E tests pass in CI.
- Visual regression output for all 22 pages is reviewed against the V18 prototype and approved by the product owner.
- README and project status describe only verified functionality.

## Prohibited completion claims

Do not describe the work as complete if any of the following is true:

- Only the frontend is implemented while the backend behavior is missing.
- Only the API exists while the user journey is disconnected.
- A button or screen is present but uses placeholder data or no real transition.
- A setting is saved but ignored by the engine.
- A test passes because it asserts the known incorrect behavior.
- A route exists but does not match the documented interaction model.
- A validation is displayed but not actually executed.
- A security proof is accepted without real authentication.

# PART VI - REQUIRED ENGINEERING HANDOFF

When implementation is ready for review, provide:

1. The completed requirement traceability table mapping every requirement ID to commits/PRs, files, and tests.
2. Migration and data-transformation notes.
3. A concise summary of API, state-model, engine, and frontend architecture changes.
4. Unit, integration, worker, API, and browser E2E test reports.
5. The final screenshot set for all 22 pages.
6. Performance, security, and data-integrity test results relevant to the changed workflows.
7. Updated installation, local development, test, and production deployment instructions.
8. A list of remaining limitations. Any deferred requirement must include explicit written product-owner approval.

## Required Claude Code completion report format

At the end of each implementation phase, report:

```text
Phase:
Completed requirement IDs:
Files changed:
Migrations added:
Tests added or updated:
Commands executed and results:
Browser journeys verified:
Screenshots/artifacts:
Known blockers:
Open product decisions:
Next requirement IDs:
```

Do not provide a generic “implemented” summary. The completion report must be specific enough for another engineer to reproduce and audit the work.
