<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# F-07 kapandı — kickoff / handoff for the next session

> **STALE-BY-DEFAULT.** Everything below was true at authoring time. Run the §Session START
> protocol (`git fetch`, `git log --oneline origin/main -6`, `gh pr list --state all`) before
> trusting a single line of it.

## Where we are

**F-07 is Complete as a whole.** Its presentation half landed in PR #404; its backend
display-DTO half (`v18_visual_traceability.md §4.4`) landed in this slice. The `CLAUDE.md`
§Next list no longer carries an F-07 row.

Two CLAUDE.md facts were found STALE and corrected while measuring:

| Was | Actually |
|---|---|
| alembic head `0039_backtest_run_cancellation` (39 migrations) | `0040_export_type_agent_pine` at slice start → **`0042_package_import_source_name`** now (41) |
| `ENGINE_VERSION = backtest-engine-v18-funding-step-order` | was **`-restriction-min-n`** (I-15a) at slice start → **`backtest-engine-v18-min-n-filtered-events-per-item-labels`** now (F-07 §4.4 bumped it) |

Also corrected: §4.4's table implied `ResultDetail.tsx` lived under `pages/`. It is
`frontend/src/components/ResultDetail.tsx`.

## What this slice left behind — reuse anchors (exact symbols)

| Symbol | What it is |
|---|---|
| `frontend/src/components/LabelledId.tsx` → `LabelledId({label, id, inline})` | **The** presentation contract for a server-labelled identifier: label PRIMARY + muted `<code>` id secondary; **label null → id alone**. Never derives a name from an id. Use it for any new such surface instead of writing `<code>{x_id}</code>` |
| `commands/mainboard.py::_snapshot_manifest` + `commands/readiness_check.py::_manifest` | **Twins.** Both write the composition snapshot's `items[].label`. Change one → change the other |
| `domain/backtest/manifest.py::pinned_item_labels` | Snapshot `items[].label` → `{item_id: label}`. Lands in `manifest["mainboard_item_labels"]`, **deliberately outside** `execution_content` |
| `jobs/backtest_engine.py::_manifest_item_labels` | The worker-side reader of that manifest key (run-manifest shape, **not** snapshot shape — do not swap the two) |
| `queries/readiness_check.py::_scope_labels` | Report → its pinned snapshot → `{item_id: label}` |
| `queries/create_package.py::_request_display_labels` | Two batched lookups per page (package name, else family display name) |
| `repositories/mainboard.py::get_snapshot` | New; loads one immutable snapshot by id |
| `commands/create_package.py::_generated_package_name` | doc 06 §510-512 "New [Type] Package" at C.D.P |

## The rule to carry forward

**A pinned artifact's label is captured where the artifact is WRITTEN, never joined at read
time.** A backtest result and a readiness report are immutable (the report is additionally
`is_current`-tracked); labelling either from the live composition attaches names the artifact
never saw. Two tests enforce it and both are **proven RED**:

- `tests/unit/test_f07_manifest_item_labels.py::test_labels_do_not_change_the_execution_key`
  — a display label must never enter `execution_key` (INF-04/INF-05).
- `tests/integration/test_f07_display_labels.py::test_renaming_the_item_does_not_relabel_an_existing_report`

**Backward compatibility is by omission, never backfill.** Pre-slice snapshots/manifests/rows
carry no label → readers return an empty map / `null` → the UI shows the id.

## Next design pointers

`CLAUDE.md` §Next now has three items, none of them F-07:

1. **R2 banner kapanışı (docs work)** — `entropia_v18_remediation_status.md`'s RE-OPENING banner:
   its condition is met, so remove the banner and make the UI rows evidence-backed Complete.
   F-07 is now a clean Complete row to cite.
2. **O-03 residue** — 4 dead error classes (`KNOWN_UNRAISED`).
3. **Round-3 backlog** — S5 (a/b/c/d) + S-L1…S-L6.

**A genuine follow-up this slice deliberately did NOT take:** the four touched routes declare
their bodies as `dict[str, Any]`, so the new fields are invisible to `docs/openapi.json` and to
the drift guard — the same blind spot O-30 recorded. Giving them typed response models needs its
own idempotent-replay compatibility analysis (an old envelope replayed against a strict schema
500s — the exact O-30 failure). Scope it before coding.

## REUSE list

- `LabelledId` — the presentation contract (above).
- `docs/implementation/v18_visual_traceability.md §4` — the JSX text-node scan method and the
  "primary identity vs advanced/audit detail" classification rule. Re-run the scan to confirm no
  new raw-id renders crept in.
- `tests/integration/test_f07_display_labels.py::_labelled_composition` — seeds a composition
  holding the SAME strategy twice so `DUPLICATE_ENABLED_ITEM` gives a deterministic item-scoped
  finding; it reuses `test_readiness_persistence`'s seed helpers rather than re-deriving a valid
  strategy payload.

## Working-loop method (what worked here)

1. **Re-measure the doc's own file:line before trusting it.** §4.4 had drifted on a path.
2. **Follow the data to where the artifact is written**, not to where it is read. That is what
   made the immutability constraint tractable instead of scary.
3. **Check what a new field is hashed into — AND what artifact it lands in.** Two separate
   questions, and this slice got the second one wrong at first. `mainboard_items` feeds
   `execution_key`, so a display string there would fork reproducibility (handled up front).
   But the persisted composite artifact ALSO grew a field, which needs an `ENGINE_VERSION`
   bump so a stale result is not idempotently reused — that one was caught only by
   `test_backtest_engine_golden.py`. Run the golden guard early when touching engine output.
4. **Prove RED.** Both invariants were verified to fail — and only their own tests to fail —
   when the wrong implementation is substituted.
5. **`git checkout <file>` reverts the WHOLE file.** Used to undo a RED probe it also threw away
   that file's real changes. Undo probes with a targeted edit instead.
6. Frontend suite: `--no-file-parallelism` is mandatory. Backend: `TEST_DATABASE_URL` to a
   worktree-private DB, one pytest call, never piped to `tail`.

---

## Paste-ready resume prompt

```
Entropia — devam. Session START protokolü: git fetch + `git log --oneline origin/main -6` +
`gh pr list --state all` ile NE'nin gerçekten merge olduğunu doğrula (handoff STALE-BY-DEFAULT).
Oku: docs/STAGE_R2_CLOSURE_KICKOFF.md → docs/STAGE2_HANDOFF.md §Next →
docs/implementation/v18_visual_traceability.md §4.

Durum: F-07 BÜTÜN olarak COMPLETE (sunum PR #404 = §4.3; backend display-DTO = §4.4).
Dört alan eklendi: display_label+created_at (PreCheck request), source_package_name (Library
import), item_label (PerItemBreakdown + ContributionMarginal), scope_label (ReadinessIssue).
Ortak sunum bileşeni: frontend/src/components/LabelledId.tsx (label PRIMARY + id muted; label
yoksa YALNIZ id — asla uydurma ad). alembic head 0042_package_import_source_name (42 migration).
ENGINE_VERSION = backtest-engine-v18-min-n-filtered-events-per-item-labels (BU SLICE BUMP ETTİ — sebebi davranış
değil ARTEFAKT ŞEKLİ: per-item + marginal satırlarına item_label eklendi; golden'da yalnız 4
portfolio.combine* senaryosu oynadı, strategy-replay bit-aynı. Bump olmadan etiketsiz eski result
re-RUN'da idempotent yeniden kullanılırdı — v17 per-item breakdown bump'ıyla aynı sınıf).

KURAL (taşınacak): pinli artefaktın (result, readiness report) etiketi artefakt YAZILIRKEN
yakalanır, okuma anında canlı composition'dan JOIN EDİLMEZ. İki test bunu koruyor ve ikisi de
RED kanıtlandı: test_labels_do_not_change_the_execution_key (display label execution_key'e
GİREMEZ) ve test_renaming_the_item_does_not_relabel_an_existing_report. Geriye uyum backfill'le
değil omission'la: eski satır label taşımaz → null → UI ham id gösterir.

Sıradaki iş (CLAUDE.md §Next, F-07 satırı DÜŞTÜ):
  1. R2 banner kapanışı (docs işi) — entropia_v18_remediation_status.md RE-OPENING banner'ı
     kaldır, UI satırlarını evidence'lı Complete yap. F-07 artık temiz bir Complete satırı.
  2. O-03 kalıntısı — 4 ölü error sınıfı (KNOWN_UNRAISED).
  3. Round-3 backlog — S5 (a/b/c/d) + S-L1…S-L6 (POST_V1_SPEC_GAP_BACKLOG_ROUND3.md).

Bilinçli ALINMAYAN takip işi: dört route gövdesini dict[str, Any] olarak bildiriyor → yeni
alanlar docs/openapi.json'a yayımlanmıyor, drift guard göremiyor (O-30 kör noktası). Typed
response model vermek kendi idempotent-replay uyumluluk analizini ister (eski zarf + katı şema
= 500, O-30'un tam olarak yaşadığı hata). Koda geçmeden kapsamı netleştir.

Konvansiyonlar: direct-author (Workflow yok), yeni dosyalar Bash heredoc, davranış değişirse
ENGINE_VERSION bump ZORUNLU. Backend verify:
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
— TEST_DATABASE_URL ile worktree'ye özel izole DB, TEK pytest çağrısı, çıktıyı dosyaya yaz
(`| tail` KULLANMA — exit code tail'in olur). Frontend verify:
cd frontend && npm run lint && npm run typecheck && npx vitest run --no-file-parallelism.
Ayrı dal, ayrı PR, NO AI attribution, self-merge yok — merge için bana sor.
```
