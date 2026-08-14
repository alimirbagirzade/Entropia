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

> **alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration yok) ·
> `ENGINE_VERSION` **değişmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`.
> **Son dalga — ADIM 64 (kabul borcu sınıf B, parti 04 — Backtest Result satır
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
