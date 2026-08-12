<!-- doc-status: historical -->
# P9-B2 — react-router `GHSA-qwww-vcr4-c8h2`: the freeze was DROPPED, not signed

**Slice:** ADIM 44 · **Date:** 2026-08-12 · **Base:** `e719af1` (origin/main)
**Verdict:** RC blocker **(4) CLOSED**. Not by signature — by removal.

## 1. What was authorised, and why it was not written

The product-owner decision was to move the freeze into
`.github/security-allowlist.json` under the signature discipline, and the signature
was supplied: **owner `Ali Mirbagirzade`, expires `2026-11-10`** (inside the
`MAX_EXCEPTION_DAYS = 90` cap). That entry was **not** written.

The same instruction said *"Bunu YENİDEN DOĞRULA — bayatlamış olabilir."* It had.
An allowlist entry records an **accepted risk**. There is no risk here to accept, so
signing one would have manufactured an exception with no finding behind it — and the
gate would have said so on every run: `WARN — allowlisted but not reported`.

## 2. The re-derivation (two independent sources)

| | 2026-08-07 record | 2026-08-12 measurement |
|---|---|---|
| advisory range | `>=7.12.0 <8.3.0` — "every 7.x affected" | **`>=7.12.0 <7.18.2` (first_patched `7.18.2`) + `>=8.0.0 <8.3.0`** |
| patched line | `8.3.0+` only (the v8 migration) | **7.18.2 is also patched** — backported to 7.x |
| installed tree | `react-router` 7.18.2, `dev=false` | unchanged; `react-router-dom@7.18.2` pins it **exactly** |
| `npm audit` (frontend) | high advisory reported | **`found 0 vulnerabilities`** |
| gate's own note | — | *"frozen but no longer reported — drop it from the list"* |

Sources: `gh api /advisories/GHSA-qwww-vcr4-c8h2` (`updated_at 2026-08-07T18:16:54Z`,
`withdrawn_at: null`) — raw in `p9b2_advisory_ghsa_qwww_vcr4_c8h2.json` — and
`npm audit --json`. Either one alone could be wrong; they agree.

The risk argument is **still materially true** (`BrowserRouter` at `main.tsx:22`; no
RSC API anywhere under `frontend/src`; the only router import specifier is
`react-router-dom`) — see `p9b2_gate_runs.txt`. It is simply no longer needed.

## 3. Timeline — the record went stale inside twenty minutes

| When | What |
|---|---|
| 2026-07-22 | `react-router@8.3.0` published (the 8.x fix) |
| 2026-07-24 16:44Z | GHSA-qwww-vcr4-c8h2 published |
| **2026-07-28 21:53Z** | **`react-router@7.18.2` published — the 7.x backport** |
| 2026-08-07 17:56:59Z | PR #637 (P9-B1) merges, correcting the freeze's facts |
| **2026-08-07 18:16:54Z** | **the advisory is re-scoped upstream** — 20 minutes later |
| 2026-08-12 | re-derived here; nobody had looked in the five days between |

The repository had been sitting on the patched version for **eleven days**.

This is the **third** repetition of one pattern. The brace-expansion pair was dropped
2026-08-03 for the same reason; js-yaml was dropped 2026-08-07, where the patch had
shipped **seven days before the freeze merged**. Every freeze this repo has ever
written has ended the same way: its reason expired before anyone re-read it.

## 4. What was changed

* `scripts/npm-audit-gate.mjs` — `FROZEN_ADVISORIES` **deleted**. The gate now reads
  `.github/security-allowlist.json`, which requires `owner` + `expires`.
* `scripts/lib/security-allowlist.mjs` — **new**; the loader, validator, expiry
  enforcement and scope check both gates share.
* `scripts/security-allowlist-gate.mjs` — switched to the shared module; its
  "allowlisted but not reported" warning is now scoped to what the run actually read.
* `.github/security-allowlist.json` — declares `npm:frontend`, `npm:frontend/e2e`
  alongside the two container scopes. **`entries` is empty and staying empty.**
* `backend/tests/contract/test_security_freeze_discipline_contract.py` — **new**, 7 tests.

Both gates now expire the **whole** list, not just their own scopes: the npm gate runs
in `ci.yml` on every push/PR, the container gate in `security.yml`. If each expired
only its own scopes, an exception's calendar would depend on which workflow ran.

**No dependency version changed. No downgrade.**

## 5. Proofs

Positive — `p9b2_gate_runs.txt`: both gates exit 0 on the working tree.

Negative — `p9b2_gate_negative_proofs.txt`, five failures and one deliberate non-failure:

| # | Attempt | Result |
|---|---|---|
| NEG-1 | entry with no `owner` | **exit 1** — malformed |
| NEG-2 | entry past `expires` | **exit 1** — *in the npm gate* |
| NEG-3 | gating an undeclared scope | **exit 1** |
| NEG-4 | window > 90 days | WARN, **exit 0** — a cap, not a wall |
| NEG-5 | real unrecorded high advisory (lodash@4.17.20 fixture) | **exit 1** |
| NEG-6 | correct advisory id, **wrong** package | **exit 1** |

NEG-4 also shows the line the abandoned move would have produced forever:
`note GHSA-… is allowlisted but no longer reported — delete the entry.`

## 6. Honest boundary

This closes the *shipped* half of P9-B2 and the *structural* half. It does **not**
claim the supply chain is clean in general: `npm audit` covers the two npm workspaces,
Trivy covers the two images, and neither sees anything outside those four surfaces.
The container gate still runs only in `security.yml` (push to main, PRs to main,
weekly cron) — an exception's expiry is caught by the npm gate on every PR, but a
*container* finding is still only re-scanned on those triggers.
