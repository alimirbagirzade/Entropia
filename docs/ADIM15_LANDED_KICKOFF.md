# ADIM 15 landed — Unified valuation clock primitive (PR #567) · ADIM 16 kickoff'u

> Bu belge **ADIM 15'in** kapanış handoff'udur. En altta **paste-ready resume prompt** var.

## Nerede duruyoruz

| | |
|---|---|
| ADIM 15 | branch `feat/portfolio-unified-clock-core` · base `801791f` · commit **`7888760`** · **PR #567 MERGED** → `ef11dc9` (2026-08-04T20:06:44Z) |
| Landed | `backend/src/entropia/domain/backtest/execution/clock.py` (**300 satır**) · `backend/tests/unit/test_backtest_unified_clock.py` (**563 satır / 28 test**) · `docs/CODEMAPS/BACKEND_LAYERS.md` `backtest` satırı (**+1/-1**). Toplam **+864 / -1**, 3 dosya. |
| Modülün durumu | **SAF ve HİÇBİR YERDEN import EDİLMİYOR.** ADR §12'de ADIM 15'in rollback'i "modülü sil"; `test_the_clock_is_not_wired_into_production_yet` bunu kilitler (kaynak ağacını tarar, importer listesi boş olmalı). |
| Migration | **YOK** — alembic head `0043_i08_registry_strategy_fks`, tek head, dokunulmadı |
| OpenAPI | **196 operation / 151 schema** — değişmedi (hiçbir response model'e dokunulmadı) |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` — **değişmedi**, bu PR'daki bir testle pinlendi |
| Golden digest | **46'sının hiçbiri oynamadı** — `run_engine` imzası **ve semantiği** korundu (ADR §3.2) |
| Containment | **Değişmedi** — `SHARED_ALLOCATION_STATUS = "future_dev"`, iki admission guard yerinde |
| Yerel doğrulama | tek `pytest` çağrısı, çıktı dosyaya, exit code ayrı okundu → **exit `0`**, coverage **%92.93** (kapı ≥90). `ruff check` / `ruff format --check` 739 dosyada temiz, `mypy src` 386 dosyada temiz. |
| CI | **6/6 yeşil** |
| Codemap | **Tazelendi (PR #567 içinde).** `docs/CODEMAPS/BACKEND_LAYERS.md` `backtest` satırı `execution/clock.py`'yi ve modülün bilinçli olarak **karar vermediklerini** taşıyor. **Bu kapanışta tekrar dokunulmadı.** |

**Bir sonraki base:** `origin/main` @ `0f44c3a` (PR #568 / F-26 relabel dahil; veya bu kapanış
PR'ı merge olduktan sonrası).
**Dallanmadan önce `git fetch` + merge doğrulaması yap** — bu seride `origin/main` oturum
ortasında birden fazla kez ilerledi.

## ⚠ ADR statüsü — kayda geçmesi gereken sapma

`docs/adr/0002-unified-clock-portfolio-simulation.md` **hâlâ `Status: Proposed`.** ADR §16 onayı
implementasyonun kapısı yapıyordu ve belgede kayıtlı bir onay **yok**. ADIM 15 buna rağmen
**kullanıcının açık talimatıyla** başladı ve indi. Bu bir ihlal değil — talimat kapıyı geçersiz
kıldı — ama **kayıt düzeltilmelidir**: ya ADR `Accepted`'a çekilip §13'ün yedi kararı bir
amendment tablosuna çözüm olarak yazılır, ya da §16 gerçek pratiği yansıtacak şekilde
gevşetilir. **Karar üründedir, agent'ta değil.** ADIM 16'ya başlayan oturum bunu yeniden sormalı.

## ADIM 15 ne bıraktı — reuse anchor'ları (tam sembol adlarıyla)

Hepsi `backend/src/entropia/domain/backtest/execution/clock.py` içinde. **Kendi eksenini icat etme.**

### Public yüzey

| Sembol | Sözleşme |
|---|---|
| `iter_ticks(streams: Sequence[ItemBarStream]) -> Iterator[ClockTick]` | Birleştirilmiş valuation noktalarını **artan zamanda**, instant başına **tek** `ClockTick` olarak üretir. `ticks(run) = sorted(union of decision_times(item_i))`, dedup'lu (ADR §4.2). Tek stream ile bu, o item'ın kendi bar eksenine indirgenir — ADR §3.2'nin sınırı. |
| `ItemBarStream(item_id: str, pin_ordinal: int, batches: Iterable[list[dict]])` | Bir item'ın pinli bar kaynağı. `batches` **worker'ın bugün elinde tuttuğu chunk'lı iterator** (`stream_bars` / `iter_bar_batches`) — aynen geçirilir. `pin_ordinal` = manifest'in deterministik pin sırasındaki index (`manifest._pinned_items`, `(root_id, selected_revision_id)`'ye göre sıralı). **Asla DOM sırası, asla istek varış sırası.** |
| `ClockTick(t_ms: int, views: tuple[ItemTickView, ...])` | Tek valuation noktası. `views` **HER** stream'i taşır — karar versin vermesin — `(pin_ordinal, item_id)` sırasında (ADR §4.4 serialization sırası). `.deciding` taze barı olanları, `.view_for(item_id)` tekini verir. |
| `ItemTickView(item_id, pin_ordinal, t_ms, bars, last_closed, last_closed_t_ms)` | Bir item'ın bir tick'teki görünümü. `.is_decision` = `bool(bars)` (ADR §5: taze bar yoksa karar yok). `.staleness_ms` = `t_ms - last_closed_t_ms`, item'ın ilk barından önce `None`. **ÖLÇÜM — eşik yok, fill yok (OD-2 açık).** |
| `tick_key(timestamp: str) -> int \| None` | Bar timestamp'ının UTC epoch ms'i, yerleştirilemiyorsa `None`. `parse_utc(timestamp, source_zone=None)` üzerinden — sevk edilmiş iki wrapper (`engine._epoch_ms_or_none`, `execution.rules.bar_epoch_ms`) ile **aynı konvansiyon**; üçünün anlaştığı bir test var (`test_tick_key_agrees_with_the_shipped_epoch_helpers`). Ayrı fonksiyon olma sebebi tek: clock, ADIM 19'un emekli edeceği `execution.rules`'a bağlanmasın. |
| `timeline_identity(t_ms_values, *, policy_version=CLOCK_POLICY_VERSION) -> str` | Bir eksenin deterministik kimliği: tick instant'ları üzerinde sha256 hex. İki koşu **tam olarak** aynı instant'lara aynı sırada ve aynı policy altında sahipse aynı kimliği taşır. **Incremental** hesaplanır — eksen materialize edilmeden kimliklenir. |
| `CLOCK_POLICY_VERSION = "clock-policy-v1"` | Tick-set kuralı (ADR §4.2) + adjudication A-1'i pinler. **Manifest'e YAZILMADI** — ADR §10.3 bunu ADIM 20'ye koyuyor. |

### Fail-closed hata sınıfları (hepsi `ValueError` türevi, `engine.UnresolvedStrategyError` kalıbı)

`ClockAxisError` (kök) → `UnplaceableBarTimestampError` (timestamp UTC instant'a çözülemedi) ·
`NonMonotonicBarStreamError` (item'ın akışı geriye gitti) · `DuplicateItemStreamError` (iki
stream aynı `item_id`'yi iddia ediyor). **Hiçbiri "atla" demiyor** — ADR §11 / Modül 12 §9:
tick'i yerleştiremeyen worker run'ı düşürür, bozuk eksende devam etmez.

### İçeriden bağlandığı yerler (yeni sözleşme yaratılmadı)

`entropia.domain.backtest.execution.state` → `_Bar`, `_normalize` (**engine ile aynı coercion
sınırı**: engine'in düşüreceği satır burada da düşer) · `entropia.domain.backtest.funding` →
`parse_utc`.

### Dört tasarım kararı — taste değil, sözleşme

1. **Tick anahtarı `t_ms`, string DEĞİL.** Karışık offset formları girince string sırası yalnız
   *kazara* doğrudur; `"...T02:00:00+01:00"` ile `"...T01:00:00Z"` **tek** tick'e düşmelidir.
2. **Tick bir valuation noktasıdır, `(item, time)` çifti değil.** Item'lar tick'in *içinde*
   yaşar → "her item `t`'de aynı snapshot'ı görür" yapısal olur, sonraki reviewer'ın yeniden
   doğrulayacağı bir disiplin değil.
3. **Dedup EKSENİN'dir, item verisinin değil.** Bir item'ın pinli akışında aynı instant'ta iki
   bar varsa **ikisi de** o item'ın `bars` tuple'ında görünür, eksen bir kez ilerler. Collapse
   kanonun vermediği bir merge kuralı ister; drop pinli veriyi sessizce atar.
4. **Streaming zorunlu.** k-way heap merge (`heapq.merge`, key `(t_ms, pin_ordinal, item_id)`) +
   `groupby`; item başına **en fazla bir** bar tutulur. Bir test kaynak generator'lardan çekilen
   satır sayısını sayar (`test_the_axis_does_not_materialize_the_streams`).

### İki sınır testi — ADIM 16/18'in kazayla kırmaması gereken

* `test_the_clock_is_not_wired_into_production_yet` — kaynak ağacını tarar, `execution.clock`
  geçen `clock.py` dışı dosya olmamalı. **ADIM 18 `run_portfolio`'yu bağladığında bu test
  bilinçli güncellenir; asla kazayla düşmemeli.**
* `test_no_clock_field_ships_in_the_manifest_yet_and_the_engine_version_stands` —
  `ENGINE_VERSION` sabit **ve** `manifest.py` içinde `clock_policy_version`,
  `arbitration_policy_version`, `mark_staleness_policy`, `engine_allocation_policy_version`
  **geçmiyor**. ADIM 20 sınırını *niyet* değil *kapı* yapar.

### Mutation testi — "ilk yazışta geçen test kanıt değildir"

Altı mutasyon uygulandı, **altısı da yakalanıyor**: cursor'ın mükerrer bardan ilkini (sonuncusu
yerine) izlemesi · barsız view'ların düşürülmesi · **merge'ün `t_ms` yerine ham timestamp
string'iyle anahtarlanması** · geriye-giden-akış guard'ının kaldırılması · `(pin_ordinal,
item_id)` sıralamasının kaldırılması · mükerrer `item_id` guard'ının kaldırılması.
**String-key mutasyonu ilk turda HAYATTA KALDI** — offset fixture'ı iki kaydı tesadüfen bitişik
bırakıyordu, `groupby` yine doğru grupluyordu. Kapatan test:
`test_a_mixed_offset_axis_orders_by_instant_and_not_by_text`. **Bu yöntem ADIM 16–19'da
tekrarlanmalı**; geçen bir suite tek başına kanıt sayılmaz.

## Dürüst sınırlar — beşi de kayda geçmeli

1. **ADR `Proposed`.** Yukarıda §"ADR statüsü". §16 onaysız implementasyonu yasaklıyordu;
   ADIM 15 kullanıcının açık talimatıyla başladı. Kayıt düzeltilmeli.
2. **Manifest policy alanları BİLEREK yazılmadı.** ADR §10.3/§12 dört alanı (`clock_policy_version`,
   `arbitration_policy_version`, `mark_staleness_policy`, `engine_allocation_policy_version`)
   `ENGINE_VERSION` bump'ıyla **birlikte** ADIM 20'ye koyuyor. Şimdi yazmak ya `execution_key`'i
   erken kaydırırdı ya da arkasında policy olmayan bir isim yayımlardı. **Uzlaşma:**
   `CLOCK_POLICY_VERSION` + `timeline_identity()` modül düzeyinde durur (policy ilk satırından
   itibaren tek eve sahip), ve bir test dört alan adının `manifest.py`'de **olmadığını** kilitler.
3. **OD-2 açık — clock ÖLÇER, eşik KOYMAZ.** `staleness_ms` bir ölçümdür; bayat barın ileri
   taşınıp taşınamayacağı ve ne kadar süreyle taşınacağı **cevapsız**. **ADIM 17 bunu
   çözmeden portföy geneli `E(t)` hesaplayamaz** — sıradaki gerçek blocker budur.
4. **Naive timestamp ekseni DÜŞÜRÜR, ama `indicators._epoch_seconds` aynı değeri UTC varsayar.**
   `parse_utc(source_zone=None)` offset'siz değeri çözümsüz sayar (K-01) → clock reddeder.
   Üretim barları ingest'te UTC-normalize edildiği için bunun tetiklenmemesi beklenir, ama
   **iki yardımcı gerçekten ayrışıyor** ve **ADIM 16/18 bununla karşılaşacak.** Bir testle
   pinli ve modül docstring'inde yazılı.
5. **ADR kendi içinde çelişiyor — düzeltilmedi, işaretlendi.** §3.2 **38** senaryonun
   kımıldamaması gerektiğini söylüyor (`portfolio.rules_none` dahil), A13 ise **37** portföy-dışı
   digest'in değişmediğini ve "yalnız 9 `portfolio.*` senaryosunun hareket ettiğini" söylüyor.
   İkisi `portfolio.rules_none` hakkında **aynı anda doğru olamaz**. **ADIM 19/20'de ısırır**,
   ADIM 15'te değil — bu yüzden sessizce biri seçilmedi.

## Açık kalemler — bu kapanışta yeniden doğrulandı

**KAPANDI (kayıt düzeltmesi):** **R-1** — `readiness_check._resolve_allocation` revision pinning
kusuru **PR #565 ile indi** (merged 2026-08-04T19:30:39Z, merge `06809cc`). Önceki
`CLAUDE.md` / `ADIM14_LANDED_KICKOFF.md` onu "açık, worktree boş" diye taşıyordu; **artık
geçersiz.** ADIM 20'nin bu önkoşulu karşılandı.

**#539'un düzeltmesi de indi** (PR #564, merged 2026-08-04T19:32:36Z, merge `b8d62e2`) — ama
**issue #539 hâlâ OPEN**; kapatma yetkisi insandadır.

**Hâlâ açık:**

1. **OD-2** (bayat mark policy) — ADIM 17'nin önkoşulu, en yakın gerçek blocker.
2. **Manifest'te eksik üç kanonik alan (ADR §10.1)** — resolved sleeve amounts, currency/FX refs,
   `engine_allocation_policy_version`. ADIM 20'den önce. *(§10.3'ün dört policy alanı ayrı kalem
   ve zaten ADIM 20'ye ait.)*
3. **#559 (DST)** — merged eksen karışık zaman dilimli kaynakları kapsamadan önce kapanmalı;
   ADIM 15 bunu **cross-item** hâle getirebilecek ekseni kurdu.
4. **#544 (NET)** — cross-item conflict policy kanonda tanımsız; ADIM 19 ile ya da öncesinde.
5. **#550 / #551 / #552** (ADIM 12) — sizing/booking uyuşmazlıkları. #550 karara bağlanmadan
   sizing üzerine yeni iş yapılmamalı.
6. **#556 / #557 / #558** (ADIM 13) — dört `xfail(strict)`'in issue eşlemesi,
   `tests/integration/test_research_point_in_time_parity.py` içinde.
7. **#514** — ekran okuyucu denetimi; kapatma yetkisi insanda.
8. **OD-1, OD-3…OD-7** — hiçbiri kapanmadı.
9. **#540** — exhaustiveness guard'ın kendi issue'su; F-26'nın guard'ı **12 bağlı alanı**
   kapsıyor, #540'ın istediği **14 alanlık** tam kapsam değil. **#533** de açık (F-26'nın
   düzeltmesi indi, issue kapatılmadı).

**Numaralandırma çakışması ÇÖZÜLDÜ:** **PR #568 merge oldu** (main `0f44c3a`) — **ADIM 14 = ADR**,
frontend capability disclosure slice = **F-26** (PR #564 ile landed). ADIM 15–20 unified-clock'a
rezerve kalır; ADIM dışı işe F-serisinden sıradaki boş numara verilir. Bu kapanış #568'in üzerine
rebase edildi, bu yüzden `STAGE2_HANDOFF.md` ve `PROJECT_HISTORY.md` **hem §F-26 hem §ADIM 15**
kaydını kronolojik sırada taşır.

## ADIM 16 için tasarım işaretleri

**Görev (ADR §12 satır 16):** `run_engine`'in **bar döngü gövdesini** resumable bir stepper'a
çıkar; `run_engine` o stepper üzerinde ince bir sürücü olarak kalır. **İmza VE semantik sabit.**
Birincil dosyalar: `domain/backtest/engine.py`, `domain/backtest/execution/state.py`.

**Tek kabul kanıtı: 46 golden digest'in HİÇBİRİ oynamamalı.** Başka hiçbir iddiaya güvenilmez
(ADR R-4). Hareket eden bir digest ADIM 16'da **yazılı gerekçeyle bile** kabul edilmez — çünkü
saf refactor'ün tanımı budur.

**Clock'a dokunma.** ADIM 16 stepper'ı clock'u **import etmez**; iki modülün buluşması ADIM 18'in
işidir. `test_the_clock_is_not_wired_into_production_yet` ADIM 16'da hâlâ yeşil kalmalı.

**REUSE listesi:** ADR §12 tablosu (PR sınırı + dosya listesi — kendi bölmeni icat etme) ·
§13 OD tablosu (kanonun sessiz olduğu her yer; bir OD'yi "herhalde böyledir" diye kapatma) ·
§14 A1–A22 (kabul kanıtı; yeni kanıt icat etmeden önce burada var mı bak) · §10.3 versiyon planı ·
`domain/allocation/capability.py` içindeki 6 numaralı kaldırma koşulu ·
`docs/CODEMAPS/BACKEND_LAYERS.md` `backtest` satırı (clock'un ne yapıp ne yapmadığı yazılı).

## Çalışma döngüsü (ADIM 15'te işe yarayan)

1. `git fetch --all --prune` → **merge'i doğrula** → `git switch -c <branch> origin/main`.
2. Yeni modülü **saf** yaz ve saflığı bir **testle kilitle** — "hiçbir şey import etmiyor"
   iddiası ancak makine doğruluyorsa rollback garantisidir.
3. **Testleri mutasyonla sına.** Altı mutasyondan biri ilk turda hayatta kaldı; onu yakalayan
   test sonradan yazıldı. Mutasyon koşmadan "28 test geçti" bir kanıt cümlesi değildir.
4. Kanonun **sessiz** olduğu yeri "canon böyle diyor" diye raporlama — OD olarak ayır, ölç,
   eşik koyma.
5. Tam suite'i **tek** pytest çağrısında, worktree'ye özel `postgresql+asyncpg` DB ile koş;
   çıktıyı dosyaya yaz, exit code'u ayrı oku (**`| tail` KULLANMA** — exit code tail'in olur).
6. Belgeyi yazarken bulunan çelişki (ADR §3.2 vs A13 gibi) **belgede kalır ve kalem olarak
   açılır** — sessizce bir taraf seçilmez.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 16: run_engine'in bar döngüsünü resumable stepper'a çıkar

ROL VE ÇALIŞMA BİÇİMİ

Sen Entropia V18 üzerinde çalışan kıdemli principal engineer ve release-closure
sorumlususun. Amaç yeni özellik icat etmek değil; canonical Production V1 sözleşmesini
current `origin/main` üzerinde kanıtlamak, yalnız doğrulanmış boşluğu dar bir PR ile
kapatmak ve sistemi geriletmemektir.

Read-only subagent'ları araştırma/inceleme için kullan; production değişikliklerini
yalnız ana oturum yapsın; tek branch, tek PR, tek sorumlu writer.

HER OTURUMUN ZORUNLU BAŞLANGICI

1. `git fetch --all --prune` · `git status --short` — temiz değilse DUR.
2. Current main SHA + açık PR/issue snapshot'ı al. **PR #567 (ADIM 15 clock) merge
   edildi mi doğrula** — edildi (`ef11dc9`, commit `7888760`); **PR #568** (F-26 relabel)
   da merge edildi (`0f44c3a`). Bu kapanış PR'ının (`docs/stage-15-landed`) durumunu doğrula.
3. `docs/ADIM15_LANDED_KICKOFF.md` (bu belge) + ADR §12 (sınırlar), §13 (açık kararlar),
   §14 (kabul matrisi) — bu üçü slice'ın sözleşmesidir.
4. **`docs/adr/0002-unified-clock-portfolio-simulation.md` STATÜSÜNÜ OKU.** ADIM 15
   indiği hâlde statü hâlâ `Proposed` olabilir (§16 onayı kapı yapıyordu; ADIM 15
   kullanıcı talimatıyla başladı). Statü hâlâ Proposed ise **devam etmeden önce sor** —
   sessizce onaylanmış sayma.
5. `docs/CODEMAPS/BACKEND_LAYERS.md` `backtest` satırını ve `domain/backtest/engine.py`
   içindeki gerçek bar döngüsünü oku.
6. Eski README/CLAUDE.md/handoff/backlog iddiasını current truth sayma — kaynak dosyayı
   oku. (Örnek: R-1 "açık" diye taşınıyordu; PR #565 ile kapandı.)

BU ADIMIN AMACI

ADR §12'nin 16 numaralı satırı: `run_engine`'in bar-döngü gövdesini resumable bir
STEPPER'a çıkar; `run_engine` stepper üzerinde ince bir sürücü olarak kalır. İmza VE
semantik korunur. Birincil dosyalar: `domain/backtest/engine.py`,
`domain/backtest/execution/state.py`. SAF REFACTOR — davranış değişikliği YOK.

TEK KABUL KANITI: 46 golden digest'in HİÇBİRİ oynamamalı. Hareket eden bir digest
ADIM 16'da yazılı gerekçeyle bile kabul EDİLMEZ; saf refactor'ün tanımı budur (ADR R-4).

ADIM 15'İN CLOCK'UNA DOKUNMA. Stepper `execution/clock.py`'yi import ETMEZ; iki modülün
buluşması ADIM 18'in işidir. `test_the_clock_is_not_wired_into_production_yet` ADIM 16
sonunda hâlâ yeşil olmalı ve `test_no_clock_field_ships_in_the_manifest_yet_and_the_
engine_version_stands` de öyle.

TAVİZ VERİLEMEZ KURALLAR

ADR §13'ün YEDİ açık kararı (OD-1…OD-7) KARARA BAĞLANMADAN o karara bağlı davranış
implemente EDİLMEZ; boşluğu boşluk olarak raporla, varsayılan uydurma. OD-2 (bayat bar
mark policy) hâlâ açık ve ADIM 17'nin önkoşulu. Containment (SHARED_ALLOCATION_STATUS)
yalnız ADIM 20'de ve yalnız §14 matrisi tam geçince kalkar. ENGINE_VERSION yalnız
ADIM 20'de bump edilir. Manifest policy alanları (clock_policy_version,
arbitration_policy_version, mark_staleness_policy, engine_allocation_policy_version)
ADIM 20'ye aittir — ADIM 16'da yazılmaz.

Trading Signal ve Trade Log Package değildir. Backtest Run ile Result aynı entity
değildir; yalnız SUCCEEDED Run immutable Result üretir. Agent human account değildir.
Uzun işler durable queue üzerinden yürür. UI hidden/disabled durumu authorization
değildir. Server-side policy, ownership, OCC, idempotency, audit ve lifecycle korunur.
Revision/snapshot/fingerprint/manifest/pinned revision geriye dönük bozulmaz. Research
Data için event_time ve available_time ayrımı korunur. Historical Result canlı
root/live registry join'iyle yeniden yorumlanmaz. Başarısız test varken `Complete`
yazılmaz.

ZORUNLU DOĞRULAMA

- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
- `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<wt>_db`
  ile **tek** pytest çağrısı, arka planda, çıktı dosyaya, exit code ayrı okunur
  (`| tail` KULLANMA — exit code tail'in olur). Suite koşarken `uv sync`/`uv run`
  çalıştırma.
- 46 golden digest ve engine suite'leri korunur; oracle paketi (`tests/unit/oracles/`)
  onların yerine geçmez ve zayıflatılmaz.
- **Testleri mutasyonla sına.** ADIM 15'te altı mutasyondan biri ilk turda hayatta kaldı;
  "suite geçti" tek başına kanıt değildir.

PR DİSİPLİNİ

Yalnız bu slice. İlgisiz refactor/dependency/görsel değişiklik yok. Migration varsa
single-head + up/down/up kanıtı. Engine semantiği değişiyorsa ENGINE_VERSION kararını
açıkça değerlendir (ADIM 16'da değişmemeli). Public API değişiyorsa OpenAPI snapshot +
frontend wire contract. Claude merge etmez, tag/release oluşturmaz. PR sonunda base SHA,
branch, commit, PR, changed behavior, unchanged boundaries, targeted tests, full-suite
exit code, migration/OpenAPI/codemap etkisi, kalan risk ve sonraki tek adım raporlanır.
```
