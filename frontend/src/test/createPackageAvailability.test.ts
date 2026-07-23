import { describe, expect, it } from "vitest";

import {
  approvalBlockReason,
  packageActionAvailability,
  type PackageRequestDetail,
} from "@/lib/createPackage";

// F-12: the lifecycle-action availability is the single source of truth the UI
// gates on. These pure tests pin it directly to the backend request state machine
// (domain/create_package/state_machine.py + the per-command gates) so the two can
// never silently drift — every button's enabled/disabled is a property proven here.

function detail(overrides: Partial<PackageRequestDetail>): PackageRequestDetail {
  return {
    request_id: "req_1",
    package_type: "indicator",
    creation_mode: "translate_existing_code",
    source_kind: "code",
    source_language: "pinescript",
    target_runtime: "python",
    output_contract: { kind: "directional_signal" },
    rationale_family_id: "fam_1",
    compatible_rationale_family_ids: [],
    linked_indicator: null,
    declared_dependencies: [],
    state: "requested",
    context_hash: "sha256:ctx",
    request_version: 1,
    owner_principal_id: "u_1",
    current_scan: null,
    precheck_fresh: false,
    package_root_id: null,
    draft_revision_id: null,
    can_generate_candidate: false,
    current_validation_run: null,
    validation_fresh: false,
    claims_equivalence: false,
    current_baseline: null,
    baseline_ready: false,
    baseline_required: false,
    created_at: null,
    ...overrides,
  };
}

describe("packageActionAvailability", () => {
  it("disables every action when no request is selected", () => {
    const a = packageActionAvailability(null);
    expect(a).toMatchObject({
      precheck: false,
      generateDraft: false,
      runValidation: false,
      requestRevision: false,
      approve: false,
      uploadBaseline: false,
      parseBaseline: false,
      nextStepHint: "",
    });
  });

  it("offers Pre-Check only in pre-candidate states", () => {
    for (const state of [
      "requested",
      "precheck_passed",
      "precheck_blocked",
      "precheck_not_applicable",
      "precheck_stale",
      "precheck_failed",
    ]) {
      expect(packageActionAvailability(detail({ state })).precheck).toBe(true);
    }
    for (const state of ["candidate_ready", "draft_created", "eligible_for_approval", "approved"]) {
      expect(packageActionAvailability(detail({ state })).precheck).toBe(false);
    }
  });

  it("offers C.D.P only before a draft exists and once a candidate can be built", () => {
    expect(
      packageActionAvailability(detail({ state: "precheck_passed", can_generate_candidate: true }))
        .generateDraft,
    ).toBe(true);
    expect(packageActionAvailability(detail({ state: "candidate_ready" })).generateDraft).toBe(true);
    // A draft already exists -> no re-draft.
    expect(
      packageActionAvailability(
        detail({ state: "draft_created", draft_revision_id: "rev_1", can_generate_candidate: true }),
      ).generateDraft,
    ).toBe(false);
  });

  it("offers Run Validation only in draft_created (its one inbound edge)", () => {
    expect(
      packageActionAvailability(detail({ state: "draft_created", draft_revision_id: "rev_1" }))
        .runValidation,
    ).toBe(true);
    for (const state of [
      "precheck_passed",
      "candidate_ready",
      "eligible_for_approval",
      "approved",
    ]) {
      expect(
        packageActionAvailability(detail({ state, draft_revision_id: "rev_1" })).runValidation,
      ).toBe(false);
    }
  });

  it("offers Request Revision only from revision_required / rejected", () => {
    expect(packageActionAvailability(detail({ state: "revision_required" })).requestRevision).toBe(
      true,
    );
    expect(packageActionAvailability(detail({ state: "rejected" })).requestRevision).toBe(true);
    for (const state of ["draft_created", "eligible_for_approval", "precheck_passed", "approved"]) {
      expect(packageActionAvailability(detail({ state })).requestRevision).toBe(false);
    }
  });

  // The core F-12 acceptance: a draft cannot call approval directly.
  it("locks Approve outside eligible_for_approval — a draft cannot approve directly", () => {
    expect(
      packageActionAvailability(detail({ state: "draft_created", draft_revision_id: "rev_1" }))
        .approve,
    ).toBe(false);
    expect(
      packageActionAvailability(
        detail({
          state: "eligible_for_approval",
          draft_revision_id: "rev_1",
          validation_fresh: true,
        }),
      ).approve,
    ).toBe(true);
  });

  it("keeps Approve locked when evidence is stale even at eligible_for_approval", () => {
    const d = detail({
      state: "eligible_for_approval",
      draft_revision_id: "rev_1",
      validation_fresh: false,
    });
    expect(packageActionAvailability(d).approve).toBe(false);
    expect(approvalBlockReason(d)).toMatch(/no longer certifies/);
  });

  it("keeps Approve locked until a claimed-equivalence baseline is parsed", () => {
    const blocked = detail({
      state: "eligible_for_approval",
      draft_revision_id: "rev_1",
      validation_fresh: true,
      claims_equivalence: true,
      baseline_required: true,
      baseline_ready: false,
    });
    expect(packageActionAvailability(blocked).approve).toBe(false);
    expect(approvalBlockReason(blocked)).toMatch(/baseline/i);

    const ready = detail({ ...blocked, baseline_ready: true });
    expect(packageActionAvailability(ready).approve).toBe(true);
    expect(approvalBlockReason(ready)).toBeNull();
  });

  it("freezes baseline actions on an approved (terminal) request", () => {
    const a = packageActionAvailability(
      detail({ state: "approved", draft_revision_id: "rev_1", current_baseline: null }),
    );
    expect(a.uploadBaseline).toBe(false);
    expect(a.parseBaseline).toBe(false);
  });

  it("guides the next step so a draft never dead-ends before validation", () => {
    expect(packageActionAvailability(detail({ state: "draft_created" })).nextStepHint).toMatch(
      /Run Validation/i,
    );
    expect(packageActionAvailability(detail({ state: "revision_required" })).nextStepHint).toMatch(
      /Request Revision/i,
    );
  });
});
