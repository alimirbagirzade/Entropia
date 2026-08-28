<!-- doc-status: current -->
# OD-2(a) mark yolunun **üretime bağlanması**: bağlansın mı, nereye, ve hangi bedelle

> **BU BELGEDE HİÇBİR ÜRÜN SEMANTİĞİ KARARA BAĞLANMAMIŞTIR.** Yazarın rolü **ölçüm ve
> hazırlık**tır. §Karar'ın imza bloklarını yalnız ürün sahibi / maintainer doldurur.
> `closure_g10_containment_lift_gate2_2026-08-26.md`, `closure_g14_net_conflict_policy_2026-08-25.md`
> ve `closure_g8_dst_fold_gap_2026-08-25.md` ile aynı disiplin.

- **Tarih:** 2026-08-28
- **Base:** `origin/main` @ `c57ea644` (`feat(stage-132): C9 — containment lift; SHARED_ALLOCATION_STATUS = active_v1 (#869)`).
  Ölçüm sırasında açık PR **yoktu** (`gh pr list --state open` boş) — bu bir anlık görüntüdür,
  garanti değil (ADIM 100).
- **İzleme:** GitHub issue **YOK**. Bu kapı ne ADR-0002 §16'da ne bir issue'da yaşıyor; ADIM 132
  onu bir **dürüst sınır** olarak kaydetti ve bu belge o sınıra imzalanacak bir yer açar.
- **Bloklar:** hiçbir şeyi bloklamıyor. `C9` **indi**; RC verdict'i **A-08 (#514)** yüzünden
  BLOCKED ve bu karar o hatta **dokunmaz**.
- **Neden şimdi:** ADIM 132 OD-2(a)'yı **sevk etti** ama **ulaşılabilir bir yola bağlamadı**.
  Bağlamak sevk edilen Result içeriğini değiştirir, yani bir **ürün kararıdır**; imzasız ürün
  kararı indirilmez.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — Ne sevk edildi, ne **ulaşılabilir**: ikisi aynı şey değil

Prompt'un öncülü (*"mark yolunun üretimde sıfır çağıranı var"*) **yeniden ölçüldü ve
DOĞRULANDI, ama olduğundan daha dar**. İkisini ayırmak gerekiyor:

**FONKSİYON düzeyinde — çağıran YOK (öncül doğru):**

| Sembol | `backend/src`'te çağıran |
|---|---|
| `execution/attribution.py::attribute` | **0** |
| `PortfolioLedger.valuation` | **1**, o da yalnız `attribute` içinden |
| `MarkPrice` (construction) | **0** — yalnız `tests/unit/test_backtest_portfolio_ledger.py` ve `…_attribution.py` kuruyor |

**MODÜL düzeyinde — öncül BAYAT, ve üç docstring onunla birlikte bayat.** İçe aktarma zinciri
üretime **ulaşıyor**:

```
application/jobs/backtest_engine.py   (dramatiq worker — üretim)
  -> execution/portfolio_projection.py
       -> execution/provenance.py
            -> execution/attribution.py
```

Bu yüzden aşağıdaki üç cümle bugün **karşı-olgusaldır** (ölçüldü, **düzeltilmedi** — bu belge
docs-only'dir ve ürün koduna dokunmaz):

- `execution/attribution.py` §1: *"CONTAINED — nothing in production imports this module."*
- `execution/provenance.py` §1: *"ADIM 19. CONTAINED — nothing in production imports this module…"*
- `execution/portfolio_ledger.py` §Design notes: *"**Nothing in production imports this module.**"*
  (`portfolio_engine.py`, `participant.py`, `provenance.py`, `arbitration.py`, `attribution.py` — **beş** importer.)

Ayrıca iki *"not yet built"* iddiası da bayat: `portfolio_engine.py` §HONEST BOUNDARY md. 3 ve
`execution/clock.py::ItemTickView` docstring'i, ikisi de OD-2 için *"and not yet built"* diyor;
ADIM 132 onu **inşa etti**.

> **Bu bir kusur listesi değil, kapsam ölçümüdür.** Bunları düzeltmek ayrı ve ucuz bir docs
> slice'ıdır; **bu kararın parçası değildir** ve burada kararlaştırılmıyor.

---

## Ölçüm 2 — ASIL BULGU: manifest bugün **fiilen olmayan** bir şeyi ilan ediyor

`execution/provenance.py::PortfolioManifest.policy_versions` şunları yayımlıyor:

```
mark_staleness_policy   = "carry_forward_bounded_v1"
mark_staleness_status   = "built"
mark_staleness_tracking = "ADR 0002 §13 OD-2"
```

ve `policy_versions()` **`execution_content()`'in İÇİNDE**, yani `identity` hash'ine giriyor.

Bağımsız olarak, `manifest.py::_portfolio_policy()` aynı `mark_staleness_policy` literalini
**her** run'ın `execution_content`'ine koyuyor — ve o modülün kendi yorumu bunu açıkça söylüyor:

> *"These are engine-wide, so an independent single-Strategy run carries them too."*

**Ölçülen çelişki.** `policy_versions()`'ın kendi docstring'i şu:

> *"Every knob whose value changes what a replay produces."*

Bugün `MARK_STALE_AFTER_MS`'i değiştirmek **hiçbir replay'in ürettiği hiçbir sayıyı
değiştirmez** — çünkü hiçbir şey mark etmiyor. Değiştirdiği tek şey `execution_key`
**namespace'idir**. Yani alan, kendisi için **yanlış olan** bir docstring'in altında duruyor;
`status: "built"` **kodun** doğru tarifi, **koşunun** değil.

**Bu, ADIM 132'nin kendi bulduğu kusurun aynı şeklidir** — `available: true` ile *"not available
in this build"*'in yan yana yayımlanması. Orada metin bayrağı takip etmiyordu; burada durum
etiketi **çalışan bir yolu** takip etmiyor.

**KARŞI-ARGÜMAN, ve zayıf değil.** `"built"` yalan değildir: mekanizma gerçekten inşa edildi,
test edildi ve `MARK_STALENESS_POLICY` bir **politika sürümüdür**, bir çalıştırma raporu değil.
`manifest.py`'nin yorumu fazladan-kaydırmayı **bilerek** ve fail-closed olarak seçiyor
(*"over-shifting costs a re-run, under-shifting returns a stale Result, and only one of those
two is silent"*). Seçenek (a) bu okumaya dayanır.

---

## Ölçüm 3 — Seam **zaten var ve adı `PV`**; girdilerin üçü de elde

`portfolio_engine.py::PHASE_ORDER` = `("P1", "P3", "PV", "P4", "P5", "P6b", "P7", "P9", "P10")`.
`PV` = *"publish exactly one PortfolioSnapshot(t), ledger FROZEN"*. Bugün `_run_tick` orada
**yalnız** `ledger.publish_snapshot(t_ms)` çağırıyor. `ledger.valuation(t_ms, marks)` onun
**kardeşidir** ve aynı noktada çağrılabilir:

- **Saf.** Gövdesi `self`'e hiçbir atama yapmaz; `_frozen_at`'e dokunmaz → **donmuş pencerede
  çağrılması yasal**, freeze disiplinini bozmaz.
- **Girdiler zaten hesaplanıyor.** `MarkPrice`'ın üç alanının üçü de `tick.views`'tan geliyor:
  `intents.py::_price_for(view)` → `(price, authority)`, `ItemTickView.staleness_ms` → yaş.
  **Yeni bir finansal hesap gerekmiyor** — mevcut değerler bugün atılıyor.

**Tek pürüz, ölçüldü:** `_price_for` **private** ve `intents.__all__`'da **yok**. Bağlama ya onu
public yapmalı (aynı modül, allowlist etkisi yok) ya da yeniden yazmalı — ikincisi ADIM 126'nın
kendi dersini tekrarlar (*"iki yazım drift üretir"*).

---

## Ölçüm 4 — Döngüden SONRA bağlamak **yapısal olarak boştur** (P10)

Bu, seçenek tasarımını belirleyen ölçümdür. `_phase_10_finalize` hâlâ açık olan her pozisyonu
`ledger.close_position(item_id)` ile **kapatır**. Üretim katılımcısıyla (`_EngineParticipant`)
gerçek bir koşu sürüldü (`test_oracle_engine_participant.py` fixture'ı; `_HELD_TO_THE_END`
item'ı **bilerek** sona kadar açık kalır):

```
=== TERMINAL STATE (after P10) ===
ledger.positions after run: {}
open count: 0
```

**Sonuç:** `project_portfolio_run` çağrı yerinde ya da worker'da terminal bir `attribute()` /
`valuation()` çağırmak **her zaman** sıfır açık pozisyon görür → `unmarked_items = ()`,
`stale_refused_items = ()`, `unrealized_pnl = 0`. Yani *"ucuz olan"* bağlama noktası, OD-2'nin
tam olarak **hiçbir şeyini** ölçmez.

**Bağlama, bağlanacaksa, tick başına ve `PV`'de olmak zorundadır.** Bu bir tercih değil, bir kısıt.

---

## Ölçüm 5 — `attribute()`, OD-2(a)'nın **kendi sayacını düşürüyor**

ADR §13.1 OD-2(a) şunu ister: *"carry the last closed bar's close forward with a declared
`stale_after` bound **and a diagnostic counter**"*.

O sayaç `PortfolioValuation.stale_refused_items`'tır ve `ledger.valuation()` onu üretir. Ama
`PortfolioAttribution`'ın alanları şunlar: `t_ms, pool_initial, equity, realized_total,
unrealized_total, marked_equity, rows, unmarked_items, realized_residual, marked_residual,
policy_version, method, counterfactual_status` — **`stale_refused_items` YOK.**

`attribute()` yalnız `unmarked_items`'ı taşır, ve `portfolio_ledger.py`'nin kendi docstring'i bu
ikisinin **aynı şey olmadığını** yazıyor: stale-refused, unmarked'ın **ALT KÜMESİDİR**; bir item
mark teklif edilmediği, `unavailable` olduğu veya fiyatı pozitif olmadığı için de unmarked
olabilir → *"Reading the count off `unmarked_items` would therefore over-report staleness."*

**Sonuç:** hangi seçenek seçilirse seçilsin, taşıyıcı **`ledger.valuation()`** olmalıdır.
`attribute()` üzerinden bağlamak OD-2(a)'yı **sayacı eksik** sevk eder.

---

## Ölçüm 6 — Bound, kanonik timeframe merdiveninde **9'un 5'ini sıfırlıyor**

`MARK_STALE_AFTER_MS = 900_000` (900 sn = 15 dk). `CANONICAL_TIMEFRAMES` üzerinde ölçüldü
(sınır **katı**: `staleness_ms > bound`; tam 900 000'de mark **kullanılabilir**):

| tf | bar (ms) | 1 bar taşıma kullanılabilir mi? | taşınabilen azami bar |
|---|---:|:---:|---:|
| 1m | 60 000 | evet | 15 |
| 3m | 180 000 | evet | 5 |
| 5m | 300 000 | evet | 3 |
| 15m | 900 000 | evet | 1 |
| **30m** | 1 800 000 | **hayır** | **0** |
| **1h** | 3 600 000 | **hayır** | **0** |
| **2h** | 7 200 000 | **hayır** | **0** |
| **4h** | 14 400 000 | **hayır** | **0** |
| **1D** | 86 400 000 | **hayır** | **0** |

Ve paylaşımlı saatte taşıma tam olarak **kaba** timeframe'li item için gerekir: 1h item'la aynı
kompozisyondaki bir 1D item, 24 tick'in 23'ünde taze bar taşımaz. Yani bound **en çok ihtiyaç
duyulan yerde** ısırıyor.

**Sonuç, tarafsız yazılmış:** 30m ve üstü için OD-2(a) davranışsal olarak, ürün sahibinin
2026-08-28'de **reddettiği** fail-closed sıfır bound ile **aynıdır**. Bu, bound'un yanlış olduğunu
söylemez — 900 sn ödünç alındığı yerde (Master Ref §Stale record, **research** kaydı) doğru
olabilir. Söylediği şu: **bağlama, ödünç alınmış sayının ilk kez gözlemlenebilir olduğu andır.**

> **BU BELGE BOUND'U DEĞİŞTİRMEZ VE DEĞİŞTİRİLMESİNİ ÖNERMEZ.** Değiştirmek yeni bir
> `carry_forward_bounded_vN` **ve** ikinci bir `ENGINE_VERSION` bump'ı gerektirir; o **ayrı bir
> karardır** ve §Karar 2'de ayrı bir kutu olarak açılmıştır.

---

## Ölçüm 7 — Mühendislik kısıtı: **imzalı importer allowlist'i** nereye yazılabileceğini belirliyor

`test_oracle_portfolio_containment_gate.py::_AUTHORISED_PHASE_LOOP_IMPORTERS`, `execution/`
dışındaki üretim modüllerini **isimle** sayar: `domain/backtest/participant.py` ve
`domain/backtest/portfolio_engine.py`. Liste **imzalı**
(`closure_participant_importer_allowlist_2026-08-18.md`, Seçenek A).

| Bağlama yeri | Allowlist etkisi | Ölçüm |
|---|---|---|
| `portfolio_engine.py` `PV` | **DEĞİŞMEZ** | Modül zaten allowlist'te **ve** zaten `execution.portfolio_ledger`'dan import ediyor; `MarkPrice` aynı modülden gelir. |
| `execution/portfolio_projection.py` | **DEĞİŞMEZ** | `execution/` **içinde** → tarama onu zaten muaf tutar. |
| `application/jobs/backtest_engine.py` (worker) | ❌ **İMZALI LİSTEYİ GENİŞLETİR** | `C4`'te birebir bu hamle denendi ve **üç dosyada beş assertion** kırmızı verdi; reddedildi (GH #731). |

**Sonuç:** uygulanabilir bağlama noktaları `portfolio_engine.py::_run_tick` (`PV`) ve
`execution/portfolio_projection.py`'dir. Worker'a yazmak **yeni bir imza** gerektirir.

---

## Ölçüm 8 — `E(t)`'ye dokunulmuyor: doğrulandı

`portfolio_ledger.py` modül docstring'i: ***"`E(t)` is realized-only, so a mark never touches
it."*** — ve `valuation()` gövdesi bunu **yapısal olarak** taşıyor: `self`'e hiçbir atama yok,
yalnız yeni bir `PortfolioValuation` döner. `E(t)` kimliği (`P0 + realized − fees − funding −
other`) her booking'de artımlı quantize ile korunuyor ve bir mark o zincire hiç girmiyor.

**Bağlama yalnız RAPOR eder.** Prompt'un md. 2'si doğrulanmıştır. ADR §5'in prozası bu eksende
**yeniden yorumlanmadı** — otorite modül docstring'idir ve bu belge onu değiştirmiyor.

---

## Ölçüm 9 — Seçenekler ve **ölçülmüş** bedelleri

Dört sayı her seçenek için ayrı ayrı ölçüldü.

**Golden tabanı — ölçülen kritik olgu:** `tests/unit/engine_golden_digests.json` **50** digest
taşıyor ve dosyada `project_portfolio_run` / `iter_portfolio` / `run_portfolio` **0 kez** geçiyor.
Dokuz `portfolio.*` senaryosunun hepsi `combine_item_runs` (sıralı fold) ya da allocation
kurallarıdır. **Yani unified faz döngüsünün çıktısını bugün hiçbir golden digest kapsamıyor.**

**OpenAPI — ölçüldü, hepsi 0 kez:** `mark_staleness`, `stale_refused`, `unmarked_items`,
`execution_key`, `engine_version`, `portfolio_policy` → `docs/openapi.json`'da **sıfır**.

**Migration — ölçüldü:** `DiagnosticArtifact.content` ve `ResultManifestSnapshot.manifest`
**JSONB**. Yeni tablo/kolon gerekmez.

| | **(a) hiç bağlama** | **(b) yalnız diagnostics** | **(c1) provenance, `execution_content` DIŞINDA** | **(c2) provenance, `execution_content` İÇİNDE** |
|---|---|---|---|---|
| Bağlama noktası | — | `PV` → `PortfolioTick` → projeksiyon `diagnostics` | (b) + provenance bölümünün `as_dict()` yarısı | (b) + `execution_content()` |
| Golden digest hareketi | **0** | **0** (ölçüldü: unified yol golden'da yok) | **0** | **≥1** — `contract.execution_key` **kesin** kayar |
| `ENGINE_VERSION` bump | **hayır** | **AÇIK ALT SORU** (§Karar 3) | **AÇIK ALT SORU** (§Karar 3) | **ZORUNLU** (deponun kendi kuralı) |
| OpenAPI | değişmez | değişmez | değişmez | değişmez |
| Migration | yok | **yok** (JSONB) | **yok** (JSONB) | **yok** (JSONB) |
| Allowlist | — | değişmez | değişmez | değişmez |
| `_price_for` public'e | gerekmez | gerekir | gerekir | gerekir |

**(c2) hakkında ölçülmüş bir itiraz, karar değil.** `execution_content` bir **kimliktir** ve
kimlik koşunun **girdilerinin** fonksiyonu olmalıdır. Mark ÇIKTISI (kaç item unmarked, hangileri
stale-refused) koşunun **sonucudur**; onu `execution_content`'e koymak kimliği kendi çıktısına
bağlar. `manifest.py`'nin `COMMISSION_MODEL` gerekçesi aynı testi uyguluyor (*"does the field buy
DISCRIMINATION nothing else already provides?"*) ve hayır cevabında alanı dışarıda bırakıyor.
**Bu bir tavsiye değildir; imzacının bilmesi gereken bir ölçümdür.**

---

## Karar

> Aşağıdaki kutuları **yalnız ürün sahibi / maintainer** doldurur. Ajan dolduramaz
> (`G10`/`G11`/`G12`/`G14` emsali).

### Karar 1 — OD-2 mark yolu üretime bağlansın mı, nereye?

☐ **(a) HİÇ BAĞLAMA — statüko.** `attribute()`/`valuation()`/`MarkPrice` test-kapsamlı ölü kod
olarak kalır. Manifest `mark_staleness_status: "built"` demeye devam eder.
*Bedeli:* Ölçüm 2'nin sözleşme asimetrisi **kalıcı olur** ve bir sonraki okuyucu `"built"`i
*"bu koşuda mark edildi"* diye okuyabilir.
*Lehine:* ADR §13.1 ve R-5 **yalnız manifest'e versiyonlu politika olarak KAYDETMEYİ** ister;
ön koşul 17'nin literali de *"OD-2 mark policy **flip**"*tir. ADIM 132 ikisini de **harfi harfine**
karşıladı — yani (a), atlanmış bir borç değil, **yazılı sözleşmenin karşılandığı nokta**dır.

☐ **(b) YALNIZ DIAGNOSTICS.** `PV`'de `ledger.valuation(t_ms, marks)` çağrılır; per-run özet
(`unmarked_items`, **`stale_refused_items`**, marked/unmarked tick sayısı) projeksiyonun
`diagnostics`'ine iner. Reproduction identity'ye **hiç** dokunulmaz.

☐ **(c1) PROVENANCE, `execution_content` DIŞINDA.** (b) + aynı özet portfolio provenance
bölümünün `identity`-dışı yarısına yazılır → Result manifest snapshot'ında kalıcı, `identity`
kıpırdamaz.

☐ **(c2) PROVENANCE, `execution_content` İÇİNDE.** (c1) + `identity`/`execution_key` kayar.
**`ENGINE_VERSION` bump'ı ve golden yeniden üretimi AYNI commit'te zorunludur.**

☐ **Başka:** ______________________________________________

**Seçim:** ____________   **İmza:** ____________   **Tarih:** ____________

**Serbest metinli gerekçe (opsiyonel):**
> ______________________________________________

---

### Karar 2 — `MARK_STALE_AFTER_MS` = 900 sn, Ölçüm 6'nın ışığında

> Karar 1'de (a) seçilirse bu soru **açık kalabilir** — bağlanmayan bir bound gözlemlenemez.

☐ **A — DOKUNMA.** 900 sn kalır; 30m ve üstünde taşıma fiilen hiç olmaz ve bu **kabul edilir**
(fail-closed; bir mark'ı uydurmaktansa reddetmek).
☐ **B — TIMEFRAME'E GÖRELİ BİR BOUND'A GEÇ** (ör. *"N bar"*). **Yeni `carry_forward_bounded_v2`
+ ikinci `ENGINE_VERSION` bump'ı gerektirir.**
☐ **C — ŞİMDİ ÇÖZME, ADIYLA DEVRET.** (ADIM 129'un `C` kararının biçimi.)

**Seçim:** ____________   **İmza:** ____________   **Tarih:** ____________

---

### Karar 3 — (b) veya (c1) seçilirse: diagnostics-only bir değişiklik `ENGINE_VERSION` bump'ı gerektirir mi?

> `execution_key` **manifest'ten** türer, `EngineOutput`'tan değil. (b)/(c1) Result'ın
> `diagnostics` içeriğini değiştirir ama reproduction identity'sini değiştirmez. Depo kuralı
> (*"an intentional output change requires an ENGINE_VERSION bump in the same commit"*) `diagnostics`
> için **hiç yorumlanmadı** — golden taban unified yolu kapsamadığı için soru bugüne kadar hiç
> sorulmadı (Ölçüm 9).

☐ **A — Bump GEREKMEZ** (identity değişmiyor; `diagnostics` bir rapordur).
☐ **B — Bump GEREKİR** (sevk edilen Result içeriği değişiyor).

**Seçim:** ____________   **İmza:** ____________   **Tarih:** ____________

---

## Bu belgenin kapsamadıkları (dürüst sınır)

1. **Hiçbir ürün kodu değişmedi.** `backend/src`, `backend/tests` ve `frontend/src`'te
   **sıfır satır**. `ENGINE_VERSION`, golden dosyası, `capability.py`, `MARK_STALE_AFTER_MS`,
   `SHARED_ALLOCATION_STATUS` **el değmedi**.
2. **Hiçbir imza kutusu doldurulmadı.** Üç kararın üçü de **AÇIK**.
3. **"OD-2 üretimde akıyor" DENMİYOR.** Bugün akmıyor; bu belge onun akıp akmayacağını sorar.
4. **Ölçüm 1'in üç bayat docstring'i ve iki *"not yet built"* iddiası DÜZELTİLMEDİ.** Ölçüldüler
   ve burada kayıtlılar; düzeltmeleri ayrı bir docs slice'ıdır.
5. **ADR-0002 §13.1'in OD-2 satırı EL DEĞMEDİ.** *"Not built. `run_portfolio` marks nothing"*
   diyor; ikinci yarısı **bugün hâlâ doğru**, birincisi kısmen bayat. Sevk edilmiş bir ADR karar
   tablosunu yeniden yazmak **adjudication**'dır (ADIM 42/128) ve bu belgenin işi değil.
6. **A-08 (#514) AYRI HATTIR, el değmedi; RC verdict BLOCKED kalır.** Karar 1 hangi şıkla
   imzalanırsa imzalansın bu değişmez.
7. **Suite koşulmadı.** Ürün/test kodunda sıfır satır olduğu için geçen test sayısı ve coverage
   **iddia edilmiyor**; otorite **CI**'dır. Bu belgedeki her sayı ya `grep`/dosya okumasıyla ya da
   `backend/.venv` içinde koşan salt-okur bir probe ile üretildi; probe'lar scratchpad'de kaldı,
   **depoya girmedi**.
8. **Frontend kapıları koşulmadı** (frontend'de sıfır satır).
