<!-- doc-status: current -->
# `instrument_mapping_ref`'i **kim yazar**, ve hangi bedelle (GH #703'ün İKİNCİ kapısı)

> **BU BELGEDE HİÇBİR ÜRÜN SEMANTİĞİ KARARA BAĞLANMAMIŞTIR.** Yazarın rolü **ölçüm ve
> hazırlık**tır. §Karar'ın imza bloklarını yalnız ürün sahibi / maintainer doldurur.
> `closure_i854_external_import_pin_stability_2026-08-28.md`,
> `closure_od2_mark_production_binding_2026-08-28.md` ve
> `closure_g14_net_conflict_policy_2026-08-25.md` ile aynı disiplin.

- **Tarih:** 2026-08-30
- **Base:** `origin/main` @ `7f2d8317` (`fix(stage-138): GH #703 — native_asset_id üretimde
  ilk kez yazılıyor …`). Ölçüm sırasında açık PR **yoktu** — anlık görüntüdür, garanti
  değil (ADIM 100).
- **İzleme:** GitHub issue **#703** (açık). İssue'yu kapatmak **insan kararıdır**; bu belge
  ona dokunmaz. ADIM 138 issue'nun **native-asset** yarısını kapattı; başlığındaki iddia
  (*"Funding-enabled runs cannot use any Research revision created through the app"*)
  **bu ikinci kapı yüzünden ayakta kaldı** ve o slice bunu açıkça öyle kaydetti.
- **Bloklar:** RC verdict'ini **bloklamaz**; tek blocker **A-08 (#514)** ve bu karar o hatta
  dokunmaz. Kusurun kendisi **sevk edilmiş kullanıcı yolundadır**.
- **Neden şimdi:** ADIM 138 kusuru *"backlog R1, kapsam dışı, TESTLE PİNLENDİ, adjudicate
  EDİLMEDİ"* bırakmıştı. ADIM 140 kusurun **ikinci düzlemini** (Ready Check) ölçtü ve
  koşulur kıldı; **düzeltmesini sevk etmez**, çünkü düzeltme bir ürün kararıdır.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — Kolonun yazıcısı: **sıfır**, ve bu ADIM 138'den beri değişmedi

`ResearchDatasetRevision.instrument_mapping_ref` `backend/src` içinde **dört yerde okunur**
(`queries/funding.py`, `commands/readiness_check.py`, `jobs/research_data.py` ×2 — biri
bundle üyesi, biri türetilmiş dizi) ve `domain/` içinde üç değer nesnesi tarafından taşınır
(`timing_provenance.py`, `readiness/issues.py`, `quality_rules.py`).

**Yazan sıfır satır vardır.** Ölçüm: `application/commands/research_data.py` içinde token
**0 kez** geçer — yani ne `create_research_dataset` ne `create_research_dataset_revision`
onu set eder. `apps/api/routes/research_data.py`'deki tek hit bir **response** modelidir
(`BundleMemberModel`, sealed bundle'ın okuma yüzeyi), `frontend/src`'teki iki hit de okuma
tarafıdır (bir TS tipi + bir test fixture'ı). Yazma yüzeyi **yoktur**.

## Ölçüm 2 — Kardeş kolon **koşulsuz** yazılır, ve kapıyı bu asimetri kapatır

`instrument_mapping_is_valid` (`domain/research_data/time_policy.py`) `has_link == has_ref`
döner. İki yarı ayrışınca kapı kapanır.

| Yol | `linked_market_dataset_revision_id` | `instrument_mapping_ref` | Predicate |
|---|---|---|---|
| `create_research_dataset` | **her zaman** yazılır | hiç | **False** |
| `create_research_dataset_revision` (`market_entity_id` verilmiş) | yazılır | hiç | **False** |
| `create_research_dataset_revision` (verilmemiş) | `None` | hiç | True |

`CreateDatasetRequest.market_entity_id` **zorunlu** bir alandır (`str`, `| None` değil) ve
`create_research_dataset` `_resolve_market_link`'i **koşulsuz** çağırır — DR3 gereği bir
research dataset'i ancak ACTIVE+APPROVED bir market'a bağlanarak doğar. Yani **kökün ilk
revizyonu her zaman `False` tarafındadır**; üçüncü satır yalnız sonradan, market linki
verilmeden çekilen bir revizyon için geçerlidir.

## Ölçüm 3 — Kapı **iki** düzlemde vuruyor; ADIM 138 yalnız birini pinledi

| Düzlem | Yüzey | Sonuç |
|---|---|---|
| Worker | `queries/funding.py::resolve_funding_schedule` -> `build_funding_schedule` | `FundingSourceInvalid` (fail-closed) |
| Admission | `domain/readiness/validators.py::_research_market_compatibility_issues` | `INSTRUMENT_MAPPING_INVALID`, **`Sev.BLOCKER`** |

Ready Check düzlemi **admission'da, worker'dan önce** vurur. ADIM 140 bunu üretim yolunda
ilk kez koştu ve ölçtü:

```
MEASURED ISSUE CODES: ['INSTRUMENT_MAPPING_INVALID', 'RESEARCH_COVERAGE_LIMITED']
STATE: not_ready
```

Aynı kompozisyon şekli, `test_readiness_research_data.py`'nin **elle tohumlanmış**
revizyonuyla `ready_with_warnings` verir ve admission'ı **geçer**
(`test_warned_research_revision_is_ready_with_warnings_not_blocked`). Ayrışmanın tek sebebi
Ölçüm 2'nin tablosudur.

## Ölçüm 4 — Kusurun **görünmez kalma** sebebi: harness üretimin üretemeyeceği şekli kuruyor

`test_readiness_research_data.py::_seed_research_revision` revizyonu elle `session.add`
eder ve `linked_market_dataset_revision_id`'yi **hiç set etmez** -> `False == False` ->
predicate **coherent** der -> BLOCKER hiç doğmaz. Üretim o şekli **üretemez** (Ölçüm 2).

Bu, ADIM 138'in dersinin ayna görüntüsüdür ve daha sinsi bir kılıktadır: orada fake
**fazladan** bir şey yapıyordu (pointer'ı set ediyordu), burada harness **eksik** bir şey
yapıyor ve o eksiklik kapıyı **güvenli** tarafa düşürüyor. *Bir fixture'ın yapmadığı şey de
bir iddiadır.*

## Ölçüm 5 — Negatif kontroller (ADIM 140, gerçek Postgres, izole DB)

Taban: üç dosya / **12 test** yeşil. Her yama uygulandı, ölçüldü, **bellekteki anlık
görüntüden** geri yazıldı (`git checkout` ile değil — ADIM 111'in dersi); `git status` temiz.

| NC | Yama | Kırmızıya dönen | Ölçtüğü |
|---|---|---|---|
| NC-1 | `instrument_mapping_is_valid` -> `return True` | ADIM 140'un 2 testi + ADIM 138'in worker testi | **`readiness_research_data`'nın 6 testi YEŞİL KALIR** = Ready Check düzlemindeki boşluk gerçekti |
| NC-2 | yalnız Ready Check kapısı sökülür | **yalnız** ADIM 140'un 2 testi | iki düzlem **bağımsız**; yeni testler worker düzleminin gölgesi değil |
| NC-3 | seeder'a `md_rev_1` linki eklenir | ADIM 140'un ayrışma testi + **`readiness_research_data`'nın 2 testi** | harness'ı üretim şekline çekmenin **ölçülmüş bedeli** (§Karar 2) |

NC-3'te ADIM 140'un diğer iki testi **yeşil kaldı** — onlar seeder'dan bağımsız, kendi
üretim revizyonlarını kurarlar.

## Ölçüm 6 — Kanonik altyapı **eksik değil, BAĞLANMAMIŞ**; ve emsali aynı repoda sevk edilmiş

`time_policy.py` boşluğu *"canonical instrument-resolution wiring is still backlog R1"*
diye adlandırır. Ölçüldü: **altyapının kendisi vardır ve sevk edilmiştir.**

- `instrument_registry` (`resolution_key` UNIQUE) + `instrument_alias` (`alias_norm` UNIQUE)
- `application/queries/instrument.py::resolve_scope`, `::resolve_scope_id`
- `application/commands/instrument.py`, `repositories/instrument.py`

**Ve Market Data tarafı bu deseni zaten kullanıyor:** `routes/market_data.py` gövdesi hem
`instrument_id` hem serbest metinli `instrument_scope` (`{venue_id, symbol, contract_type}`
ya da `{alias}`) alır; `commands/market_data.py` scope'u `resolve_scope_id` ile kanonik
`instrument_id`'ye çözer ve çözülemezse **fail-closed 422** verir
(`INSTRUMENT_SCOPE_UNRESOLVABLE`), kendi ifadesiyle *"no flow ever silently persists a
free-text instrument assumption"*. `MarketDatasetRevision.instrument_id` bu yolla yazılır.

Yani R1, yazılacak yeni bir alt sistem değil — **Research Data'nın Market Data'da sevk
edilmiş deseni aynalamamasıdır.** Doc 12 §430'un dili de bu ikiliyi adlandırır:
*"instrument_scope / instrument_mapping_ref … Must map to linked market universe **or
explicitly document market-wide/provider-defined scope**."*

## Ölçüm 7 — Maliyetler (türetildi; migration ve şema iddiaları ölçüldü)

| | Migration | OpenAPI | Frontend | golden / `ENGINE_VERSION` |
|---|---|---|---|---|
| (a) | yok | yok | yok | yok |
| (b) | yok | yok | yok | yok |
| (c) | **yok** (kolon var) | **değişir** (route gövdesi) | **gerekir** (v18 mockup önce) | yok |
| (d) | yok | yok | yok | yok |

`instrument_mapping_ref` **zaten** `String(256)` bir kolondur ve `0004_research_data`'da
inmiştir; hiçbir seçenek şema değiştirmez. `ENGINE_VERSION`/golden hiçbirinde oynamaz — bu
alan `execution_key`'e girmez, run manifest'inin research bölümünde taşınır.

---

## §Karar 1 — `instrument_mapping_ref`'i kim yazar?

### Karar kutusu — **İMZALI: `(b)` LİNK'TEN TÜRET (2026-08-31)**

☐ **(a) STATÜKO — kusur kabul edilir.** App-created hiçbir research revizyonu funding
  koşusunda kullanılamaz; #703 başlığındaki iddia doğru kalır ve issue açık kalır.
  **Bedeli:** `RD-09.c4` kapatılamaz durumda kalır (funding-enabled bir RUN, ref'i elle set
  etmeden kurulamaz — ki bu tam olarak ADIM 138'in kör noktasının şeklidir).

☑ **(b) LİNK'TEN TÜRET.** Research create/revise, linkli market revizyonunun
  `instrument_id`'sini `instrument_mapping_ref`'e kopyalar. **Ölçülmüş bedeli:**
  `MarketDatasetRevision.instrument_id` de **nullable**'dır ve yalnız çağıran `instrument_id`
  ya da `instrument_scope` verdiyse dolar — yani kaynak boşsa ref sessizce `None` kalır ve
  **aynı kusur bir katman öteye taşınır** (fail-open). Kopyalamayı fail-closed yapmak, bugün
  scope'suz kurulmuş market revizyonlarına bağlı research kayıtlarını **retroaktif olarak
  bloklar**.

☐ **(c) MARKET DESENİNİ AYNALA.** Research route gövdesine `instrument_scope` /
  `instrument_id` eklenir, `queries/instrument.py::resolve_scope_id` ile çözülür,
  çözülemezse 422. **Emsali sevk edilmiştir** (Ölçüm 6) ve doc 12 §430'un iki yarısını da
  karşılar. **Bedeli:** OpenAPI değişir; **frontend'e alan gerekir ve v18 mockup otoritedir**
  -> önce mockup güncellemesi (ADIM 114'ün `commission_basis` emsali).

☐ **(d) PREDICATE'İ GEVŞET.** Mapping conjunct'ı BLOCKER'dan WARNING'e iner ya da kalkar.
  **Bedeli fail-open'dır ve iki düzlemi birden etkiler:** NC-1 bunun tam ölçümüdür (üç test
  kırmızı, ikisi anti-lookahead sınırını koruyanlar). Doc 12 §8.4 rule 2'nin mapping
  conjunct'ını üründen düşürür.

☐ **Başka:** ______________________________________________

☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-31

> **Gerekçe.** Karar oturum içinde, ADIM 140'ın yedi ölçümü sunulduktan sonra verildi
> (2026-08-31). **Seçilen şıkkın kendisine sunulan metni verbatim:** *"(b) LİNK'TEN TÜRET.
> Research create/revise, linkli market revizyonunun `instrument_id`'sini
> `instrument_mapping_ref`'e kopyalar."* Rakipleri karşısındaki konumu da sunulduğu gibidir:
> `(a)` kusuru kabul eder ve `RD-09.c4`'ü kapatılamaz bırakır; `(c)` aynı sonucu **yeni bir
> API alanıyla** verir ve v18 mockup otoritesi yüzünden **önce mockup güncellemesi** ister
> (ADIM 114'ün `commission_basis` emsali); `(d)` fail-open'dır ve doc 12 §8.4 rule 2'nin
> mapping conjunct'ını üründen düşürür.
>
> **BU İMZA ŞIKKI SEÇER, ALT ÇATALINI ÇÖZMEZ — ve şıkkın kendi metni o çatalı adlandırır.**
> `MarketDatasetRevision.instrument_id` de **nullable**'dır ve yalnız çağıran `instrument_id`
> ya da `instrument_scope` verdiyse dolar. Dolayısıyla kopyalamanın davranışı ayrıca
> kararlaştırılmalıdır:
>
> * **(b1) FAIL-OPEN:** kaynak boşsa ref sessizce `None` kalır → **aynı kusur bir katman
>   öteye taşınır** (belgenin kendi ifadesi). #703'ün başlığındaki iddia bu dünyada
>   *bazı* revizyonlar için ayakta kalır.
> * **(b2) FAIL-CLOSED:** kaynak boşsa research create/revise reddedilir → bugün scope'suz
>   kurulmuş market revizyonlarına bağlı research kayıtlarını **retroaktif olarak bloklar**.
>   Üretimdeki etkilenen satır sayısı **ölçülmemiştir** (ADIM 140 §dürüst sınır).
>
> Bu ek çatal bir kapsam genişletmesi değildir: `(b)`'nin sunulan metninde **"ölçülmüş
> bedeli"** olarak zaten yazılıydı. **Aynı gün `§Karar 1a` olarak `(b2)` imzalandı** —
> uygulamanın önündeki karar kapısı kalktı.

## §Karar 1a — `(b)`'nin davranışı: kaynak boşsa ne olur?

`(b)` kopyalamayı seçer ama **kopyalanacak şey yoksa** ne olacağını söylemez, ve bu boşluk
şıkkın kendi *"ölçülmüş bedeli"* cümlesinde adlandırılmıştı. **Ölçüldü (2026-08-31):**

| Ölçüm | Sonuç |
|---|---|
| `market_dataset_revision.instrument_id` (`market_data.py:84`) | `nullable=True` |
| Create route'ta `instrument_id` (`routes/market_data.py:32`) | `str \| None = None` — **opsiyonel** |
| Create route'ta `instrument_scope` (`:36`) | `dict \| None = None` — **opsiyonel** |
| `resolved_instrument_id` (`commands/market_data.py:140`) | `= instrument_id`; **yalnız** `instrument_scope` verilirse çözülür |

⇒ **İkisini de göndermeyen SIRADAN bir istek `instrument_id = NULL` bir market revizyonu
üretir.** Yani `(b2)`'nin retroaktif bloklama riski **hipotetik değil, sevk edilmiş API ile
üretilebilir**. Risk *iddia edilmedi, yapısal olarak gösterildi.*

### Karar kutusu — **İMZALI: `(b2)` FAIL-CLOSED, DÜZ (2026-08-31)**

☐ **(b1) FAIL-OPEN.** Kaynak boşsa ref sessizce `None` kalır. **Bedeli:** aynı kusur bir
  katman öteye taşınır; #703'ün iddiası bir alt küme için ayakta kalır.

☑ **(b2) FAIL-CLOSED, DÜZ.** Kaynak boşsa research create/revise **reddedilir** — mevcut
  kayıtlar dahil, ayrım yapılmadan.

☐ **(b2-g) FAIL-CLOSED, GRANDFATHER'LI.** Kural yalnız yeni create/revise'a uygulanır;
  mevcut satırlar dokunulmaz. Retroaktif bloklama olmaz, ama **iki dünya** doğar.

☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-31

> **Gerekçe.** Ürün sahibi önce **sayıyı istedi**; sayı **alınamadı ve ikame edilmedi**
> (§Ön koşul PRE-1). Karar o ölçümün *yokluğuyla* değil, onun yerine geçen **yapısal**
> ölçümle verildi: kusurlu şekil üretilebilir, dolayısıyla `(b1)` kusuru gerçekten bir
> katman öteye taşırdı. `(b2-g)` reddedildi çünkü bugün **deploy edilmiş bir üretim yok**
> (0 tag / 0 release / 0 deploy workflow) — retroaktif bloklama boş kümeyi bloklar ve iki
> dünyanın kalıcı bakım maliyeti karşılığında hiçbir şey satın alınmaz. Grandfather'lı
> varyant **reddedilmedi, GEREKSİZ bulundu**; ilk deploy'dan sonra aynı soru yeniden
> sorulmalıdır ve PRE-1 tam olarak bunu zorlar.

### Ön koşul PRE-1 — uygulamadan önce DEĞİL, ilk deploy'da koşulur

**ADIM 124'ün `B0` emsali:** ölçülemeyen bir sayı, uygulamayı bloklamak yerine **kaydedilir
ve ölçülebilir hale geldiği anda koşulur**. Bu depoda `0 tag / 0 release / 0 deploy eden
workflow` var, yani *"üretim"* bugün gözlenebilir bir olay değildir (ADIM 124'ün birebir
ölçümü). Sorgu, tablo ve kolon adları **koddan doğrulanmıştır**, tahmin değildir:

```sql
-- (b2) altında retroaktif olarak bloklanacak research revizyonları.
-- 0 dönerse (b2) düz güvenlidir. >0 dönerse (b2-g) YENİDEN AÇILMALIDIR.
SELECT count(*) AS blocked_research_revisions
FROM research_dataset_revision r
JOIN market_dataset_revision m
  ON m.revision_id = r.linked_market_dataset_revision_id
WHERE r.linked_market_dataset_revision_id IS NOT NULL
  AND m.instrument_id IS NULL;
```

**Zorunluluk:** bu sorgu ilk gerçek deploy'da koşulur. Sonucu **`0` değilse `(b2)` imzası
yeniden değerlendirilir** — `(b2-g)` o noktada gereksiz olmaktan çıkar. Sonuç bu belgeye
yazılır; **koşulmadan `(b2)` "doğrulanmış" sayılamaz.**

## §Karar 2 — Mevcut Ready Check harness'ı ne olacak?

### Karar kutusu — **İMZALI: `A` HARNESS ÜRETİM ŞEKLİNE ÇEKİLSİN (2026-08-31)**

NC-3 ölçtü: `_seed_research_revision`'a market linki eklemek `test_readiness_research_data`'nın
**iki** testini kırar. O iki testin bugünkü yeşilliği, üretimin üretemeyeceği bir şekle dayanır.

☑ **A — HARNESS ÜRETİM ŞEKLİNE ÇEKİLSİN.** Seeder link yazar; kırılan iki test **kasıtlı**
  güncellenir. Yalnız Karar 1 (b)/(c) ile tutarlıdır — (a) altında o iki test kalıcı olarak
  `not_ready` olur ve konularını (usage-scope, warning-not-blocking) **ölçemez** hale gelir.

☐ **B — HARNESS OLDUĞU GİBİ KALSIN.** Ayrışma ADIM 140'un testiyle pinlidir ve sessizce geri
  gelemez. (Bu slice'ın **sevk ettiği** durumdur; imza onu onaylar, değiştirmez.)

☐ **C — KARAR 1 ÇÖZÜLENE KADAR ERTELE.**

☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-31

> **Gerekçe.** `A`, şıkkın kendi metnine göre **yalnız Karar 1 `(b)`/`(c)` ile tutarlıdır**
> ve Karar 1 aynı gün `(b)` olarak imzalandı — yani bu imza bir tercih değil, verilmiş bir
> kararın **zorunlu sonucudur**. `B` (harness olduğu gibi kalsın) `(b)` altında ADIM 140'ın
> ölçtüğü ayrışmayı kalıcılaştırırdı: `_seed_research_revision`
> `linked_market_dataset_revision_id`'yi **hiç set etmiyor**, dolayısıyla predicate
> `False == False` ile *coherent* diyor ve **BLOCKER hiç doğmuyor** — üretimin
> **üretemeyeceği** bir şekil. `C` (ertele) konusuz kaldı: Karar 1 çözüldü.
>
> **BEDELİ ÖLÇÜLDÜ, TAHMİN EDİLMEDİ.** NC-3 (ADIM 140, gerçek Postgres, izole DB):
> seeder'a market linki eklemek `test_readiness_research_data`'nın **iki** testini kırar.
> O iki testin bugünkü yeşilliği üretimin üretemeyeceği bir şekle dayanıyor, yani kırılma
> bir regresyon değil **düzeltmenin kendisidir**; iki test **kasıtlı** güncellenecek ve bu
> imza o güncellemeye yetki verir. Sessizce yapılmaması için ADIM 140 kapsam dışı bırakıp
> ayrı kutuya açmıştı — kutu şimdi dolduruldu.
>
> **BU İMZA KOD DEĞİLDİR.** Harness bu PR'da **değiştirilmedi**; `backend/` içinde sıfır
> satır. Uygulama, Karar 1 `(b)` + Karar 1a `(b2)` ile **aynı slice'ta** yapılmalıdır —
> ayrı inerlerse iki testin arada hangi dünyayı ölçtüğü tanımsız kalır.

## §Karar 3 — `RD-09.c4` bu karara bağlanıyor mu?

### Karar kutusu — **İMZALI: `A` EVET, BAĞLIDIR (2026-08-31)**

`RD-09.c4` (funding-enabled bir RUN üzerinden research revizyon değişmezliği) bugün ancak
`instrument_mapping_ref` **elle** set edilerek kurulabilir — ADIM 138'in kör noktasının aynısı.

☑ **A — EVET, bağlıdır.** Karar 1 (b)/(c) inene kadar `RD-09.c4` `partial` kalır; kabul
  borcu defterine **dokunulmaz**.

☐ **B — HAYIR.** `RD-09.c4` elle set edilmiş bir ref üzerinde kapatılabilir sayılır.
  **Bedeli:** kriter, üretimin üretemeyeceği bir dünyada `covered` işaretlenir.

☐ **C — ŞİMDİ ÇÖZME, ADIYLA DEVRET.**

☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-31

> **Gerekçe.** `B` reddedildi ve gerekçesi şıkkın kendi bedel cümlesinde yazılıydı:
> `RD-09.c4`'ü **elle set edilmiş** bir ref üzerinde `covered` işaretlemek, kriteri
> **üretimin üretemeyeceği bir dünyada** kapatmak olurdu — ADIM 138'in kör noktasının
> ve ADIM 140'ın *"bir fixture'ın YAPMADIĞI şey de bir iddiadır"* dersinin birebir tekrarı.
> Bu depo o şekli iki kez ölçtü; üçüncüsüne imza atılmadı.
>
> `C` (adıyla devret) konusuz kaldı: Karar 1, 1a ve 2 aynı gün imzalandı, devredilecek
> açık bir soru yok.
>
> **SONUCU BİR KISITTIR, BİR İŞ DEĞİL:** `RD-09.c4` **`partial` KALIR** ve
> `docs/audit/acceptance_coverage_baseline.json` ile borç defterine **DOKUNULMAZ** —
> hiçbir tavan oynamaz. Kriter ancak `(b)` + `(b2)` uygulaması indikten **sonra**,
> üretimin gerçekten ürettiği bir ref üzerinde kapatılabilir. Ratchet yalnız aşağı iner;
> bu imza onu **yukarı oynatmaz**.

---

## Bu belgenin kapsamadıkları (dürüst sınır)

- **Kusur DÜZELTİLMEDİ.** ADIM 140 yalnız ikinci düzlemin testini sevk eder; `backend/src`'te
  **sıfır satır** değişti. NC yamaları uygulandı, ölçüldü ve **bayt bayt geri alındı**.
- **#703 KAPATILMADI** ve durumu değiştirilmedi — insan kararı. **§Karar 1 2026-08-31'de
  `(b)` olarak, **§Karar 1a `(b2)` FAIL-CLOSED DÜZ olarak İMZALANDI**, ama kusur **hâlâ
  düzeltilmedi** — `backend/src`'te sıfır satır. Karar kapısı kalktı, uygulama başlayabilir.
  **Ön koşul PRE-1** (üretim sayımı) ilk deploy'da koşulmayı bekler. §Karar 2 ve §Karar 3
  **İMZASIZ**. **§Karar 2 2026-08-31'de `A` olarak İMZALANDI** — harness üretim şekline
  çekilecek ve `test_readiness_research_data`'nın iki testi **kasıtlı** güncellenecek;
  bu PR'da **yapılmadı**, uygulama Karar 1 ile aynı slice'a aittir. **§Karar 3 2026-08-31'de `A` olarak İMZALANDI** — `RD-09.c4`
  `partial` KALIR, kabul borcu defterine ve tavanlara **dokunulmaz**; kriter ancak `(b)` +
  `(b2)` uygulaması indikten sonra, üretimin ürettiği bir ref üzerinde kapatılabilir.
  **#703'ün DÖRT kararının DÖRDÜ de imzalı.**
- **UYGULANDI — ADIM 149 (2026-08-31).** Yukarıdaki *"kusur hâlâ DÜZELTİLMEDİ"* cümlesi
  bu belgenin kendi tabanında doğruydu ve artık **tarihseldir**: `(b)` + `(b2)` iki yazma
  yüzeyinde de sevk edildi (`commands/research_data.py::_instrument_mapping_ref_for`),
  §Karar 2 = `A` uyarınca harness üretim şekline çekildi ve öncülü ölen testler **kasıtlı**
  yeniden yazıldı. Ölçülen sonuç imzanın öngördüğünden **geniş**: #703'ün İKİNCİ kapısı da
  kapandı — `resolve_funding_schedule` app-created bir revizyonu artık hiç reddetmiyor, yani
  ADIM 138'in *"başlıktaki iddia ikinci kapı yüzünden ayakta"* dürüst sınırı düştü.
  **Değişmeyenler:** **§Ön koşul PRE-1 KOŞULMADI** (bu depoda hâlâ 0 tag / 0 release /
  0 deploy eden workflow → *"üretim"* gözlenebilir bir olay değil) ⇒ `(b2)` **doğrulanmış
  sayılamaz**, sorgu ilk gerçek deploy'da koşulur ve `0` değilse `(b2-g)` yeniden açılır ·
  §Karar 3 = `A` uyarınca `RD-09.c4` **`partial` KALDI**, kabul defterine ve tavanlara
  **dokunulmadı** · **#703 KAPATILMADI** (insan kararı) · frontend'e dokunulmadı.
- **Frontend'e dokunulmadı**, frontend kapıları koşulmadı.
- **Üretimde kaç research revizyonunun etkilendiği SAYILMADI** — bu bir üretim DB sorgusudur
  (`G15` §Ölçüm 3 ve #854 ile aynı sınır). Karar bu sayı olmadan verilebilir: Ölçüm 2 kusurun
  **her** app-created kökte doğduğunu kod yolundan gösterir, bir örnekleme değil.
- **(b)'nin fail-open riski türetildi, deneyle ölçülmedi** — `MarketDatasetRevision.instrument_id`
  nullable'dır ve yazıcısı koşulludur; kaç üretim satırının boş olduğu sayılmadı.
- **`quality_rules._check_instrument_mapping` (WARNING düzlemi) bu belgenin konusu değildir.**
  Aynı asimetriyi bildirir ama approval'ı bloklamaz; seçilen karar onu da etkileyecektir.
