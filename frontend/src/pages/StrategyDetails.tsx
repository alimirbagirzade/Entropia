import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StrategyDetailsPanel } from "@/components/StrategyDetailsPanel";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, useDefaultMainboard } from "@/lib/backtest";
import { useRationaleFamilies } from "@/lib/createPackage";
import { useCreateStrategyDraft } from "@/lib/strategy";

// Failures surface the backend canonical envelope verbatim — the client never
// invents strategy-domain messages. A stale OCC token arrives here as 409
// STRATEGY_DRAFT_CONFLICT (AT-19); a blocked save as a 422 whose details carry
// the compiler issue list.
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Strategy Details (Stage 3b, doc 02 §7–§9; UI-02 doc 02 §3 3-column layout).
// The standalone /strategy route is a back-compat deep-link into the SAME
// StrategyDetailsPanel that now renders inline inside a Mainboard row (the
// primary interaction, UI-01/UI-02) — not the exclusive editing surface.
// URL modes: ?draft= (durable editor handle — the backend exposes NO
// root→draft lookup, so losing this URL means the draft is only reachable
// again via a fresh create), ?strategy= (root header + revisions, discoverable
// from the default Mainboard), ?revision= (immutable deep-link).
export function StrategyDetails() {
  const [searchParams, setSearchParams] = useSearchParams();
  const revisionParam = searchParams.get("revision");
  const strategyParam = searchParams.get("strategy");
  const draftParam = searchParams.get("draft");
  const hasIdentifier = revisionParam !== null || strategyParam !== null || draftParam !== null;

  return (
    <>
      <h1 className="page-title">Strategy Details</h1>
      <p className="page-sub">
        Compose and edit your strategy draft, validate the config, and save immutable revisions —
        the editor path feeding Ready Check and RUN. The same editor also opens inline from a
        Strategy row on the Mainboard.
      </p>

      {hasIdentifier ? (
        <StrategyDetailsPanel
          draftId={draftParam}
          revisionId={revisionParam}
          rootId={strategyParam}
          onDraftCreated={(draftId) => setSearchParams({ draft: draftId })}
        />
      ) : (
        <>
          <CreateStrategyCard onCreated={(draftId) => setSearchParams({ draft: draftId })} />
          <AttachedStrategiesCard />
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Create (POST /strategy-drafts — no OCC, fresh Idempotency-Key)
// ---------------------------------------------------------------------------

function CreateStrategyCard({ onCreated }: { onCreated: (draftId: string) => void }) {
  const [name, setName] = useState("");
  const [familyId, setFamilyId] = useState("");
  const families = useRationaleFamilies(null);
  const create = useCreateStrategyDraft();

  return (
    <section className="card" aria-labelledby="strat-create-h">
      <h3 id="strat-create-h" style={{ marginTop: 0 }}>
        Create strategy
      </h3>
      <p className="cp-note">
        Creates the strategy root and its mutable editor draft. No revision exists until the first
        Save — an unsaved draft cannot enter Ready Check or RUN (AT-01). Keep the editor URL: the
        draft id is the only handle to the draft.
      </p>
      <form
        className="cp-form"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(
            {
              displayName: name,
              rationaleFamilyId: familyId === "" ? null : familyId,
            },
            { onSuccess: (result) => onCreated(result.draft_id) },
          );
        }}
      >
        <label className="cp-field">
          <span>Display name</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Momentum breakout A"
            required
          />
        </label>
        <label className="cp-field">
          <span>Rationale family (optional)</span>
          <select value={familyId} onChange={(event) => setFamilyId(event.target.value)}>
            <option value="">None</option>
            {(families.data?.data ?? []).map((family) => (
              <option key={family.entity_id} value={family.entity_id}>
                {family.display_name}
              </option>
            ))}
          </select>
        </label>
        <div className="cp-field cp-wide">
          <button className="btn btn-primary" type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create draft"}
          </button>
        </div>
      </form>
      {create.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(create.error)}
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Discovery: strategy items attached to the default Mainboard (RUN/Ready-Check
// composition pattern). Only ATTACHED strategies appear here — a created but
// never-attached strategy stays reachable through its create-time ?draft= URL.
// ---------------------------------------------------------------------------

function AttachedStrategiesCard() {
  const mainboard = useDefaultMainboard();
  const strategyItems = (mainboard.data?.items ?? []).filter(
    (item) => item.item_kind === "strategy",
  );

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-attached-h">
      <h3 id="strat-attached-h" style={{ marginTop: 0 }}>
        Attached strategies
      </h3>
      {mainboard.isLoading ? (
        <Loading />
      ) : mainboard.isError ? (
        <ErrorState error={mainboard.error} onRetry={() => void mainboard.refetch()} />
      ) : strategyItems.length === 0 ? (
        <EmptyState
          title="No strategy items on the default Mainboard"
          description="Strategies appear here once attached to the composition. A fresh draft is reached through its editor URL."
        />
      ) : (
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Label</th>
              <th>Strategy root</th>
              <th>Pinned revision</th>
              <th>Enabled</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {strategyItems.map((item) => (
              <tr key={item.item_id}>
                <td>{item.display_label_override ?? EM_DASH}</td>
                <td>
                  <code>{item.work_object_root_id}</code>
                </td>
                <td>{item.pinned_revision_id ? <code>{item.pinned_revision_id}</code> : EM_DASH}</td>
                <td>{item.is_enabled ? "yes" : "no"}</td>
                <td>
                  <Link to={`/strategy?strategy=${encodeURIComponent(item.work_object_root_id)}`}>
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
