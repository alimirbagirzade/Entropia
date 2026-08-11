# Entropia — Claude Operating Guide

Backend-first, **spec-driven, staged** build (FastAPI + Postgres + Alembic + dramatiq).
Specs live in `docs/spec/NN_*`; the stage roadmap is `docs/STAGE_BUILD_PLAN.md`; the
running handoff is `docs/STAGE2_HANDOFF.md`; each slice has a `docs/STAGE<x>_KICKOFF.md`
with a **paste-ready resume prompt** at the bottom.

> Conversation language: **Turkish**. Technical identifiers stay in English.

---

## Session START protocol (do this FIRST, every session)

1. **Verify — the handoff/summary is STALE-BY-DEFAULT.** Never trust a prior-session
   summary or local branch. Run `git fetch`, `git log --oneline origin/main -6`,
   `gh pr list --state all`. Confirm what actually **landed/merged** before acting.
2. **Read in authority order:** (1) latest `docs/STAGE<next>_KICKOFF.md` (this slice's
   full handoff), (2) `docs/STAGE2_HANDOFF.md` ("... landed" + "Next"), (3)
   `docs/STAGE_BUILD_PLAN.md` (stage table + acceptance), (4) `docs/spec/NN_*` (extract
   the spec FULLY), (5) memory checkpoints for the prior stage (ecc graph + claude-mem).
3. The **paste-ready resume prompt** at the bottom of the kickoff doc is your
   continuation seed — that is what gets pasted into a fresh session.
4. **Kod tarafına geçmeden:** dokunacağın alanın `docs/CODEMAPS/` haritasını oku, sonra
   `codebase-memory-mcp` ile sembolleri bul (§"Kod arama"). Geçmiş bir slice'ın ayrıntısı
   gerekiyorsa `docs/PROJECT_HISTORY.md`'den **hedefli** oku — baştan sona okuma.

---

## Session CLOSING ritual (do this at EVERY close — MANDATORY)

Before stopping a working session, produce **ALL** of the following:

1. **Handoff** — update `docs/STAGE2_HANDOFF.md`: add a `## Stage <x> — <title> landed (PR #n)`
   entry (migration, new tables, test counts, review outcome, deferred items) and set
   `## Next: Stage <y> — <title>`.
2. **Kickoff + resume prompt** — create/refresh `docs/STAGE<next>_KICKOFF.md`: where we
   are, what the last slice **left behind (reuse anchors with exact symbol names)**, next
   design pointers, REUSE list, working-loop method, and a **paste-ready resume prompt
   block** (the exact text to paste into a clean session to continue).
3. **Tarihçe + özet — İKİSİ AYRI (context disiplini):**
   - **`docs/PROJECT_HISTORY.md`** → slice'ın **tam** kaydı buraya eklenir (ne landed,
     migration, OCC biçimi, test sayıları, honest boundary'ler).
   - **`CLAUDE.md` §Current position** → SADECE 5–6 satırlık özet güncellenir (HEAD sha,
     alembic head, test sayıları, son dalga, Next). **Buraya slice anlatısı YAZMA** —
     CLAUDE.md her oturumda tamamı context'e yüklenir, ince kalmak zorunda.
4. **Memory checkpoint — write BOTH systems:**
   - **ecc knowledge graph** — an entity `Entropia Stage <x> — <title>` with rich factual
     observations + a relation to the next stage (`unblocks`).
   - **claude-mem** — a checkpoint observation for the slice (searchable via `mem-search`).
5. **Codemap tazeleme** — slice yeni endpoint / tablo / sayfa / job eklediyse
   `docs/CODEMAPS/` içindeki ilgili haritayı güncelle (veya `ecc:update-codemaps`).
6. **Commit -> PR -> await merge** — commit on branch `docs/stage-<x>-landed` (conventional
   message, **NO AI attribution**), push, open a PR to `main`, `gh pr checks <n> --watch`;
   **self-merge is blocked -> ask the user to merge** once green.

---

## Conventions

- **Cost-conscious.** No unnecessary parallel agents or full-file reads. **Empirically
  verify** every code-review CRITICAL/HIGH finding before fixing (they are often wrong).
- **Tembel merdiven (ponytail).** Kod yazmadan önce: gerekiyor mu → codebase'de var mı
  (codemap + `codebase-memory-mcp`) → stdlib → native → kurulu bağımlılık → tek satır.
  Merdiven ve **pazarlıksız Entropia override listesi** (coverage kapısı, katman deseni,
  adjudicated alanlar): `.claude/skills/ponytail-entropia/SKILL.md`.
- **Direct-author (no Workflow)** for backend slices; mirror the previous slice's pattern
  (module-level async commands, one-tx no-commit, `run_idempotent`,
  `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- **GateGuard:** write NEW files via Bash heredoc (`cat > f << 'PYEOF'`) -> gate-free; an
  EDIT/WRITE to an existing file triggers fact-force (present 4 facts: importers / affected
  public API / data schema / user request verbatim -> retry). First Bash of a session
  triggers a one-time fact gate.
- **Local verify (backend):** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
  — `addopts` artık `--cov-fail-under=90` taşıyor, yani **tam suite** koşusu CI'daki coverage
  kapısını da doğruluyor (**ölçülen toplam %92.06**, 2712 passed; frontend %84.67 line —
  modül dökümü + kalibrasyon gerekçesi `docs/audit/coverage_baseline.md`).
  **Alt küme koşarken `--no-cov` ekle:** tek
  dosyalık bir koşu paketin tamamını ~%4 ölçer ve kapı sahte kırmızı verir. Frontend karşılığı
  `npm run coverage` (eşikler `frontend/vite.config.ts`). İkisi de **kapıdır, rapor değil** —
  düşen sayıyı indirme, eksik testi yaz.
  + an **L1 FK insert-order proof for every new `create_*`** + **alembic `<n>` up/down/up**
  (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` before the proof)
  + migration<->model column parity. Local Postgres on **:5432** (`entropia`/`entropia`).
- **Git:** `feat/stage-<x>-<slug>` for features, `docs/stage-<x>-landed` for closing docs.
  Commit `<type>(stage-<x>): <subject>`. **No AI attribution** (disabled globally).
- **Hata zarfı = tek şekil, adjudicated (O-02).** Her HTTP hatası
  `shared/responses.py::ErrorBody`: `code, message, details, request_id, correlation_id`
  (Module 19 orijinali, isimleri **asla değişmez**) + recovery bloğu `category, retryable,
  suggested_action, remediation, scope_type, scope_id, field_path`. **İki spec arasındaki
  isim farkı şöyle karara bağlandı:** doc 01 §11.2'nin `field_issues`'ı = shipped `details`
  (aynı anlam, sevk edilmiş ad kazanır); doc 01'in `suggested_action`'ı ile doc 04 §11.1'in
  `remediation`'ı **iki AYRI alan olarak kalır** — ilki makine token'ı (`"rerun_ready_check"`),
  ikincisi insan metni; birleştirmek birini kaybettirirdi. `category`/`retryable` hata
  **sınıfında** bildirilir (`shared/errors.py::ErrorCategory`); `scope_type`/`scope_id`/
  `field_path`/`remediation` hem sınıfta hem **raise yerinde** pinlenebilir. Sınıflandırılmamış
  hata asla `retryable=true` reklamı yapmaz. Readiness blocker'ında lider blocker'ın
  `remediation`/`field_path`/`scope_id`'si zarfa yükseltilir
  (`commands/backtest_run.py::_readiness_blocked`), `details` yine tüm issue'ları taşır. Yeni
  hata sınıfı eklerken kategorisini bildir; zarf `docs/openapi.json` →
  `components.schemas.ErrorResponse` altında yayımlanır (drift guard onu korur).
- **OCC dual-token = TEK kural, çelişki 409 (O-12).** 16 mutating op token'ı hem gövdeden
  (`expected_*`) hem `If-Match`'ten kabul eder. Bunlar **tek değerin iki yazımıdır**, iki
  bağımsız önkoşul değil (doc 15 §11, doc 20 §14 "Do not treat them as interchangeable
  fields", doc 21 §7). Kural tek yerde: `shared/concurrency.py::reconcile_occ_tokens` —
  **ikisi de verilmiş ve ÇELİŞİYORSA → 409 `OCC_TOKEN_CONFLICT`**
  (`shared/errors.py::OccTokenConflictError`, `category=concurrency_or_preflight`,
  **`retryable=false`** çünkü aynı çelişkiyi tekrar göndermek hep aynı hatayı verir;
  `details` iki değeri de yankılar). Biri verilmişse o kazanır; anlaşıyorlarsa gövde geçer →
  **tek-token çağıranlar (frontend dahil) etkilenmez**. Yeni dual-token uç eklerken kuralı
  route'a KOPYALAMA, bu fonksiyondan geçir. `rationale.revise_family` bilerek dışarıda:
  oradaki `If-Match` atıldı ve farklı eksendi (ETag=row_version, token=revision id) →
  parametre kaldırıldı. Tam liste: `docs/CODEMAPS/BACKEND_ROUTES.md` §DUAL-TOKEN.
- **Idempotency-Key = `run_idempotent`, yeni altyapı YOK (O-13).** Kalıcı satır yazan her
  mutating op `Idempotency-Key` okumalı ve komut gövdesini
  `application/idempotency.py::run_idempotent` ile sarmalı. **Fingerprint'e komutun KENDİSİNİN
  değiştirdiği durumu koyma** (head pointer, row_version) — retry farklı hash'lenir ve sonsuza
  dek 409 verir; girdileri hash'le (`op`, id'ler, payload, çağıranın gönderdiği `expected_*`).
  ORM döndüren komutlarda `_op()` JSON `response_ref` döner, sonra satır o referanstan
  **yeniden okunur** → replay aynı kaynağı, aynı tipte döner. Idempotency-Key okumayan 16 op
  gerekçeli (salt-okuma POST, oturum işlemi, OCC korumalı soft-delete, geçici opener).
- **Upload dosya-tipi kapısı = fail-closed (K-07).** TXT/CSV kaynak yüklemelerinde ortak kapı
  `domain/importing/source_file.py::assert_supported_source_file`: filename yok/boş → **RED**
  (asla "atla"), uzantı iddiası içerik sniff'i ile desteklenir. **Hata kodu sayfa taksonomisine
  göre ayrışır** (adjudicated): Trade Log → `UNSUPPORTED_SOURCE_FILE_TYPE` (doc 05 §12.1),
  Trading Signal → `FILE_TYPE_NOT_ALLOWED` (doc 04 §11), Create Package baseline → aynı kod
  (doc 06 §8.3), Market Data → `MARKET_DATA_FILE_TYPE_NOT_ALLOWED` (doc 11), Research Data →
  `RESEARCH_DATA_FILE_TYPE_NOT_ALLOWED` (doc 12). Kodlar aynı kusuru anlatır; her sayfanın kendi
  §-taksonomisi otoritedir. **Dört komut yüzeyi de** (trade_log, trading_signal, market_data,
  research_data) bu tek kapıyı çağırır — yeni bir upload yüzeyi eklerken kendi kodunla buraya bağla.
- **Trash tip kataloğu = yazılmış yol (K-06).** `domain/trash/page.py::TRASH_OBJECT_LOCATIONS`
  içindeki her tipin soft-delete yolu `trash_repo.add_trash_entry` **yazmak zorundadır** — aksi
  halde nesne aktif projeksiyondan çıkar ama Admin Trash'e hiç ulaşmaz (restore/purge'ün dayanacağı
  entry yok). Registry kökü olmayan tipler (`backtest_result`, `manual_document`,
  `hypothesis_artifact`) kendi satırlarındaki `deletion_state` üzerinden `commands/deletion.py` +
  `jobs/purge.py` + `queries/trash.py` içinde **`entity_type` dalı** ile yürür; yeni tip eklerken
  hepsini birden ekle. Agent artifact: soft delete owner-Agent/Admin (doc 20 §11), restore/purge
  Admin-only, purge preflight **canlı source task**'ta `PURGE_NOT_ELIGIBLE` verir (doc 20 §10).
- **Purge 202 gövdesi = iki ad, tek değer (O-30).** Doc 20 kendi içinde çelişiyor: §7'nin
  literali `root_lifecycle_state: 'soft_deleted'` derken §9.2'nin state machine'i (ve §4, §9.3,
  §12) `soft_deleted --purge request--> PURGE_PENDING` diyor. **Adjudicated:** DEĞER'de §9.2
  kanonik (satır gerçekten `purge_pending` olur ve `PURGE_PENDING -> restore` yasaktır;
  `'soft_deleted'` reklamı "restore hâlâ açık" yalanı olurdu), AD'da §4/§7 kanonik. Bu yüzden
  `commands/deletion.py::request_purge` gövdesi **`deletion_state` ve `root_lifecycle_state`
  anahtarlarının İKİSİNİ birden** `"purge_pending"` değeriyle döndürür — biri kaldırılmaz,
  ikisi asla ayrışmaz. Gövde `run_idempotent` zarfında birebir saklandığı için replay de aynı
  şekli verir; `frontend/src/lib/trash.ts::PurgeResult` bu sözlüğü verbatim aynalar. Gövde
  `routes/trash.py::PurgeAcceptedResponse` ile **şemada yayımlanır** (`components.schemas`);
  bare `dict` döndüren bir route drift guard'ı yeşil tutarken sözleşmeyi görünmez bırakıyordu —
  `test_purge_202_publishes_both_state_field_names` bunu kilitler. O-30 ÖNCESİ yazılmış
  Idempotency-Key kayıtları bu alanı taşımaz; `request_purge` replay'de `deletion_state`'ten
  **backfill** eder (kopyalayarak — `response_ref` JSON kolonu mutate EDİLMEZ), aksi halde katı
  şema eski zarfı 500'e çevirirdi. Yeni bir mutating route eklerken gövdeyi typed model olarak
  bildir: `dict[str, Any]` dönüşü sözleşmeyi şemadan gizler.
- **Stage order is authoritative** (`STAGE_BUILD_PLAN.md`) — never skip sub-stages.
  Stage 5 = docs 15/16/17; Stage 6 = docs 18/19/20; Stage 7 = docs 21/22.
- **UI / frontend = v18 mockup is the visual reference (mandatory).** Every frontend/UI
  change takes `docs/spec/index_guncellenmis_duzeltilmis_v18.html` (the canonical v18 mockup)
  as its layout/style source of truth; the theme lives in `frontend/src/styles/global.css`
  variables (`--accent:#00a9e8 --border:#cfcfcf --radius:4px --text:#222`, Arial). Work is
  **presentation-only** — never touch route paths, react-query keys, OCC tokens
  (If-Match / `expected_*_version` / `X-*-Version`), Idempotency-Key, hooks, SSE taxonomy,
  API calls, or `lib/*.ts` data logic; `app/nav.ts` NAV/ALL_NAV_ITEMS stay verbatim. A broken
  test is re-aligned to the NEW markup (option values + OCC/Idempotency assertions unchanged;
  only visible labels / container scope via `aria-label` + `role`). To preview locally,
  `cp docs/spec/index_guncellenmis_duzeltilmis_v18.html frontend/public/mockup_v18.html` (a
  gitignored dev-only copy — canonical stays in `docs/spec/`).

---

## Current position (keep in sync at each closing)

> **SAYISAL OTORİTE BU BLOK DEĞİL** →
> [`docs/generated/repository_facts.md`](docs/generated/repository_facts.md) (**üretilmiş**:
> alembic head/sayı, tablo & FK, HTTP operation, frontend route, `ENGINE_VERSION`,
> capability ve test **collection** sayıları). Üretici `scripts/generate_repository_facts.py`;
> CI'da `--check` **bloklayıcıdır** ve bu blokla çelişen bir head / `ENGINE_VERSION` /
> `SHARED_ALLOCATION_STATUS` iddiasını kırmızıya çevirir. Aşağısı **elle** yazılır ve
> içindeki **HEAD sha'sı yapısal olarak bayattır** — kapanış commit'inin kendisi onu
> değiştirir; sha'ya değil üretilmiş bloğa güven. Bir belgenin güncel mi tarihsel mi
> olduğunu ilk satırındaki `<!-- doc-status: … -->` işareti söyler.

> **HEAD `881d273`** · **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).
> **Son dalga — ADIM 37 (RC §6.7 / P10-B2, sayfalama sınırı):** 9 kelepçeli `limit`
> parametresi artık sınırını **yayımlıyor** (YENİ `apps/api/pagination.py::clamped_limit_query`
> → `x-clamp-default` / `x-clamp-maximum`; ölçülen 19 ENFORCING + 9 CLAMPING, **UNPUBLISHED 0**).
> **Kalem KAPANMADI:** aşımın sessiz clamp mi 422 red mi olacağı **ürün kararıdır**, canonical
> sessizdir → **PO kararı bekliyor** (rapor §6.7.5). Yeni `limit` eklerken sınırsız bırakma —
> kelepçeliyorsa bu declarator'dan geçir, reddediyorsa `le=` yaz; kapı kırar. Tam kayıt:
> `PROJECT_HISTORY.md` §ADIM 37; devir: `docs/ADIM37_LANDED_KICKOFF.md`.
> Öncesinde ADIM 36 (RC §6.7 / P6-ek + P6-6, harness fail-fast, #658) ve
> **ADIM 35** (`PortfolioRun` → composite `EngineOutput` projeksiyonu, #659): YENİ
> `execution/portfolio_projection.py::project_portfolio_run`; **üretim yolu YOK ve bilerek
> yazılmadı** — §4.1'in (a)/(b) engelleri KAPANMADI, PR B hâlâ ADR §16 insan kapısının
> arkasında (`PROJECT_HISTORY.md` §ADIM 35, `docs/ADIM35_LANDED_KICKOFF.md`).
> Öncesinde ADIM 34 (RC §6.7 / P4-1 + P4-2, şema paritesi, #657): model↔migration index ekseni
> **40 sapmadan 0'a**, `scripts/schema_parity_gate.py` `ci.yml`'a bağlı ve negatifi kanıtlı;
> `alembic check` **yine de exit 255** (P4-3 — 60 `modify_default`, ölçüldü, düzeltilmedi).
> **Yeni index eklerken `index=True` KULLANMA** — `__table_args__` içinde
> `Index("<ad>", "<kolon>")` yaz ve migration'da AYNI adı kullan, yoksa kapı kırmızıya döner.
> Öncesinde ADIM 33 (P9-F1 — frontend build reproducibility, #656),
> ADIM 32 (P9-F2 — SPA origin'inde CSP, #655),
> ADIM 31 (RC blocker 3 — fail-closed bildirim yolu; blocker 4→3),
> ADIM 30 (RC blocker 2, harness — `flows` 60/0/2, ama **CI kapısı değil**),
> ADIM 29 (RC verification, #632–#636; P9-B1 düzeltmesi #637), ADIM 29 (A-08 kayıt
> uzlaştırması, #631), ADIM 28 (#628/#630), ADIM 27
> (#626/#627), ADIM 26 (#624), ADIM 25 (#622) — **ADIM 23/24 artık `PROJECT_HISTORY.md`'de
> KAYITLI** (borç kapandı).
> **Açık sınırlar:** **A-08 denetimi YAPILMADI** (defter BOŞ, dört çıkış kriteri de ☐) ve
> izleme issue'su #514 **KAPALI** — iş açık, izleme kapalı; hiçbir belge A-08'i
> `Complete`/`PASS`/`Done` gösteremez · **P9-B2 imzasız** (react-router freeze'inde owner
> yok — insan işi) · K-2..K-6 ölçüldü ama **düzeltilmedi** ·
> **Alertmanager ARTIK VAR (ADIM 31)** ama üç artık açık: kurallar **gerçek production
> serilerine karşı hiç değerlendirilmedi** (repo içinde kapatılamaz, imzalı sapma DEĞİL) ·
> delivery proof'u **CI kapısı değil** · **monitörü izleyen yok** ·
> **P5/P6 ADIM 30'da yeniden ölçülüp COMMIT EDİLDİ** (`evidence/2026-08-10/`) — ama
> **`flows` CI'da koşmuyor**, sunucu katmanı regresyonu sessizce dönebilir ·
> **P1..P13 tanımı REPODA DEĞİL** (yalnız sohbet transkriptinde) ·
> ~~**`ci.yml` concurrency kusuru**~~ **ONARILMIŞ** (ADIM 34'te doğrulandı): `ci.yml:9–14`
> artık `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` — main'de iptal KAPALI.
> Tarihsel kayıt sabit kalır: `e8d1d48` (#633) ve `bc59dae` (#634) 0 job ile cancelled olmuş,
> CI'ları HİÇ koşmamıştı. Yeni bir job eklerken **gerçekten koştuğunu job log'undan** doğrula.
> **Next:** **PR B** — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.
> ADIM 35 §4.1'in **(c)** engelini kapattı (projeksiyon var); kalan **(a)** faz-bölünmüş bar ve
> **(b)** book-etmeyen değerlendirme girişi `run_engine`'in gövdesine dokunur → **ADR §16 insan
> kapısı + ADR amendment'ı** gerekir, o kapıdan geçmeden başlama.
> **Yarım-cent yuvarlama KARARA BAĞLANDI (2026-08-06):** `initial_sleeve_capital` yeniden
> quantize edilmez, dondurulmuş `derived_amounts`'tan **kopyalanır**; iki yuvarlama sabiti de
> değişmez. Henüz **uygulanmadı** — `STAGE2_HANDOFF.md` §Yarım-cent.

> **Uyarı:** `docs/audit/current_main_ground_truth_2026-08-03.md` §18'in 2/3/4/6 kalemleri
> ADIM 5–8 ile kapandı ama o belge güncellenmedi — ona güvenmeden önce doğrula.
> **İKİ slice adı çift kullanılmış; numaralar bilerek yeniden atanmadı** — merge edilmiş PR
> başlıkları ve commit mesajları değiştirilemez, yeniden numaralandırma dokümanları git
> geçmişinden ayırırdı. Ayrım **başlık ekiyle** yapılır, kural budur:
> **`ADIM 16 (sevk edilen)`** = item intent katmanı (#571/#572) ·
> **`ADIM 16 (ADR §12)`** = `run_engine` resumable stepper (#602) ·
> **`ADIM 21 (worker delivery)`** = at-least-once delivery guard (#587), planlı `ADIM 21` =
> `ItemParticipant`. Yeni kayıt yazarken bu ekleri **aynen** kullan — eksiz "ADIM 16" tek
> anlamlı değildir. Çakışma **kaldırılmadı**, tek-anlamlı hale getirildi (insan kararı).
> **Docs regresyonu ÜÇ KEZ oldu (2026-08-06'da onarıldı):** bayat base'li docs PR'ları
> `PROJECT_HISTORY.md`'den kayıt sildi — #590 (ADIM 18, 211 satır) ve #604 (ADIM 22 + ADIM 16,
> 194 satır; ayrıca bu bloğu boşalttı). Hiçbir CI kapısı `docs/` okumaz. **Docs PR'ı merge
> etmeden önce `git show <sha> -- docs/ | grep '^-## '` çalıştır.** İki rakip ADIM 16 kickoff
> dosyası main'de yan yana — hangisi otorite, insan kararı.


- **Durum:** V1 ROADMAP COMPLETE (Stages 0–8, docs 01–22) + post-V1 + video-alignment +
  V18-R2 dalgası + **auth remediation dalgası COMPLETE** (güvenlik denetimi #346–#364).
  Tüm route yüzeyleri frontend'e bağlı; TIER 2 sayfa haritası 24/24.



- **Testler (backend 2026-08-10 / ADIM 31'de ölçüldü; frontend 2026-08-06 / ADIM 25):**
  **otorite CI'dır.** Backend tam suite **3987 passed / 1 xfailed / 0 failed**, coverage
  **%93.53** (kapı ≥90) — ADIM 31 frontend'e dokunmadı, o yüzden frontend sayıları ADIM 25
  ölçümüdür ve yeniden koşulmadı: **721 passed / 70 dosya**, **%84.92 line**. **Dikkat (eski bir hata, tekrarlama):** ADIM 17
  koşusunda pytest'in özet satırı ve exit code'u yakalanmamıştı — çıktıyı dosyaya yaz, `$?`'i
  **ayrı** oku. **Bilinçli `xfail(strict)` sayısı 1'dir** (eskiden 4 yazıyordu — **bayat**):
  `test_research_point_in_time_parity.py:583`, tek issue **#558** (available-time policy pin'i
  bir ÜRÜN kararı, bug değil). **#556 ×2 ve #557 düzeltildi**, artık normal assert ediyor
  (gateway `rd_jobs.admit_bundle_member` kapısından geçiyor). Oracle paketinde xfail **sıfır**.
  Doğrula: `gh run list --branch main --limit 1` → job log.
  **Ortam tuzağı:** paralel worktree oturumları aynı anda koşuyor — `TEST_DATABASE_URL` ile
  worktree'ye özel izole DB kullan (**sürücü `postgresql+asyncpg://` olmalı**). Tam suite'i
  **tek pytest çağrısında** koş ve **ortada öldürme**; suite koşarken `uv sync`/`uv run`
  çalıştırma ve **`pytest … | tail` KULLANMA** (exit code `tail`'in olur).

- **F-07 raw-id sweep — dört alan LANDED, bir kalıntı AÇIK.** `display_label`,
  `source_package_name`, `item_label`, `scope_label` + ortak `components/LabelledId.tsx`
  yerinde; pinli artefaktların etiketi snapshot/manifest'ten gelir, canlı composition'dan
  ASLA join edilmez. **Kalıntı:** `pages/PanelLogs.tsx:134` hâlâ id'den türetilmiş
  `Backtest Result <id>` başlığını basıyor (Results History'de bilerek terk edilmişti).
  (vitest için **`--no-file-parallelism` ZORUNLU**; worktree'de `frontend/node_modules`
  yoksa önce `npm ci` — ilk koşudaki `ERR_MODULE_NOT_FOUND` test hatası değil.)




- **Açık iş (dürüst sınır):** ekran okuyucu (NVDA/VoiceOver) denetimi **hâlâ yapılmadı**.
  ADIM 28 (#628) yalnız **iskeleyi** kurdu — `scripts/a11y-audit-stack.sh` +
  `docs/audit/a11y_screen_reader_audit_results.md` (**BOŞ defter**, dört çıkış kriteri de ☐).
  Takip **GitHub #514 — 2026-07-30'da kanıtsız kapatılmış, 2026-08-03'te yeniden açılmış,
  2026-08-07'de yine kanıtsız kapatılmıştır**; kapatma yetkisi insandadır, agent kapatamaz.
  Kapalı issue ile boş defter arasındaki ayrışma **sürüyor**; ADIM 29 onu **çözmedi, KAYDETTİ**
  — kanonik blok `docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸ *Tracking-issue
  state*, diğer tüm belgeler oraya işaret eder. Açık duran iki çözüm yolu da **insan işidir**:
  (A) imzalı kalıcı sapma (D-10 biçimi: adı verilmiş imzalayan + ISO tarih + kapsam) —
  **imzalayan verilmediği için böyle bir kayıt YOK**; (B) #514'ün insan eliyle yeniden
  açılması. Hiçbirini agent yapamaz.
  Visual regression ve axe-core ratchet'i CI'da bloklayıcı. Kalan 45 düğüm imza-mavisi
  **D-10 (2026-07-30) imzalı kalıcı sapmasıdır**; WCAG 2.2 AA 1.4.3 karşılanmıyor, ürün bu
  ölçüt için uyumlu sayılamaz.


- **KAPSAM DIŞI (bilerek):** retention auto-purge (doc 20 §16 — "Production V1'de kapalı"),
  LLM generation (Future-Dev), Graphic View renderer (doc 22 — V18 statik placeholder kalır).

> **Tam tarihsel kayıt** — her PR'ın ne getirdiği, ENGINE_VERSION geçmişi, her sayfanın OCC
> token biçimi, honest boundary'ler: **`docs/PROJECT_HISTORY.md`**. Bir slice'ın ayrıntısı
> gerektiğinde oradan **OKU**; buraya geri taşıma. Kapanışta yeni slice kaydı **oraya** yazılır,
> buradaki özet 5–6 satır güncellenir.

---

## Kod arama — dosya okumadan ÖNCE (ZORUNLU)

Bu repo **488 dosya / ~114k satır**. Kör grep + tam dosya okuma hem pahalı hem yavaş.
**Önce graph'a sor, sonra dosya oku.**

`codebase-memory-mcp` bu repoyu **indekslemiş durumda** (~13k node / ~59k edge).
ToolSearch ile yükle ve ilk başvuru noktası yap:

| Araç | Ne için |
|---|---|
| `search_graph` | fonksiyon / class / route bul (isim veya qualified-name deseni) |
| `trace_path` | çağrı zinciri, veri akışı, servisler arası iz |
| `get_code_snippet` | sembolün tam kaynağı (kesin satır aralığı) |
| `get_architecture` | katman / modül yapısı |
| `search_code` | graph-destekli metin araması |

Grep/Glob'u **config, doc ve kod-dışı** dosyalar için serbestçe kullan.
Düzenlemeden önce **her zaman** Read (Edit bunu zaten zorunlu kılar).

**Sıkıştırılmış mimari haritalar → `docs/CODEMAPS/`**

| Harita | İçerik |
|---|---|
| `BACKEND_ROUTES.md` | her endpoint: path → command/query → OCC biçimi → Idempotency → rol kapısı |
| `BACKEND_LAYERS.md` | commands / queries / domain modül haritası + dokunulan tablolar |
| `DATA_MODEL.md` | tablolar, FK'ler, soft-delete + row_version kolonları, alembic head |
| `FRONTEND_MAP.md` | sayfa → `lib/*.ts` → react-query key → endpoint grubu; SSE `EVENT_QUERY_KEYS` |
| `JOBS_AND_EVENTS.md` | dramatiq actor'ları, kuyruklar, outbox→SSE akışı, event taksonomisi |

Bir alana **ilk kez** dokunuyorsan ilgili codemap'i oku — kod taramaya oradan başla.
Codemap'ler türetilmiş dosyadır: mimari değişince `ecc:update-codemaps` ile tazele.
