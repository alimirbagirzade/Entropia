import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PackagePicker } from "@/components/PackagePicker";
import type { PackageRefForm } from "@/lib/strategyGraph";
import { stubApi } from "./helpers/apiStub";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// F-19 — the pinned view resolves the package's human name from the Library
// detail read and demotes the raw root/revision/hash ULIDs to a collapsed
// "Technical identifiers" disclosure. The pinned ref VALUE is unchanged.
const DETAIL = {
  entity_id: "pkg_lib",
  package_kind: "indicator",
  name: "Reversal Sensor",
  current_revision_id: "rev_lib",
  revision_no: 4,
  lifecycle_state: "active",
  validation_state: "passed",
  approval_state: "approved",
  visibility_scope: "published",
  content_hash: "hash_lib",
};

const PINNED: PackageRefForm = {
  package_root_id: "pkg_lib",
  package_revision_id: "rev_lib",
  package_content_hash: "hash_lib",
};

function renderPinned() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PackagePicker kind="indicator" label="Indicator package" value={PINNED} onChange={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("PackagePicker pinned summary (F-19)", () => {
  it("shows the resolved package name, ULIDs demoted to the disclosure", async () => {
    stubApi({ "GET /library/pkg_lib": DETAIL });
    renderPinned();

    expect(await screen.findByText(/Reversal Sensor/)).toBeTruthy();
    const disclosure = screen.getByText("Technical identifiers").closest("details") as HTMLElement;
    // Exact identifiers preserved and verifiable, just no longer the primary surface.
    expect(within(disclosure).getByText("pkg_lib")).toBeTruthy();
    expect(within(disclosure).getByText("rev_lib")).toBeTruthy();
    expect(within(disclosure).getByText("hash_lib")).toBeTruthy();
  });

  it("falls back to a generic label before the name resolves", () => {
    stubApi({ "GET /library/pkg_lib": DETAIL });
    renderPinned();
    // Before the async detail resolves, the primary label is generic (never a raw ULID).
    expect(screen.getByText("Pinned package")).toBeTruthy();
  });
});
