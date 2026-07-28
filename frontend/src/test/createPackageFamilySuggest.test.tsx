// S-L5 — Rationale Family suggestion chips in the Create Package composer.
//
// Master ref Module 6 §11 defines GET /rationale-families:suggest as suggestion-only,
// and §9.3 states the hazard it guards: a suggestion is an INFERENCE, so the backend
// must never silently create a Family card or change a package assignment on the
// user's or the Agent's behalf. These tests pin the read-only contract at the UI
// boundary: chips render, picking one only fills the existing selector, and an
// unmatched query offers no create-on-the-fly path.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { CreatePackage } from "@/pages/CreatePackage";
import { stubApi } from "./helpers/apiStub";

const FAMILIES_PAGE = {
  data: [
    { entity_id: "fam_1", display_name: "Momentum", normalized_name: "momentum", display_color: null },
    { entity_id: "fam_2", display_name: "Mean Reversion", normalized_name: "mean reversion", display_color: null },
  ],
  meta: { cursor: null, has_more: false },
};

const SUGGESTIONS = {
  data: [
    {
      entity_id: "fam_2",
      current_revision_id: "rfrev_2",
      display_name: "Mean Reversion",
      normalized_name: "mean reversion",
      subfamilies: ["reversal"],
    },
  ],
  meta: { q: "reversal", has_more: false },
};

const EMPTY_SUGGESTIONS = { data: [], meta: { q: "funding exhaustion", has_more: false } };

// The suggest route MUST precede the plain list route: the stub matches by substring,
// and "/rationale-families" is a prefix of "/rationale-families:suggest".
function routes(suggest: unknown): Record<string, unknown> {
  return {
    "GET /rationale-families:suggest": suggest,
    "GET /rationale-families": FAMILIES_PAGE,
    "GET /create-package/requests": { data: [], meta: { cursor: null, has_more: false } },
    "GET /library": { data: [], meta: { cursor: null, has_more: false } },
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/create"]}>
        <CreatePackage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Create Package — Rationale Family suggestion chips", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders a chip per suggestion, labelled with its subfamilies", async () => {
    stubApi(routes(SUGGESTIONS));
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Search rationale families"), {
      target: { value: "reversal" },
    });

    const chip = await screen.findByRole("button", { name: "Use rationale family Mean Reversion" });
    expect(chip).toHaveTextContent("Mean Reversion · reversal");
  });

  it("picking a chip only fills the existing selector — it issues no request", async () => {
    const fetchMock = stubApi(routes(SUGGESTIONS));
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Search rationale families"), {
      target: { value: "reversal" },
    });
    const chip = await screen.findByRole("button", { name: "Use rationale family Mean Reversion" });

    const callsBefore = fetchMock.mock.calls.length;
    fireEvent.click(chip);

    // The canonical selector — the field the request body actually reads — is set.
    await waitFor(() =>
      expect((screen.getByLabelText("Rationale family") as HTMLSelectElement).value).toBe("fam_2"),
    );
    // §9.3: no write, and no extra read either — the chip is pure local state.
    expect(fetchMock.mock.calls.length).toBe(callsBefore);
  });

  it("never issues a mutating request from the suggestion box", async () => {
    const fetchMock = stubApi(routes(SUGGESTIONS));
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Search rationale families"), {
      target: { value: "reversal" },
    });
    await screen.findByRole("button", { name: "Use rationale family Mean Reversion" });

    const methods = fetchMock.mock.calls.map(([, init]) =>
      String((init as RequestInit | undefined)?.method ?? "GET").toUpperCase(),
    );
    expect(methods.every((m) => m === "GET")).toBe(true);
  });

  it("an unmatched query says so and offers no create-on-the-fly path", async () => {
    stubApi(routes(EMPTY_SUGGESTIONS));
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Search rationale families"), {
      target: { value: "funding exhaustion" },
    });

    expect(await screen.findByText(/No existing family matched/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Create .*family/i })).toBeNull();
  });

  it("stays silent below the minimum query length — no request is fired", async () => {
    const fetchMock = stubApi(routes(SUGGESTIONS));
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Search rationale families"), {
      target: { value: "r" },
    });

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes(":suggest")),
      ).toBe(false),
    );
  });
});
