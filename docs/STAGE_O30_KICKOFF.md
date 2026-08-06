<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# O-30 landed — sıradaki oturum için kickoff

> Bu dosya **O-30 kapanışında** yazıldı. En altta **paste-ready resume prompt** var.

## Nerede duruyoruz

- **PR #451** (`feat/o30-purge-pending-response-shape` → `main`) purge-request 202 gövdesindeki
  spec çelişkisini adjudicate etti. **Migration YOK**, alembic head
  `0039_backtest_run_cancellation` sabit, `ENGINE_VERSION` sabit.
- Tam kayıt: `docs/PROJECT_HISTORY.md` §"O-30 · Purge-request 202 gövdesi".
  Kural özeti: `CLAUDE.md` §Conventions → "Purge 202 gövdesi = iki ad, tek değer (O-30)".

## Bu slice'ın geride bıraktığı reuse anchor'ları (kesin sembol adları)

| Sembol | Dosya | Ne için |
|---|---|---|
| `PurgeAcceptedResponse` | `apps/api/routes/trash.py` | 202 gövdesinin **yayımlanan** şeması; yeni mutating route eklerken kopyalanacak kalıp |
| `request_purge` | `application/commands/deletion.py` | `run_idempotent` sonrası **legacy-envelope backfill** deseni (kopyala, mutate etme) |
| `test_purge_202_publishes_both_state_field_names` | `tests/contract/test_openapi_contract.py` | yayımlanan bileşeni okuyup alan kaybını yakalayan test kalıbı |
| `test_purge_replay_of_pre_o30_envelope_backfills_the_field` | `tests/integration/test_trash_page.py` | eski Idempotency-Key zarfını birebir üretme kalıbı (`request_fingerprint` + `idem_repo.add_key/complete_key`) |
| `PurgeResult` | `frontend/src/lib/trash.ts` | backend sözlüğünün verbatim aynası |

## Öğrenilen iki ders (sonraki slice bunlara dikkat etsin)

1. **`dict[str, Any]` dönen route sözleşmeyi şemadan gizler.** Drift guard yeşil kalır ama
   `docs/openapi.json` alanları hiç saymaz. Gövde ekliyorsan **typed response model bildir** —
   guard'ın yeşilliği tek başına kanıt değildir.
2. **Katı response model + `run_idempotent` = geriye dönük tuzak.** Replay `response_ref`'i birebir
   döndürdüğü için eski sürümün yazdığı zarf yeni zorunlu alanı taşımaz ve 500 verir. Yeni zorunlu
   alan eklerken **backfill** yaz.
3. **Merge commit'leri PROJECT_HISTORY bölümlerini düşürebiliyor.** #408'de olmuştu, bu slice'ta
   `0af080f`'te tekrar oldu. Rebase/merge sonrası **`grep -c "^## <slice>" docs/PROJECT_HISTORY.md`
   ile kaydın hâlâ orada olduğunu doğrula.**

## Sıradaki iş (öncelik sırası)

1. **PO imzası + R2 kapanışı** — `docs/implementation/v18_final_acceptance.md` §4 (D-1…D-9).
2. **F-07 §4.4** — 4 yüzey backend display-DTO bekliyor (`v18_visual_traceability.md §4.4`).
3. **O-03 kalıntısı** — 5 ölü error sınıfı (`KNOWN_UNRAISED`).
4. **Round-3 backlog** — S5 (a/b/c/d) + S-L1…S-L6 (`POST_V1_SPEC_GAP_BACKLOG_ROUND3.md`).
5. **Kayıtlı borç:** `docs/CODEMAPS/BACKEND_ROUTES.md` satır numaraları bayat (`purge:113`
   gerçekte ~192); `RestoreConflictError.category` hâlâ `CONFLICT` (O-17 kayıtlı sapması).

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Önce ampirik doğrula.** "API hiçbirini döndürmüyor" iddiasının yarısı yanlıştı: değer zaten
  §9.2'ye uygundu. Spec çelişkisinde **hangi tarafın kaç yerde tekrarlandığını say** — outlier'ı
  bulmak kararı verir.
- **Çelişkiyi kaybeden tarafı silerek değil, ikisini de karşılayarak çöz** (O-02/O-12 içtihadı):
  ad bir taraftan, değer diğerinden.
- İzole test DB: `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_o30`.

---

## Paste-ready resume prompt

```
Entropia — O-30 landed (PR #451, purge 202 gövdesi doc 20 §4/§7 ↔ §9.2 adjudicated).
Session START protokolünü uygula: git fetch, git log --oneline origin/main -6,
gh pr list --state all ile #451'in gerçekten merge olduğunu DOĞRULA (handoff stale-by-default).

Oku: docs/STAGE_O30_KICKOFF.md (bu dosya) → docs/STAGE2_HANDOFF.md §"O-30" + §Next →
docs/PROJECT_HISTORY.md §"O-30 · Purge-request 202 gövdesi" (hedefli oku, baştan sona değil).

Sıradaki iş listesi kickoff §"Sıradaki iş"te. Varsayılan hedef: R2 PO imzası bloke değilse
F-07 §4.4 (4 yüzey backend display-DTO) veya Round-3 backlog S5.

Dikkat — bu slice'ın bıraktığı üç kural:
1) Yeni mutating route'ta gövdeyi TYPED response model olarak bildir; dict[str, Any] dönüşü
   sözleşmeyi docs/openapi.json'dan gizler ve drift guard yine yeşil kalır.
2) Yeni ZORUNLU yanıt alanı eklerken run_idempotent replay'i için backfill yaz — eski zarf
   alanı taşımaz ve katı model onu 500'e çevirir (bkz. commands/deletion.py::request_purge).
3) Rebase/merge sonrası grep -c "^## <slice>" docs/PROJECT_HISTORY.md ile kaydın düşmediğini
   doğrula — #408 ve 0af080f'te iki kez düştü.

Lokal verify: cd backend && uv run ruff check . && uv run ruff format --check . &&
uv run mypy src && TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_o30
uv run pytest --no-cov -q  (tek çağrı, ortada öldürme, tail KULLANMA).
```
