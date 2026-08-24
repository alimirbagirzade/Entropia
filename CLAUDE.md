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
   the spec FULLY), (5) önceki slice'ların hafıza indeksi — `agentmemory` MCP'si
   (`memory_recall` / `memory_smart_search`). **Taze bir container'da store BOŞTUR**;
   `node scripts/memory_index.mjs --sync` (~3 sn) `docs/PROJECT_HISTORY.md`'den yeniden
   üretir — tekrar koşmak güvenlidir. Sunucu `.mcp.json` üzerinden **kendiliğinden**
   kalkar (`scripts/memory_mcp.sh`); kalkmışsa arama semantiktir, kalkmamışsa **harfi
   harfine** olur ve İngilizce parafraz hiçbir şey bulmaz (§Hafıza). İndeks kaydı
   **otorite DEĞİLDİR**, işaret ettiği `PROJECT_HISTORY.md` §bölümü otoritedir.
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
   block** (the exact text to paste into a clean session to continue). **Yeni kickoff
   `current`, bir önceki `historical` olur — ikisi birlikte yapılır.** Yalnız kendi
   belgeni işaretlemek yetmez: #697 kendi kickoff'unu `historical` bırakıp öncekini canlı
   bıraktı, #714 ise arada yeni bir slice indiği için yanlış belgeyi promote etti. İkisi de
   tek `current` taşıdığı için sayı kuralından geçmişti; artık `check_classification` yakalar.
3. **Tarihçe + özet — İKİSİ AYRI (context disiplini):**
   - **`docs/PROJECT_HISTORY.md`** → slice'ın **tam** kaydı buraya eklenir (ne landed,
     migration, OCC biçimi, test sayıları, honest boundary'ler).
   - **`CLAUDE.md` §Current position** → SADECE 5–6 satırlık özet güncellenir (HEAD sha,
     alembic head, test sayıları, son dalga, Next). **Buraya slice anlatısı YAZMA** —
     CLAUDE.md her oturumda tamamı context'e yüklenir, ince kalmak zorunda.
4. **Memory checkpoint — TÜRETİLİR, elle yazılmaz (ADIM 53'te değişti).** Slice kaydını
   md. 3'te `docs/PROJECT_HISTORY.md`'ye yazdıktan **sonra** tek komut:
   `node scripts/memory_index.mjs --sync --only <slice-slug>`. Tek doğruluk kaynağı
   **git'teki belge**; agentmemory onun **aranabilir indeksidir**, rakibi değil — bu yüzden
   efemer bir container'da kaybolması bir borç doğurmaz, `--sync` (argümansız) baştan
   üretir. **Kayıt kendi otoritesini adıyla taşır** (`§<başlık>` + satır no) ve char
   bütçesinde kesilir: bu repoda bir cümlenin düşmesi anlamı tersine çevirir (O-30'un iki
   adı, `ADIM 16 (sevk edilen)`/`(ADR §12)` ekleri, K-6a/K-6b bölünmesi) — indeks o metne
   **işaret eder**, yerini almaz. `--check` CI'da (`Frontend` job'ının adımı) her `## `
   kaydının tekil id türettiğini doğrular; **id çakışması = başlıkta ayırt edici ek yok**.
   > **Neden değişti (insan kararı, 2026-08-13):** `ecc` + `claude-mem` ikilisi remote
   > container'da **kayıtlı değil** ve elle yazılan checkpoint efemer store'la birlikte
   > ölüyordu → md. 4 ADIM 47/48/49'da **üst üste üç kez** düştü. `docs/memory/PENDING_CHECKPOINTS.md`
   > *"üçüncü bir seçenek yok"* diyordu; vardı — **bağımlılığı ters çevirmek**. İkisi
   > yerelde bağlıysa yazmak serbest, ama **artık zorunlu değil**.
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
- **İki bloklayıcı guard artık plugin kurulumundan bağımsız koşar (ADIM 58).**
  `.claude/settings.json` `guard-git.sh` (Bash) + `guard-generated.sh` (Edit/Write) betiklerini
  doğrudan kaydeder. Pratik sonucu: **`git push --force … main`, self-merge (`gh pr merge`) ve
  bu desenleri yalnızca İÇEREN bir heredoc/döngü Bash çağrını bloklar** — eşleşme komut
  dizesinin tamamındadır (fail-closed, bilinçli). Böyle bir metni **Write ile dosyaya yaz,
  sonra dosyayı koştur.** Davranış kapısı `scripts/hook-guard-proof.sh` (`Frontend` job'ında).
- **Local verify (backend):** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
  — `addopts` artık `--cov-fail-under=90` taşıyor, yani **tam suite** koşusu CI'daki coverage
  kapısını da doğruluyor. **BURAYA SAYI YAZMA.** Toplanan (collected) sayıların tek otoritesi
  `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` ile kapılı); **geçen
  (passed) sayının ve coverage yüzdesinin tek otoritesi bir CI koşusudur** — üretilmiş
  artefakt bunu bilerek taşımaz ("only a full CI run reports passes"). Eskiden burada duran
  `%92.06 / 2712 passed / frontend %84.67` **ADIM dönemi tabanıydı**; `docs/audit/coverage_baseline.md`
  (`doc-status: historical`) içinde **doğru**, burada present-tense okunduğu için **bayattı**
  (P-B/DR-2). Kalibrasyon gerekçesi ve modül dökümü için o belgeye bak.
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
- **OCC dual-token = TEK kural, çelişki 409 (O-12).** Bir dizi mutating op token'ı hem gövdeden
  (`expected_*`) hem `If-Match`'ten kabul eder — **kaç tane olduğunu buraya YAZMA**: tek tek
  sayılmış kanonik liste `docs/CODEMAPS/BACKEND_ROUTES.md` §DUAL-TOKEN'da yaşar (buradaki elle
  yazılmış sayı `trash.soft_delete` O-18'de dual olduğunda bayatlamış ve öyle kalmıştı). Bunlar **tek değerin iki yazımıdır**, iki
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
- **Aktif-koşu reddi = TEK ad, sevk edilen kazanır (O-31).** Üç sayfa belgesi **tek** bir
  reddi üç türlü adlandırıyor: `ACTIVE_RUN_DEPENDENCY` (doc 03 §14, doc 04 §15),
  `DELETE_BLOCKED_BY_RUNNING_JOB` (doc 20 §15), `OBJECT_IN_ACTIVE_RUN` (doc 01/15). Yalnız
  sonuncusu sevk edilmiş (`shared/errors.py::ObjectInActiveRunError`, 409). **Adjudicated
  (O-02 emsali): sevk edilen ad kanoniktir, diğer ikisi tarihseldir** — sevk edilmiş kodu bir
  belgeye uydurmak için yeniden adlandırmak bir yazım uğruna tüm çağıranları kırardı. Wire
  kodu + 409 `test_backtest_persistence.py::test_active_run_blocks_work_object_delete`
  içinde **pinlidir**; exception TİPİNİ assert etmek yetmez, yazım sessizce kayar.
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
> olduğunu ilk satırındaki `<!-- doc-status: … -->` işareti söyler. **Canlı kickoff EN YENİ
> slice'ınkidir** ve `check_classification` bunu CI'da doğrular: tek bir `current` yetmez,
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varsa kapı kırmızı verir.

> **Araç yapılandırması — SLICE DEĞİL (PR #739, 2026-08-17):** `.claude/settings.json`
> `permissions.allow` **18 → 42** girdi. Eklenenler: §Local verify'ın dört backend adımı,
> üç frontend kapısı, iki `memory_index` kapısı (dokuzu da **tam biçim**) + 15 salt-okur MCP
> aracı (`codebase-memory-mcp` graph araçları, `Claude_Code_Remote` listeleme). **Joker
> yok** — `Bash(uv run *)` / `npm run *` / `node *` keyfi kod çalıştırdığı için bilerek
> dışarıda, `Bash(uv run ruff check *)` bile alınmadı (`--fix` dosya yazar); mutating MCP
> aracı (`index_repository`, `delete_project`, `ingest_traces`, `manage_adr`) alınmadı.
> **Ürün kodu, migration, `ENGINE_VERSION`, OpenAPI değişmedi; blocker sayısı DEĞİŞMEDİ
> (1 — yalnız A-08).** Mevcut 18 girdiye, `hooks` bloğuna ve ADIM 58'in dört guard kaydına
> dokunulmadı. **`PROJECT_HISTORY.md` kaydı ve kickoff'u YOK, bilerek** — bu bir ADIM
> slice'ı değil, izin yapılandırması (insan kararı: kısa not yeterli).

> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. **Son dalga — ADIM 102 (kabul borcu batch 23, doc 16 Results History BACKEND):
> ÜRÜN KODU DEĞİŞMEDİ, iki yeni integration case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız
> A-08), BLOCKED.**
> İki kriter kapandı — **`RH-13.c2`** (profil değişimi History digest'ini
> kıpırdatmaz) · **`RH-14.c3`** (`artifact.create` referans verdiği Result satırına yazmaz);
> ikisi de son açık clause'du → `debt_class`'ları **KALDIRILDI** ve **doc 16 BİTTİ (16/16)**.
> **Tavanlar İNDİ: `partial` 64 → 62 · `debt_class.B` 32 → 30** (açık borç 71 → 69).
> Taban `43dc70d`. Tam kayıt: `PROJECT_HISTORY.md` §ADIM 102 ·
> `docs/ADIM102_LANDED_KICKOFF.md`.

> Öncesinde **ADIM 101 (kabul borcu batch 22, doc 21 User Manual BACKEND): ÜRÜN
> KODU DEĞİŞMEDİ, iki yeni integration case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız
> A-08), BLOCKED.**
> İki kriter kapandı — **`UM-08.c5`** (soft delete'in izi) · **`UM-13.c3`** (eşzamanlı append);
> ikisi de son açık clause'du → ikisinin de `debt_class`'ı **KALDIRILDI**.
> **`UM-08.c5`: olay ZATEN yazılıyordu, hiç kimse OKUMUYORDU** — `commands/manual.py:625-646`
> üç düzlemi birden yazar (`ManualPublicationEvent` + audit + outbox) ama suite bu şekli **yalnız
> purge için** pinlemişti → **tüm iz komuttan silinse dosyadaki 27 testin 27'si de yeşil kalırdı**
> (iddia değil, NC-1'de ölçüldü). Yeni case üç düzlemi de sürer **artı dördüncü bir eksen: iz
> EKLENİYOR, yeniden yazılmıyor**; belge silinmeden önce **revize edilir**, yoksa `revision_id`
> *"delete anındaki head"* ile *"ilk revizyon"*u ayırt edemez. **`UM-13.c3`: mekanizma vardı,
> ÇEKİŞME ALTINDA hiç sürülmemişti** — dosyadaki her test tek session'ı sırayla sürüyor, yani ne
> `pg_advisory_xact_lock` ne de iki unique kısıt bir yarışa **hiç hakemlik etmemişti**; yeni case
> iki **bağımsız engine/bağlantı** üzerinde iki append koşar ve ikisini **`asyncio.Barrier`** ile
> salar — **bariyer komuttan ÖNCE**, içeride salmak kilitlenir. **BEŞ negatif kontrol, beşi de
> HEDEF assertion'ında kırmızı ve beşinde de önceden var olan 27 test YEŞİL kaldı.**
> **ASIL DERS: GÖLGE KALDIRILABİLİR, sadece kaydedilmek zorunda değil** — ilk üç assertion
> dördüncüyü gölgeliyordu; NC-4 belgenin **eski** olaylarını siler ama delete olayını **doğru
> alanlarla** yazar → (1)(2)(3) **geçer**, yalnız sıralı iz karşılaştırması düşer (ADIM 100
> gölgeyi deftere yazmakla yetinmişti; önce **kaldırmayı** dene). **İKİNCİ DERS: bir yarış
> testinin VACUITY KANITI kendi negatif kontrolüdür** — kilit kaldırılınca **çakışma oluyorsa**
> örtüşme ölçülmüştür (sıralı iki append çakışmazdı); determinizm **iki yönde** ölçüldü: kilitle
> **8/8 yeşil**, kilitsiz **5/5 kırmızı**. **Tavanlar İNDİ: `partial` 66 → 64, `debt_class.B`
> 34 → 32**; açık borç **71** (A=1 · B=32 · C=6 · D=32). **DOC 21'İN BACKEND BORCU BİTTİ** —
> kalan üç `partial` satırın ikisi sınıf D (`UM-04.c4`, `UM-12.c3`), biri sınıf B ama **frontend**
> (`UM-15.c3`). **ORTAM: container ÇIPLAK başladı** — `.venv` ve Postgres cluster'ı yoktu, ikisi
> de kuruldu; `alembic upgrade head` **`LC_ALL=C.UTF-8 PYTHONUTF8=1`** ile koşuldu.
> **DÜRÜST SINIR:** frontend'de sıfır satır → hiçbir frontend kapısı koşulmadı; tam suite uçtan
> uca koşulmadı → geçen sayı ve coverage **CI'ın otoritesinde**. `test_user_manual.py` 27 → 29.
> **NUMARA: dal `7f4d927`'den kesildi ve o an açık PR listesi BOŞTU** — ADIM 100'ün kaydettiği
> gibi bu bir garanti değil, **anlık görüntüdür**; main ilerlerse dal **rebase** edilir ve tavan
> **merged ağaçta yeniden ölçülür**, taşınmaz.
> `PROJECT_HISTORY.md` §ADIM 101 · `docs/ADIM101_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 100 (kabul borcu batch 21, doc 22 Future Dev BACKEND): ÜRÜN
> KODU DEĞİŞMEDİ, iki yeni integration case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız
> A-08), BLOCKED.**
> İki kriter kapandı — **`FD-04.c4`** · **`FD-05.c4`**; ikisi de son açık clause'du → ikisinin de
> `debt_class`'ı **KALDIRILDI**. **Davranış ZATEN SEVK EDİLMİŞTİ** (`query_view_dataset` ile
> `create_analysis_artifact`'in gövdelerinde herhangi bir result tablosuna **tek bir yazma yok**);
> boşluk şuydu: doc 22'nin FD-04/FD-05 testlerinin **hepsi** komuta **literal** bir ref veriyordu —
> `"result_abc123"` — ve o dize **hiçbir satırı adlandırmıyor** → *"referans edilen Backtest
> Result'a dokunulmadı"* iddiası doğruydu çünkü **dokunulacak bir şey yoktu**. Yeni case'ler
> **yoğun** bir result tohumlar (3 kanonik metrik, 2 trade-ledger satırı, pinlenmiş manifest
> snapshot'ı), **o result'ın kendi id'sini** ref olarak geçirir ve her şeyi **Postgres'ten** geri
> okur. **ÜÇ TAŞIYICI, üçü de ölçüldü:** yoğunluk muhafızı (boş kökte "değişmedi" **bedavadır**) ·
> geri okumadan önce **`session.expire_all()`** — integration fixture'ı `expire_on_commit=False`
> kurar, yoksa karşılaştırma veritabanına değil **identity map'e** karşı yapılır (ADIM 94
> kuralının **okuma yoluna** uygulanmış hâli) · işlemin **gerçekten indiği**. **BEŞ negatif
> kontrol, beşi de HEDEF assertion'ında kırmızı ve beşinde de önceden var olan 23 test YEŞİL
> kaldı** (24 nokta + 1 F) — boşluğun *iddiası* değil **ölçümü**. **ASIL DERS: EZME ile EKLEME
> AYRI KUSUR SINIFLARIDIR** — satır **demetlerini** karşılaştırmak ezmeyi (NC-3), tam sıralı
> **listeleri** karşılaştırmak eklemeyi (NC-4) yakalar, hiçbiri diğerini göremez ve `count(*)`
> ikisini birden kaçırır. **İKİNCİ DERS: `finally` SÜREÇ SIGTERM ALIRSA KOŞMAZ** — bir kontrol
> koşusu araç zaman aşımıyla öldü, ağaç yamalı kaldı ve bir sonraki kontrol onu **sessizce**
> ölçerdi → **her turdan sonra `git status`**. **GÖLGE AÇIKÇA KABUL EDİLDİ:** `FD-05` case'inin
> son `result_row` assertion'ı üç assertion tarafından gölgelenir → **kendi ekseni sayılmadı**
> (o iddia `FD-04`'ün NC-1'i ile bağımsız ölçülüyor) ve defter notu bunu **yazıyor**.
> **Tavanlar İNDİ: `partial` 68 → 66, `debt_class.B` 36 → 34**; açık borç **73**
> (A=1 · B=34 · C=6 · D=32). **DOC 22'DE SINIF-B KALMADI** — kalan üç `partial` satırın üçü de
> sınıf D (`FD-02.c4` insan HTTP hattında denial kaydı yok · `FD-09.c4` `AnalysisArtifact`'te
> split/seed **kolonu** yok · `FD-13.c4` refüz `_audit_and_outbox`'a hiç ulaşmadan raise ediyor).
> **ORTAM: container ÇIPLAK başladı** — `.venv` ve Postgres cluster'ı yoktu, ikisi de kuruldu;
> `alembic upgrade head` **`LC_ALL=C.UTF-8 PYTHONUTF8=1`** ile koşuldu. **DÜRÜST SINIR:** frontend
> kapıları koşulmadı (frontend'de sıfır satır) → geçen sayı ve coverage CI'ın otoritesinde.
> **NUMARA: dal `2b41cf8`'den kesildi ve o an AÇIK PR LİSTESİ BOŞTU** (`ADIM 99` / `batch 20`
> yazıldı) — **ikisini de kaybetti:** bu PR açıkken **#812** indi ve `ADIM 99` ile `batch 20`'nin
> **İKİSİNİ birden** merge edilmiş adla aldı → bu kayıt **`ADIM 100` / `batch 21`**, kickoff
> dosyası dahil yeniden adlandırıldı. **DERS: boş bir açık-PR listesi bir GARANTİ değil, bir ANLIK
> GÖRÜNTÜDÜR** — dal PR'ını açtıktan sonra da main ilerler (ADIM 91 "çakışma dosya yolunda ölçülür"
> ve ADIM 92 "ayrılan numara güvenli değildir" üzerine üçüncü şekil), ve ADIM 97'nin *"iki numara
> bağımsız taşınABİLİR demek bağımsız taşınIR demek DEĞİLDİR"* uyarısı burada **birebir** gerçekleşti.
> **REBASE edildi, *"Update branch"* düğmesi KULLANILMADI**; on çakışmanın hepsi **iki tarafı da
> koruyarak** çözüldü (`## ADIM` 92 → **93**, silinen kayıt yok) ve **TAVAN TAŞINMADI** — dalın ilk
> freeze'i 67/35 idi, arada #812 `RF-18`'i kapatıp tavanı 68/36'ya çekti, merged ağaçta taze
> `--report` **66/34** verdi. 67/35'i taşımak tavanı gerçek sayının bir üstünde bırakır ve
> `--ratchet` sonsuza dek yeşil kalırdı.
> **YAN İŞ: `docs/generated/repository_facts.*` + README'nin gömülü bloğu bayatladı** (iki test
> collection sayısını oynattı) → yeniden üretildi; ADIM 60'ın dersi bu partide yine yaşandı.
> `PROJECT_HISTORY.md` §ADIM 100 · `docs/ADIM100_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 98 (kabul borcu batch 19, doc 14 Ready Check BACKEND): ÜRÜN
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 99 (kabul borcu batch 20, doc 10 FRONTEND): ÜRÜN KODU
> DEĞİŞMEDİ, tek vitest case + bir opsiyonel harness parametresi + defter. Blocker sayısı
> DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Tek clause **`RF-18.c1`** (sahnelenmiş yeniden
> atamalar remount'ta düşer) → `RF-18` **covered**, **`debt_class` KALDIRILDI**.
> **DERS (yeni kontrol kuralı): "durum kayboldu" iddiasını ölçerken cache'i SICAK tut** —
> remount **AYNI** `QueryClient` ile yapılır; staging query cache'e park edilmiş bir dünyada
> **taze istemcili** sürüm **9/9 geçiyor** (ölçüldü), yani taze istemci bir **yanlış-negatif
> harness**. **ÜÇ negatif kontrol:** modül düzeyi store → **yalnız** yeni test kırmızı, **sekiz
> mevcut case YEŞİL KALIR** (clause'un açık olduğunun kanıtı; mevcut staging testi *stage → SAVE*
> yönünü sürüyor ve kusuru göremiyor) · query cache → aynı assertion · **atıf kontrolü**
> (ADIM 97 kuralı): `renderPage` opsiyonel `client` parametresi aldığı için birinci kontrol yeni
> case **harness'ı tamamen atlayarak** yeniden koşuldu → yine kırmızı.
> **DOC 10'DA TESTİN KAPATABİLECEĞİ SATIR KALMADI** (kalan `RF-08` kayıtlı bulgu +
> `RF-04`/`RF-13` sınıf D). **TAVAN #811 İNDİKTEN SONRA YENİDEN ÖLÇÜLDÜ, İKİ FREEZE
> ÇIKARILMADI** — bu dal `b7e66ad`'de 71→70 / 39→38 ölçmüştü, #811 aynı dosyaya iki kriter daha
> yazdı; merged ağaçta taze `--ratchet`: **`partial` 69 → 68, `debt_class.B` 37 → 36**, açık
> borç **75** (A=1 · B=36 · C=6 · D=32). **DÜRÜST SINIR:** tam frontend suite **yerelde koştu**
> (72 dosya / **736 passed**, coverage kapısı yeşil, lint + typecheck temiz); **backend'e sıfır
> satır → hiçbir backend kapısı koşulmadı ve Postgres kurulmadı**, otorite CI.
> **NUMARA: `96` boşluk DEĞİL — #811 onu `98`'e taşıyıp aldı**; bu kayıt **99 / batch 20**.
> `PROJECT_HISTORY.md` §ADIM 99 · `docs/ADIM99_LANDED_KICKOFF.md`.
>
>

> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. **Öncesinde ADIM 98 (kabul borcu batch 19, doc 14 Ready Check BACKEND): ÜRÜN
> KODU DEĞİŞMEDİ, üç yeni integration case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız
> A-08), BLOCKED.**
> İki kriter kapandı — **`RC-10.c2`** (*"yeni bir katalog revizyonu tek başına raporu stale
> etmez"*; suite'te karşılığı yalnız `is_stale(a, a) is False` idi, o da fingerprint'in HANGİ
> revizyon id'sinden kurulduğunu söylemez → clause **iki katalog** üzerinde sürüldü: iş nesnesi
> head'i ilerler/pin durur, ve APPROVED `md_rev_2` dataset head'i olur/payload `md_rev_1`'i
> adlandırır) · **`RC-17.c2`** (üç mevcut testin üçü de **komut sınırında** durur, orada gövde
> yoktur; yeni case rotayı **ASGI app + gerçek session** ile sürüp **serileştirilmiş zarfı**
> tarar, ve pozitif kontrol aynı rotanın sahibine **aynı kimlikleri yayımladığını** assert eder).
> **YEDİ negatif kontrol; BİRİ REDDEDİLDİ VE DERS ODUR:** market head'ini fingerprint'in
> **kendisine** katan kontrol raporu **doğduğu anda** stale ediyordu → test kendi **ÖN
> KOŞULUNDA** kırmızı verdi ve yanında **ilgisiz, önceden var olan** bir testi de düşürdü;
> kırmızı vardı ama **clause'a atfedilemiyordu**. **BİR KONTROL YALNIZ HEDEF TESTİ VE YALNIZ
> HEDEF ASSERTION'I DÜŞÜRMELİDİR** — yerine ön koşulu bozmayan biri kuruldu. İkinci ders:
> **KEY LOOKUP BİR SIZINTI TESTİ DEĞİLDİR** — sızıntı `message` içindeki düz metne konunca
> `details == []` ve `scope_id is None` **yeşil kalır**, yakalayan tek şey substring taramasıdır.
> **Yedi kontrolün hepsinde önceden var olan suite YEŞİL kaldı** (istisna **tipini** assert
> etmek zarfın ne taşıdığını göremez) → ikisi de gerçek boşluktu.
> **Tavanlar İNDİ: `partial` 71 → 69, `debt_class.B` 39 → 37**; açık borç **76**
> (A=1 · B=37 · C=6 · D=32). **DOC 14'ÜN BACKEND BORCU BİTTİ** (kalan `RC-09.c3` frontend).
> **ORTAM: container ÇIPLAK başlayabilir** — `.venv` ve Postgres cluster'ı **yoktu**, ikisi de
> kuruldu; **`alembic upgrade head` `LC_ALL=en_US.UTF-8` ile `UnicodeDecodeError` verir bu
> imajda** (`C.UTF-8` + `PYTHONUTF8=1` ile geçer). **DÜRÜST SINIR:** frontend kapıları
> koşulmadı (frontend'de sıfır satır), tam suite sonuna kadar koşmadı (yalnız `--collect-only`)
> → geçen sayı ve coverage CI'ın otoritesinde. **NUMARA: açık İKİ PR (#806, #809) da
> `docs/ADIM95_LANDED_KICKOFF.md` ekliyordu; PR açıkken **#809 `95`'i, sonra #806 `97` + `batch
> 18`'i aldı** → bu kayıt **`96` → `98`'e taşındı** (kickoff dosyası dahil yeniden adlandırıldı;
> `check_classification` canlı işaretin EN YÜKSEK numaralı dosyada olmasını ister) ve
> **`batch 19`** kaldı. `batch 18` boşluk OLMADI — #806 doldurdu, yani atlama kararı doğru çıktı.**
> **İKİ KEZ REBASE, VE İKİNCİSİ BİR TAVAN HATASI YAKALADI:** *"Update branch"* düğmesi hiç
> kullanılmadı (ADIM 93/94'ün iki zararı); her seferinde main üzerine rebase edildi, çakışmalar
> **iki tarafı da koruyarak** çözüldü (ADIM 95 ve 97'nin kayıtları+handoff'ları duruyor,
> kickoff'ları `historical`), `## ADIM` sayısı 89 → 90 → **91**, silinen kayıt yok. **ASIL
> BULGU:** bu dalın ikinci freeze'i **71/39** taşıyordu ve #806 sonradan **aynı sayıları** başka
> iki kriter için yazdı (iki dal da tam iki kriter kapatıyor) → kendi 71/39'unu taşımak tavanı
> gerçek sayının **iki üstünde** bırakırdı ve **`--ratchet` sonsuza dek yeşil kalırdı**. Merged
> ağaçta taze `--report`: **69 / 37**. **Kapı bunu yakalamaz, koşturan kişi yakalar.**
> `PROJECT_HISTORY.md` §ADIM 98 · `docs/ADIM98_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 95 (üretilmiş kabul artefaktlarının drift kapısı):
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 97 (kabul borcu batch 18, doc 10 BACKEND): ÜRÜN KODU
> DEĞİŞMEDİ, iki pytest case + bir opsiyonel harness parametresi + defter.
> Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> İki kriter kapandı — **`RF-07`** (`.c2`) · **`RF-12`** (`.c3`); ikisinde de son açık
> clause'du → ikisinin de **`debt_class` KALDIRILDI**.
> **DERS 1: "raise ediyor" ile "YAZMADAN raise ediyor" AYNI İDDİA DEĞİLDİR** — mevcut
> `test_duplicate_active_name_conflicts` istisnayı assert edip duruyor ve guard'ın insert'in
> **üstünde mi altında mı** olduğunu ayırt edemiyor; yeni test satırları **sayar** ve hayatta
> kalan revizyonu geri okur. **DERS 2 (bu depoda İLK KEZ yazılıyor): refüz testinde `rollback`
> YAPMA** — rollback post-insert bir guard'ın yazdığı satırı **da** atar ve test **vacuous**
> geçer; `flush()` + `expire_all()` ile aynı transaction içinde **veritabanından** oku.
> **DERS 3 (yeni kontrol kuralı): paylaşılan bir HARNESS'a parametre eklediysen red'i kendi
> değişikliğine atfedilemez yap** — `RF-12`'de Family'yi geri koyan negatif kontrol
> kompozisyonun `ready` olduğunu gösterir. **ÜÇ negatif kontrol, üçünde de hangi assertion'da
> kırmızıya döndüğü OKUNARAK:** `_check_name_available`'ı insert'in altına taşımak **yalnız**
> yeni testi kök sayısında düşürür (eski test **yeşil kalır**) · `rationale_family_id`'ye
> default vermek readiness assertion'ını düşürür · readiness kapısından önce `BacktestRun`
> yazmak run-sayısı assertion'ını düşürür. **Tavanlar İNDİ: `partial` 73 → 71, `debt_class.B`
> 41 → 39**; açık borç **78** (A=1 · B=39 · C=6 · D=32), clause `covered` 1046 → 1048.
> **Doc 10'un BACKEND borcu bitti** (kalan `RF-18` **frontend**).
> **ON BİRİNCİ BULGU — `RF-08.c2`:** doc 10 §10.1 kurtarma metnini **kelimesi kelimesine**
> veriyor ama `RationaleFamilyNameReserved` yalnız `code`+`message` bildiriyor ve tek raise yeri
> **çıplak** → 409 hiçbir `remediation` taşımıyor. **`TL-16.c4`'ten farkı ÖLÇÜLDÜ:** o zarfı
> **genişletmeyi** ister, bu **hiçbir yeni şey istemez** (aynı dosyada **yirmi** sınıf onu
> bildiriyor) → spec'in yazdığı metinle **tek satırlık** bir düzeltme. Sevk **EDİLMEDİ** ve
> **yeniden sınıflandırılmadı**.
> **İKİNCİ BULGU — #808 KAYITSIZ İNDİ, SONRADAN KAPANDI:** `ADIM 94` main'e indi ama
> `docs/PROJECT_HISTORY.md`'ye **hiç dokunmadı** (`grep -c 'MB-01'` → **0**) → kapanış
> ritüelinin **3. maddesi koşmadı**. Bu slice o kaydı **UYDURMADI**; sahibi yazdı — **#810**
> (`521e8de`, +99 satır) bu dal sıra beklerken indi, dal onun üstüne **rebase edildi**.
> **Ders değişmedi: hiçbir kapı aradaki pencereyi yakalamıyor** — `check_classification`
> kickoff **dosyasına** bakar, `PROJECT_HISTORY` kaydının varlığına değil.
> **DÜRÜST SINIR:** Postgres ayakta + migrate + **izole DB** → iki case ve üç negatif kontrol
> **gerçekten koştu** (#804'ün ve #805'in dosyaları da yanında yeşil); **tam suite ve coverage
> CI'a bırakıldı** — üç yerel deneme ortam yüzünden geçersizdi (paylaşılan DB çekişmesi, yanlış
> cwd → sistem Python, Postgres çökmesi), bu dal için yerel sayı **iddia edilmiyor**.
> **NUMARA DÖRT KEZ TAŞINDI: `ADIM 93` → `94` → `95` → `97`.** Üçüncüsünü **#809** aldı
> (kabul partisi DEĞİL, bir CI kapısı — yani parti numarası hiç taşımadı), `96`'yı ise
> **açık #811** `docs/ADIM96_LANDED_KICKOFF.md` **dosyasını ekleyerek** talep ediyordu
> (o PR bu kayıt indikten sonra **`ADIM 98`'e renumber etti**, dosya adı dahil) →
> çakışma başlıkta değil **DOSYA YOLUNDA** ölçülür (ADIM 91), ve ayrılan numara güvenli
> numara değildir (ADIM 92). #804 `ADIM 93`'ü aldı; **#808 HEM
> `ADIM 94` HEM `batch 17`'yi birlikte aldı** → bu kayıt `batch 18`. **DERS: iki numara bağımsız
> taşınABİLİR demek bağımsız taşınIR demek DEĞİLDİR** — ayrı ayrı ölç. **Tavan ÜÇ tabanda
> yeniden ölçüldü** (77/45 → 73/41 → 71/39) ve **elle aritmetik tuzağı var:** bu dal ile #808
> **ikisi de tam iki kriter** kapatıyor ve bu dalın #808 öncesi freeze'i **73/41** taşıyordu —
> #808 sonradan **aynı sayıları** başka kriterler için yazdı. **Sayıların eşleşmesi hiçbir şey
> kanıtlamaz.** `PROJECT_HISTORY.md` §ADIM 97 · `docs/ADIM97_LANDED_KICKOFF.md`.
>
>

> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. **Öncesinde ADIM 95 (üretilmiş kabul artefaktlarının drift kapısı):
> ÜRÜN KODU DEĞİŞMEDİ (`backend/src`'te sıfır satır), TAVANLAR OYNAMADI (73 partial /
> 7 uncovered · A1 B41 C6 D32). Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> `acceptance_semantic_scan.py` iki checked-in artefakt üretiyor; **iddia ölçümle DARALTILDI**
> — defter **zaten** kapılıydı (`test_the_debt_ledger_is_not_stale`), **kapısız olan RAPORDU**
> ve sürüklenen de o oldu: **ADIM 60'tan (#719) beri YEDİ kabul partisi**
> (`234 covered / 126 partial` ↔ ölçülen `276 / 84`), **CI hep yeşildi**. Yeni
> `::check_generated` + `ci.yml` → `--report --check-generated --ratchet` (**yeni job DEĞİL**,
> mevcut adıma bayrak). Kapı **eksik dosyayı taze saymaz** (`MISSING`), suçlamayı **dosya
> başına** ayrıştırır, hata mesajında **yeniden üretme komutunu** verir; **yazıcı ile kapı tek
> renderer'ı paylaşır** (ayrışsalardı kapı *tatmin edilemez* olurdu → kaynak düzeyi test).
> **DÖRT negatif kontrol + testin kendisinin ÜÇ negatif kontrolü, yedisi de kırmızı**; en
> öğreticisi **tarihsel kusurun kendisi** — rapor `d012a63`'teki ADIM 60 sürümüne geri konuldu
> ve kapı kırmızı verdi. **DERS: bir kapı ölçtüğü şeyin TAMAMINI ölçtüğünü iddia etmez** —
> `--ratchet` **borcun tavanını** korur, üretilmiş belgenin doğruluğunu değil.
> **DERS 2:** test ekleyen slice olguları tazelemeli (ADIM 60 emsali yine yaşandı).
> **DERS 3 (asıl): TAM SUITE, odaklı koşunun göremediği kapıyı kırdı** —
> `test_the_ratchet_is_wired_into_ci` CI satırının **birebir literalini** pinliyordu; test
> kendi konusuna göre yeniden yazıldı (literal değil **bayrak** assert'i) ve o dosyayı okumak
> yukarıdaki yanlış iddiayı ortaya çıkardı. **NUMARA: bu slice İKİ KEZ taşındı** (92 → 94;
> kapanış yazılırken main 92 **ve** 93'ü birden aldı) ve rebase sekiz belge çakışması verdiği
> için dal main'e **sıfırlanıp** yalnız dört kod dosyası yeniden uygulandı.
> **DÜRÜST SINIR:** kapı yalnız bu **iki** artefaktı kapsar; `repository_facts.*` ve
> `openapi.json` zaten kendi guard'larına sahip, **başka üretilmiş belgeler taranmadı**.
> `PROJECT_HISTORY.md` §ADIM 95 · `docs/ADIM95_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 94 (kabul borcu batch 17, doc 01 Mainboard BACKEND): ÜRÜN
> KODU DEĞİŞMEDİ, iki yeni integration case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız
> A-08), BLOCKED.**
> İki kriter kapandı — **`MB-01.c4`** (kriterin adlandırdığı dört yüzeyden
> yalnız Ready Check hiç anonim aktörle sürülmemişti; artık `UnauthenticatedError` **ve hiç
> rapor satırı yok**, authenticated çağrı pozitif kontrol) · **`MB-27.c4`** (iki adımlı çıkarım
> yerine iki bağımsız gözlem: **etkin** durum `stale`'e düşer / **saklanan** durum kıpırdamaz,
> ve yeniden koşu **`COMPOSITION_EMPTY`** raporlar). **BEŞ negatif kontrol; ÜÇÜNCÜSÜ DERS:**
> guard'ı insert'in altına taşıyan kontrol **YEŞİL geçti** ve assertion'ın **TOTOLOJİK**
> olduğunu ortaya çıkardı — test saymadan önce `session.rollback()` yapıyor, komutun yazdığı
> satırı atıyordu. Rollback silindi, kontrol yeniden koştu: `assert 1 == 0`. **BİR YAN ETKİNİN
> YOKLUĞUNU İDDİA EDEN ASSERTION'IN ÖNÜNDE ONU GERİ ALAN HİÇBİR ŞEY OLAMAZ.** Ayrıca **kontrol
> harness'i onarıldı** (çok dosyalı kontrolde yarıda patlayan tekillik assertion'ı ağacı kirli
> bırakıyor, sonraki kontrol onu sessizce ölçüyordu → geri yazma `finally`'de).
> **ON BİRİNCİ BULGU — `MB-22.c4`:** *"restore'dan sonra rapor kullanılamaz"* iddiasının
> **tersi** sevk edilmiş; restore aynı `(root, revision)`'ı geri koyar, fingerprint orijinaline
> **birebir** döner (`02edaff5…` → `9e72b8a1…` → `02edaff5…`, probe ile ölçüldü) ve rapor
> yeniden `ready`/`current` okunur → sınıf D şekli, **yeniden sınıflandırılmadı**.
> **Tavanlar İNDİ: `partial` 75 → 73, `debt_class.B` 43 → 41**; açık borç **80**
> (A=1 · B=41 · C=6 · D=32). **DOC 01'İN BACKEND BORCU BİTTİ** (kalan `MB-22` bulgu).
> **ORTAM TUZAĞI: container yeniden başlayınca Postgres DÜŞER** ve koşu `ss` (iki SKIPPED) +
> **exit 0** verir — skip'li yeşil kanıt değildir. **DÜRÜST SINIR:** frontend kapıları
> koşulmadı, tam suite sonuna kadar koşmadı → geçen sayı ve coverage CI'ın otoritesinde.
> **NUMARA: #806 açıkken yazıldı ve o kendini *"batch 17 / doc 10 backend"* diye adlandırıyor
> → bu slice bilerek BAŞKA belge seçti; #806 önce inerse bu kayıt `batch 18` olur.**
> `PROJECT_HISTORY.md` §ADIM 94 · `docs/ADIM94_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 93 (kabul borcu batch 16, doc 02 BACKEND): ÜRÜN KODU
> DEĞİŞMEDİ, beş yeni integration case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
> BLOCKED.** Dört kriter kapandı — **`AT-01.c2`** (kompozisyona giren tek kapı
> `attach_mainboard_item`'dır; kaydedilmemiş draft'ın kökünde **hiç `work_object_revision`
> yok** → iki sahte-id dalı da reddedilir, Save + kendi mirror'ı **pozitif kontrol**) ·
> **`AT-11.c2/c3`** (kapalı stop hem saklanan `strategy_revision.payload`'dan hem pinlenmiş
> `protection_stop_indicator` **kenarından** düşer; re-enable draft'ın **kendi saklanmış**
> değerini revalidate eder → 422) · **`AT-22.c3`** (Supervisor red / Admin grant, **aynı**
> yabancı draft, sahip değişmez) · **`AT-23.c3`** (zaten revizyonu olan kök Clear'lanır;
> revizyon + kenarlar + head pointer sağ, `trash_entries` **doğrudan** sorgulanır).
> **YEDİ negatif kontrol, hepsi doğru assertion'da kırmızı** ve her biri koşmadan önce
> **yamasının uygulandığını** assert etti. **DERS: aynı mekanizmadan beslenen iki
> assertion'ın ilki ikincisini GÖLGELER** — kenar assertion'ı ancak testin payload satırı
> geçici olarak düşürülünce ölçülebildi. **DERS 2: bir reddi exception SINIFIYLA pinleme**
> (AOS-12 kind kontrolü aynı sınıfı fırlatıp testi yeşil tutardı) → zarfın ekolanan alanını
> assert et. **Tavanlar İNDİ: `partial` 79 → 75, `debt_class.B` 47 → 43**; açık borç **82**
> (A=1 · B=43 · C=6 · D=32). **DOC 02'NİN BACKEND BORCU BİTTİ** — kalan tek test kalemi
> `AT-07` ve o **frontend**. **ORTAM DEĞİŞTİ: bu container'da Postgres 16 kurulu**, yerel
> cluster kaldırıldı ve integration suite **gerçekten koştu** → son beş dalganın *"Postgres
> yok, otorite CI"* sınırı **artık zorunlu değil** (komutlar kickoff §çapalar). **DÜRÜST
> SINIR:** frontend kapıları koşulmadı (`node_modules` yok, frontend'de sıfır satır); tam
> suite'in **geçen** sayısı ve coverage CI'ın otoritesinde. **NUMARA: bu kayıt `ADIM 89` /
> *"batch 15"* yazıldı; #803 **91**'i + *"batch 15"*'i, #799 **92**'yi merge edilmiş adla aldı
> → bu kayıt **93** / *"batch 16"*. **89'un BOŞ olması onu güvenli yapmıyordu** — kapı canlı
> kickoff'un ağaçtaki EN YÜKSEK numaralı `ADIM<n>` DOSYASI olmasını ister, `doc-status`
> işaretine değil. **DERS (asıl olan): tavan hatası SESSİZ olurdu.** Dal 79/47'yi kendi
> tabanına karşı doğru ölçmüştü, ama #803 indikten sonra main **zaten** 79/47'deydi; rebase
> sonrası taze `--report` **75/43** verdi (kriterler ayrık → ikisi de düşürüyor). Eski
> freeze'le `--ratchet` **yeşil kalırdı** — ölçülen < tavan asla kırmızı vermez — ve tavan
> dört fazla taşırdı. **Kapı bunu yakalamaz, koşturan kişi yakalar.**
> `PROJECT_HISTORY.md` §ADIM 93 ·
> `docs/ADIM93_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev` (**DEĞİŞMEDİ**). Öncesinde **ADIM 92 (`C4`/E5, worker'ın paylaşımlı saat dalı):
> ÜRÜN KODU DEĞİŞTİ (tek dosya), gözlenebilir ÜRETİM DAVRANIŞI DEĞİŞMEDİ; 50 golden digest BAYT
> BAYT AYNI. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `_use_unified_clock` **tek**
> yerde (iki conjunct da taşıyıcı), dal item döngüsünün **kardeşi** + ADR §3.2'nin
> `len(prepared_items) > 1` koşulu, `iter_portfolio` elle sürülür, **checkpoint #3b** (A21).
> Tripwire **DARALTILDI, silinmedi** — iki dokunulmaz assertion yeşil. **İMPORTER ALLOWLIST'İ
> DEĞİŞMEDİ:** worker'da `ItemIdentity`/`ItemBarStream` kurmak **üç dosyada beş assertion**
> kırmızıya çeviriyordu (sayıldı) ve imzalı listeyi **ikinci, imzasız** bir modülle büyütürdü →
> genişletmek yerine **tasarım değişti**, `participant.py::build_engine_participant` (no-touch
> listesinde DEĞİL). Kaçınma vacuous değil: import'lar geri konunca üç guard kırmızı.
> **BU SEÇİM ARTIK İMZALI — `docs/decisions/closure_c4_worker_importer_visibility_2026-08-19.md`
> (#801) ☑ Seçenek A (#799); rakip #800 (allowlist'i genişleten yazım) KAPATILDI.** İmza bedeli
> de kabul eder ve o bedel bir **honest boundary**'dir: worker'ın contained alt sisteme uzanımı
> importer guard'ına **GÖRÜNMEZ** — *"import etmiyor"* doğru, *"erişmiyor"* **yanlış**.
> **#800'ün iki bulgusu devralındı;** ikincisi bu ağaçta yeniden ölçüldü: gate'in **substring**
> assertion'ları conjunct silinince **yeşil kalıyor** (ad `_use_unified_clock`'un kendi
> docstring'inde geçiyor) → taşıyıcı pinler `ast` yürüyüşü + davranışsal truth table, ve
> **ölçülen sınır assertion'ın yanına yazıldı**.
> **DERS: negatif kontrol GERÇEK bir kusur buldu** — checkpoint #4'ün
> ilerleme sözlüğü yalnız bağımsız kolun bağladığı `item_runs`'ı okuyordu → paylaşımlı iptalde
> `UnboundLocalError`; **yedi test de yeşildi** çünkü hepsi daha erken #3b'de iptal oluyordu.
> **DERS 2: alt küme yeşili tam suite yeşili DEĞİL** — on negatif kontrole rağmen iki-dünya
> kapısı kırık kaldı (ADIM 76'nın **kendi ısmarladığı** güncelleme), yakalayan tam suite oldu;
> coverage **%93.80/%93.81**. **Sıradaki kalem KOD DEĞİL, İKİ İMZA** (`G11`+`G12` → `C6`); `C5`
> zaten sevk edilmiş. **NUMARA DÖRT KEZ TAŞINDI (87→88→89→92)** ve sonuncusunun sebebi bir
> çakışma değil bir **nezaketti**: #803 89'u bu dala bilerek bıraktı ama **91 olarak önce indi**,
> kapı ise canlı kickoff'un ağaçtaki **en yüksek numara** olmasını ister (dosya **varlığına**
> bakar) → **ayrılan numara güvenli numara değildir**. Ayrıca dalın head'i bu oturum dışında bir
> **Update-branch merge commit'iyle** oynadı ve `Backend`'i kırmızıya çevirdi (testler değil,
> **documentation-truth gate**: bayat üretilmiş bloklar + iki `current`) → merge **rebase ile
> değiştirildi**, artefaktlar **yeniden üretildi**.
> `PROJECT_HISTORY.md` §ADIM 92 · `docs/ADIM92_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. **Öncesinde ADIM 91 (kabul borcu batch 15, doc 17 BACKEND): ÜRÜN KODU
> DEĞİŞMEDİ, dört yeni pytest case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
> BLOCKED.** Dört kriter kapandı — **`AM-03`** (`.c2`+`.c3`) · **`AM-05`** (`.c2`) ·
> **`AM-06`** (`.c3`) · **`AM-07`** (`.c2`); dördünde de son açık clause'du → dördünün de
> **`debt_class` KALDIRILDI**. **Dördü de AYNI şekle sahipti: iddia yanlış dünyada ölçülmüştü**
> — boş seçim **hiç revizyonu olmayan** sentinel'e gönderiliyordu (`AM-05`), sürülen tek
> sahiplik kapısı **kilitsiz** profildi (`AM-07`, o aslında `AM-14`'ün senaryosu), lock/unlock
> testi bir `BacktestResult`'a **hiç dokunmuyordu** (`AM-06`), ve e2e'nin manifest
> assertion'ının arasından bir **Trash delete+restore** geçtiği için iddia Apply'a
> **kapsanmamıştı** (`AM-03`). **DERS: "hiçbir şey kıpırdamadı" iddiası İKİ yerden vacuous
> olur** — işlemin *gerçekten indiği* ayrıca assert edilmezse hiçbir şey yapmayan bir çağrı
> için de geçer, ve *boş* bir tabloda ölçülen "run oluşmuyor" dolu bir tablodakinden zayıftır
> (test önce SUCCEEDED bir `BacktestRun` + `Job` seed eder ve sayı değil **kimlik listesi**
> karşılaştırır). **BEŞ negatif kontrol, beşi de hangi assertion'da kırmızıya döndüğü
> OKUNARAK:** boş-seçim `raise`'ini append'in **ALTINA** taşımak `test_min_selection_blocked`'ı
> **yeşil bırakır** ve yalnız yeni testin **head** assertion'ını düşürür (→ `pytest.raises` tek
> başına o clause'u asla kapatamazdı) · kilit varken `ensure_can_edit`'i atlamak
> `test_foreign_profile_role_guard`'ı **yeşil bırakır** (o kilitsiz profil sürer — **eski testin
> yeşil kalması KANITTIR**, kusur değil) · Lock'un metrik değerlerini sıfırlaması yalnız
> çevrim-ortası kart karşılaştırmasını düşürür · Apply'ın `Job` eklemesi / `manifest_hash`
> yazması ilgili assertion'ları düşürür. **Tavanlar İNDİ: `partial` 83 → 79, `debt_class.B`
> 51 → 47**; açık borç **86** (A=1 · B=47 · C=6 · D=32), clause `covered` 1034 → 1039.
> **Doc 17'de testle kapanacak sınıf-B satır KALMADI.** **DÜRÜST SINIR:** bu container'a
> **Postgres 16 KURULDU** (+ `alembic upgrade head`) → dört case ve beş negatif kontrol
> **gerçekten koştu** (`test_arrange_metrics.py` 17 → 21 passed); frontend'e sıfır satır
> dokunuldu → frontend kapıları koşulmadı, otorite CI; e2e/`@a11y` **yazılmadı**.
> **İKİ TUZAK, birinci elden:** `pytest -q | tail` **200 collection error'ü `exit 0` gösterdi**
> (çıktıyı dosyaya yaz, exit code'u ayrı oku) · yerelde **`alembic upgrade head` koşulmadan**
> tam suite bu diff'le ilgisi olmayan **~40 hata** verir (contract testleri migrate edilmiş
> `DATABASE_URL` DB'sini kullanır; atıf, dalın hiç dokunmadığı bir contract dosyasını ayrı bir
> DB'de sürerek **kanıtlandı**). **ZİNCİR ATEŞLENDİ:** dal önce `a5b46ab`'ye donduruldu
> (79/8, B 48), **#797** açıkken indi → `ee5ab38`'e taşındı ve `--ratchet` **yeniden koşuldu**
> (79/7, B 47) — **`partial` tesadüfen aynı, `B`/`uncovered` DEĞİL**, elle çıkarma yanlış tavan
> üretirdi. **NUMARA: `ADIM 89` yazıldı, `ADIM 91`'e TAŞINDI** — #799 `ADIM89`, #802 `ADIM90`
> kickoff **dosya yolunu** ekliyor; **çakışma başlıkta değil DOSYA YOLUNDADIR** ve
> `check_classification` bunu yakalayamaz. Parti numarası taşınmadı (batch 14 = #797).
> `PROJECT_HISTORY.md` §ADIM 91 · `docs/ADIM91_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 90 (kayıtsız inen #779'un ritüeli): BU SLICE DEFTER,
> kaydettiği slice TEK PLAN BELGESİ (+37/−7). Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
> BLOCKED, açık kapı 11.** #779 main'deydi, kaydı **yoktu** (`grep '#779'` → yalnız ADIM 87'nin
> zincir notu). Kapattığı şey kusur değil **çelişkiydi**: §2 sayım tablosu `G6`/`G7`'yi çözülmüş
> sayarken satırların kendisi `UNSIGNED` diyordu → satırlar ölçülerek düzeltildi, eski metin
> `Was "…"` ile korundu. **ASIL DEĞER YAN ÖLÇÜMLERDE:** (a) tablodaki **altı** `decisions:NNN`
> referansının **altısı da** bayattı → bölüm adına çevrildi (§Conventions: satır no değil sembol
> yaz); bugün `grep -c 'decisions:[0-9]'` → **2** döner ama **ikisi de `Was "…"` alıntısının
> içinde**, canlı işaretçi **0** — alıntıyı temizlemek kanıtı siler. (b) **ÜÇ issue durumu
> bayattı, ama İKİSİ KAPIYI AÇMAZ** — bu kaydın en önemli cümlesi: #558/#559/#544 üçü de kapalı,
> ama yalnız **#558**'in kapanış yorumu üç karar sorusunu **yazılı** cevaplıyor (+ imza
> `§Karar 2`'de bağımsız duruyor) → `G6`/`G7` **çözüldü**; **#559** ve **#544** sıfır yorum,
> closing PR yok, imza bloğu **boş** → `G8` ve `G14` **AÇIK kalır**. Kapanışı imza saymak
> **11 açık kapıyı 9'a** indirirdi; **indirilmedi**. **DERS: bir kapıyı düşürmeden önce ÜÇÜNÜ
> birden ölç** — issue durumu, issue'da yazılı karar, `decisions` imza kutusu; ayrıştıklarında
> otorite **imza kutusudur**. (c) **`cancelled` ≠ `failure`, ve artık kökü de biliniyor**: A11Y
> işi `Install Playwright browsers` içinde **38 dk 50 sn** asılıp iptal oldu (axe adımı
> **skipped** → hiçbir test gövdesi koşmadı), rerun **3 dk 08 sn**'de yeşil; kök **#795**'te
> ölçüldü (`azure.archive.ubuntu.com` aynası düştü, GitHub **timeout'u `cancelled` raporlar**).
> **Ayırt edici, kendim ölçtüm:** aynı attempt'te **üç kardeş işin** aynı adımı **yeşildi**
> (1–3 dk) → genel kesinti **değil**; *"install yavaş, tavanı büyüt"* yanlış düzeltmeydi. Sınıf
> artık korunuyor → yeni E2E işinde **`npx playwright install` YAZMA**,
> `scripts/ci-install-playwright-chromium.sh`'tan geçir. **ORTAM DÜZELTMESİ: `actions:write`
> VAR** (`actions_run_trigger` mevcut) — devir promptunun *"403, rerun edilemez"* notu **bayat**;
> bu slice onu **kullanmadı** (kırmızı yoktu). **DÜRÜST SINIR:** ürün kodunda sıfır satır →
> **suite koşulmadı**, doğrulama `repository_facts --check`. **ÇAKIŞMA ÖLÇÜLDÜ: `C4` hattı ÜÇ
> açık PR tarafından sürülüyor (#799/#800/#801), kabul borcu hattı #797** → hiçbirine
> dokunulmadı. **NUMARA: #797 → 88 (bu dal sıra beklerken İNDİ, `ee5ab38` — dal onun üstüne
> REBASE edildi), #799 → 89 → bu kayıt 90. Sonra **#803 = ADIM 91** (`42c8185`) ve **#799 = ADIM 92** (`3994725`, kendisi de 89'dan taşındı) indi; **ikisi de `ADIM90` yolunu eklemedi** → numara çakışmadı, **yeniden atanmadı**; kayıt sırası 87 → 88 → 91 → 92 → 90. Bedeli: canlı kickoff artık `ADIM92`'ninki, bu slice'ın kickoff'u **`historical` doğdu** (ADIM 82 emsali). **DERS: kuralın iki yarısı AYRIDIR** — *"numaralar yeniden atanmaz"* KAYDI korur; kickoff'un canlılığını `_check_live_kickoff_is_newest` **dosya varlığından** okur, `doc-status`'tan değil. **`89` kalıcı BOŞLUK, `90` bu kayıt.** `PROJECT_HISTORY.md` §ADIM 90 · `docs/ADIM90_LANDED_KICKOFF.md`.
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 88 (kabul borcu batch 14, doc 05 frontend): ÜRÜN KODU DA
> TEST KODU DA DEĞİŞMEDİ — diff yalnız defter + üretilmiş artefakt.** Tek kriter `TL-18`
> kapandı ve **bedeli SIFIR TEST** oldu: kapsama **zaten sevk edilmişti**.
> **Blocker sayısı DEĞİŞMEDİ — hâlâ tek blocker var (A-08), verdict BLOCKED.** `frontend/src/test/presentationState.test.tsx` ADIM 60'ta
> (`d012a63`, PR #719) inmiş ve describe adı birebir *"Mainboard row presentation state
> (TS-16 / **TL-18** / AOS-16)"*; kardeş `TS-16`/`AOS-16` o iki düğümü o günden beri cite
> ediyordu, `TL-18` ise *"Nothing in the suite asserts this"* notuyla borç görünüyordu —
> **defterde gözden kaçma, eksik kapsama değil** (ADIM 68 `RD-09.c4` emsali). Clause'un dört
> yarısı da düğümlerde: yazma isteği yok (`writeRequests` `[]` + `/mainboard` kapsamlı non-GET
> filtresi), `hash_abc` sabit, `Backtest Ready: Ready` sabit; artı bir **vacuity muhafızı**
> (editor gerçekten açılıyor). **`uncovered` KRİTER tavanı İLK KEZ indi: 8 → 7** — altı
> dalgadır (73/75/78/79/80/84) yalnız `partial`/`B` iniyordu; `debt_class.B` 52 → 51, açık
> borç **90** (A=1 · B=51 · C=6 · D=32). **DERS 1: parti seçmeden önce KRİTER ID'SİNİ TEST
> AĞACINDA GREP'LE** — bir kriter, kendi id'sini taşıyan bir testle beş dalga borç görünebilir.
> **DERS 2: yeşil bir negatif kontrol çoğu zaman HİÇ UYGULANMAMIŞ bir kontroldür** — ilk yama
> tek eşleşme varsaydı, handler dizesi üçtü, dosya değişmedi ve koşu yeşil kaldı; yakalayan şey
> `assert count == 3` idi. **DERS 3: "yapı gereği doğru" her clause yanlışlanamaz değildir** —
> ayırt edici ölçü kırmanın KAÇ NOKTALI olduğudur (`TL-18` tek noktalı → kapatıldı;
> `TL-02.c2` üç noktalı → işaretlendi). **Doc 05'te bir test slice'ının kapatabileceği satır
> KALMADI.** **NUMARA: bu slice `ADIM 87`/`batch 13` yazıldı, PR açıkken #785 ikisini birden aldı
> (doc 18 frontend) → merge edilmiş ad kazanır, bu kayıt `ADIM 88`/`batch 14`. ADIM 84'te #781
> ile BİREBİR AYNISI olmuştu — çakışma yapısal, kapanışta numarayı VE parti etiketini birlikte
> doğrula.** `PROJECT_HISTORY.md` §ADIM 88 · `docs/ADIM88_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 87 (kabul borcu batch 13, doc 18 FRONTEND): ÜRÜN KODU
> DEĞİŞMEDİ, tek vitest case + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> Tek clause: **`AL-06.c3`** (reddedilen directive submit'inden sonra compose kutusu boşalmıyor)
> → `AL-06` **covered**, **`debt_class` KALDIRILDI**. **DERS (ADIM 83'ün ikizi): "metin korundu"
> iddiasını hiç submit edilmemiş bir formda ölçmek TOTOLOJİDİR.** Doc 18 §15 bir **422** ister,
> ama sevk edilen istemcide whitespace-only directive sunucuya **hiç ulaşmaz** (düğme `disabled`
> + `sendDirective` erken döner) → boş metin + stub'lanmış 422 **üretimin üretemeyeceği bir
> dünyayı** ölçerdi. Ölçülen çıkış: **iki boş-metin kapısı aynı fikirde değil** — compose kapısı
> JS `String.trim()` (**`U+001C`–`U+001F`'i KORUR**), komut kapısı Python `str.strip()`
> (**siler** → 422 `MESSAGE_TEXT_REQUIRED`); test bu yüzden **`U+001C`** gönderir. Bu ayrım
> **kusur DEĞİL** (fail-closed) ve bulgu olarak kaydedilmedi. **İki negatif kontrol, İKİ AYRI
> EKSEN:** `onSuccess` → `onSettled` **yalnız** yeni testi ve **yalnız** textarea assertion'ını
> düşürür (diğer on dört test yeşil) · `sendDirective`'i dispatch etmez yapmak testi
> **`role="alert"` assertion'ında** düşürür → red **gözleniyor**, varsayılmıyor. **Tavanlar İNDİ:
> `partial` 86 → 85, `debt_class.B` 55 → 54**; açık borç **93** (A=1 · B=54 · C=6 · D=32),
> clause `covered` 1028 → 1029. **DOC 18 TAMAMEN KAPANDI (18/0/0)** — doc 03 ve doc 07'ye
> katıldı. **YAN İŞ: `acceptance_semantic_traceability.md` ADIM 42 sayılarını (234/126)
> taşıyordu** — o dosya `--check` kapısının **kapsamında değil**, sessizce bayatlamıştı;
> yeniden üretildi (275/85). **ÇAKIŞMA ÖLÇÜLDÜ: `HAT B`/`C3` İKİ açık PR tarafından birden
> sürülüyor (#777, #782)** → bu oturum ona **hiç dokunmadı**. **DÜRÜST SINIR:** backend kapıları
> koşulmadı (backend'de sıfır satır, Postgres yok) → otorite CI; e2e/`@a11y` **403**.
> `PROJECT_HISTORY.md` §ADIM 85 · `docs/ADIM85_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 86 (kayıtsız inen İKİ slice'ın ritüeli: P1-proof #765 +
> P2 #766): BU SLICE DEFTER; kaydettiği #766 19 satır ürün kodudur, #765 test-only. Blocker
> sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** İkisi de main'deydi, ikisinin de kaydı
> **yoktu** (`grep -c` → 0/0). **Sonuç: P-C2 §D.1'in üç N+1 bacağından İKİSİ artık flat** —
> leg 1 `tick_data_leg` (1/1, P1 = #751), leg 2 `strategy_mirror_leg` (2/2, #766: #754'ün
> attığı `mirrors` dikişini **bağladı**); **leg 3 AÇIK ve bilerek** (`run_readiness_check`
> `per_item: 1`, 8 → 18) — anahtarı UNIQUE değil, batch'lemek **hangi satırın kazandığı**
> sorusudur = **`G15` ürün kararı, imzasız → İNDİRME.** **DERS: bir ratchet satırının
> SINIRINI da ölç** — batch kaldırılınca `assert 12 <= 2` (kırmızı), ama batch yerindeyken
> per-item okuma geri konunca **yeşil kalır** (ısınmış identity map); satır **kaldırılmış
> batch'i** yakalar, gereksiz okumayı değil. **DERS 2: slice'a başlamadan önce AÇIK PR'LARI
> tara** — bu dalgada iki slice de paralel yazıldı, #764 kapatıldı ve P2'nin rakip mekanizması
> düşürüldü. **G9/G13 İMZALI** (ADR-0002 §13.2, #753) — devir promptu yanlış biliyordu.
> `PROJECT_HISTORY.md` §ADIM 86 · `docs/ADIM86_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev` (**DEĞİŞMEDİ**). Öncesinde **ADIM 85 (C3 / E4c, `_EngineParticipant`):
> ÜRÜN KODU DEĞİŞTİ ama ÜRETİMDE ÇAĞIRANI YOK; 50 golden digest BAYT BAYT AYNI. Blocker
> sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Yeni tek modül
> `domain/backtest/participant.py` — bilerek `execution/` **DIŞINDA** (içeride containment
> gate'in importer taraması **kör** olurdu). **Beş** allowlist tek adlandırılmış modülle
> genişledi (imzalı karar 2026-08-18, Seçenek A); **karar yalnız containment gate'ini
> ölçmüştü, dört kardeş guard insan incelemesine bırakıldı.** Negatif kontrol koştu ve
> kalıcı teste dönüştü. İki değişmez pinlendi: **reconciliation** (havuz attribution'ı ==
> item ledger delta'sı) ve **sleeve parity** (`Ci(t)`'nin iki türetimi, her tick/item, üç
> sermaye modeli) — ikincisi **üründe de** zorlanır. **Ölçülmüş, kapatılmayan gap:** giriş
> fill'i komisyonunun havuza aynalanacağı bir faz yok; kaydırmak PD-2'nin zamanlama
> gerekçesini bozardı → `C4`/`C6`'ya bırakıldı. **Yeni bulgu:** `same_direction_stacking`
> şema **varsayılanı** `allow_stacking` ve adaptör onu reddediyor → §C.3.7/§C.3.8 forkunun
> kayıtsız **üçüncü** kardeşi, `C6` için **ürün kararı**. `engine.py`'de tek genişleme:
> `_apply_entry(..., size_override=None)` (tasarımın yazdığı çağrı kurulamıyordu).
> **Next: `C4`.** `PROJECT_HISTORY.md` §ADIM 85 · `docs/ADIM85_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 84 (kabul borcu batch 12, doc 05 backend): ÜRÜN KODU
> DEĞİŞMEDİ, yalnız test + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> İki kriter kapandı: **`TL-13`** (var olan bir readiness raporu bir Trade Log pin'inin
> **üzerinden** taşındı — iki yarı da kanıtlıydı, **dikişi** hiç geçilmemişti; güncellik hiç
> saklanmadığı için tek gözlenebilir şey aynı değişmez raporun **etkin** durumunun oynaması ve
> **saklanan** durumunun oynamaması) ve **`TL-22`** (başarı yolunda `AgentToolCall` satırı ilk
> kez geri okundu + Agent'ın `attach=True` işi insan panosunu kıpırdatmıyor).
> **Tavanlar İNDİ** (`partial` ve `debt_class.B` ikişer; sayısal otorite
> `docs/audit/acceptance_coverage_baseline.json` — bu dal #781'in üstüne rebase edildikten
> SONRA yeniden ölçüldü, iki freeze'in farkından türetilmedi). **`TL-16.c3` kapandı ama HİÇBİR TAVAN OYNAMADI** — `TL-16.c4` **sevk edilmemiş**
> (üç raise yeri de çıplak `WorkObjectRevisionConflictError()`, `AppError` `details=[]` yazar →
> 409 zarfı kökün güncel head'i hakkında hiçbir şey taşımaz): sınıf D görünüyor, **taşınmadı**,
> defterde artık **on** böyle bulgu var. **DERS: kırmızının HANGİ assertion'da olduğunu oku** —
> `TL-22.c4`'ün ilk negatif kontrolü kırmızı verdi ama `status == succeeded` üzerinde; özellik
> **iki bağımsız kapıyla** korunuyor (aktör kapsamlı çözüm **ve** `_require_owned_workspace`),
> yani tek kapıyı kırmak mutasyon değil **REJECTED** üretir. **Doc 05'in BACKEND yarısı bitti**;
> `TL-18` (tek clause, tamamen `uncovered`) **frontend** ve kapanırsa `uncovered` **kriter**
> tavanını 8 → 7 indirir. **NUMARA: bu slice `ADIM 83`/`batch 11` yazıldı, PR açıkken #781
> ikisini birden aldı (doc 18) → merge edilmiş ad kazanır, bu kayıt `ADIM 84`/`batch 12`.**
> `PROJECT_HISTORY.md` §ADIM 84 · `docs/ADIM84_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 83 (kabul borcu batch 11, doc 18 backend): ÜRÜN KODU
> DEĞİŞMEDİ, yalnız test + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> Dört kriter kapandı — **`AL-05`** (queued directive'in audit + outbox satırı, directive **id'sine**
> kapsanmış) · **`AL-09`** (Supervisor reddinden sonra runtime satırı **geri okunuyor**) ·
> **`AL-10`** (Stop admission'dan SONRA, `run_backtest`'ten BİR SINIR ÖNCE: `BacktestRun` **var**,
> `BacktestResult` **yok**; checkpoint'ler hayatta) · **`AL-18`** (yeni revizyon pinlenmiş context
> manifest'e **kaymıyor**) — ayrıca `AL-06.c2`. **DERS 1: "Result yok" iddiasını hiç backtest admit
> edilmemişken ölçmek TOTOLOJİDİR** → test durable executor'ı sürer ve Admin Stop'unu
> `backtest_requested` checkpoint'inde bastırır (üretimdeki `stop_run` koşar). **DERS 2: guard'ı
> mutasyonun ALTINA taşımak istisnayı AYNI ŞEKİLDE fırlatır** → `pytest.raises` tek başına bir
> "durum değişmedi" clause'unu asla kapatmaz, satırı **geri oku**. **Altı negatif kontrol, altısı da
> yalnız yeni testi düşürdü**; en öğreticisi `data_bundle.resolve`'un manifest'i çağıran task'a
> damgalaması — **tüm** gateway/executor/e2e suite'i yeşil kalıyordu. **Tavanlar İNDİ: `partial`
> 90 → 86, `debt_class.B` 59 → 55**; açık borç **94** (A=1 · B=55 · C=6 · D=32), clause `covered`
> 1022 → 1028. **Doc 18'in backend borcu BİTTİ**; tek açık satır `AL-06.c3` **frontend olduğu için**
> açık (bulgu DEĞİL, sıradan sınıf-B). **BU PARTİDE YENİ BULGU YOK.** **DÜRÜST SINIR:** frontend
> kapıları koşulmadı (`node_modules` yok, frontend'de sıfır satır) → otorite CI.
> `PROJECT_HISTORY.md` §ADIM 83 · `docs/ADIM83_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 82 (kayıtsız inen `C2`'nin ritüeli, PR #759): BU SLICE
> DEFTER, KAYDETTİĞİ SLICE ÜRÜN KODU. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> #759 (`c78b15b`) `settle`/`finalize`'ı **zorunlu** Protocol üyesi yaptı, `PHASE_ORDER`'ı
> **8 → 9 faza** çıkardı (P10), `PortfolioLedger.fold_tick` (G13 = FOLD) ve `iter_portfolio`'yu
> sevk etti — ama `PROJECT_HISTORY.md`'de **hiç anılmıyordu** (`grep -c '#759'` → 0), yani
> ritüelin 1–6. maddeleri hiç koşmadı (#728/#729 = ADIM 69/70 emsali). **DERS: PR gövdesi
> otorite değildir** — gövde *"containment gate el değmedi"* diyordu, ölçüldü: gate **güçlendi**
> (`_LOOP_ENTRY_POINTS` artık `iter_portfolio`'yu da arıyor), o ekleme olmadan üretim tüm fazları
> o giriş noktasından sürerken assertion **yeşil kalabilirdi**. **Sıradaki mühendislik kalemi
> `C3`** (`execution/participant.py` yok; önünde importer-allowlist **insan incelemesi**, #761
> ile Seçenek A imzalandı). Kickoff'u **YOK, bilerek** (geriye dönük kayıt).
> `PROJECT_HISTORY.md` §ADIM 82.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 81 (§2 kapı tablosu tazelendi, PR #769): ÜRÜN KODU
> DEĞİŞMEDİ, tek docs dosyası (+93/−30). Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> Kapı sayımı ölçüldü: **16 kayıtlı · 11 açık · 11 bloklayan** (çözülmüş: G5 G6 G7 G9 G13);
> **`G4`/`G12`/`G15` BRIEFED ama İMZASIZ** (#755/#752/#747) — **brifingli ≠ imzalı, sayımı
> değiştirmez**; `G11` de **#771 ile brieflendi** (bu PR beklerken indi) → **brifsiz kapı
> KALMADI, sayım yine DEĞİŞMEDİ**.
> **İki ders:** kısmi ölçüm = STALE-BY-DEFAULT ihlali (G6/G7 ölçülmeden taşındı → *"13 açık"*,
> düzelten bir kapı değil **insan**) · **çift iş** (#772 aynı §'yı tazeledi → taban **daha doğru
> ölçen** dal oldu; tazelemeden önce `list_pull_requests`). **O sırada kayıtsız olan ürün slice'ı
> (`C2` = PR #759) ARTIK KAYITLI** — ADIM 82 onu geriye dönük yazdı (#778); sıradaki
> mühendislik kalemi **`C3`** (`execution/participant.py` **yok**; importer-allowlist kararı
> **#761'de İMZALANDI — Seçenek A**, negatif kontrol zorunlu).
> `PROJECT_HISTORY.md` §ADIM 81 · `docs/ADIM81_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 80 (kabul borcu batch 10, doc 03 frontend): ÜRÜN KODU
> DEĞİŞMEDİ, yalnız test + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> Tek clause: **`AOS-01.c2`** (chooser klavye paritesi) — parite **native** (`OutsourceSignal.tsx`
> seçimleri `<Link>` render eder), eksik olan **assertion**'dı. **DERS: "seçimler link" demek
> yetmez, o zaten asserted** — `tabIndex={-1}` role/ad/href'i bozmadan chooser'ı mouse-only yapar
> ve membership testi **yeşil kalır**; bu yüzden yeni assertion **SIRA** hakkında (chooser'da
> klavyeye pointer'ın stop'larının tam aynısı, aynı sırayla). İki negatif kontrol **yalnız yeni
> testi** düşürdü. **Dürüst sınır:** jsdom'da native anchor activation yok → `Enter`
> **basılamaz**, test bastığını iddia etmiyor; gerçek tarayıcı kanıtı `@a11y` suite'ine
> yazılırdı ama bu container onu **koşamıyor** (403) → **yazılmadı**. **Tavanlar İNDİ:
> `partial` 97 → 96, `debt_class.B` 66 → 65**; açık borç **104** (A=1 · B=65 · C=6 · D=32).
> **Doc 03'te testin kapatabileceği satır KALMADI.** **ZİNCİR: bu freeze main `347fe19`'a karşı;
> batch 08/09 hâlâ PR #768'de (91 / B 60) → ikinci inen rebase edip YENİDEN DONDURMALI**
> (numara da öyle: 78/79 #768'in, bu yüzden burası **80**).
> `PROJECT_HISTORY.md` §ADIM 80 · `docs/ADIM80_LANDED_KICKOFF.md`.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 79 (kabul borcu batch 09, doc 03 backend): ÜRÜN KODU
> DEĞİŞMEDİ, yalnız test + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> İki kriter kapandı: **`AOS-13.c3`** (doc 03 §13'ün adlandırdığı **SUPERVISOR** rolü hiç
> sürülmemişti — testler ikinci bir düz USER ya da Agent seçiyordu; yeni test **iki fiili**
> `create_work_object_revision` + `soft_delete_work_object`, **iki external kind** üzerinde
> sürer ve reddin **kalıcı** olduğunu doğrular) ve **`AOS-05.c1`** (transient-draft sözleşmesi
> yalnız `trading_signal` dalında kanıtlıydı; `trade_log` **ödünç alınmadı**, ayrı pinlendi).
> **Tavanlar İNDİ: `partial` 93 → 91, `debt_class.B` 62 → 60**; açık borç **101 → 99**
> (A=1 · B=60 · C=6 · D=32), clause `covered` 1019 → 1021.
> **İKİ BULGU, ikisi de YANLIŞLANAMAZ:** `AOS-04.c2` `TS-02.c2`'nin **birebir ikizi**;
> `AOS-06.c2` daha net — **`discard` ağaçta hiç yok** (komut yok, uç yok, handler yok; tek anma
> yokluğu tarif eden bir yorum), yani clause bir **eylemsizliğin** etkisizliğini iddia ediyor.
> **`AOS-01.c2` kapatılamadığı için değil FRONTEND olduğu için ertelendi** — chooser seçimleri
> link, klavye pariteliği native, assertion ve negatif kontrolü **gerçek**; doc 03'ü bitirecek
> tek satırlık bir parti. **DERS: negatif kontrolün NEDEN kırmızıya döndüğünü oku** — bu slice'ta
> ilk kontrol yetki yerine **doğrulama** hatasıyla düştü, yani red yetkilendirmeye atfedilemiyordu;
> test düzeltildi. **Defterde artık on üç bulgu var ve DÖRDÜ aynı yanlışlanamaz şekle sahip**
> (`TS-02.c2`, `PC-02.c2`, `AOS-04.c2`, `AOS-06.c2`) — bu artık bir **adjudication kalemi**.
> **SIRA — ÖLÇÜLDÜ, ZİNCİR ÇÖZÜLDÜ:** #768 tek PR olarak ADIM 78 + 79 taşır; batch 10
> (**ADIM 80**) main'e ÖNCE indi ve tavanlarını 97/66'dan bağımsız dondurdu, bu yüzden
> bu dal rebase edilip tavanlar YENİDEN ÖLÇÜLEREK donduruldu — defter seri bir kaynaktır.
> **AYNI PR'DA İKİ KAYIT İNDİ:** `ADIM 78` = kabul borcu batch 08 (doc 04 backend, dört
> kriter) bu PR'ın alt commit'idir ve kendi `CLAUDE.md` girdisini yazmamıştı — özeti
> burada tekrarlanmaz, kaydı `PROJECT_HISTORY.md` §ADIM 78'dedir.
> `PROJECT_HISTORY.md` §ADIM 79 · `docs/ADIM79_LANDED_KICKOFF.md` · §ADIM 78.
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> `future_dev`. Öncesinde **ADIM 77 (P1 + P4, PR #751 + #754): ÜRÜN KODU DEĞİŞTİ, gözlenebilir
> DAVRANIŞ DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** #617'nin şeklinin
> **dördüncü ve beşinci** örneği kapandı: `readiness_check.py::_resolve_tick_data_issues`
> (**1 → 11**, slope 1) ve `backtest_run.py::_resolve_tick_pins` (**3 → 23**, slope 2) — ikisi de
> artık `per_item: 0`. P4 **admission yolundaki İLK bütçe satırıdır**; o yüzey `README.md` §8'de
> adlandırılmasına rağmen hiç ölçülmemişti. İki yeni çoğul okuyucu **mevcut aynaların kopyası**
> (`find_approved_tick_revisions_for_instruments` ← `get_dataset_roots`, `get_strategy_revisions`
> ← `get_work_object_revisions`) — üçüncü idiom YOK. **`_resolve_strategy_payload` opsiyonel bir
> prefetch haritası alır** (`mirrors=None`), böylece "mirror NEDİR" sorusunun tek tanımı kalır ve
> eski çağıranlar statement statement değişmez. **ASIL NOKTA: "batch aynı satırı seçer" bir hız
> iddiası DEĞİL, bir GİRDİ iddiasıdır** — pinlenen revizyon değişmez manifest'e girer (doc 15
> §15, INF-04/INF-05); `DISTINCT ON` yalnız sıra **TOTAL** olduğu için güvenlidir ve test bunu
> **eşit `created_at`'li** bir fixture ile sürer (ayrı damgalarla tie-break hiç koşmaz, her
> implementasyon geçer). **Leg 3 (`_resolve_external`) bilerek ONARILMADI** — orada per-item
> kazanan tanımsız, o bir **ürün kararıdır (G15)**; satırı `per_item: 1`'de bırakıldı.
> **DERS: fail-closed bir bacakta FIXTURE ölçümün kendisidir** — kapıyı açmayan bir fixture hiç
> koşmamış bir bacak için yeşil slope raporlar. **DERS 2: `cancelled` ≠ `failure`** — bu dalgada
> iki bağımsız PR `playwright install` içinde ~60 dk asıldı, hiçbir test gövdesi koşmadan.
> **NUMARA + DÜRÜST SINIR: ikisi de ritüelsiz açıldı ve AYRI merge edildi** (P1 = #751, P4 = #754);
> kaydı dalgayı merge eden oturum yazdı, ölçülen ile dalın iddia ettiği kayıtta AYRI işaretli.
> `PROJECT_HISTORY.md` §ADIM 77 · `docs/ADIM77_LANDED_KICKOFF.md`.
>
>
>
>
> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
> **`future_dev` (DEĞİŞMEDİ)**. Öncesinde **ADIM 76 (P-E6/C8: containment kapısının İKİNCİ
> DÜNYASI): ÜRÜN KODU DEĞİŞMEDİ, yalnız test + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız
> A-08), BLOCKED.** **22 containment ön koşulunun 2'si yeşil** → **flag'e DOKUNULMADI**
> (`G8`/`G14` = #559/#544 **açık**; **`G10` (Gate 2 — lift onayı) TALEP EDİLMEDİ**;
> `G11`/`G12` açık) → prompt'un 1–3. maddeleri **yazılamazdı**: `_EngineParticipant`,
> `_use_unified_clock`, `settle`/`finalize`, `iter_portfolio`, `PHASE_ORDER`'da P10 **yok**.
> **BULGU 1: kapı TEK DÜNYALIYDI** — `active_v1`'i kuran tek test resolver'ın flag'i
> *görmezden geldiğini* kanıtlamak için var, yani üç üretim yüzeyi (`rules.py:154`,
> `backtest_run.py:542`, `allocation_plan.py:59`) + frontend fixture'ı lifted dünyada **hiç
> koşulmamıştı**; YENİ `test_shared_allocation_two_world_gate.py` (10 test) + bir lifted
> frontend render testi, **`future_dev` pinleri gevşetilmeden**. **BULGU 2 (asıl sonuç): flag
> bir REDDETMEDİR, MOTOR DEĞİL** — worker `shared_allocation_is_executable`'ı hiç çağırmaz, o
> yüzden bugün flag çevrilse shared Result **sıralı yaklaşımla** üretilirdi: **drawdown 5000,
> gerçeği 3000** (`portfolio_mode.py`'nin flag-bağımsızlığı okuru korur ama **sayıyı
> düzeltmez**) → `C9`'un neden SON slice olduğunun ölçülmüş gerekçesi. **BULGU 3 (`C9`
> devraldı):** capability bloğu lifted dünyada `available: true` + *"not available in this
> build"* der (sayfa korunuyor, sözleşme değil) — #559 emsaliyle characterization pinlendi.
> **DERS: `and`/`or` kapısını BİLEŞİK sonucuyla test etmek kısa devrenin arkasını ölçmez** —
> sekiz negatif kontrolden biri yeşil kaldı, test hücre başına **iki conjunct'ı ayrı** assert
> edecek şekilde düzeltildi. Ratchet'e **dokunulmadı**; **A4 NOT EVALUABLE, `covered`
> işaretlenMEDİ**. **SLICE KAPANIRKEN DEĞİŞTİ: `G9` + `G13` İMZALANDI** (#753, `9fc5580`,
> ADR-0002 **§13.2**) → **`G9` APPROVED**, **`G13` = FOLD** (aynı `t_ms`'te `commit_tick`;
> append reddedildi, A5 by-construction kalır). **Ön koşul sayısı DEĞİŞMEDİ (2/22)** — madde
> #5 bileşiktir ve P10 **sevk edilmedi** (*"No product code ships with this amendment"*).
> **Ama ADIM 72'nin "sıradaki hamle bir İMZADIR" tespiti ARTIK GEÇERSİZ: sıradaki hamle
> KODDUR — `C2`/E4b** (`settle`+`finalize` **zorunlu** Protocol üyesi, `hasattr` probe'u
> **yasak**; `PHASE_ORDER`'a P10; `iter_portfolio`). **DERS: bir denetimin "imzasız"
> bulgusu SHA'ya bağlıdır, kalıcı gerçek değildir** — denetim satırları donduruldu, canlı
> belgeler güncellendi. **NUMARA: bu kayıt İKİ KEZ taşındı** (74 yazıldı → `#758` 74'ü,
> `#757` 75'i merge edilmiş/sıraya girmiş adla aldı → **76**); dal adı numara taşımaz.
> Sırayı tercih değil **kapı** belirledi: `check_classification` canlı kickoff'un ağaçtaki
> en yüksek numaralı `ADIM<n>` dosyası olmasını ister. `PROJECT_HISTORY.md` §ADIM 76 ·
> `docs/ADIM76_LANDED_KICKOFF.md` ·
> `docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md`.
>
>
> Öncesinde **ADIM 75 (kabul borcu batch 07, doc 07 frontend): ÜRÜN KODU
> DEĞİŞMEDİ, yalnız test + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> Batch 06'nın **tümleyeni**: aynı belge, frontend yüzeyi. Üç kriter daha kapandı —
> **`PC-01`** (`.c2` literal `Not Checked` pill + `.c3` render etmek revizyon yazmaz, okuma
> yolu sürülerek), **`PC-17.c4`** (kapanış hiç non-GET istek atmaz **ve** yeniden açılış
> sunucudan okur) ve **`PC-21`** (`.c2` kanonik PASSED metni + `.c3` **negatif kapsam**:
> yüzey repaint/lookahead/validation/approval iddia etmez). **ALTI negatif kontrol, altısı da
> kırmızı.** **Tavanlar İNDİ: `partial` 100 → 97, `debt_class.B` 69 → 66**; açık borç
> **108 → 105** (A=1 · B=66 · C=6 · D=32), clause `covered` 1010 → 1015. **DOC 07'DE SINIF B
> KALMADI** — iki batch altı kriter kapattı; kalan satırlar yalnız bulgular ve iki sınıf-D
> Agent satırı (`PC-15`, `PC-16`). **BULGU: `PC-02.c2` HİÇ KURULAMAZ** (sınıf C şeklinde) —
> overlay yalnız `detail !== null` iken render edilir, boş kaynaklı istek route'ta DB'den önce
> reddedilir, yani boş-girdi Pre-Check sonucunun çizileceği ekran **yok**;
> **yeniden sınıflandırılmadı**, defterde artık **dokuz** böyle bulgu var. **DERS: yanlış
> sebeple kırmızıya dönen negatif kontrol hiçbir şey kanıtlamaz** — kırmızının **hangi
> assertion'da** olduğunu oku. **`C2` hâlâ BLOKLU — G9 + G13 imzasız.**
> `PROJECT_HISTORY.md` §ADIM 75 · `docs/ADIM75_LANDED_KICKOFF.md`.
>
>
>
>
> Öncesinde **ADIM 74 (R2 + R3, PR #742 + #745): ÜRÜN DAVRANIŞI DEĞİŞMEDİ —
> `bundle_hash` kıpırdamadı, `_BUNDLE_COMPILER_VERSION` `research-bundle-v2`'de kaldı.
> Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `R2` research timing sözlüğünün
> **üçüncü elle kopyasını** sildi (`_pin_member` → `TimingProvenance.as_bundle_member()`;
> `_enum` **kaldırıldı**) — iki projeksiyon **kasıtlı olarak farklı ad** taşır, sabit kalması
> gereken **değerdir**. `R3` sealed body'nin şeklini `compiler_version`'a **golden digest**
> ile kilitledi; `resolved_at` yarısı **zaten #730'da inmişti** ve planın durdurma koşulu
> **tetiklenmedi**. **R3'ün golden'ları R2'nin ALTINDAN geçti** (R2 öncesi pinlendi, R2'li
> tabanda değişmeden tuttu) → aynı şeklin iki bağımsız türetimi. **`R4` için iş YOKTU** —
> iki teslimatı da #730'da inmişti → **PACKAGE R BİTTİ**. **CodeQL alert 256 HAKLIYDI**,
> savunma gerekçem yanlıştı (`_SEALED_BODY_KEYS` private + ölü; `MANIFEST_REVISION_KEYS`
> public + `__all__`) → sabit kaldırıldı, kural yoruma indi. **DERS: `strict: true` bir
> MERDİVENDİR** — R3'ün dalında **onbir CI koşusu** yapıldı (6 yeşil, 5 supersede), head on
> kez oynadı, PR **~14 saat** açık kaldı ve ürün kodu hiç değişmedi; tam suite üç kez yeşil
> indi, ilk ikisi **gene de** merge edilemedi. Kapı green değil **güncelliktir**. **İKİNCİ DERS:
> "CodeQL kırmızı" tek başına hiçbir şey demez** — LOG'a bak: bulgu mu üretti (gerçek), yoksa
> init'te mi öldü ("No server is currently available" = kesinti, çare rerun). Bu dalgada
> **ikisi de** yaşandı, aynı PR'da. **ÜÇÜNCÜ DERS: yeşil exit code kanıt değildir** —
> entegrasyon suite'i Postgres'siz `exit 0` + **39 skipped** verdi. **NUMARA: bu kayıt ÜÇ kez
> taşındı** (72 → 73 → **74**; #746 72'yi, #749 kendi 72 iddiasını 73'e renumber edip aldı).
> `PROJECT_HISTORY.md` §ADIM 74 · `docs/ADIM74_LANDED_KICKOFF.md`.
>
> Öncesinde **ADIM 73 (kabul borcu batch 06, doc 07 backend): ÜRÜN KODU
> DEĞİŞMEDİ, yalnız test + defter. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> Doc 07'nin **son açık clause'u backend olan** üç kriteri kapandı: `PC-07.c3` (tipli
> `RESOLVER_SIGNATURE_MISMATCH` artık **scan düzleminde** gözleniyor), `PC-09.c2`
> (`_enforce_precheck_gate`'in **registry kolu** — context kolundan durable audit'teki
> `new_registry_fingerprint` ile ayrıştırılıyor) ve `PC-11.c3` (admission `idempotency_key`
> replay'i: bir Job + bir audit + bir scan). **Üçü de negatif kontrolden geçti** (davranış
> üründen kaldırıldı → kırmızı). **Tavanlar İNDİ: `partial` 103 → 100, `debt_class.B`
> 72 → 69**; açık borç **111 → 108** (A=1 · B=69 · C=6 · D=32), clause `covered`
> 1007 → 1010. **BULGU: `PC-20.c3` sınıf D** — "restore edilen request bayat döner" **sevk
> edilmemiş** (restore yalnız `deletion_state`'i çevirir; restore edilen istek Send kapısını
> **geçer**); **yeniden sınıflandırılmadı**, defterde artık **sekiz** böyle bulgu var.
> **DERS: kickoff'un taban ETİKETİNE değil SHA'sına güven** — bu slice'ın kickoff'u tabanı
> "ADIM 68 sonrası" sanıyordu, o commit'te son kayıt **ADIM 71**'di. **`C2` hâlâ BLOKLU —
> G9 + G13 imzasız.** `PROJECT_HISTORY.md` §ADIM 73 · `docs/ADIM73_LANDED_KICKOFF.md`.
>
>
> Öncesinde **ADIM 72 (kayıtsız inen İKİ slice'ın ritüeli: C5 #740 + E5 #738):
> İKİSİ DE SIFIR ÜRÜN SATIRI. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> `C5` = R-1 pinlemesi **zaten sevk edilmişti** (plan bayattı, kod değil; negatif kontrol
> `test_allocation_revision_pin.py`'yi bayt-eşleşme satırında kırmızıya çevirdi) — sevk edilen
> ölçüm + plan düzeltmesi, **ADR kaydı BİLEREK İMZASIZ** (imza verildi, uygulandı, ürün sahibi
> geri aldı → **geri uygulama**). `E5` = `C4` **kurulamaz** (`C3` yok, `C2` yok, `G9`/`G13`
> imzasız); containment gate **değiştirilmedi**, o yüzden negatif kontrol **koşulmadı**.
> **ASIL SONUÇ: `C1` (#735) son mühendislik ön koşuluydu → kritik yol artık kodla değil bir
> İMZAYLA başlıyor.** **DERS: parti seçmeden ÖNCE ÖLÇ** ve bir kayıt kaybolmuş görünüyorsa
> **önce delile bak** (tam+tutarlı geri alım = kaza değil karar).
> `PROJECT_HISTORY.md` §ADIM 72 · `docs/ADIM72_KICKOFF.md`.
>
>
> Öncesinde **ADIM 71 (describe/book split, C1/E4a, PR #735): ÜRÜN
> DAVRANIŞI DEĞİŞMEDİ — 50 golden digest BAYT BAYT AYNI (ADR §15 R-4). Blocker sayısı
> DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Üç karar fazı çifte ayrıldı (`_compute_carry`/
> `_book_carry`, `_evaluate_held`/`_apply_held`, `_evaluate_entry`/`_apply_entry`); `_step`
> **karakter karakter aynı**. Kazanım: değerlendirme artık **gerçekten salt-okur** — üç
> sayaç (`suppressed_entries`, `entries_blocked_by_restriction`, `strength_adjustments`)
> karar nesnesinde `_LedgerEffect` olarak taşınıp yalnız `_book_effects`'te uygulanır.
> **`_phase_tail` scaling AYRILAMAZ** (guard'ı `position` + `led.trades` okur, stacking
> ikisini de yazar) → **G12 sözleşme sorusu**, P-C2 §C.3.8 (a) **zorunlu**. **DERS: geçen
> bir negatif kontrol, testin iyi olduğunu değil YOLUN HİÇ KOŞULMADIĞINI söyler.**
> **`C2` hâlâ BLOKLU — G9 + G13 imzasız.** **NUMARA: bu slice İKİ KEZ taşındı** — ADIM 68
> yazıldı, `#736` onu aldı, sonra `#732` iki kaydı birden indirip 69 ve 70'i aldı → **71**;
> dal `docs/stage-68-landed` adında kalır. `PROJECT_HISTORY.md` §ADIM 71 ·
> `docs/ADIM71_LANDED_KICKOFF.md`.
>
>
> Öncesinde **ADIM 69 + ADIM 70 (kayıtsız inen İKİ slice'ın kapanış ritüeli:
> P-D #728 ve F1 #729): ÜRÜN KODU DEĞİŞMEDİ — altı belge, `backend/src`'te sıfır satır.
> Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** İkisi de main'deydi, ikisinin de
> `PROJECT_HISTORY` kaydı, handoff satırı ve memory checkpoint'i **yoktu**; sebepleri ayrı:
> #728'in promptu çıktıyı tek dosyaya kilitlemişti, #729 ritüeli *"post-merge docs PR'ına
> ait"* diye **bilerek** ertelemişti. **NUMARALAR MERGE SIRASININ TERSİ ve bu slice DÖRT KEZ
> taşındı:** 67 yazıldı → #730 66'yı, **#733 67'yi**, **#736 68'i** merge edilmiş adla aldı →
> **69 + 70**. Dal/commit `stage-67` yazar; **merge edilmiş ad kazanır, numaralar yeniden
> atanmaz.** Tablo `PROJECT_HISTORY.md` §ADIM 70 başında.
> **ADIM 70'in kickoff'u YOK, bilerek** — geriye dönük kayıt, canlı seed `ADIM69`'unki;
> `check_classification` numarayı **dosya adından** okur, o yüzden kapı bunu görmez ve sapma
> üç yerde birden yazılı. **Planın kendisi düzeltildi (§0.5):** F1'in `Production files`
> satırı sabiti `portfolio_ledger.py`'ye koymayı söylüyordu, o yerleşim **iki containment
> kapısını kırıyor** → sabit `execution/sizing.py::SIZE_RESOLVED_TO_ZERO`'ya indi. **Ders:
> bir tasarımın *"şu dosyaya koy"* talimatı ölçülmüş bir kısıt DEĞİLDİR — kapı kırmızıysa
> kapıyı değil planı düzelt**; ve **davranışsal test bir sabit promosyonunu koruyamaz**
> (çağrı yeri literal'e dönerse hepsi yeşil kalır) → kaynak düzeyi ratchet
> `test_oracle_sizing.py:394`.
> **BU KAPANIŞTA DÜZELTİLEN BAYAT İDDİA:** handoff'un `## Next:` bloğu *"`R1`/`R2` #730 ile
> indi"* diyordu; plan `R1`'i (`final_closure_ordered_plan_2026-08-13.md:331`)
> **`TimingProvenance` + byte-identity proof** olarak tanımlıyor, yani `R1` = **#734**,
> #730 ise `P-E3`/bundle kimliğiydi. Blok ölçülmüş hâliyle yeniden yazıldı.
> **DÜRÜST SINIR:** **#734 (R1) ve #735 (C1) main'de ama kendi ADIM kayıtları HENÜZ YOK** —
> bu kapanış onların anlatısını uydurmadı, kaydı **sahiplerinin** yazması gerekir; ölçülen
> tek şey `## Next:` tablosuna girdi. Hiçbir ürün sorusu karara bağlanmadı, hiçbir issue
> durumu değişmedi. **A-08 DEĞİŞMEDİ** — 2/184 hücre, 0/10 akış, SR-1 hiç başlamadı,
> **0/4**, #514 açık.
> **KAPANIŞ YAZILIRKEN İNEN İKİ ÖLÇÜM PLANI DEĞİŞTİRDİ (§0.5 md. 3–4):** **`C1`'in stop
> condition'ı ateşlendi** — `_phase_tail`'in scaling bölümü describe/book olarak ayrılabiliyor
> ama **stacking book etmeden önce sıralanamıyor** → paylaşımlı run için *"ayrılamaz"* ile aynı
> şey → **`G12` artık öneri değil ÖLÇÜLMÜŞ ZORUNLULUK** (planın `C6` satırı hâlâ nötr bir
> *"blokla ya da modelle"* seçimi gibi çerçeveliyor; **G12 için o çerçeve yanlış**). Ve
> **`C3`'ün önünde 17. bir kapı ölçüldü (#731):** Protocol'ün **altı tipinin altısı da**
> `_PHASE_LOOP_MODULES` içinde → adaptör nereye konursa konsun importer kapısı tepki verir,
> **allowlist genişletmesi İNSAN incelemesidir**. Sicil **16 → 17 kapı**, **16'sı açık**.
> **Next: `P3` + `C5`** (`C1` ve `R1` indi). `PROJECT_HISTORY.md` §ADIM 69 + §ADIM 70 ·
> `docs/ADIM69_LANDED_KICKOFF.md`.
>
>
> Öncesinde **ADIM 68 (kabul borcu batch 05, doc 12): İKİ KRİTER KAPANDI
> (`RD-09`, `RD-15`), `partial` 105 → 103, `debt_class.B` 74 → 72 (ratchet AŞAĞI). ÜRÜN KODU
> DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** **`RD-09.c4` YENİ TEST
> YAZILMADAN kapandı:** ADIM 54 onu *"yalnız funding-enabled bir run ile kapanır"* diye
> bırakmıştı, o harness **ADIM 67'de indi**, ve oradaki `RD-11.c3` testi clause'u **birebir**
> assert ediyordu (*"an existing run OR RESULT stays bound to v1.0"* — iki yarısı da kanıtlı)
> → mevcut düğüm **cite edildi**. **Ders: yeni partiye başlamadan önce son iki slice'ın REUSE
> anchor'larını oku, bir clause bedavaya kapanabilir.** `RD-15.c4` yeni frontend testiyle
> kapandı (`display_name: null` satır hâlâ `entity_id` ile tanınır; negatif kontrol =
> fallback'i kaldır). **İKİ BULGU ÖLÇÜLDÜ, KAYDEDİLDİ, ÜZERİNE GİDİLMEDİ:** `RD-13.c4`
> (reload/compare/new-revision kurtarma yolu research frontend'inde **yok**) ve `RD-12.c4`
> (sayfa job durumunu **hiç yeniden okumuyor**) → ikisi de **sınıf D görünüyor**, ikisi de
> **yeniden sınıflandırılMADI** (B → D **D tavanını yükseltir** = adjudication). Defterde
> artık **yedi** böyle bulgu var. **Tuzaklar:** stub şeklini varsayma (`{data, meta}`);
> frontend düğüm id'si **`::` değil ` > `**; clause toplamlarını `--report`'tan **oku**,
> tahmin etme. `PROJECT_HISTORY.md` §ADIM 68 · `docs/ADIM68_LANDED_KICKOFF.md`.
>
>
> Öncesinde **ADIM 67 (RD-11.c3: successor onayı koşan/bitmiş run'ın
> manifest'ini yeniden yazmaz, doc 12 §14): ÜRÜN KODU DEĞİŞMEDİ. `partial` 106 → 105,
> `debt_class.B` 75 → 74 (ratchet AŞAĞI). Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
> BLOCKED.** Clause dört partidir açıktı çünkü **harness yoktu** (*enabled funding policy
> üzerinden research revision pinleyen TAMAMLANMIŞ run*); ölçüldü — `FundingPolicy` kullanan
> dört dosyanın hiçbiri `run_backtest` çağırmıyordu. **"Saklanan satır değişmedi" TEK BAŞINA
> TOTOLOJİDİR:** manifest admission'da yazılır, Result'a kopyalanır, hiçbir şey yeniden
> yazmaz — kriterin koruduğu kusur bir **OKUMA yüzeyinin** pini canlı çözmesidir, o yüzden
> her saklanan-satır assertion'ı `manifest_excerpt.research_data_revision_refs` (doc 16 §8.2)
> ile eşleştirildi. **Negatif kontrol İKİ eksende koştu:** saklanan JSON tahrif → saklanan
> assertion'lar kırmızı; `history.py::_research_revision_refs` bozuldu → **yalnız** okuma-yolu
> kırmızı (üçüncü assertion'ın ayırt edici olduğunun kanıtı). **Successor'ın gerçekten
> indiği de assert edilir** (yeni id + `approved` + root head), yoksa test vacuous geçer.
> Clause'un **kendi sözü** "running OR finished" olduğu için **iki test**: SUCCEEDED+Result
> ve QUEUED (worker hiç koşmadan). Harness: `_ready_composition` **`funding_for` callback**'i
> aldı (literal değil — funding pini ancak market revision **var olduktan sonra** kurulabilir;
> readiness link eşitliği şart koşar), varsayılan `None` mevcut çağıranları **bayt bayt aynı**
> bırakır. **Fundable revision'ın BEŞ kapısı var, beşi farklı yerden** (`funding_rate`+native,
> `research_backtest`+APPROVED, pozitif delay'li `fixed_delay`, market link eşitliği,
> `instrument_mapping_ref` coherence). **Linki ELLE YAZMA** (DR3 komutu pinler);
> **successor'a `market_entity_id` geçir** (onay `_ensure_market_link_active`'ten geçer).
> **Kriterin son clause'u kapanınca `debt_class` KALDIRILIR.** AÇIK: sınıf D kalemleri,
> **Karar 1 (#552) ve Karar 3 (#559) HÂLÂ İMZASIZ**, A-08 değişmedi.
> `PROJECT_HISTORY.md` §ADIM 67 · `docs/ADIM67_LANDED_KICKOFF.md`.
>
>
> Öncesinde **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev` ·
> **OpenAPI DEĞİŞTİ**. **ADIM 66 (research timing provenance bundle KİMLİĞİNE
> pinlendi, P-E3 / GH #558): ÜRÜN KODU DEĞİŞTİ, `bundle_hash` ŞEKİL DEĞİŞTİRDİ. Blocker
> sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Ön koşul **imzasızdı ve slice
> DURDU**: `closure_product_decisions_2026-08-13.md` §Karar 2'nin beş kutusu da boştu →
> karar oturum içinde ürün sahibine soruldu ve **imzalandı (A1+A2, 2026-08-14)**; #720'nin
> Karar 1 imzasızken sevk etme emsali **tekrarlanmadı**. İstenen *"A1, A2, B ve C"* birlikte
> imzalanamazdı (**B = hiç pinleme**, A'nın tersi; **C = A1'in alt kümesi**) → düzeltilerek
> imzalandı. `jobs/research_data.py::_pin_member` (YENİ) **her** üyeyi tek yerden pinler →
> "en fakir yüzey" yapı gereği imkânsız; `::_seal_bundle` §9.2'nin **kendi adlarıyla** üç
> türetilmiş dizi yayımlar (O-30 idiomu). **`_derived`'ın `sorted()`'ı TAŞIYICIDIR** —
> `canonical_json` dizi elemanlarını sıralamaz, kaldırmak hash'i çağıranın argüman sırasına
> bağlar. `compiler_version` → **`research-bundle-v2`** (eski/yeni hash uzaylarını
> kendiliğinden ayırır → migration/dual-read **gerekmedi**). **Deponun TEK `xfail(strict)`'i
> KALDIRILDI** — gevşetilmedi, ürün değişti; doğrulama **üretilmiş artefaktla** (`Backend
> xfail markers: 1 (1 strict)` → **`0 (0 strict)`**). **Tipli gövdeyi `response_model` ile
> BAĞLAMA:** `response_model=None` + `responses={200: {"model": ...}}` — ölçüldü,
> `response_model` gövdeyi yeniden serileştirip `task_id`/`run_request_id`'yi `null` olarak
> geri ekler, oysa `_seal_bundle` onları düşürür ve **düşürülmüş gövde hash'lenen gövdedir**.
> **Arkasında sevk edilmiş alan olmayan bir §9.2 adını `[]` yayımlama** — boş dizi *"böyle
> bir şey yok"* diye **beyan eder** (provenance yalanı), yokluk **boşluktur**;
> `alignment_policy_versions[]` + `missing_and_stale_policies[]` **sınıf D olarak imzalandı**
> (`grep` ile ölçüldü: `backend/src`'te sıfır kaynak). **Kabul borcunda CLAUSE ≠ KRİTER:**
> `RD-11.c2` kapandı ama **hiçbir tavan oynamadı** (tavanlar kriter sayar; `RD-11` `c3`
> yüzünden partial/B kalır) — clause defteri **uncovered 124 → 123**. **AÇIK:** `RD-11.c3`,
> §9.2'nin iki sınıf-D adı, **Karar 1 (#552) ve Karar 3 (#559) HÂLÂ İMZASIZ**, #558'e
> dokunulmadı (kapatmak **insan kararı**). `PROJECT_HISTORY.md` §ADIM 66 ·
> `docs/ADIM66_LANDED_KICKOFF.md`.
>
>
> Öncesinde **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`.
> **ADIM 65 (adli denetim kaydı + #541'in iki blocker gerekçesi, PR #700,
> DARALTILDI): FİNANSAL MANTIK OKUNDU, DOKUNULMADI. Blocker sayısı DEĞİŞMEDİ (1 — yalnız
> A-08), verdict BLOCKED. Closes #541.** `capabilities.py`'nin scaling-timeframe grubundaki
> iki `dependency` metni kanonu okuyunca **ayakta kalmıyordu** ve ikisi de ağaca karşı
> **yeniden ölçüldü**: `indicators.py:544::_ReferenceSeries` resampled seriyi **kuruyor**
> (yani *"replay kurmuyor"* yanlıştı; eksik olan **kanonik satır** — doc 02 §5.7'de düz
> per-layer override yok) · doc 02 §6.1 rung'ı **sabitliyor** (*"bir üst timeframe'e"*,
> 15m→30m→1h = `CANONICAL_TIMEFRAMES` index+1), yani *"ikiye katlama"* hiç alternatif
> değildi — gerçek kalan merdivenin **TEPESİ** (`1D` sonrası: clamp/durdur/reddet **üç
> ayrı ürün**). Hiçbir satırın `status`/`value`/`field_path`/`label`/`blocker_code`'u
> değişmedi. **`dependency` metnini UZATMA** — `CapabilityNote.tsx:24` her `future_dev`
> seçeneğin dependency'sini tek paragrafta birleştirir, bu grupta **on tane** var → uzun
> metin kullanıcıya **on kez** gider; gerekçe **kaynak yorumuna** yazılır. `capabilities.py`
> değişince **TS aynasını yeniden üret** (byte-parity pinli).
> **KAPSAM BİLEREK DARALTILDI, ölçüm önce yapıldı:** `booking.py` docstring'i **ALINMADI
> çünkü REGRESİFTİ** — main'in #720 sonrası *"COMMISSION IS PER-FILL, PD-2 decided"*
> metnini silip *"PD-2 uygulanmadı"* yazardı, oysa **#720 onu uyguladı**; containment gate
> + harness + `BACKEND_LAYERS.md` de alınmadı, main'in **#722** sürümü daha yeni.
> **`git diff origin/main <dal>` bir kapsam kararı için KANIT DEĞİLDİR** (dalın gerisinde
> kaldığı her şeyi "silinmiş" gösterir) — `merge-base`'e göre **iki tarafı da** ayrı say.
> **Denetim belgeleri ölçtükleri anı DONDURUR:** §7/§13'ün #550/#551/#552 satırları "hâlâ
> bozuk" der, `e2fa521`'de doğruydu, **#720 üçünü de sevk etti** → banner bunu açıkça
> söyler, satırlar **bilerek güncellenmedi**. `PROJECT_HISTORY.md` §ADIM 65 ·
> `docs/ADIM65_LANDED_KICKOFF.md`.
>
>
> Öncesinde **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`.
> **ADIM 64 (kabul borcu sınıf B, parti 04 — Backtest Result satır
> değişmezliği, doc 16, PR #704): `RH-05` `RH-10` `RH-11` `RH-12` `RH-16` KAPANDI,
> `partial` 111 → 106, `debt_class.B` 80 → 75. ÜRÜN KODU DEĞİŞMEDİ. Blocker sayısı
> DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Tema: Result satırı **tarihsel
> kayıttır** — okumak/karşılaştırmak/üzerine inşa etmek ona dokunamaz; dokunan iki işlem
> (soft delete, restore) denetlenir ve hash'leri korur. Suite bunu **projeksiyon**
> üzerinden kanıtlamıştı; satırı komşu işlemden sonra **geri okumayı** hiç yapmamıştı.
> **İKİ OLAY ADI SEVK EDİLMEMİŞ (ölçüldü):** doc 16 `RESULT_SOFT_DELETED`/`RESULT_RESTORED`
> der, sevk edilenler **`backtest.result_soft_deleted`** ve **`trash.restored`** → O-02/O-31
> emsali, **sevk edilen ad kanonik**. Restore testi `target_entity_id`'yi pinler, yoksa
> **herhangi bir** trash etkinliğiyle geçerdi. **`moved == {deletion_state, row_version}`
> kümesi TAM olmalı** — gevşetmek testi "delete smoke test"ine indirir. **`pytest.raises
> (Exception)` yazma** (`ruff` B017). **ERTELENENLER ölçülü:** `RH-13.c2` metrik registry
> seed'i ister, `RH-14.c3` `_walk_to_limited` çakışması → **yarım kanıtla işaretlenmedi**.
> **#703 açık:** `revision.native_asset_id` üretimde **hiç yazılmıyor**. **P1-Gate3
> KAPANMADI** (A=1 · B=75 · C=6 · D=32, açık **114**). **NUMARA: bu slice ÜÇ kez taşındı**
> (60→62→63→**64**). `PROJECT_HISTORY.md` §ADIM 64 · `docs/ADIM64_LANDED_KICKOFF.md`.
>
>
> Öncesinde **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`.
> **ADIM 63 (K-5'in SORUSU düzeltildi — checklist A-3, PR #719): KOD YOK.
> Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED. K-5 KAPANMADI.**
> Bu slice bir bulguyu değil **aracı** düzeltti: A-3 *"`h1→h2→h3` atlamasız"* diye
> soruyordu, ama `specs/20-a11y-prechecks.spec.ts` bunu **zaten** her rotada sayıyor
> (`headingSkips`, **22/23**) → insandan makine çıktısını tekrarlaması isteniyordu, yani
> **denetim K-5'i kaç rota gezerse gezsin kapatamazdı**. Yeni beklenti atlamanın
> **yanıltıp yanıltmadığını** istiyor (`…audit_checklist.md` **§A-3 notu**).
> **GEVŞETME DEĞİL** (advisory susturulmadı, 22/23 sayılmaya devam eder, K-5 `Open`) ve
> **`D-xx` YAZILMADI** — D-10/D-11 bir **gözlemin** dispozisyonunu imzalar, bu **aracı**
> düzeltir; üçüncü satır *"K-5 adjudicated"* diye okunurdu, **sicil iki kararda kaldı**.
> **Rota 1'in `—` hücresi `—` KALDI.** **İki maliyet ölçümü düzeltildi:** tag-scoped CSS
> kuralı **beş değil ALTI** (`.data-guide-card h4`, `global.css:2261` her listede eksikti)
> · merdiveni kaydırmak **v18 SAPMASI DEĞİL** (mockup `h1:0 h2:1 h3:0 h4:14 h5:0`) → sıra
> **önce altı kuralı sınıfa çevir, sonra tag**. **Bonus:** `/market-data` "iki seviye
> atlıyor" değil **yanlış yuvalama** (`h1 → h4×4 → h3×3`) — kaydı düzeltildi, **ayrı kalem
> yapılMADI**. **A-08 DEĞİŞMEDİ:** 2/184 hücre, 0/10 akış, SR-1 hiç başlamadı, **0/4**,
> #514 açık. **NUMARA: bu slice BEŞ kez taşındı** (58→59→60→61→62→**63**); commit mesajları
> `adim-58` yazar. `PROJECT_HISTORY.md` §ADIM 63 · `docs/ADIM63_LANDED_KICKOFF.md` · RC §6.5.
>
> Öncesinde **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`.
> **ADIM 62 (Ready Check'in son iki artık N+1'i batch'lendi, P-E2, PR #712):
> DAVRANIŞ DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
> ADIM 46 (#617) market-data bacağını kapatmıştı; **aynı şekil iki bacakta daha yaşıyordu
> ve hiçbir issue onu izlemiyordu** (#700'ün denetiminde **M-13**). `signal_market_data_leg`
> ve `research_funding_leg` artık **`per_item: 0`** — **ratchet, tavanı yükseltme**.
> Yeni `research_data.py::get_dataset_roots`, `market_data`'nınkinin **alan-alan aynası**
> (üçüncü idiom icat etme). **Filtre paritesi ölçüldü:** tekil okuyucu yalnız `entity_type`'a
> bakar, batch aynı yükümü **SQL'de** uygular. **Bütçe sayacının ÖLÇÜLMÜŞ kör noktası var** —
> batch'in ısıttığı identity map yüzünden aynı PK'ye konan `session.get` **hiç SQL üretmez**
> ve sayaç görmez; gerekçe `query_budgets.json` `_comment`'inde beş şekliyle yazılı, kokuyu
> kapıya bağlamak **kaynak-düzeyi assertion'la** olur. **Negatif kontrolü pristine dosyayla
> koş** — ilk deneme sahte yeşil verdi. **Dört döngü-içi okuma bilerek ALINMADI**
> (`_resolve_external`'ın `work_object_revision_id`'si **UNIQUE DEĞİL** → bugünkü kazanan
> **tanımsız**, önce ürün kararı). **NUMARA: bu slice DÖRT kez taşındı** (57→58→59→60→**62**);
> commit mesajları ADIM numarası taşımaz. `PROJECT_HISTORY.md` §ADIM 62 ·
> `docs/ADIM62_LANDED_KICKOFF.md`.
>
> Öncesinde **HEAD `5e52465`** · **alembic head `0043_i08_registry_strategy_fks`** (migration yok) ·
> **`ENGINE_VERSION` = `backtest-engine-v18-percent-sizing-per-fill-commission` (BUMP)** ·
> `SHARED_ALLOCATION_STATUS` = `future_dev`. **Son dalga — ADIM 61 (üç canlı finansal kusur
> KAPANDI, PR #720, 2026-08-14): ÜRÜN KODU DEĞİŞTİ, FİNANSAL SONUÇLAR OYNADI.** #550 sizing
> **yüzde** oldu (`_percent_of_capital` tek dönüşüm; **`max_position_size_cap` YENİ public** —
> cap'i okuyan HER yer ondan geçer) · #551 pozitif olmayan boyut (**negatif dahil**) hiçbir
> modda açmaz — *"load-bearing"* cross-item iddiası **ÇÜRÜTÜLDÜ** (`build_prior_intervals`
> zaten düşürüyor) ve bust-equity invariant'ı **bilerek** tersine çevrildi (PO-4, ürün kararı) ·
> #552 komisyon **fill başına** (PD-2). Kayıtlı revizyon **taşınamaz** → Ready Check
> `STRATEGY_SIZING_SEMANTICS_UNCONFIRMED` (kapı **ALAN** tabanlı, metot değil); formdan
> kaydetmek temizler. Golden **46 → 50** senaryo — #552 46'nın **0'ını** oynatmıştı, matris
> komisyonu hiç yapılandırmıyordu; dört yeninin **negatif kontrolü kanıtlı**. **AÇIK: komisyon
> TABANI** (kanon bps-on-notional ↔ sevk edilen düz tutar; #709 Karar 1/Seçenek C). Blocker
> sayısı DEĞİŞMEDİ (1 — yalnız A-08), **BLOCKED**. **Süreç: main'i içeri alırken MERGE DEĞİL
> REBASE** (başlık yeniden adlandırması `docs-history-guard`'a kayıt silme gibi görünür;
> kapıyı kapatma). **`update_pull_request_branch`'i BELGE PR'ında KULLANMA** — sunucu
> tarafı merge bu slice'ta ADIM kaydını sessizce düşürdü ve **hiçbir kapı görmedi**
> (guard yerel commit ister, CI `docs/` kayıt silmesini okumaz).
> `PROJECT_HISTORY.md` §ADIM 61 · `docs/ADIM61_LANDED_KICKOFF.md`.
>
> Öncesinde **P-B (kapanış uzlaştırması, DOCS-ONLY, PR #722)** — main'in kendi bloğu
> aşağıda **aynen** duruyor. Onun *"PD-2 repoda kayıtlı değil"* tespiti bu kapanışla
> **kısmen** kapanır: `PROJECT_HISTORY.md` §ADIM 61 kararı ve gerekçesini yazılı hâle
> getirir; `docs/decisions/closure_product_decisions_2026-08-13.md` §Karar 1'in kendisi
> **hâlâ imzasızdır** ve komisyon **tabanı** açık kalır.
>
> **alembic head `0043_i08_registry_strategy_fks`** · **`ENGINE_VERSION` DEĞİŞTİ** →
> `backtest-engine-v18-percent-sizing-per-fill-commission` (**#720**, 2026-08-14: #550/#551/#552
> KAPANDI) · `SHARED_ALLOCATION_STATUS` = `future_dev`. Test sayıları: **toplanan** için
> `docs/generated/repository_facts.md`, **geçen** için CI. **Son dalga — P-B (kapanış
> uzlaştırması, DOCS-ONLY): ürün davranışı DEĞİŞMEDİ. Blocker 1 (yalnız A-08), BLOCKED.**
> Üç W0 denetimi güncel main'e karşı uzlaştırıldı; DR-2/DR-3/DR-4 (bayat sayılar) onarıldı,
> `_ItemStepper`'ın "hiç yazılmadı" iddiası son yerinde de kapatıldı, portfolio alt sistemi
> ilk kez codemap'e girdi. **AÇIK (insan):** #720 per-fill komisyonu **sevk etti** ama
> `docs/decisions/closure_product_decisions_2026-08-13.md` §Karar 1 **İMZASIZ** ve `PD-2`
> repoda **kayıtlı değil** → komisyon modeli yazılı adjudication'sız sevk edilmiş durumda.
> **Next: P-C1 + P-C2.**
> `docs/audit/final_closure_reconciliation_2026-08-13.md`.
>
>
> Öncesinde **HEAD `ac5cf50`** · **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev`.
> **Son dalga — ADIM 60 (doküman kapısı artık HANGİ kickoff'un canlı olduğunu doğruluyor,
> PR #716, 2026-08-14): ÜRÜN KODU DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
> verdict BLOCKED.** `check_classification` sayıyı koruyordu, doğruluğu değil: **#697** ADIM 55'i,
> **#714** ADIM 56'yı canlı bıraktı — ikisi de tek `current` taşıdığı için **yeşil geçti**.
> Artık daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede
> duramaz (`::_check_live_kickoff_is_newest`). **Numarasız kickoff'larda bilerek susar** —
> `strict: true` altında yanlış kırmızı tüm merge'leri kilitler. **Kapı kendi PR'ını bir kez
> kırmızıya çevirdi ve haklıydı:** üretilmiş olgular **test collection** sayısını taşır
> (3541 → 3545) — **test ekleyen slice olguları TAZELEMELİ**. `PROJECT_HISTORY.md` §ADIM 60 ·
> `docs/ADIM60_LANDED_KICKOFF.md`.
>
> Öncesinde **HEAD `e547391`** · **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).
> **Son dalga — ADIM 59 (P-A1 shared portfolio erişilebilirlik denetimi, PR #707, 2026-08-13):
> ÜRÜN KODU DEĞİŞMEDİ (dört ağaçta 0 satır). Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
> verdict BLOCKED.** Kanıtlandı: `run_portfolio` (`portfolio_engine.py:531`),
> `project_portfolio_run` ve `build_portfolio_manifest` üretimde **çağrısız** (son ikisinin
> `backend/src`'te **sıfır importer'ı** var); `ItemParticipant`'ın üretim implementasyonu
> **yok** (tek örnek test sahipli `_ScriptedParticipant`); ilk sapma **tek satır** —
> `jobs/backtest_engine.py:299` `for prepared in prepared_items:`. **YENİ BULGU: §Next'in (a)
> engeli ZATEN KAPALI** — `_ItemStepper` (`engine.py:756`) barı fazlara bölünmüş sevk ediyor
> ve `E(t)` girişi `_phase_entry(bar, *, equity)` (`engine.py:2448`) olarak mevcut (#602'den
> beri); **kalan tek engel (b)**: üç faz **book eder**, `ItemParticipant` **tarif** ister →
> `run_engine`'in bar gövdesi → **ADR §16 kapısı yerinde**. **Containment-gate'in YEŞİLİ ters
> okunur:** shared engine'in aktif olduğunu değil, üretimin `run_portfolio`'ya **ulaşmadığını**
> kanıtlar (`assert callers == []`, ve `5000.00` fixture'ı fold hâlâ **yanlış** olduğu için
> geçer). **E5 tripwire'ı DARALTIR, SİLMEZ**; `:225-233` ve `:103` E5'te **değişmez**.
> **`combine_item_runs` bağımsız modun da yoludur** — hepsini faz döngüsüne yönlendiren bir
> wiring bayraksız her bağımsız Result'ı yeniden fiyatlar. **Ortam tuzağı:** alt küme
> koşusundan önce `uv sync --all-extras`, yoksa **exit 4** (`--no-cov` tanınmaz).
> **NUMARA: bu slice 58 → 59 taşındı.** Denetim PR'ı `#707` ADIM 58 adıyla merge edildi;
> kapanış PR'ı `#718` sıra beklerken main **`#715`**'i aldı ve o **`feat(adim-58)`** adıyla
> indi. **Merge edilmiş ad kazanır**; dal/commit `stage-58` yazar, slice **ADIM 59**'dur.
> **Auto-merge'ün kapatamadığı pencere ÖLÇÜLDÜ:** çare denetim PR'ında **çalıştı** (#707,
> üç main ilerlemesi, taşıma yok), ama **kapanış** PR'ı `Backend`'in ~50 dk'sı boyunca açık
> kalmak zorunda → paralel oturum o pencerede numarayı alabiliyor. **Numarayı kapanış
> commit'ini YAZARKEN doğrula, merge'den hemen önce `grep '^## ADIM'` ile bir kez daha.**
> `PROJECT_HISTORY.md` §ADIM 59 · `docs/ADIM59_LANDED_KICKOFF.md` ·
> `docs/audit/closure_w0_shared_portfolio_2026-08-13.md`.
>
>
> Öncesinde **HEAD `e0c25e6`** ·
> **ADIM 58 (plugin hook'ları kurulumdan bağımsız oldu, 2026-08-13): ÜRÜN KODU
> DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
> **Ölçüm: `enabledPlugins` KURULUM DEĞİLDİR** — `installed_plugins.json` bu container'da
> **boş**, çünkü kurulum bir **onay istemi** ister ve remote etkileşimsizdir (yapılandırma
> hatası DEĞİL; `agent-config-gate` adı çözüyor). Yani `guard-git.sh`'in docs-regresyon
> kapısı #590/#604'ten sonra yazılmıştı ve **hiç koşmamıştı**. `.claude/settings.json` artık
> `guard-git.sh` + `guard-generated.sh`'i `${CLAUDE_PROJECT_DIR}` ile **doğrudan** kaydediyor —
> **dosya kopyalanmadı, ikilenen yalnız KAYIT**. **Çift koşma bilinçli taviz** (yerelde plugin
> kuruluysa iki kez koşar; ölçülen **≈25 ms/çağrı**, salt-okur + idempotent); alternatifi
> *"kuruluysa atla"* **fail-open** olurdu. Gerekçe `plugins/entropia-maintenance/README.md`
> §Çift koşma'da — *"kopya bırakılmadı"* kararı sessizce çiğnenmedi, **açıkça gözden geçirildi**.
> YENİ KAPI **`scripts/hook-guard-proof.sh`** → `Frontend` job'ına **ADIM** (yeni job DEĞİL):
> **19 beklenti = 6 engelleme + 13 GEÇİŞ**, çünkü her şeyi engelleyen guard pozitif-yalnız
> testi geçer. Üç negatif kontrol ailesi de kırmızı verdi; **kapı bu oturumun kendi Bash
> çağrılarını üç kez blokladı** (canlı kanıt). **Ölçülmüş sınır:** `guard-git.sh` **komut
> dizesinin tamamında** desen arar → `feat/main-menu` de, bu desenleri *içeren* bir
> heredoc/döngü de bloklanır (fail-closed, düzeltilmedi) → metni **Write ile dosyaya yaz**.
> **Plugin HÂLÂ kurulu değil** — ajanlar/skill'ler/komutlar remote'ta yüklenmiyor; kurmak
> **insan kararı**. `PROJECT_HISTORY.md` §ADIM 58 · `docs/ADIM58_LANDED_KICKOFF.md`.
>
> **NUMARA: bu slice ADIM 57 yazıldı, `#698` o adı MERGE EDİLMİŞ olarak aldı → ADIM 58.**
> Kural değişmedi: **numaralar yeniden atanmaz, merge edilmiş ad kazanır**; dal commit
> mesajları `adim-57` yazar. Aynı gün main'e inen K-3/D-11 slice'ı da üç ad taşımıştı
> (54 → 55 → 56 → 57) — bu haftanın **üçüncü** çakışma dizisi.
>
> Öncesinde **HEAD `31ed27d`** · **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).
> **Öncesinde ADIM 57 (K-3 ADJUDICATED, imzalı karar D-11, 2026-08-13): KOD YOK, tek
> satır bile değişmedi. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
> K-3 (`contentinfo` landmark yok, 23/23) **kod yazmadan** kapandı: eksik olan ürün değil
> **BEKLENTİYDİ** — hiçbir WCAG SC'si contentinfo zorunlu kılmaz (1.3.1 *var olan* yapıyı
> ister), v18'de footer yok. **Checklist A-2 artık ÜÇ landmark bekliyor**
> (`banner`/`navigation`/`main`); dört arayan bir denetçi yanlış `FAIL` yazar. Kayıt
> `a11y_ci_ratchet_and_adjudication.md` **§4b `Karar # : D-11`** — bu belge artık imzalı
> a11y kararlarının **sicili** (D-10 kontrast + D-11 landmark); **imzalayan adı olmadan
> D-xx YAZILMAZ**. **Boş/gizli footer AÇIKÇA REDDEDİLDİ** (sayacı yeşile çevirir, rotor
> kullanıcısına hiçbir şey vermez) ve **advisory SUSTURULMADI** — karar dispozisyonu
> belirler, ölçümü değil. **D-10 ile karıştırma:** D-10 gerçek bir ihlali (1.4.3, 45 düğüm)
> imzalar, D-11 **olmayan bir yükümlülüğü** kaydeder. Yönü doğrulayan insan gözlemi:
> A-08 SR-2 route 1'de denetçi üç landmark duydu, yokluğu **kozmetik** buldu (tek rota
> genellenmez) — **ADIM 56'nın kaydettiği oturumun aynısı**. **Yan iş:** audit §6
> K-tablosunda K-4/K-5/K-6 satırları **iki kezdi** (ikinci küme bayat: K-4 `Open`,
> K-5 `21/23`) — merge artefaktı, üç fazla satır silindi.
> **NUMARA: bu slice DÖRT kez taşındı** — ADIM 54 yazıldı, `#701` 54'ü, `#699` 55'i,
> `#697` 56'yı merge edilmiş adla aldı → **ADIM 57**; commit mesajları `adim-54` yazar.
> **Sebep yapısal:** `Backend` ~50 dk + ruleset `strict: true` → yoğun günde koşu bandı
> (**beş tur**). **Çare uygulandı: auto-merge** — elle beklemek bandı kapatmıyor.
> **A-08 DEĞİŞMEDİ:** defter **2/184** hücre, SR-1 hiç başlamadı, **0/4**, #514 açık.
> Açık: **K-5** (22/23) ve **K-6a** → yalnız A-08; **K-7** ölçüldü.
> `PROJECT_HISTORY.md` §ADIM 57 · `docs/ADIM57_LANDED_KICKOFF.md` · RC §6.5.
>
> Öncesinde **ADIM 56 (A-08 denetimi BAŞLADI: SR-2 oturum 1, PR #684, 2026-08-13):
> ÜRÜN KODU DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
> Defter boş olmaktan çıktı: bir insanın duyduğu **2 hücre** (rota 1 `/`, A-1 + A-2) =
> **184'ün 2'si**, **0/10 akış**, **0/23 rota TAM**, **SR-1 hiç başlamadı** → çıkış kriterleri
> **0/4** ve kriter 1/2 tek kombinasyonla **kapatılamaz**. Denetçi **`neither`** (ürün sahibi),
> rol **atanmadı**. **`A-3` bilerek `—`** ("atlamayı fark etmedim" ≠ cevap) → **K-5 AÇIK**.
> İkinci yarı: `CLAUDE.md`'nin bayat A-08 bloğu düzeltildi — **#687 defterleri uzlaştırmış ama
> rehbere dokunmamıştı**. **Süreç bedeli:** P11-1 ruleset'i ilk kez kapı oldu (**22/22 yeşilken
> merge reddedildi** — dal main'in gerisindeydi; çözüm main'i içeri almak, **bypass DEĞİL**) ·
> **`-X theirs` sözleşme testinin pinlediği cümleyi sessizce düşürdü** → strateji-çözümünden
> sonra testi koştur · `Backend` **85 dk**'ya çıktı, koşarken log'u **404**.
> **NUMARA: bu slice AYNI GÜN İKİ KEZ taşındı** (54 → #701 aldı → 55 → #699 aldı → **56**;
> merge edilmiş ad kazanır, dal commit mesajları `adim-54`/`adim-55` yazar). **Kapanış
> yazmadan önce `git fetch` + `grep '^## ADIM' docs/PROJECT_HISTORY.md` ile numarayı doğrula.**
> `PROJECT_HISTORY.md` §ADIM 56 · `docs/ADIM56_LANDED_KICKOFF.md`.
>
> **Öncesinde ADIM 55 (agentmemory sunucusu YERELE alındı, 2026-08-13): ÜRÜN KODU
> DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
> ADIM 53'ün açık bıraktığı semantik geri çağırma kapandı — **hiçbir şey barındırmadan**:
> `.mcp.json` artık `scripts/memory_mcp.sh`'ı çağırıyor, o da tam sunucuyu **yerelde**
> kaldırıp shim'e dönüyor. **Ölçüldü:** araç **7 → 53** · soğuk kalkış **33 sn** (cache
> sıcakken 4 sn) · **LLM anahtarı GEREKMİYOR** (`zero-LLM: BM25 + on-device embeddings`) ·
> İngilizce `focus ring contrast accessibility` sunucusuz **boş**, sunucuyla Türkçe
> **§ADIM 48**'i buluyor. `--sync` ADIM 53'ün *"`--write` çoğaltır"* tuzağını kapattı.
> **İki kusuru kendi negatif kontrolüm yakaladı:** sunucu URL'deki porta değil
> `III_REST_PORT`'a bağlanıyordu (tek makinede **tek örnek** koşar), ve
> `agent-config-gate.mjs` MCP komutu `npx` değilse pin kontrolünü **atlıyordu** →
> **kapı kendi negatifini geçmişti**, düzeltildi. **Barındırma hâlâ GEREKMİYOR** — tek ek
> getirisi makineler arası elle yazılmış hafıza, o da otomatik yakalama kapalı olduğu için
> üretilmiyor. `PROJECT_HISTORY.md` §ADIM 55 · `docs/ADIM55_LANDED_KICKOFF.md` · §Hafıza.
>
> Öncesinde ADIM 54 (kabul borcu sınıf B, parti 03 — Research Data revizyon
> değişmezliği, doc 12): `RD-04` + `RD-06` KAPANDI, `partial` 113 → 111,
> `debt_class.B` 82 → 80. BLOCKER SAYISI DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**
> **Ürün kodu DEĞİŞMEDİ.** `RD-09` **partial KALDI** (yalnız c3 kapandı; c4 funding-run
> yolunu ister, yarım kanıtla işaretlenmedi). **KRİTERİN SÖZÜ ≠ SEVK EDİLEN DAVRANIŞ:**
> RD-04 *"stale işaretlenir"* diyor, sevk edilen daha güçlü — onaylı revizyon yeniden
> zamanlanamaz (`ensure_time_policy_mutable`), replacement DRAFT doğar, `DRAFT→APPROVED`
> yasal değil; test bayrak **icat etmedi**. İki tuzak: politika önce kurulmazsa **yanlış
> refüz** kanıtlanır, onay **Admin-only**. **ÜÇ YENİ BULGU (insan/PO):** `RD-01.c4`
> (analysis'te kapı yok, gerekmiyor) · `RD-05.c5` (`ToolName`'de research aracı yok) ·
> `RD-11.c2` (paket üyeleri beş alan). **Defterde artık BEŞ açık bulgu** — ADIM 42
> sınıflandırmayı `notes`'tan okudu, ürün kodunu doğrulamadığını kendi yazdı:
> **PARTİ SEÇMEDEN ÖNCE ÖLÇ.** **P1-Gate3 KAPANMADI** (A=1·B=80·C=6·D=32, açık **119**).
> `PROJECT_HISTORY.md` §ADIM 54 · `docs/ADIM54_LANDED_KICKOFF.md`.
>
> Öncesinde ADIM 53 (hafıza türetilir oldu + iki sessiz ajan kapısı, 2026-08-13):
> ÜRÜN KODU DEĞİŞMEDİ. Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
> Kapanış ritüeli **md. 4 yeniden yazıldı (insan kararı)**: memory checkpoint elle yazılmaz,
> `docs/PROJECT_HISTORY.md`'den **türetilir** (`scripts/memory_index.mjs --write --only <slug>`)
> ve pinli `@agentmemory/mcp@0.9.28`'e yazılır → efemer container artık **borç doğurmaz**;
> `PENDING_CHECKPOINTS.md` **silindi**, ADIM 47/48/49 borcu **kapandı**. Ürünün **otomatik
> yakalama yarısı bilerek bağlanmadı** (özet enjeksiyonu §Session START md. 1'in tersi).
> **YENİ BULGU:** `.claude/settings.json` **#651'den beri geçersiz JSON'du** → `docs-history-guard`
> ve `ultrareview-advisor` aradaki her oturumda **ölüydü**; `plugins/entropia-maintenance` de
> **hiç etkin değildi**. İkisi de onarıldı, `scripts/agent-config-gate.mjs` (4 kontrol, dördünün
> negatifi kanıtlı) `Frontend` job'ına **adım** olarak bağlandı — **yeni job DEĞİL** (ruleset
> `20765617`). **Doğrulanmadı:** plugin'in yüklendiği (oturum başında yüklenir) · semantik
> geri çağırma yok (sunucusuz kip **harf eşleşmesi**; kalıcı sunucu **insan kararı**) ·
> suite'ler koşmadı (Postgres/`node_modules` yok) → **otorite CI**.
> `PROJECT_HISTORY.md` §ADIM 53 · `docs/ADIM53_LANDED_KICKOFF.md` · `CLAUDE.md` §Hafıza.
>
> **Öncesinde ADIM 52 (kabul borcu sınıf B, parti 02 — dış work object run
> provenance'ı, docs 03/04/05): 5 kriter KAPANDI, `partial` 118 → 113,
> `debt_class.B` 87 → 82. BLOCKER SAYISI DEĞİŞMEDİ (1 — yalnız A-08), verdict
> BLOCKED.** Kapananlar: `TL-12` `TL-20` `TS-11` `TS-21` `AOS-21`. **Ürün kodu
> DEĞİŞMEDİ.** Eksik olan tek şey bir harness'tı — *dış work object içeren
> kompozisyonda TAMAMLANMIŞ Backtest Run*; yeni
> `tests/integration/test_external_object_run_provenance.py::_attach_trade_log` +
> `::_completed_run`, diğer builder'lar **aynen** yeniden kullanıldı.
> **ÜÇ AÇIK BULGU (insan/PO):** `TL-11.c3` **KAPATILAMAZ** — allocation-enabled run
> bu build'de **admission'da fail-closed** (`SHARED_ALLOCATION_STATUS=future_dev`),
> sınıfı **C** görünüyor ve **ADIM 48 (B-01)'in "kapatılabilir" önerisi YANLIŞTI**;
> `TL-16` D görünüyor; `TL-01.c4` yol sapması. **Hiçbiri yeniden sınıflandırılmadı —
> o tavanı YÜKSELTİRDİ.** **Parti seçmeden ÖNCE ÖLÇ:** kriterin adlandırdığı davranış
> `backend/src`'te sevk edilmemişse sınıfı yanlıştır. **NUMARA: bu slice DÖRT KEZ
> taşındı** (49→#691, 50→#685, 51→#687 merge edilmiş adlarla aldı) → **ADIM 52**;
> branch/commit `stage-49` yazar. **P1-Gate3 KAPANMADI** (A=1 · B=82 · C=6 · D=32,
> açık **121**). `PROJECT_HISTORY.md` §ADIM 52 · `docs/ADIM52_LANDED_KICKOFF.md`.
>
> Öncesinde **ADIM 51 (#514 izleme ayrışması KAPANDI, A-08 blocker AÇIK, 2026-08-12):
> KOD DEĞİŞMEDİ.**
> #514 `11:08:58Z`'de **insan eliyle yeniden AÇILDI** → ADIM 29'un kaydettiği "kapalı issue
> ↔ boş defter" ayrışması kapandı; 8 belge uzlaştırıldı (RC raporu **kendi içinde
> çelişiyordu**: banner yeniden açılmayı yazarken §6.1 + P12 tablosu + `İzleme` bloğu hâlâ
> `CLOSED` diyordu). **BLOCKER SAYISI DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED** —
> defter hâlâ boş, `0/4`, 0/46 rota, 0/20 akış. **Yeniden açma bir SONUÇ DEĞİLDİR**;
> değişen tek şey izlemenin artık açık olması. **Harf karışıklığı pinlendi:** defterde
> (A)=imzalı kabul / (B)=geri alma, RC §6.1'de (A)=denetimi koştur / (B)=imzalı sapma —
> issue'daki *"path (A)"* **RC anlamındadır**; ikisi de yeniden numaralandırılMADI.
> **#514'e DOKUNULMADI** (`human-only`). **NUMARA: bu slice ÜÇ KEZ taşındı** — ADIM 48'i
> #686+#688, ADIM 49'u #691, ADIM 50'yi #685 aldı; dördü de merge edildiği için başlıkları
> değişmez, benimki edilmemişti → **ADIM 51**. `PROJECT_HISTORY.md` §ADIM 51 ·
> `docs/ADIM51_LANDED_KICKOFF.md`.
>
> **Öncesinde ADIM 50 (RC §6.5'in İKİ PO kararı, 2026-08-12): K-2 + K-4 KAPANDI (PR #685).
> BLOCKER SAYISI DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Skip link (`Layout.tsx`
> `.skip-link` + `<main id="main-content" tabIndex={-1}>`) ve `/user-manual` `<h1>`.
> **K-2 bir UYGUNLUK düzeltmesi DEĞİLDİ** — 2.4.1 landmark'larla (ARIA11) zaten
> karşılanıyordu, axe `bypass` hep yeşildi; ergonomiydi. **K-4'ün bedeli ÖLÇÜLDÜ:**
> `/user-manual` K-5'in kümesine girdi → **K-5 21 → 22**, advisory toplamı **90 → 67**
> (CI job `94221023796`; tek+soğuk koşu → 22 bir **taban**). **Eksik `<h1>`'i precheck'te
> BLOCKING YAPMA** — sonda ilk DOM'u okur, veri render'ıyla yarışır; pin
> `17-page-coverage.spec.ts` `level: 1`. **K-6 İKİYE ayrıldı:** K-6a (halka görünüyor mu)
> A-08 bekler ve **mevcut sonda ona kanıt üretmez** (programatik `el.focus()`
> `:focus-visible`'ı eşleştirmez); **K-6b ölçüldü ve DÜŞÜYOR** — `#00a9e8` ↔ beyaz
> **2.68 : 1 < 3 : 1** (1.4.11), axe koşmuyor, D-10 (1.4.3) kapsamıyor → **`#688`'de KAPANDI**
> (halka `var(--text)`; main'de ADIM 48 adıyla kayıtlı). **K-3 hâlâ PO'da** — prompt `docs/ADIM50_KICKOFF.md` §P-2. Frontend **722 passed /
> 71 dosya**, coverage line **%84.90**. `PROJECT_HISTORY.md` §ADIM 50 · RC §6.5.
> **NUMARA ÇAKIŞMASI (aynı gün DÖRT oturum):** bu slice ADIM 48 yazıldı → 49 denendi →
> `#691` 49'u merge edilmiş adla alınca **ADIM 50** oldu. Kural: **numaralar yeniden
> atanmaz, merge edilmiş ad kazanır**; taşınan taraf hep merge edilmemiş olandır. Branch
> commit mesajları `adim-48` yazar. Çakışmayı gözle değil **`doc-status` kapısı** yakaladı.
> **Başkasının slice'ını yeniden düzenleme:** K-6b'yi ayrı belgeye taşıma denemesi
> `#691`'in kaydı üzerine **geri alındı** — o düzenleme bir **insan kararıdır**.
>
> Öncesinde ADIM 49 (P11-1 KAPANDI): **main'de required status check ruleset'i
> `20765617` AKTİF** (PR #683 hazırlığı + ayarı insan uyguladı). **16 zorunlu check**,
> hepsi `integration_id: 15368`; `pull_request` (0 onay) · `strict: true` ·
> `bypass_actors: []`. **ÇALIŞMA ŞEKLİ DEĞİŞTİ: main'e doğrudan push YOK, her PR 16 yeşil
> check + main ile güncellik ister** (`Backend` ~48 dk — bilinçli bedel). **Yeni CI job'ı
> ya da `name:` değişikliğinde SIRA: önce merge → adın üretildiğini gör →
> `scripts/required-checks-preflight.sh <pr>` → `PUT …/rulesets/20765617`. TERS SIRA TÜM
> MERGE'LERİ KİLİTLER.** Lighthouse **insan kararıyla** zorunlu; çırpınırsa **taban
> indirilmez** (`LH_REPEATS` medyanı) ve **`armed: false` kapının sessiz kapatma
> düğmesidir**. Blocker sayısı DEĞİŞMEDİ (1 — A-08), verdict BLOCKED. **Ruleset repoda
> DEĞİL — silinirse hiçbir kapı fark etmez (drift kapısı açık iş).** **Memory checkpoint
> yine YAZILAMADI** (ortam yapısal — remote'ta `ecc`/`claude-mem` kayıtlı değil) → borç
> **ADIM 47 + 48 + 49**; sahnelenmiş içerik `docs/memory/PENDING_CHECKPOINTS.md`.
> `PROJECT_HISTORY.md` §ADIM 49 · `docs/ADIM49_LANDED_KICKOFF.md`.
> Öncesinde **ADIM 48 (K-6b: odak halkası kontrastı, WCAG 1.4.11): TEK CSS deklarasyonu.**
> `global.css` `:focus-visible` halkası `var(--accent)` → **`var(--text)`**: eski hâli
> **hiçbir** zeminde 3:1'i geçmiyordu (beyaz 2.68:1, `#f5f5f5` 2.46:1, `.dropdown-blue`
> **1.00:1**), yenisi **her** zeminde geçiyor (beyaz 15.91:1; en kötü zemin `#0092c8`
> `.menu-blue:hover` **4.50:1**). **axe bunu KOŞMAZ** — yeşil ratchet bu soru için kanıt
> değildi. **Bu D-10 DEĞİL** (D-10 = 1.4.3 metin ekseni; bu 1.4.11 metin-dışı) ve **v18
> sapması DEĞİL** (mockup hiçbir odak durumu tarif etmiyor); `--accent` token'ına ve
> palete DOKUNULMADI. **K-6 defterde İKİYE ayrıldı: K-6b KAPANDI (ölçülü), K-6a AÇIK —
> yalnız A-08 kapatabilir.** Blocker sayısı DEĞİŞMEDİ (1 — A-08), verdict BLOCKED.
> **`npm run visual` / `npm run a11y` YERELDE KOŞMADI** (ortam Docker Hub blob CDN'ine
> **403**) → **otorite CI**; görsel diff çıkarsa **tabanı güncelleme**, selector'ı daralt.
> **Memory checkpoint YAZILAMAZ, sebebi YAPISAL (ölçüldü 2026-08-12):** remote container'da
> `ecc`/`claude-mem` **kayıtlı değil** (`mcpServers` boş, `.mcp.json` yok) → borç bu ortamdan
> kapatılamaz, **yerel** oturum ister. İçerik **hazır bırakıldı**:
> **`docs/memory/PENDING_CHECKPOINTS.md`** (ADIM 47 + ADIM 48, yapıştır-ve-sil).
> Sunucuları kaydetmek ya da remote'u md. 4'ten muaf tutmak **insan kararıdır**.
> `PROJECT_HISTORY.md` §ADIM 48 · `docs/ADIM48_LANDED_KICKOFF.md`.
> Öncesinde ADIM 47 (RC §6.7'nin İKİ PO kararı, 2026-08-12): §6.7.9 + §6.7.5 KAPANDI.
> **Son dalga — ADIM 48 (kabul borcu sınıf B, parti 01 — doc 05 Trade Log backend yüzeyi):
> 8 kriter KAPANDI, `partial` 126 → 118, `debt_class.B` 95 → 87. BLOCKER SAYISI
> DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Kapananlar: `TL-03` `TL-06` `TL-07`
> `TL-08` `TL-15` `TL-17` `TL-21` `TL-23`. **Ürün kodu DEĞİŞMEDİ** (tek satır bile).
> **RATCHET YALNIZ AŞAĞI İNER** — `uncovered`/A/C/**D** tavanları el değmedi,
> `total_criteria` **383 sabit (TABAN)**: rahatsız edici bir `partial`ı silerek tavan
> düşürmek yasak, kapı yakalar. **Sınıflar AYRI ratchet'lenir** → bir kriteri B'den D'ye
> taşımak **D tavanını YÜKSELTİR**, o yüzden bir adjudication'dır, test slice'ının kararı
> değil. **"İşaretlemek ≠ kapsamak":** her assertion negatif kontrolden geçirildi
> (`TL-15`'te key düşünce `ROW_VERSION_CONFLICT`, `TL-17`'de akran `USER2` ile
> `AccessDenied`). **İKİ BULGU AÇIK (insan/PO):** `TL-16`'nın sınıfı **şüpheli** —
> `c4`'ün istediği "409 kanonik durum" alanı **yok**, B değil **D** görünüyor;
> `TL-01.c4` **yol sapması** (kriter `GET /packages`, sevk edilen `GET /library`).
> **Sıradaki parti:** `TL-11.c3`+`TL-12.c3`+`TL-20.c3` — üçü de *Trade Log içeren
> kompozisyonda TAMAMLANMIŞ Backtest Run* harness'ını paylaşır. **P1-Gate3 KAPANMADI**
> (A=1 · B=87 · C=6 · D=32, açık toplam **126**).
> `PROJECT_HISTORY.md` §ADIM 48 · `docs/ADIM48_LANDED_KICKOFF.md`.
>
> Öncesinde ADIM 47 (RC §6.7'nin İKİ PO kararı, 2026-08-12): **§6.7.9 + §6.7.5 KAPANDI.
> BLOCKER SAYISI DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** (A) `../validate` +
> `../baseline-parse` **200 → 202** + tipli gövde (`ValidationRunAcceptedResponse`,
> `BaselineParseAcceptedResponse`); **otorite PO KARARIDIR, kanonik hâlâ sessiz** — "repo
> zaten 202 döndürüyor" gerekçe DEĞİL. Frontend (`apiClient` yalnız 204'ü ayırır) ve
> Idempotency (gövde aynı) **etkilenmedi**. (B) 9 kelepçeli `limit` **200 KALIR**, 422'ye
> çevrilmez — kod değişmedi, kapanan şey **gerekçenin yazılı olmaması**ydı; 19 ENFORCING /
> 9 CLAMPING ayrımı **bilinçlidir**. **§6.7 BİTMEDİ (kickoff'un "on iki kalem" iddiası
> yanlıştı, SAYILDI):** §6.7.N alt bölümleri **12'de 11 kapalı** (§6.7.10/P1-Gate3 açık),
> §6.7 tablosu **24 satırda 10 AÇIK** (P4-3 · P10-B6 · P11-1 · P11-6b · P11-3b · P8-B3b ·
> P1-Gate3 · P10-B3/B4/B5). **`/library/{id}/validation-runs` 201'de KALDI** — karar onu
> kapsamadı, ayrışma açık. **Bu oturumda ecc/claude-mem BAĞLI DEĞİLDİ → memory checkpoint
> YAZILAMADI.** `PROJECT_HISTORY.md` §ADIM 47 · `docs/ADIM47_LANDED_KICKOFF.md` · RC §6.7.5 + §6.7.9.
> Öncesinde ADIM 46 (RC §6.6, iki KOD kalemi): #617 `per_item` 1 → 0, #618 `per_item`
> 2 → 0. BLOCKER SAYISI DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** `query_budgets.json`
> iki satırda da `per_item: 0` — **ratchet, tavanı yükseltme**; N+1 geri gelirse slope
> assertion'ı kırar. **`_prefetch`'in batch SIRASI taşıyıcıdır** (`embedded_revision_id`
> vermeyen ref entry'nin `trusted_active_revision_id`'sine düşer → revizyon batch'i
> registry'den SONRA). Yeni okuma yüzeyinde döngü içine `session.get` koyma; batch
> karşılığını yaz. **#617/#618 issue durumu insan kararıdır.**
> `PROJECT_HISTORY.md` §ADIM 46 · `docs/ADIM46_LANDED_KICKOFF.md` · RC §6.6.
>
> Öncesinde ADIM 45 (RC blocker 2 KAPANDI): blocker sayısı 2 → 1, GERİYE YALNIZ A-08
> KALDI, verdict BLOCKED KALIR. `flows` artık `e2e.yml::acceptance-flows` olarak
> **bloklayıcı** bir CI kapısı ve **gerçekten koştu** (job `94097720164` → **67 passed /
> 0 failed / 1 skipped**, `duration_seconds=137`); ürün kodu değişmedi. **`E2E_MAX_SKIPS`
> bir KARARDIR** (CI: 1) — yeni skip'te tavanı yükseltme, RC §6.2'de gerekçelendir.
> **`[c2]`'nin `validation_state=failed` pini ürün-değişikliği dedektörüdür**; kırmızıya
> dönerse testi düzeltip geçme, `[c5]`'in yapısal SKIP kararını yeniden aç. **P11-1 hâlâ
> açık: required status check olmadan bu kapı merge'i DURDURAMAZ.**
> `PROJECT_HISTORY.md` §ADIM 45 · `docs/ADIM45_LANDED_KICKOFF.md` · §6.2.
> Öncesinde ADIM 44 (RC blocker 4 KAPANDI + blocker 1 koşulabilir): **blocker sayısı
> 4 → 2, verdict BLOCKED KALIR.** react-router `GHSA-qwww-vcr4-c8h2` freeze'i **imzayla
> değil KALDIRMAYLA** kapandı: imza verilmişti, ama advisory 2026-08-07T18:16:54Z'de
> upstream'de yeniden kapsamlandı (`first_patched` 7.x için **7.18.2**) ve kurulu ağaç
> **zaten 7.18.2** → `npm audit` **0 vulnerability**. **Var olmayan bir açığa imza
> atılmaz.** **`FROZEN_ADVISORIES` SİLİNDİ** — yeni npm freeze'i
> `.github/security-allowlist.json`'a `scope: npm:<dir>` + `owner` + `expires` ile yaz;
> iki kapı da `scripts/lib/security-allowlist.mjs`'ten geçer ve **ikisi de TÜM listeyi
> expire eder**; bildirilmemiş scope `exit 1`. **A-08 KAPANMADI** (0/4, defter boş,
> #514'e dokunulmadı) — yığın güncel main'de **9/9**, denetçi runbook'u yazıldı, **K-7
> eklendi** (ilk DOM'da `aria-live` yok, 21/23). **Precheck sayısını TEK KOŞUYLA
> TAZELEME:** ilk koşu soğuktur ve eksik raporlar (K-5'i 18 gösterdi, doğrusu 21) — en az
> iki kez koş. `PROJECT_HISTORY.md` §ADIM 44 · `docs/ADIM44_LANDED_KICKOFF.md` · §6.1 + §6.4.
> Öncesinde ADIM 43 (RC §6.7 / P11-8 + P10-7, iki kapı): **P10-7 KAPANDI — saat zaten
> dolmuştu** (toplayıcı ADIM 24'ten beri koşuyordu, **altı** yeşil gece birikmişti). Bant
> ölçümden türedi (`1.5 × 1.62` → **`--max-ratio 2.5`**); baseline artık **takipli dosya**
> (`docs/performance/baseline_ci.json`), artefakt saklamasına bağlı değil. **Bandı yalnız
> workflow'da genişletemezsin** — üç yerde pinli (workflow · `test_loadgen.py::_BAND` ·
> README §6), drift testi kırmızıya çevirir. **P11-8 KAPANDI:** Lighthouse **ratchet** olarak
> bağlandı, **23/23 rota** (liste `screenshotMatrix.ts::TARGET_PAGES` türevi — **elle liste
> yazma**, tabansız rota kırmızı verir). **Lighthouse a11y kategorisi ASLA açılmaz** (axe
> otoritedir) ve **hiçbir çıktısı A-08 kanıtı DEĞİLDİR**; `loadgen` = **sunucu**,
> Lighthouse = **tarayıcı**, biri diğerinin sorusuna cevap veremez. **Taban indirilmez,
> tolerans genişletilmez** — gürültü → `LH_REPEATS`/warm-up. `panel-management` performance
> tabanı **98'de KALMALI** (ölçülmüş 98–100 varyansı; 100'e sıkılaştırmak çırpınan kapı verir).
> Donmuş kusurlar (`errors-in-console` 23/23, `meta-description` 23/23, `robots-txt` 23/23,
> CLS 1/23) **AÇIK → #677**. `PROJECT_HISTORY.md` §ADIM 43 · `docs/ADIM43_LANDED_KICKOFF.md` ·
> §6.7.11 + §6.7.12. **P11 ve P10 KAPANMADI.**
> Öncesinde ADIM 42 (RC §6.7 / P1-Gate3, kabul kriteri kapsamı): sayılar **bayat
> değildi** (229/131/8 birebir yeniden üretildi); kalem "sayı yanlış" diye değil **"sayı
> anlamsız"** diye açıktı. 139 kaydın tamamı okundu, **üç sınıf veriye uymadı** → A/B/C/**D**;
> açık borcun **%24'ü sınıf D = uygulama boşluğu, hiçbir test kapatamaz**. Borç
> `acceptance_coverage_baseline.json` ile **tavan** olarak donduruldu (`--ratchet`, CI'da,
> **paysız**, negatifi kanıtlı); defter `acceptance_coverage_debt_ledger.md` **üretilmiş**.
> **Yeni `partial`/`uncovered` kriter eklersen `debt_class` ZORUNLU** — kapı sınıfsızı
> kırmızıya çevirir; **tavanı yükseltme, kriteri kapat ya da sınıfını gerekçelendir.**
> 8 clause pinlendi → yeni taban **234/126/8**. `PROJECT_HISTORY.md` §ADIM 42 ·
> `docs/ADIM42_LANDED_KICKOFF.md` · §6.7.10. **P1-Gate3 KAPANMADI.**
> Öncesinde ADIM 41 (RC §6.7 / P8-B2, durable admission status): on üç admission ucu
> **türetilerek** sınıflandırıldı (`enqueue_job` transitive closure; hepsi async, senkron uç
> YOK). Kanonik **status veren** iki uç hizalandı — `../pre-check` ve `../generate-candidate`
> artık **202** + tipli gövde; kanonik **sessiz** olan `../validate` ve `../baseline-parse`
> **200 kaldı → PO kararı bekliyor** (raporun *"diğer dokuz 202"*'si de yanlıştı: **4×200 +
> 1×201 + 8×202**). **Yeni admission ucu eklersen** `tests/contract/test_p8b2_admission_status.py`
> sınıflandırmadan geçmeyeni kırmızıya çevirir. **Kanonik boşlukta sevk edilmiş desenden wire
> contract türetme.** `PROJECT_HISTORY.md` §ADIM 41 · `docs/ADIM41_LANDED_KICKOFF.md` · §6.7.9.
> Öncesinde ADIM 40 (RC §6.7 / P1-B1+B2 + P8-B1+B3): elle yazılmış sayılar **silindi,
> sahipleri değişti** — katman sayıları üretiliyor (`repository_facts.md` §*Application modules*),
> dual-token sayısının tek sahibi `BACKEND_ROUTES.md` §DUAL-TOKEN. **Sayı yazma:** yeni
> application modülü / dramatiq aktörü eklersen **codemap satırı ZORUNLU** —
> `generate_repository_facts.py::check_codemap_coverage` CI'da kırmızıya çevirir (aktör satırında
> **kuyruk** da doğrulanır). **Satır numarası yazma, sembol adı kullan.** **P8-B3b** açık;
> **P8 KAPANMADI** (P8-B2'nin PO yarısı da açık). `PROJECT_HISTORY.md` §ADIM 40.
> Öncesinde ADIM 39 (P11-2, #665): görsel kapı **8 → 23 rota**, liste `screenshotMatrix.ts::TARGET_PAGES`
> türevi (**elle liste yazma**). **Baseline üretirken sıra ZORUNLU:** `down -v` → seed → **`npm test`**
> → `screenshots:update`; CI-dışı Linux runner'a EŞİT DEĞİL — **toleransı büyütme, maske icat etme,
> rotayı çıkarma**. Öncesinde ADIM 38 (P11-3 + P11-6): `-darwin` seti silindi,
> `scripts/visual-baseline-platform-gate.sh` geri dönüşü kırıyor (**`-linux` dışı platform eki
> commit EDİLEMEZ**), tab sırası 3/23 → 23/23.
> **P11 KAPANMADI:** P11-1 (branch protection — **insan kararı**), P11-6b, P11-8 açık.
> Öncesinde ADIM 37 (RC §6.7 / P10-B2, sayfalama sınırı, #663): 9 kelepçeli `limit` sınırını
> **yayımlıyor** (`apps/api/pagination.py::clamped_limit_query` → `x-clamp-*`; UNPUBLISHED 0);
> **kalem KAPANMADI** — aşımın clamp mi 422 mi olacağı **ürün kararı**, **PO bekliyor**
> (rapor §6.7.5). Yeni `limit` eklerken sınırsız bırakma; kelepçeliyorsa o declarator'dan
> geçir, reddediyorsa `le=` yaz.
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
> **Açık sınırlar:** **A-08 denetimi BAŞLADI ama BİTMEDİ** (SR-2'nin ilk oturumu 2026-08-12;
> **2/184** hücre, **0/10** akış, SR-1 hiç başlamadı → dört çıkış kriteri de ☐) ve
> izleme issue'su #514 **2026-08-12'de yeniden AÇILDI** — hiçbir belge A-08'i
> `Complete`/`PASS`/`Done` gösteremez (ADIM 44 yalnız **hazırlığı** bitirdi: yığın 9/9,
> runbook, tazelenmiş sayılar — **denetim değil**) · ~~P9-B2 imzasız~~ **KAPANDI (ADIM 44)** ·
> **K-2 + K-4 KAPANDI (#685), K-6b KAPANDI (#688), K-3 ADJUDICATED (D-11, kod yok)**;
> **K-5 + K-6a yalnız A-08 ile kapanır**, **K-7** ölçüldü ama düzeltilmedi. K-5/K-7'nin
> sayısı **koşudan koşuya oynuyor** (ilk koşu soğuk, eksik raporlar) ·
> **Alertmanager ARTIK VAR (ADIM 31)** ama üç artık açık: kurallar **gerçek production
> serilerine karşı hiç değerlendirilmedi** (repo içinde kapatılamaz, imzalı sapma DEĞİL) ·
> delivery proof'u **CI kapısı değil** · **monitörü izleyen yok** ·
> **P5/P6 ADIM 30'da yeniden ölçülüp COMMIT EDİLDİ** (`evidence/2026-08-10/`) — ama
> ~~**`flows` CI'da koşmuyor**~~ **KAPANDI (ADIM 45)** — `e2e.yml::acceptance-flows` ·
> **§6.6'nın #617/#618 KOD yarısı KAPANDI (ADIM 46)** — `per_item` ikisinde de ölçülen
> **0**; izleme kaydı da **KAPANDI**: insan **2026-08-13 11:07Z**'de ikisini de `completed`
> ile kapattı (**bu satır "açık kaldı" derken bayattı**, P-B/§6.2). **Tuzak:** GitHub #617'nin
> closing PR'ı olarak **#619**'u gösterir, o **ölçüm** PR'ıdır — onarım `6da8a95` = **#681**,
> ki #618'i de o onardı (bu yüzden #618'in hiç linkli PR'ı yok). **Linkage ≠ provenance.**
> #514/#558/#559 **açık kaldı** · **Ready Check'in kalan İKİ N+1 bacağı hâlâ canlı**
> (`readiness_check.py:554` sinyal, `:749` research; ölçülen slope **1.0**) — P-E2 **merge
> EDİLMEDİ** ve ikisi için **hiç issue açılmadı** ·
> **P1..P13 tanımı REPODA DEĞİL** (yalnız sohbet transkriptinde) ·
> ~~**`ci.yml` concurrency kusuru**~~ **ONARILMIŞ** (ADIM 34'te doğrulandı): `ci.yml:9–14`
> artık `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` — main'de iptal KAPALI.
> Tarihsel kayıt sabit kalır: `e8d1d48` (#633) ve `bc59dae` (#634) 0 job ile cancelled olmuş,
> CI'ları HİÇ koşmamıştı. Yeni bir job eklerken **gerçekten koştuğunu job log'undan** doğrula.
> **Next:** **PR B** — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:299` call site.
> ADIM 35 **(c)**'yi (projeksiyon), **ADIM 58 (a)'yı** kapattı: faz-bölünmüş bar
> `_ItemStepper` (`engine.py:756`) olarak **sevk edilmiş**, `E(t)` girişi
> `_phase_entry(bar, *, equity)` (`engine.py:2448`). **Kalan tek engel (b):** üç faz
> **book eder**, `ItemParticipant` arbitrasyon öncesi **tarif** ister — bu `run_engine`'in
> bar gövdesine dokunur → **ADR §16 insan kapısı + ADR amendment'ı** gerekir, o kapıdan
> geçmeden başlama. Ölçüm ve seam sıralaması:
> `docs/audit/closure_w0_shared_portfolio_2026-08-13.md`.
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
  ölçümüdür ve yeniden koşulmadı: **721 passed / 70 dosya**, **%84.92 line**.
  **Bu iki sayı da ÖLÇÜM TARİHLİDİR, current truth DEĞİL** — dosya sayısı `repository_facts.md`'nin
  ürettiği sayının (**72 dosya / 716 call site**) altında kaldığı için tek başına okunursa
  yanıltır (P-B/DR-4). Toplanan sayı için üretilmiş artefakta, geçen sayı için CI'a bak. **Dikkat (eski bir hata, tekrarlama):** ADIM 17
  koşusunda pytest'in özet satırı ve exit code'u yakalanmamıştı — çıktıyı dosyaya yaz, `$?`'i
  **ayrı** oku. **Bilinçli `xfail(strict)` sayısı ARTIK 0'dır** (ADIM 66'da 1 → 0; buraya sayı
  yazma, üretilmiş `repository_facts.md` §*Backend `xfail` markers* otoritedir). Son strict
  xfail `test_research_point_in_time_parity.py`'deydi ve tek issue **#558**'di
  (available-time policy pin'i bir ÜRÜN kararı, bug değil): **Karar 2 A1+A2 olarak imzalandı
  (2026-08-14)**, `jobs/research_data.py::_pin_member` pini sevk etti ve marker **kaldırıldı**
  — `strict=False` yapılarak **gevşetilmedi**. **#556 ×2 ve #557 düzeltildi**, artık normal
  assert ediyor (gateway `rd_jobs.admit_bundle_member` kapısından geçiyor). Oracle paketinde
  xfail **sıfır**. Yeni bir strict xfail eklersen onu **bir ürün kararına** bağla; bir bug'ı
  xfail'lemek onu görünmez yapar.
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




- **Açık iş (dürüst sınır):** ekran okuyucu denetimi **BAŞLADI, BİTMEDİ**. ADIM 28 (#628)
  **iskeleyi**, ADIM 44 **koşulabilirliği** kurdu; **2026-08-12'de SR-2 (VoiceOver/Safari)
  ilk oturumu koştu** — defter artık boş değil ama **184 Section A hücresinin 2'si** dolu,
  **10 akışın 0'ı**, **SR-1 (NVDA/Firefox) hiç başlamadı** → dört çıkış kriteri de ☐ ve
  hiçbir belge A-08'i
  `Complete`/`PASS` gösteremez. Oturumu **ürün sahibi kendisi** koştu
  (`neither`); denetçi rolü **hâlâ atanmadı**.
  Takip **GitHub #514 ŞU AN AÇIK** — `2026-08-12T11:08:58Z`'de insan eliyle yeniden açıldı
  (`reopened`), öncesinde 2026-07-30 ve 2026-08-07'de **iki kez kanıtsız kapatılmıştı**.
  Yani ADIM 29'un kaydettiği ayrışma **(B) yolu ile ÇÖZÜLDÜ**; (A) — imzalı kalıcı sapma —
  **hiç yazılmadı ve yazılmamalıdır**. Kanonik blok
  `docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸ *Tracking-issue state*.
  **Agent bu issue'yu ne kapatabilir ne açabilir** (`human-only` etiketi + issue gövdesi);
  issue'nun durumu kanıt değildir — kapı §5 çıkış kriterleridir.
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

`codebase-memory-mcp` repo kökündeki **`.mcp.json`** ile kayıtlı
(`npx -y codebase-memory-mcp@0.10.2`). **İNDEKS MAKİNEYE ÖZELDİR, REPOYLA GELMEZ:** yerelde
bu repo indekslenmişti (~13k node / ~59k edge), ama taze bir remote container'da
`list_projects` **boş** döner (2026-08-12'de ölçüldü) — orada graph araçlarını kullanmadan
önce `index_repository` çağır, yoksa boş sonucu "sembol yok" sanırsın.
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

---

## Hafıza — `agentmemory` (ADIM 53, sunucu ADIM 55)

Slice hafızası `.mcp.json`'daki **`agentmemory`** sunucusunda yaşar. İçeriği
**türetilmiştir**: `docs/PROJECT_HISTORY.md`'nin her `## ` kaydı bir memory kaydına karşılık
gelir. **Barındırılan hiçbir şey yok** — `.mcp.json` `scripts/memory_mcp.sh`'ı çağırır, o da
tam sunucuyu **yerelde** ayağa kaldırır (`localhost:3111`) ve sonra shim'e dönüşür.

| Komut | Ne yapar |
|---|---|
| `node scripts/memory_index.mjs --sync` | **hidratasyon budur**: store'da eksik olanları yazar (tekrar koşmak güvenli) |
| `… --sync --only <slug>` | tek slice yazar (kapanış ritüeli md. 4) |
| `… --write` | **TOPLAYICI** — yalnız sunucusuz kipte (export yok); ikinci koşu çoğaltır |
| `… --emit` / `--check` | JSON bas / CI kapısı (ikisi de ağsız) |
| `scripts/memory_server.sh` | sunucuyu idempotent ayağa kaldırır; canlıysa hiçbir şey yapmaz |

**Pazarlıksız sınırlar:**
- **Kayıt otorite değildir.** Her kayıt `§<başlık> (satır n)` işaretini taşır; karar
  vermeden önce `PROJECT_HISTORY.md`'nin o bölümünü **oku**. Kayıtların üçte ikisi char
  bütçesinde kesilmiştir.
- **Sunucu VARSA semantik, YOKSA harfi harfine.** Ölçüldü: sunucusuz kipte
  `focus ring contrast accessibility` **hiçbir şey bulmaz**; sunucu ayaktayken aynı
  İngilizce sorgu Türkçe `§ADIM 48` kaydını bulur (çapraz-dilli, cihaz-üstü embedding,
  **API anahtarı gerekmez**). Araç sayısı da 7 → **53** olur.
- **Tek makinede TEK örnek koşar.** İkinci bir örnek `III_REST_PORT` farklı olsa bile
  `Port already in use` verir — iii engine portu sabittir (ölçüldü). `memory_server.sh`
  bu yüzden önce `livez` sorar.
- **Sunucunun deposu da kalıcı değil** (yeniden başlatma sonrası 0 kayıt ölçüldü) — ve bu
  bir sorun DEĞİL: indeks türetilmiş, `--sync` üç saniyede geri getirir. Kalıcılık için
  bir yere sunucu **barındırmak gerekmez**; barındırmanın tek ek getirisi makineler arası
  paylaşılan **elle** yazılmış hafızadır ve otomatik yakalama kapalı olduğu için öyle bir
  içerik üretilmiyor.
- **Otomatik yakalama KAPALI** (`AGENTMEMORY_AUTO_COMPRESS` / `GRAPH_EXTRACTION_ENABLED`
  `false`, LLM anahtarı verilmedi). Ürünün 12 lifecycle hook'u ve konsolidasyon katmanı
  **bilerek bağlanmadı**: sıkıştırılmış bir önceki-oturum özetini otoritemiş gibi enjekte
  etmek §Session START md. 1'in (*STALE-BY-DEFAULT*) tersidir ve adjudicated ifadeleri
  sessizce yeniden yazar. İndekslenen şey insanın yazdığı, review'dan geçmiş metindir.
