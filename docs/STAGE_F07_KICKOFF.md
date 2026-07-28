# F-07 landed — kickoff / handoff for the next session

> **STALE-BY-DEFAULT.** Everything below was true at authoring time. Run the §Session START
> protocol (`git fetch`, `git log --oneline origin/main -6`, `gh pr list --state all`) before
> trusting a single line of it.

## Where we are

The **F-07 raw-id presentation sweep** is empirically resolved — the long-standing
`Not started` / "overlaps P-11/12/16" ambiguity in `docs/implementation/v18_visual_traceability.md`
is gone, replaced by a measured result in that file's new **§4**.

- **P-11 / P-12 / P-16 verified landed** (PR #375, `3c6887c`, `20ccacc`). The traceability §1 rows
  10 / 13 / 16 carried **stale "raw ids" reasons**; corrected (the rows stay OPEN — PO D-4/D-5 and
  A-06 are separate gates and remain unsigned).
- **Two residuals fixed, presentation-only**, both on Portfolio — the page P-11 supposedly swept.
- **Four residuals deliberately left open**; they need a backend display DTO and are the next
  engineering slice.

## What this slice left behind — reuse anchors (exact symbols)

In `frontend/src/pages/Portfolio.tsx`:

| Symbol | What it is |
|---|---|
| `labelsByCompositionItem(entries)` | module-private; builds `Map<composition_item_id, label>` from any row carrying `{composition_item_id, item_type, display_label_override}` (structural param — works for both `AllocationEntry[]` and the local `EntryRow[]`) |
| `UNLABELLED_ITEM` | `"Composition item"` — the last-resort **primary** label. The raw `mbi_` id never becomes a name |
| `itemDisplayLabel(override, itemType)` | pre-existing; `display_label_override` else the kind label |
| `ItemLabel({label, itemId, inline})` | pre-existing; name primary + muted `<code>` id beneath (or inline) |
| `IssuesTable({issues, emptyText, labelByItem})` | **`labelByItem` is now a required prop** — any new call site must pass it |

**This is the pattern to copy** for the remaining four surfaces once the server sends a label:
the browser only maps `id -> server-provided label`; it never derives a name from an id.

## Next design pointers — the F-07 backend display-DTO slice

Not PO-blocked. Pure engineering. Each needs a human label added **at the query boundary**
(F-07's own prescription), then a one-line frontend swap to `ItemLabel`.

| Surface | Frontend site | What the DTO must add |
|---|---|---|
| Pre-Check request picker | `PreCheck.tsx:124` | a name/title on the Create-Package request row (`lib/createPackage.ts`) |
| Package Library imports | `Library.tsx:1259`, `1274` | a label on the import-job row |
| Result per-item breakdown | `ResultDetail.tsx:420`, `589` | a label on `PerItemBreakdown` / `ManifestItemRef` — **from the pinned manifest**, not the live composition (the result is immutable; a live join mislabels) |
| Ready Check issues | `ReadyCheck.tsx:291` | a label on `ReadinessIssue` — **from the report**, not the live composition (the report is immutable and `is_current`-tracked; labelling a stale report from live data is actively wrong) |

The immutability constraint is the whole difficulty: two of the four are pinned artifacts, so the
label must be captured **when the artifact is written**, which likely means a manifest/report field
and therefore a migration. Scope it before coding.

## REUSE list

- `ItemLabel` / `itemDisplayLabel` / `labelsByCompositionItem` (above) — the presentation contract.
- `docs/implementation/v18_visual_traceability.md §4` — the method (JSX text-node scan) and the
  classification rule; re-run the scan to confirm no new raw-id renders crept in.
- `portfolio.test.tsx` "names the item a validation issue points at…" — the acceptance-test shape
  (`within(issueRow)`, so the label must be in the row, not merely on the page).

## Working-loop method (what worked here)

1. **Never trust the status row.** Measure first — the scan turned one unverifiable `Not started`
   into 2 fixed + 4 scoped + 155 explicitly-permitted.
2. **Read the finding's own acceptance before counting violations.** F-07 permits IDs in
   support/audit detail; a raw count of 161 would have been a false alarm.
3. **Prove RED.** Revert only the fixed render, confirm the new test — and only it — fails.
4. **Frontend suite: use `--no-file-parallelism`.** The default parallel run failed 55 tests on
   5s timeouts from worker contention; serial run is 608/608. Backend has the same trap via the
   shared `entropia_test` DB — use `TEST_DATABASE_URL`.

## Honest boundaries carried forward

- **F-07 is NOT Complete** — only its presentation layer is.
- PO signature (D-1…D-9) still gates the R2 RE-OPENING banner; nothing goes Complete without it.
- Unchanged: NVDA/VoiceOver audit not done, 10-page deep visual compare pending (A-06),
  A11Y-01 contrast (228 serious nodes) and A11Y-02 open.

---

## Paste-ready resume prompt

```
Entropia — devam. Session START protokolü: git fetch + `git log --oneline origin/main -6` +
`gh pr list --state all` ile NE'nin gerçekten merge olduğunu doğrula (handoff STALE-BY-DEFAULT).
Oku: docs/STAGE_F07_KICKOFF.md → docs/STAGE2_HANDOFF.md §Next →
docs/implementation/v18_visual_traceability.md §4.

Durum: F-07 raw-id sweep'in SUNUM katmanı kapandı. Empirik sonuç: P-11/P-12/P-16 gerçekten
landed (traceability'nin 10/13/16 satırlarındaki "raw ids" gerekçeleri bayattı, düzeltildi);
Portfolio'da iki kalıntı presentation-only düzeltildi (IssuesTable artık labelByItem alıp
ItemLabel render ediyor; örnek satırı fallback'i UNLABELLED_ITEM). vitest 608/608
(--no-file-parallelism ZORUNLU — paralel koşu worker contention'dan 55 test düşürüyor).
Backend'e dokunulmadı: ENGINE_VERSION bump yok, migration yok. alembic head 0035_portfolio_rules.

İş: F-07'nin KALAN dört kalıntısı — backend display-DTO slice'ı (PO-blocked DEĞİL).
Detay ve gerekçe: docs/implementation/v18_visual_traceability.md §4.4.
  1. PreCheck.tsx:124 — Create-Package request satırına ad/başlık
  2. Library.tsx:1259/1274 — import job satırına etiket
  3. ResultDetail.tsx:420/589 — PerItemBreakdown/ManifestItemRef etiketi, PINLI MANIFEST'ten
     (canlı kompozisyondan join etme: result immutable, öğeler değişmiş olabilir → yanlış etiket)
  4. ReadyCheck.tsx:291 — ReadinessIssue scope etiketi, RAPORDAN (rapor immutable + is_current;
     bayat raporu canlı kompozisyondan etiketlemek aktif olarak yanlış)
(3) ve (4) pinli artefakt olduğu için etiketin artefakt YAZILIRKEN yakalanması gerekebilir —
yani muhtemelen migration. Koda geçmeden kapsamı netleştir.

Frontend'de kopyalanacak desen hazır: Portfolio.tsx içindeki ItemLabel / itemDisplayLabel /
labelsByCompositionItem — tarayıcı yalnızca id -> sunucunun gönderdiği etiket eşlemesi yapar,
ASLA id'den ad türetmez (F-07: "never reconstruct names from IDs in the browser").
IssuesTable'ın labelByItem prop'u artık ZORUNLU — yeni çağrı yeri eklerken geçir.

Sırada bekleyen (bana ait değil): R2 product-owner imzası —
docs/implementation/v18_final_acceptance.md §4 (D-1…D-9). İmza gelmeden
entropia_v18_remediation_status.md'deki R2 RE-OPENING banner'ı KALDIRILMAZ, hiçbir satır
Complete işaretlenmez. F-07 de §4.4 kapanmadan bütün olarak Complete DEĞİL.

Konvansiyonlar: direct-author (Workflow yok), yeni dosyalar Bash heredoc, davranış değişirse
ENGINE_VERSION bump ZORUNLU. Backend verify:
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q
— TEST_DATABASE_URL ile worktree'ye özel izole DB kullan. Frontend verify:
cd frontend && npm run lint && npm run typecheck && npx vitest run --no-file-parallelism.
Ayrı dal, ayrı PR, NO AI attribution, self-merge yok — merge için bana sor.
```
