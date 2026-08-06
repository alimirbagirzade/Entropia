<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# O-06 landed — kickoff / handoff for the next slice

> Bu dosya **O-06 (CancelBacktestRun — controlled cancellation)** kapandıktan sonraki temiz
> oturum için yazıldı. Tam tarihsel kayıt: `docs/PROJECT_HISTORY.md` §"O-06 · CancelBacktestRun".
> Kısa özet + Next: `docs/STAGE2_HANDOFF.md` §"O-06 — ... landed".

---

## Neredeyiz

- **alembic head:** `0039_backtest_run_cancellation` (tek head). O-06 öncesi head
  `0038_backtest_run_event` idi. **CLAUDE.md §Current position bir süre `0035`'i gösteriyordu —
  bayattı; STALE-BY-DEFAULT kuralını her oturumda uygula.**
- **ENGINE_VERSION:** `backtest-engine-v18-funding-step-order` (**O-06'da bump YOK** — motor
  semantiği değişmedi, yalnız durma noktaları eklendi).
- **Backtest RUN yüzeyi artık tam:** admission (`request_backtest_run`) · durum + olay replay
  (`get_backtest_run`, `list_backtest_run_events`) · **cancel** (`cancel_backtest_run`) · retry
  (`retry_backtest_run`) · Result soft-delete (`soft_delete_backtest_result`).
- **Blokaj (değişmedi):** product-owner imzası — `docs/implementation/v18_final_acceptance.md` §4.

---

## O-06 ne bıraktı — REUSE anchor'ları (tam sembol adlarıyla)

| Sembol | Dosya | Ne için yeniden kullanılır |
|---|---|---|
| `cancel_backtest_run` | `application/commands/backtest_run.py` | owner/Admin + OCC + Idempotency taşıyan iptal komutu deseni |
| `_cancel_queued_run` / `_request_worker_cancellation` | aynı dosya | "worker sahiplenmemişse terminal, sahiplenmişse niyet" ayrımı |
| `_emit_cancellation_audit` | aynı dosya | aktör kimliğiyle audit + outbox ikizi |
| `_cancellation_requested` | `application/jobs/backtest_engine.py` | **stage sınırında** iptal yoklama (refresh + flag) |
| `_cancel_run` | aynı dosya | terminal CANCELLED + `RUN_CANCELLED` + audit + job finalize, **Result YAZMADAN** |
| `bt_repo.get_run(..., for_update=True)` | `infrastructure/postgres/repositories/backtest.py` | claim/cancel yarışını **ek round trip olmadan** kapatan satır kilidi |
| `RunNotCancellableError` | `shared/errors.py` | 409 `RUN_NOT_CANCELLABLE`, `LIFECYCLE`, retryable=false |
| `reconcile_occ_tokens` | `shared/concurrency.py` | O-12 dual-token kuralı — cancel dahil her dual uç buradan geçer |
| `_CANCEL_DELIVERY_POLICY = "cancellation_safe_boundary"` | `commands/backtest_run.py` | geç kalan iptalin dürüst sözleşmesi (Analysis Lab `stop_run` ile aynı) |
| `tests/integration/test_backtest_run_cancellation.py` | — | `_provisioning_run` helper'ı: worker'ı öldürüp run'ı **durably PROVISIONING** bırakma tekniği |

**Kritik tasarım kararı — tekrar etmeden önce oku.** Cancel bir **state değil**. Doc 15 §4
BacktestRun state kümesini sabitler (`queued/provisioning/running/succeeded/failed/cancelled`);
bekleyen istek o kümenin üyesi olmadığı için `cancel_requested_at` **kolonu** kullanıldı.
`RunEventType` taksonomisine yeni üye eklenmedi — `RUN_CANCELLED` zaten tanımlıydı.

---

## Sonraki slice için tasarım işaretleri

1. **Cancel UI (en doğal devam).** Backend hazır; Mainboard RUN kartına iptal düğmesi + `cancellation:
   "requested"` ara durumunun gösterimi. Doc 15 §6.1 metni **zaten yazılı**: "Backtest was cancelled.
   No Backtest Result was created." UI kuralı: v18 mockup otoritedir, route/react-query key/OCC
   token/SSE taksonomisi **değiştirilmez** (CLAUDE.md §UI).
2. **Cancelled run teşhisi kalıcı artifact isteniyorsa:** `diagnostic_artifact` FK'sini gevşetme —
   o tablo `backtest_result`'a bağlı ve CR-03 yalnız SUCCEEDED run'a Result izni veriyor. Run'a
   bağlı **ayrı** bir tablo tasarla. Şu an olay `detail`'i yeterli ve dürüst.
3. **O-serisi backlog'unda kalanlar** için `docs/PROJECT_HISTORY.md`'yi hedefli oku — baştan sona
   okuma.

---

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Önce ampirik doğrula.** O-06 tam da "spec'te var, kodda yok" tipiydi; `grep -i cancel` +
  enum okuması bunu 2 dakikada kanıtladı. Aynı disiplini her O-maddesine uygula.
- **Direct-author (Workflow yok).** Önceki slice'ın desenini aynala.
- **İzole test DB'si ZORUNLU:** `TEST_DATABASE_URL=...entropia_test_<slug>`. Paralel worktree
  oturumları gerçekten aynı anda koşuyor.
- **Tam suite'i tek pytest çağrısında koş.** Tek komutta zincirlenmiş **arka arkaya iki** çağrı,
  ilkinin bağlantıları bırakılmadan ikinciyi başlatıp sahte ERROR üretir (O-06'da
  `test_backtest_run_events.py`'de 4 tane). Koşuyu ortada **öldürme**.
- **GateGuard:** yeni dosyayı Bash heredoc ile yaz; mevcut dosyada EDIT/WRITE fact-force tetikler
  (importers / etkilenen public API / veri şeması / kullanıcı isteği verbatim → retry).
- **PR AÇMADAN ÖNCE `git fetch && git rebase origin/main`.** O-serisi paralel ilerliyor; O-06
  yazıldıktan sonra #414 (O-12/O-13/O-18) aynı dosyaya indi ve CI 22 saniyede 9 × `F821` verdi.
  Lokal suite yeşilken CI kırmızı olabilir — **otorite CI'dır.**
- **Yeni bir mutating uç eklerken O-12'yi hatırla:** gövde token'ı + `If-Match` varsa uç
  **dual-token**'dır; `reconcile_occ_tokens`'tan geçir ve
  `tests/contract/test_occ_dual_token_contract.py` tablosuna ekle.

---

## Paste-ready resume prompt

```
Entropia — O-06 (CancelBacktestRun) landed. Session START protokolünü uygula:
git fetch && git log --oneline origin/main -6 && gh pr list --state all  → neyin gerçekten
merge olduğunu doğrula (handoff STALE-BY-DEFAULT).

Oku (otorite sırası): docs/STAGE_O06_KICKOFF.md (bu dosya) → docs/STAGE2_HANDOFF.md
(§"O-06 ... landed" + §Next) → docs/STAGE_BUILD_PLAN.md → ilgili docs/spec/NN_*.
Kod tarafına geçmeden docs/CODEMAPS/ içinden dokunacağın haritayı oku
(BACKEND_ROUTES / BACKEND_LAYERS / DATA_MODEL / FRONTEND_MAP / JOBS_AND_EVENTS),
sonra codebase-memory-mcp ile sembolleri bul.

Doğrulanmış durum: alembic head 0039_backtest_run_cancellation (tek head);
ENGINE_VERSION backtest-engine-v18-funding-step-order (O-06'da bump yok);
backtest RUN yüzeyi tam (admit / status+events / cancel / retry / result soft-delete).

Sıradaki iş: <BURAYA SLICE>. Öneri sırası:
(a) Cancel UI — POST /backtest-runs/{run_id}/cancel için Mainboard RUN kartı iptal düğmesi +
    "requested" ara durumu; v18 mockup otorite, route/react-query key/OCC/SSE değişmez.
(b) O-serisi backlog'unda kalan maddeler.

Kurallar: direct-author (Workflow yok) · her CRITICAL/HIGH review bulgusunu ampirik doğrula ·
izole TEST_DATABASE_URL · tam suite TEK pytest çağrısı · backend verify
(ruff + ruff format --check + mypy src + pytest) + migration varsa alembic up/down/up +
kolon paritesi + her yeni create_* için L1 FK insert-order proof · NO AI attribution ·
feat/<slug> dalı, ayrı PR.
```
