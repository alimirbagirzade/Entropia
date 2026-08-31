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
> Uygulama, `(b1)` / `(b2)` imzalanmadan **başlatılamaz**. Bu ek çatal bir kapsam genişletmesi
> değildir: `(b)`'nin sunulan metninde **"ölçülmüş bedeli"** olarak zaten yazılıydı.

## §Karar 2 — Mevcut Ready Check harness'ı ne olacak?

NC-3 ölçtü: `_seed_research_revision`'a market linki eklemek `test_readiness_research_data`'nın
**iki** testini kırar. O iki testin bugünkü yeşilliği, üretimin üretemeyeceği bir şekle dayanır.

☐ **A — HARNESS ÜRETİM ŞEKLİNE ÇEKİLSİN.** Seeder link yazar; kırılan iki test **kasıtlı**
  güncellenir. Yalnız Karar 1 (b)/(c) ile tutarlıdır — (a) altında o iki test kalıcı olarak
  `not_ready` olur ve konularını (usage-scope, warning-not-blocking) **ölçemez** hale gelir.

☐ **B — HARNESS OLDUĞU GİBİ KALSIN.** Ayrışma ADIM 140'un testiyle pinlidir ve sessizce geri
  gelemez. (Bu slice'ın **sevk ettiği** durumdur; imza onu onaylar, değiştirmez.)

☐ **C — KARAR 1 ÇÖZÜLENE KADAR ERTELE.**

## §Karar 3 — `RD-09.c4` bu karara bağlanıyor mu?

`RD-09.c4` (funding-enabled bir RUN üzerinden research revizyon değişmezliği) bugün ancak
`instrument_mapping_ref` **elle** set edilerek kurulabilir — ADIM 138'in kör noktasının aynısı.

☐ **A — EVET, bağlıdır.** Karar 1 (b)/(c) inene kadar `RD-09.c4` `partial` kalır; kabul
  borcu defterine **dokunulmaz**.

☐ **B — HAYIR.** `RD-09.c4` elle set edilmiş bir ref üzerinde kapatılabilir sayılır.
  **Bedeli:** kriter, üretimin üretemeyeceği bir dünyada `covered` işaretlenir.

☐ **C — ŞİMDİ ÇÖZME, ADIYLA DEVRET.**

---

## Bu belgenin kapsamadıkları (dürüst sınır)

- **Kusur DÜZELTİLMEDİ.** ADIM 140 yalnız ikinci düzlemin testini sevk eder; `backend/src`'te
  **sıfır satır** değişti. NC yamaları uygulandı, ölçüldü ve **bayt bayt geri alındı**.
- **#703 KAPATILMADI** ve durumu değiştirilmedi — insan kararı. **§Karar 1 2026-08-31'de
  `(b)` olarak İMZALANDI**, ama kusur **hâlâ düzeltilmedi**: imza şıkkı seçer, `(b1)`/`(b2)`
  alt çatalı açık kalır ve uygulama ondan önce başlayamaz. §Karar 2 ve §Karar 3 **İMZASIZ**.
- **Frontend'e dokunulmadı**, frontend kapıları koşulmadı.
- **Üretimde kaç research revizyonunun etkilendiği SAYILMADI** — bu bir üretim DB sorgusudur
  (`G15` §Ölçüm 3 ve #854 ile aynı sınır). Karar bu sayı olmadan verilebilir: Ölçüm 2 kusurun
  **her** app-created kökte doğduğunu kod yolundan gösterir, bir örnekleme değil.
- **(b)'nin fail-open riski türetildi, deneyle ölçülmedi** — `MarketDatasetRevision.instrument_id`
  nullable'dır ve yazıcısı koşulludur; kaç üretim satırının boş olduğu sayılmadı.
- **`quality_rules._check_instrument_mapping` (WARNING düzlemi) bu belgenin konusu değildir.**
  Aynı asimetriyi bildirir ama approval'ı bloklamaz; seçilen karar onu da etkileyecektir.
