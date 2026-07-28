# T-01 landed — kickoff / resume seed

> **Bu belge bir sonraki oturumun devam tohumudur.** En altta **paste-ready resume prompt** var.
> Değerler **2026-07-28** tarihinde repodan ampirik doğrulandı; yine de **STALE-BY-DEFAULT** kabul et.

---

## Neredeyiz

**T-01 landed (PR #422, merge commit `b54d7d7`).** Üç kritik modülün mevcut davranışı teste
kilitlendi. **Kaynak koda dokunulmadı** — yeni davranış yok, migration yok, `ENGINE_VERSION`
sabit. Diff tamamen `tests/` altında: 3 dosya, +748 satır, 55 test.

**Ortam uyarısı — main bu slice sırasında altımızdan kaydı.** #422 merge edilirken paralel
oturumlar K-09 (engine god-module extraction, #423/#425/#426/#424) ve K-10 (bar-loop ledger,
#428/#429) ile #427 (engine golden-digest guard) indirdi. Bu kickoff **yalnız T-01'i** anlatır;
K-09/K-10'un kendi kapanış kayıtları ayrı gelir (veya gelmemiştir — kontrol et).

**Ampirik olarak doğrulanmış güncel değerler (`origin/main` @ `f78404f`):**

- **alembic head: `0039_backtest_run_cancellation`** (39 migration). Chain sonu:
  …→0035_portfolio_rules→0036_manual_duplicate_override→0037_package_revision_link→
  0038_backtest_run_event→0039_backtest_run_cancellation (`0039` O-06 / #419 ile geldi).
  **Not:** bu oturumun worktree'si `eff8ffe` tabanlıydı ve oradaki CLAUDE.md `0035` diyordu;
  bu bayat bir doküman değil, eski bir oturum tabanıydı — main'deki CLAUDE.md O-06 kapanışında
  zaten güncellenmişti. Ders: worktree kopyasındaki değere değil, `origin/main`'e sor.
- **`ENGINE_VERSION` = `backtest-engine-v18-funding-step-order`** (`domain/backtest/manifest.py:83`) —
  değişmedi.

---

## T-01'in geride bıraktığı reuse anchor'ları (tam sembol adlarıyla)

| Dosya | Ne sağlıyor — yeni test yazarken BUNU kopyala |
|---|---|
| `backend/tests/unit/test_role_matrix_contract.py` | `_CANONICAL_ROWS` + `_ALL_CELLS` deseni: politika tablosunu **modülden türetmeden** literal yaz, `pytest.mark.parametrize` ile hücre hücre karşılaştır. Bir politika matrisini kilitlemenin referans şekli. |
| `backend/tests/integration/test_audit_log_read_model.py` | `_seed_events()` — `evt_%04d` sıfır-dolgulu id'ler gerçek ULID'lerin zaman-sıralı davranışını taklit eder, keyset cursor'ı deterministik test eder. `_override(app, actor, session)` — **gerçek Postgres session'ı ile route sürme** (contract testleri `_DummySession` kullanır; bu, route + query'yi birlikte test etmenin yolu). |
| `backend/tests/integration/test_allocation_settlement_currency.py` | `_item(kind, pinned_revision_id)` — `MainboardWorkingItem`'ı **session'a eklemeden detached** kur; resolver yalnız 3 alan okuduğu için tüm FK zinciri (workspace/registry/composition) kurulmadan branch testi yazılabilir. `_mirror_revision()` — doc 02 §7.1 mirror şeklini `strat_repo.create_strategy` + `append_strategy_revision` + `mb_repo.append_work_object_revision` ile **validation/reference makinesine girmeden** üretir. `_signal_revision()` / `_trade_log_revision()` — `source_asset` + normalized/batch satırını pinleyip work-object revision'a bağlar. |

**Mutasyon disiplini (bu slice'ta uygulandı, tekrarla):** bir "davranışı kilitleyen" test yazdın mı,
kaynağa kasıtlı kusur enjekte edip **tam olarak bir** testin düştüğünü gör, sonra geri al. Yeşil
kalan bir kilit testi, kilitlemediğini kanıtlamaz.

---

## Bu slice'ın düzelttiği iki backlog yanlışı (O-26 kaydına işlenmeli)

1. **`role_matrix` "testsiz" DEĞİLDİ.** `tests/unit/test_admin_panel_taxonomy.py::test_role_matrix_projection`
   ve `tests/integration/test_panel_management_logs.py::test_role_matrix_admin_only` zaten referans
   veriyordu. Ama 20 rol×yetenek hücresinden **14'ü** pinlenmemişti. Endişe (sessiz regresyon)
   doğruydu, gerekçe yanlıştı. Kaydı **"eksik kapsanmış"** diye düzelt.
2. **`list_audit_events`'in filtresi YOK.** Brief "filtre kombinasyonları" istiyordu; bu modül
   sadece `cursor` + `limit` alır. Filtreli log yüzeyi **ayrı** bir modüldür: Admin Panel
   `list_log_events` (doc 19, `domain/admin_panel/log_taxonomy.py` + log cursor) ve o zaten test
   edilmiş. Olmayan filtreye test yazmak "yeni davranış EKLEME" yasağını çiğnerdi.

---

## Sıradaki tasarım işaretleri

**Ana blokaj değişmedi: PO imzası.** `docs/implementation/v18_final_acceptance.md` §4 (D-1…D-9).
İmza olmadan `entropia_v18_remediation_status.md`'deki R2 RE-OPENING banner'ı kalkmaz, hiçbir satır
Complete olmaz (GAP madde 17).

**Test-boşluğu backlog'u devam ederse** (T-serisi mantıklı bir seri adı):
- `queries/audit_log.py`'nin filtreli kardeşi **`list_log_events`** — zaten testli; T-01 ona
  dokunmadı, kapsam derinliği **denetlenmedi**. Aynı hücre-hücre disiplini orada da uygulanabilir.
- O-03'ten devreden **5 ölü error sınıfı** (`KNOWN_UNRAISED`) ayrı slice bekliyor.
- K-09/K-10 engine extraction'ı yeni modüller doğurdu (order matching, stop resolution, sizing,
  leverage, cost model, funding decision, `_Ledger`). **Bunların test kapsamı denetlenmedi** —
  #427'nin golden-digest guard'ı uçtan uca davranışı pinliyor ama modül-içi dalları pinlemiyor.
  T-02 için en güçlü aday bu.

---

## REUSE listesi (yeniden yazma)

- **Test izolasyonu:** `tests/integration/conftest.py::session` — her testte `drop_all`/`create_all`.
  **`TEST_DATABASE_URL` ZORUNLU** (aşağıdaki tuzağa bak).
- **Route sürme:** `RequestContext` + `request_context` dependency override (contract testlerindeki
  `_override` deseni), `ASGITransport` + `AsyncClient`.
- **Seed yardımcıları:** `instrument_repo.create_instrument`, `asset_repo.create_source_asset`,
  `ts_repo.create_normalized_revision`, `tl_repo.create_record_batch`, `mb_cmd.create_work_object`
  (Trading Signal / Trade Log için `available_time` ZORUNLU, gelecekte olamaz).

---

## Çalışma yöntemi (bu slice'ta işe yarayan döngü)

1. **Önce ampirik doğrula, backlog'a inanma.** Bu slice'ta 3 iddiadan 1'i yanlış, 1'i yarı yanlış çıktı.
2. Testi yaz → koştur → **mutasyonla ısırdığını kanıtla** → mutasyonu geri al.
3. Backend verify: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
   ardından izole DB ile tam suite.
4. Commit → PR → `gh pr checks <n> --watch` → **self-merge kapalı, kullanıcıdan merge iste**.

### Ortam tuzakları — ikisi de bu slice'ta ısırdı

- **Paylaşılan test DB'si:** paralel worktree oturumları `entropia_test`'i ezer.
  `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_test_<slug>` kullan.
- **Tam suite koşarken `uv` komutu çalıştırma.** Bu slice'ta suite koşarken `uv sync`/`uv run`
  çalıştırıldı; venv ortadan yeniden kuruldu ve **20 sahte ERROR** üretti. Sessiz yeniden koşuda
  sıfır hata. Ayrıca **`pytest ... | tail` KULLANMA** — exit code `tail`'in olur, pytest'in değil;
  bu slice'ta bir tur boyunca kırmızı suite yeşil sanıldı. Çıktıyı dosyaya yaz, `$?`'i ayrı oku.

---

## Paste-ready resume prompt

```
Entropia — T-01 sonrası devam. Session START protokolünü uygula: git fetch, git log --oneline
origin/main -6, gh pr list --state all ile NE MERGE OLDUĞUNU doğrula (main hızlı akıyor,
handoff STALE-BY-DEFAULT). Sonra oku: docs/T01_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md
(§T-01 + §Next) → docs/STAGE_BUILD_PLAN.md. Ayrıntı gerekirse docs/PROJECT_HISTORY.md §T-01'den
HEDEFLİ oku.

Bağlam: T-01 (PR #422) audit-log read model, role matrix ve settlement-currency resolver'ının
mevcut davranışını teste kilitledi — kaynak koda dokunmadan, 55 test, migration yok.
Doğrulanmış değerler: alembic head 0039_backtest_run_cancellation,
ENGINE_VERSION backtest-engine-v18-funding-step-order.

Sıradaki en güçlü aday T-02: K-09/K-10'un engine extraction'ıyla doğan yeni modüllerin
(order matching, stop resolution, position sizing, leverage, cost model, funding decision,
_Ledger) test kapsamını ampirik denetle — #427'nin golden-digest guard'ı uçtan uca davranışı
pinliyor ama modül-içi dalları pinlemiyor. Önce grep ile kapsamı DOĞRULA, backlog iddiasına
güvenme.

Kural: yeni davranış EKLEME, yalnız mevcut davranışı kilitle. Her kilit testini mutasyonla
ısırdığını kanıtla. Test isimleri davranışı anlatsın. Backend verify ZORUNLU:
TEST_DATABASE_URL ile izole DB, tam suite'i tail'e BORULAMA (exit code yanıltır),
suite koşarken uv komutu çalıştırma. Ayrı branch, ayrı PR, NO AI attribution.
```
