<!-- doc-status: historical -->
> **HISTORICAL RECORD — this is not the live slice handoff.** It records the audit
> procedure as of the date below. Current authority: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (generated, gated in CI with `--check`).
> The one number here that rots is the route count; re-derive it from
> `frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES` (a contract test pins it).

# A-08 — auditor runbook (read this first, it is one page)

> **Written in English on purpose.** The rest of this repository documents itself in
> Turkish; this file is handed to the person doing the audit, who may be an external
> screen-reader professional, and it is the companion to
> [`a11y_screen_reader_audit_results.md`](../audit/a11y_screen_reader_audit_results.md),
> which is also English.

**Your job:** drive this product with a real screen reader and write down what you
hear. Nothing in this repository substitutes for that. The automated checks (axe-core,
keyboard flow, structural prechecks) already ran; they measure the DOM, not the
announcement, and **no output of theirs may be copied into the results worksheet.**

**Budget:** two combinations × (23 routes + 10 flows). Expect two sessions, not one.
Partial is fine and expected — record what you did, leave the rest `—`. A half-filled
worksheet is evidence; an empty one is not.

---

## 0. Next session — start here (the one-page card)

> **Prepared 2026-08-25 against `45ecebc`.** Everything in this card is derived from
> the worksheet's §5 session log and from the **frozen** precheck evidence
> `docs/releases/evidence/2026-08-12/a08_precheck_results_run5.json`. **No precheck was
> re-run for it** — the container it was written in has no Docker daemon, so
> `a11y-audit-stack.sh up` could not be brought up (worksheet §6.1a records the
> attempt). Re-run the prechecks yourself if you want a fresh reach count; §4's
> run-it-twice rule still applies.

**Combination: SR-2 — VoiceOver / Safari / macOS. Continue it; do not start SR-1.**

Not because SR-2 matters more — because SR-1 has no machine and no auditor yet. SR-1
needs a Windows box with NVDA and a person assigned to it; that is a scheduling step,
not a session. SR-2 already has both, and 2 of its cells are filled.

> **Say this out loud before you start, so nobody misreads the result afterwards:**
> finishing SR-2 *entirely* — all 23 routes and all 10 flows — still leaves exit
> criterion 1 at **1 / 2** and criterion 2 at **23 / 46** routes. A-08 does not get
> closer to done by one combination getting further. It gets closer when the *second*
> combination starts. Worksheet §5 states this; it is repeated here because this card
> is what the next auditor actually reads.

### Where you pick up

| | |
|---|---|
| **Route** | **1 — `/` (Mainboard)** — it is the only route with any cells at all, and it is 6 cells short of being the first *complete* row in the worksheet |
| **Cells, in this order** | **A-3**, then **A-4, A-5, A-6, A-7, A-8** |
| **Already filled — do not redo** | **A-1** `PASS` · **A-2** `PASS` (three landmarks; `contentinfo` is not expected — D-11) |
| **Then** | routes **2 → 23** in §4's order, all eight cells each |
| **After Section A** | §2's ten flows, B-1 → B-10 |

### The three things worth knowing before you touch route 1

**1. Route 1 cannot settle K-5, and the last session's question about it was
unanswerable there.** The A-3 cell was left `—` after the auditor was asked whether
*"the `h1 → h3` jump"* misled them. **There is no such jump on `/`.** Measured, not
inferred: in the frozen five-run evidence, `/` is the **only one of the 23 routes that
emits no `heading outline` advisory at all** — every other route emits one. So route 1's
A-3 is a question about an outline that is already unbroken, and a `PASS` there is a
statement about `/` and about nothing else.

> **What this means for the cell:** answer A-3 on route 1 on its own merits — does the
> Mainboard's heading list show you the page's real structure? — and expect that answer
> to be `PASS` and to be *uninformative about K-5*. **K-5 is settled on a route inside
> its set**, and the worksheet's own worked example is `/backtest/run`
> (`h1 "RUN & Backtest Results" → h3 "Composition"`). Do not record a route-1 `PASS` as
> progress on K-5.

**2. K-6a — *"can you see where focus is?"* — is answerable on route 1, in about a
minute, and only a human can answer it.** The computed-style probe that raised it
sampled exactly one element, on exactly this route (`/` is the only route emitting a
`focus indicator` advisory), and a probe cannot see a UA default ring. Tab through the
shell with your eyes on the screen and write down whether you can always tell where
focus is. **This is not a Section A cell** — record it against K-6a in worksheet §6, and
open a finding if the answer is no.

**3. K-7 is not a Section A question and you will not settle it in Section A.** *"No
live region in the initial DOM"* is about what gets **announced when something
happens**, which is flows **B-3** (Ready Check verdict), **B-4** (RUN
`queued → running → completed`) and **B-6** (409 conflict). Keep the Speech Viewer /
VoiceOver caption panel open when you get to Section B and watch whether *anything*
arrives on the state change.

### If you only have half an hour

Not the recorded order — the recorded order is route 1 → 23 → flows, and that is what
§4 says. This is what to spend a short session on if you cannot finish route 1, and it
is advice, not a re-plan:

1. **K-6a on route 1** (~1 min, human-only, unblocks a product decision)
2. **A-4 … A-8 on route 1** (~15 min, makes `/` the first complete row: 8 / 8)
3. **A-3 on one K-5-set route** — `/backtest/run` — (~10 min, the only way K-5 moves)

Leave everything else `—`. A half-filled worksheet is evidence; a guessed one is worse
than an empty one.

### One stale instruction — corrected in the source, still frozen in the evidence

**Fixed 2026-08-25.** The precheck's `::warning::` output used to print, next to every
heading-outline advisory, the note *"checklist A-3 asks for h1→h2→h3 with no skipped
level"* — **the superseded question.** A-3 was rewritten on 2026-08-13 precisely because
counting skips is a machine measurement the precheck already produces (see the checklist's
`§A-3 notu`), and three neighbouring notes were stale the same way (the `contentinfo` note
said A-2 expects four landmarks, which D-11 overturned; the skip-link note and the
missing-`<h1>` note each described a defect PR #685 fixed — the latter also repeated the
retired A-3 question). All four now read correctly in
`frontend/e2e/specs/20-a11y-prechecks.spec.ts`; the **counts and the gating behaviour never
changed** — only the prose. Worksheet §6.1b records the before and after.

**Two of those four advisories cannot fire on a shipped route any more** (skip link, missing
`<h1>` — both shipped away by PR #685). They are kept deliberately, as regression tripwires,
and their notes now say so. If you ever see one in a fresh run, that is a real regression.

**Where the old wording survives, deliberately:** the frozen evidence JSONs
(`docs/releases/evidence/2026-08-12/`, `2026-08-11/`) are a record of what the probe printed
on those dates and are never edited. If you are reading a precheck report from an archived
run rather than a fresh one, its A-3 note is the retired question — ignore it and use the
checklist.

---

## 1. Before you start (5 minutes)

You need **both** combinations. One is not enough and never becomes enough:

| # | Screen reader | Browser | Platform |
|---|---|---|---|
| **SR-1** | NVDA, latest stable | Firefox | Windows |
| **SR-2** | VoiceOver | Safari | macOS |

Open these two files side by side and keep them open:

* **Worksheet** — `docs/audit/a11y_screen_reader_audit_results.md` — where results go.
* **Checklist** — `docs/implementation/a11y_screen_reader_audit_checklist.md` — what
  each check (A-1…A-8, B-1…B-10) actually asks.

---

## 2. Bring the stack up (one command)

Requires Docker. From the repository root:

```bash
scripts/a11y-audit-stack.sh up
```

It builds, starts, seeds the three fixtures, and then validates that the fixtures
landed. **It must end with `0 failed`.** If it does not, stop — you would be auditing
empty pages for a seeding reason rather than a product reason. It prints the web URL,
the API URL and the Admin credentials on success.

**Running the screen reader on a different machine** (the usual case: the stack on
macOS, NVDA on a Windows box). Pass the host's LAN address — one knob, and it must be
an address the auditor's browser can actually open:

```bash
A11Y_HOST=192.168.1.20 scripts/a11y-audit-stack.sh up
```

`0.0.0.0` is rejected on purpose: it is a bind address, not a reachable one, and it
would bake an unopenable URL into the web bundle and the CORS allowlist.

Useful afterwards — neither re-builds anything:

```bash
scripts/a11y-audit-stack.sh validate   # re-check the fixtures mid-session
scripts/a11y-audit-stack.sh status     # what is running, where
```

**The stack stays up until you tear it down.** That is deliberate — an automatic
teardown would destroy your session the moment the script returned.

## 3. Sign in

Sign in as the **Admin** printed by the `up` output. Admin is not optional: `/trash`,
`/panel/management` and `/panel/logs` do not render without it, and they are three of
the routes on the list.

---

## 3b. NVDA in one screen — SR-1 only

Skip this if you are an NVDA user; it is here because SR-2's session was run by
someone who had never driven a screen reader, and SR-1 will most likely be too.
**None of it tells you what to conclude** — it only stops the tooling from being
the reason a cell stays `—`.

**The NVDA key** is `Insert` (or `CapsLock` on the laptop layout). Written `NVDA+…`
below. `NVDA+Q` quits.

**Browse mode vs focus mode.** On a web page Firefox starts in *browse mode*, where
the single-letter keys below jump around the document. Type into a text field and
NVDA switches to *focus mode*, where those same letters are typed, not obeyed.
**If a quick key suddenly does nothing, you are in focus mode — press `NVDA+Space`
to go back.** This one confusion accounts for most "the shortcut is broken" reports.

| Check | Keys | What you are listening for |
|---|---|---|
| **A-1** page title | `NVDA+T` after load | the page's own name, not "Entropia" alone |
| **A-2** landmarks | `D` repeatedly, or `NVDA+F7` → *Landmarks* | **three**: banner, navigation, main. `contentinfo` is **not** expected (D-11) |
| **A-3** headings | `H` (next), `Shift+H` (previous), `1`…`6` (by level), `NVDA+F7` → *Headings* | a jump from `h1` straight to `h3` — **K-5 is this question** |
| **A-4** everything reachable | `Tab` through, then arrow-read the page in browse mode | anything you can see but never land on |
| **A-5** button vs link | `B` (buttons), `K` (links) | an action announced as "link", navigation as "button" |
| **A-6** accessible name | `NVDA+Tab` re-reports the focused control | "button 3", "düğme", a raw id — instead of the task |
| **A-7** tables | `T` to the table, then `Ctrl+Alt+←↑→↓` between cells | the column header spoken with the cell |
| **A-8** images | `G` (graphics) | decorative images should be **silent**, not "graphic" |
| **B-8** focus trap | `Tab` past the last control in the modal; `Esc` | focus escaping to the page behind; Esc not returning focus to the trigger |

**Read the whole page:** `NVDA+↓` (desktop layout) or `NVDA+A` (laptop).

**Speech Viewer — use it, and know what it is.** *NVDA menu (`NVDA+N`) → Tools →
Speech Viewer* opens a window transcribing everything NVDA speaks. Two reasons it
matters here: it is the cheapest way to fill the worksheet's *"Session recording /
audio evidence path"* field, and it is the only practical way to answer **K-7**
(B-3 Ready Check verdict, B-4 the `queued→running→completed` transition, B-6 the
409 conflict) — you watch whether *anything* arrives when the state changes.

Its transcript is **not** automated output in the sense §6.1 forbids: it is the
screen reader's own speech, which is precisely the evidence A-08 asks for, unlike a
DOM scan. But it records what was *spoken*, not what was *heard* — it will not show
you that one announcement cut another off, or that a `polite` region never got its
turn because focus moved first. **Keep the sound on.**

---

## 4. Order of work

**Section A first, all 23 routes, then Section B.** Section A teaches you the shell;
Section B assumes you already know how it announces.

The 23 routes, in the order the worksheet lists them. "22 pages" elsewhere counts spec
*documents* — doc 19 contributes two routes, so the route list is 23 long:

| # | Route | # | Route |
|---:|---|---:|---|
| 1 | `/` | 13 | `/portfolio` |
| 2 | `/strategy` | 14 | `/backtest/ready-check` |
| 3 | `/outsource-signal` | 15 | `/backtest/run` |
| 4 | `/trading-signal` | 16 | `/backtest/history` |
| 5 | `/trade-log` | 17 | `/backtest/metrics` |
| 6 | `/packages/create` | 18 | `/analysis-lab` |
| 7 | `/packages/pre-check` | 19 | `/panel/management` *(Admin)* |
| 8 | `/packages/library` | 20 | `/panel/logs` *(Admin)* |
| 9 | `/packages/embedded` | 21 | `/trash` *(Admin)* |
| 10 | `/rationale-families` | 22 | `/user-manual` |
| 11 | `/market-data` | 23 | `/future-dev` |
| 12 | `/research-data` | | |

Then the 10 flows, checklist section B: **B-1** Add menu · **B-2** Add Package popover
· **B-3** Ready Check result · **B-4** Backtest RUN progress + SSE · **B-5** error
envelope (`code` / `message` / `remediation`) · **B-6** OCC conflict (409) · **B-7**
file upload + rejected file type · **B-8** Trash restore/purge confirmation · **B-9**
long tables · **B-10** Login.

**Where to look first.** The preparation measured seven structural observations
(K-1…K-7) in the worksheet's *"Already-known observations"* table. They are **not**
findings — nobody has heard them. They are the highest-yield places to point a screen
reader. **Four have since been resolved and are not your problem:** K-2 and K-4 were
fixed in code (PR #685), K-6b was fixed in one CSS declaration (PR #688), and K-3 was
adjudicated without code by PO-signed **D-11** — three landmarks are what this product
has and what checklist A-2 now asks for.

**Three remain open, and all three are waiting on you** — each has a product decision
behind it that nobody will take until a person has listened:

* **K-5** — does the `h1 → h3` outline actually *mislead* rotor navigation? (Note the
  question: not *"is there a skip"* — the precheck already counts those, **22 / 23
  routes**. See §0 and the checklist's `§A-3 notu`.)
* **K-6a** — can you *see* where focus is? A computed-style probe cannot answer this;
  only an eye can. **A-08 settles this one and nothing else does.**
* **K-7** — do the Ready Check verdict, the RUN state change and a 409 conflict get
  announced at all? This is Section **B** (B-3 / B-4 / B-6), not Section A.

**K-1 you leave alone** — see §6.2.

**If you re-run the prechecks yourself, run them twice and use the second result.** The
probe races the pages' first data render, so the first run after `up` under-reports —
by three routes on K-5 and eleven on K-7 in the measured case. The worksheet's
methodology note carries the five-run spread and names the three routes that stay
flaky even warm.

---

## 5. Recording what you hear

**Per session, before you start:** fill the session header block in worksheet §0 for
the combination you are running — auditor, screen-reader version, browser version, OS,
date. A result with no version string cannot be reproduced later.

**Per check:** fill the cell in worksheet §1 (Section A) or §2 (Section B). Leave `—`
for anything you did not run. Do not guess.

**Per defect:** allocate the next `SR-BULGU-nn` in the worksheet's §3 findings
register, then open a GitHub issue with the **A11Y — screen-reader finding (A-08)**
template (`.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml`). Every field of
that template maps one-to-one onto a register column, so the issue and the worksheet
cannot drift. Each finding needs a status: **FIX** or **PO-APPROVE**.

An axe-core violation is not a screen-reader finding — file those as ordinary bugs.

---

## 6. Four things not to do

1. **Do not copy any automated output into §1, §2 or §3.** An empty template is not
   evidence, and a template filled from a DOM scan is worse: it looks like evidence.
2. **Do not re-file K-1.** The 45 accent-blue low-contrast nodes are a PO-signed
   permanent deviation (D-10, 2026-07-30) on the *low-vision* axis. Record anything
   **new** you hit, not that.
3. **Do not touch GitHub #514.** It carries the `human-only` label. It is currently
   **open** — a human re-opened it on `2026-08-12T11:08:58Z` to run this audit, which
   resolved the earlier closure/evidence divergence. Closing it again is a
   product-owner decision and belongs after the four exit criteria are `☑`, never
   before; an agent may neither close nor re-open it.
4. **Do not fix K-5, K-6a or K-7 on the way past.** Each one's remedy is a product
   decision — re-cut **22** pages' heading outlines? mount a persistent status region?
   — and K-5 / K-6a are precisely what your session is meant to answer first. The
   measured cost of the K-5 remedy alone is **204 headings across 42 files plus six
   tag-scoped CSS rules**; it is not a change anyone makes in passing. (K-2, K-3, K-4
   and K-6b are already resolved — see §4.)

## 7. When you stop

```bash
scripts/a11y-audit-stack.sh down    # removes the volumes; the seeded data is gone
```

A-08 closes only when all four of worksheet §5's exit criteria are `☑`: both
combinations run; Section A complete on all 23 routes and Section B on all 10 flows,
for both; every finding carrying FIX or PO-APPROVE; every FIX landed or converted into
a PO-signed deviation. **Until then no document may show A-08 as Complete, PASS or
Done — and closing the tracking issue satisfies none of the four.**
