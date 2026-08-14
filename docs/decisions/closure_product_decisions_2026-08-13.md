# Closure product decisions — 2026-08-13

> **Bu belge KARAR BEKLİYOR. İmzalanmadan P-E1 ve P-E3 BAŞLATILAMAZ.**

- **Tarih:** 2026-08-13
- **Base:** `origin/main` @ `0d8bf8f7134d86d77a7eee10023dadd3d80aab0d`
  (`docs: name the PR behind every landed slice heading (#702)`)
- **Branch:** `docs/closure-product-decisions`
- **Kapsam:** GH #552 (commission modeli) · GH #558 (research bundle shape) · GH #559 (DST)
- **Yazarın rolü:** hazırlık. **Bu belgede hiçbir karar verilmemiştir**; seçenek elenmemiştir.
  "Önerilen seçenek" başlıkları bir **öneridir**, karar değildir.

## Taban notu (dürüstlük)

Paketin beklediği taban `31ed27dfc1f3bf7448b0e03c7c732d22d8b758c4` idi; ölçülen taban bir
commit ileride: `0d8bf8f` (#702). Aradaki tek commit **yalnız `docs/`** dosyalarına dokunur
(slice başlıklarına PR numarası ekler) — `backend/src`, `frontend/src`, migration ve test
ağacına dokunmaz. Bu belgedeki her kod alıntısı ve her ölçüm `0d8bf8f` üzerinde yeniden
okunmuştur; §0 tipi bir doğrulama tablosu bu paketle gelmediği için yeniden ölçülecek satır
yoktur.

## Bu belgede kanıt olarak kullanılmayan şeyler

- **E1 / E3 / E4 / E5 slice tanımları repoda YOKTUR.** `grep -rl "P-E1\|E4/E5" docs/` sıfır
  sonuç verir — tıpkı `CLAUDE.md`'nin P1..P13 için yazdığı gibi ("**P1..P13 tanımı REPODA
  DEĞİL** — yalnız sohbet transkriptinde"). Bu yüzden aşağıda "E1'i bloklar" gibi bir hüküm
  **slice adına değil**, adlandırılabilir bir kod/kanon yüzeyine bağlanmıştır: Karar 1 →
  `booking.py::close_position` + `ENGINE_VERSION`; Karar 2 → `_seal_bundle` + `bundle_hash`;
  Karar 3 → `execution/clock.py` merged axis + `funding.py::build_funding_schedule`.
- **Issue durumu.** Üç issue de `state=open`, `state_reason=reopened` (2026-08-12/13'te
  ölçüldü). Açıklık bir kanıt değil, yalnızca bir işarettir.

---

## Karar 1 — Commission modeli (GH #552)

### Canonical ne diyor

Kanon **tek bir yerde bile "bir partial lot şu kadar komisyon öder" demiyor.** Söylediği dört
şey var ve üçü birbirini tam örtmüyor:

| # | Kaynak | Literal | Ne söyler |
|---|---|---|---|
| K1 | Master Ref, Modül 6 §8 (`:7513`) | *"Rounding policy, instrument quantity incrementi ve **komisyon dağılımı engine manifestinde açık olmalıdır**."* | Partial exit'te komisyon **dağılımının** manifestte **açıklanmasını** ŞART koşar; dağılımın kendisini seçmez. |
| K2 | Master Ref, Modül 6 §6.2 (`:7425`) | Commission: *"Sayısal giriş. Birim/para formatı konfigürasyonla açık olmalı; boşsa policy default değil, **manifestte resolved default** taşınmalıdır."* | Commission bir **sayısal giriş**tir ve birimi konfigürasyonla açık olmalıdır. Birimi seçmez. |
| K3 | Master Ref, Modül 4 §2.3 tablosu (`:3110`) | Commission rule → *"**Notional üzerinden bps bazlı** işlem komisyonu"* | Kanonun **tek somut örneği** oran bazlıdır (bps × notional), sabit tutar değil. |
| K4 | Master Ref, Modül 6 §7 madde 7 (`:7738`) | *"Legal actionlar selected execution / fill modeline göre order veya **simulated fill eventine** dönüştürülür. **Commission**, spread, slippage ve funding uygulanır."* | Maliyetler **fill event'i** başına uygulanır diye okunur — per-fill'e en yakın kanon cümlesi. |

K3 ile sevk edilen şema **çelişir**: `domain/strategy/config.py:313` →
`commission: Decimal | None = Field(default=None, description="Per-trade fee")` — sabit tutar,
oran değil. Bu çelişki bu kararın parçasıdır ve Seçenek C'de ele alınır.

### Kod şu an ne yapıyor (file:line)

`backend/src/entropia/domain/backtest/execution/booking.py:93`:

```python
commission_lot = costs.commission * 2 if is_full else costs.commission * 2 * fraction
```

Sevk edilen model **hibrittir**, üç ayrı kuralı vardır:

| Olay | Ücret | Nerede |
|---|---|---|
| İlk entry fill | **0** (açılışta alınmaz) | — kapanışta `×2`'nin içinde |
| Scale layer entry fill | `commission × 1`, fill anında | `engine.py:3129-3133` |
| Stack tranche entry fill | `commission × 1`, fill anında | `engine.py:2952-2953` |
| Partial-fill remainder | `commission × 1`, fill anında | `booking.py:221-222` |
| FULL close | `commission × 2` | `booking.py:93` |
| PARTIAL close | `commission × 2 × fraction` | `booking.py:93` |

`fraction` = `close_percentage / 100` (`engine.py:974`), **run boyunca sabit** bir config
alanıdır; `close_size` ise `pos.size × fraction` (`booking.py:86`) — yani **kalan** boyutun
yüzdesi.

### Çelişki tam olarak nerede

Üç ayrı çelişki var; issue #552 yalnız birincisini adlandırıyor.

**Ç1 — docstring kendi kodunu yanlış tarif ediyor.** `booking.py:82-83`:
*"Commission is charged proportional to the fraction so N partial lots summing to the whole
position pay exactly one round-trip."* Bir partial'ı bir FULL close izlediğinde bu tutmaz:
son kapanış `is_full` olduğu için kalan boyut ne olursa olsun **tam** bir round trip alır.
Issue'nun elle hesabı: 1 partial + 1 full = **1.4 round trip**. Deponun kendi oracle'ı bunu
pinliyor: `tests/unit/oracles/test_oracle_position_lifecycle.py:140`
`test_a_partial_lot_pays_commission_in_proportion_but_the_final_close_pays_a_full_one`.

**Ç2 — komisyon KAPATILAN MİKTARLA değil, PARAMETREYLE orantılı.** (Issue'da yok, burada
ölçüldü.) `close_size = pos.size × fraction` ama `commission_lot = commission × 2 × fraction`.
`fraction` sabit olduğu için pozisyon küçüldükçe **birim başına ücret artar**. Örnek
(`close_percentage = 40`, 100 birim): 1. lot 40 birim kapatır ve 0.40 öder (birim başına
0.0100); 2. lot 24 birim kapatır ve **yine 0.40** öder (birim başına 0.0167). Docstring'in
"proportional to the fraction" ifadesi doğrudur — ama "fraction" *kapatılan oran* değil,
*config parametresi*dir; ikisi ilk partial'dan sonra ayrışır.

**Ç3 — K1 hiçbir modelde karşılanmıyor.** Manifest `execution_content`
(`manifest.py:228-238`) şunları taşır: `composition_fingerprint`, `mainboard_items`,
`capital_execution`, `result_artifact_context`, `engine_version`, `tick_data`,
`strategy_package_context`, `external_object_context`, `data_time_context`. **Komisyon
dağılımını anlatan hiçbir alan yok.** Cost config'i pinli strategy revision'ının içinde bir
hash olarak yaşar; **bir hash bir açıklama değildir**. Yani K1 (`:7513`) bugün — hangi model
seçilirse seçilsin — **karşılanmamış durumdadır** ve bu kararın çıktısı bir manifest alanı
İÇERMEK ZORUNDADIR.

### Seçenekler

Ortak notasyon: `c` = konfigüre edilen commission değeri. Sevk edilen kodda bir round trip
`2c`'dir.

#### Seçenek A — per-fill commission

- **Tanım.** Her fill `c` öder. Entry fill'i açılışta, her exit lot'u kapanışta. Round-trip
  kavramı kaybolur; ücret **fill sayısına** bağlıdır. K4'ün (`:7738`) doğrudan okunuşu ve
  `config.py:313`'ün kendi şema açıklamasının (*"Per-trade fee"*) okunuşu.
- **Kod etkisi.** `booking.py:93` → `commission_lot = costs.commission` (fraction'dan
  bağımsız). İlk entry fill için `engine.py`'a **yeni** bir açılış-ücreti yazması gerekir
  (bugün yok — kapanışın `×2`'si onu üstleniyor). `portfolio_ledger.book_trade`'in
  `commission` argümanı artık "round-trip" değil "bu lot'un fee'si" olur; docstring
  (`portfolio_ledger.py:555`, *"the round-trip commission it paid"*) düzeltilir.
  `book_fee` (scale/stack/remainder) **değişmez** — zaten per-fill'dir, yani A bu üç yolu
  ana yola **hizalar**.
- **Hangi test kırılır.** `tests/unit/oracles/test_oracle_costs.py:110`
  `test_commission_is_charged_twice_for_a_round_trip` (adıyla birlikte),
  `:118` `test_costs_reach_the_run_total_and_not_only_the_trade_row`,
  `tests/unit/oracles/test_oracle_position_lifecycle.py:140` (#552 pinlemesi),
  ve oracle paketinin başlık kimliği `test_oracle_costs.py:19`
  (`pnl = (exit_eff - entry_eff) * size - commission * 2`). Ölçüldü: oracle ağacında
  **sıfırdan farklı commission kullanan 3 çağrı yeri** var
  (`test_oracle_costs.py:113`, `:121`, `test_oracle_position_lifecycle.py:153`);
  depo genelinde `commission` geçen **25 test dosyası / 72 satır**, çoğu şema ve readiness
  testidir ve sayı assert etmez.
- **Historical Result etkisi.** Saklanmış Result satırları **değişmez** (yeniden
  hesaplanmazlar). Değişen tek şey: `ENGINE_VERSION` bump'ı `execution_key` namespace'ini
  kaydırdığı için **pre-bump bir Result yeni bir RUN için idempotent olarak yeniden
  kullanılamaz** (INF-04/INF-05 — `manifest.py:110-126`'daki #549 emsalinin birebir aynısı).
- **`ENGINE_VERSION` etkisi.** **Bump ZORUNLU.** Komisyonu sıfırdan farklı olan her run
  farklı PnL verir.
- **3-parçalı vs 1-parçalı kapanış toplam ücreti.** 1-parçalı: 2 fill → `2c`. 3-parçalı:
  4 fill → `4c`. **Ücret parça sayısıyla lineer artar** ve bu A'nın kabul edilen anlamıdır
  (gerçek borsa davranışı).
- **Rollback.** Tek satır geri + `ENGINE_VERSION` bir sonraki değere bump (eski string'e
  DÖNÜLMEZ; bir namespace geri alınmaz, ileri sarılır).

#### Seçenek B — one complete round-trip allocation

- **Tanım.** Bir pozisyon ömrü boyunca **tam olarak bir** round trip (`2c`) öder; bu tutar
  kapanan lot'lara **kapatılan miktarla** orantılı dağıtılır. Docstring'in bugün iddia ettiği
  şey — ama kapatılan miktara göre, `close_percentage` parametresine göre değil (Ç2).
- **Kod etkisi.** `close_position` pozisyonun **orijinal boyutunu** bilmek zorunda:
  `_Position`'a `initial_size` (veya kalan komisyon bütçesi `commission_remaining`) alanı
  eklenir; `commission_lot = 2c × (close_size / initial_size)`, full close ise **kalan
  bütçenin tamamı**. Scale/stack/remainder fill'leri `initial_size`'ı büyüttüğü için
  bütçenin de büyümesi gerekir — yoksa 10 kez scale yapan bir pozisyon 1 round trip öder ve
  `engine.py:3133`'ün "N layers pay exactly N extra fills" yorumu ile **doğrudan çelişir**.
  Bu, B'nin en pahalı kısmıdır: B tek başına tutarlı değildir, `book_fee` yolunun ne olacağı
  **B'nin içinde ikinci bir alt-karardır**.
- **Hangi test kırılır.** `test_oracle_position_lifecycle.py:140` (beklenen `-65.60 / -14.00`
  → `-65.60 / -8.40`). `test_oracle_costs.py:110/:118` **geçmeye devam eder** (tek lot'lu tam
  round trip). Toplam kırılan yüzey A'dan **dar**.
- **Historical Result etkisi.** A ile aynı: satırlar değişmez, namespace kayar.
- **`ENGINE_VERSION` etkisi.** **Bump ZORUNLU** — partial içeren her run değişir; partial
  içermeyen run'lar **aynı sayıyı** verir (ama namespace yine de kayar).
- **3-parçalı vs 1-parçalı kapanış toplam ücreti.** **İkisi de `2c`.** Ücret parça sayısından
  **bağımsızdır**; strateji kaç adımda çıkarsa çıksın aynı ücreti öder.
- **Rollback.** A'dan zor: `_Position` alanı ve `book_fee` hizalaması geri alınır.

#### Seçenek C — bps on notional (kanondan türetilmiş üçüncü explicit model)

- **Tanım.** Kanonun **tek somut komisyon örneği** (K3, `:3110`): komisyon bir **oran**dır ve
  her fill'in **notional**'ı üzerinden alınır. `fee = rate × |fill_price × fill_size|`.
  Bu bir "başka model" değil, **kanonun kendi yazdığı** modeldir; sevk edilen sabit-tutar
  şeması ondan sapmadır.
- **Kod etkisi.** **En geniş.** `config.py:313` (`Decimal | None`, "Per-trade fee") bir
  **oran** alanına dönüşür ya da yanına `commission_mode: flat|bps` eklenir → **API şeması
  değişir**, `docs/openapi.json` drift guard'ı tetiklenir, kaydedilmiş strategy revision'ları
  için bir **migration ya da dual-read** gerekir (eski satırlar `flat` olarak okunmalı).
  `readiness/validators.py:661` commission/spread boşluk kontrolü güncellenir. Engine
  tarafında her fill'in notional'ı zaten hesaplanıyor (`closed_notional`,
  `entry_notional`) — asıl maliyet **motorda değil, şema ve göç tarafında**.
- **Hangi test kırılır.** A'nın kırdığı her şey + `tests/contract/test_strategy_save_contract.py`
  + `tests/unit/test_strategy_config_validation.py` + OpenAPI drift kapısı. Ölçüldü:
  `commission` geçen 25 test dosyasının çoğu **burada** ısırır, A/B'de ısırmaz.
- **Historical Result etkisi.** Satırlar değişmez; ek olarak **eski config'lerin nasıl
  okunacağı** bir uyumluluk kararıdır (dual-read olmadan eski revision'lar okunamaz hale
  gelir — bu, A/B'de olmayan gerçek bir risk).
- **`ENGINE_VERSION` etkisi.** **Bump ZORUNLU** + ayrıca bir **şema/migration sürümü**.
- **3-parçalı vs 1-parçalı kapanış toplam ücreti.** İkisi de `rate × 2N` (N = entry
  notional), çünkü exit notional'ları toplamı entry notional'ına eşittir (fiyat farkı
  ihmal). **Parça sayısından bağımsız, ama miktar-doğru** — B'nin bağımsızlığını Ç2'yi de
  çözerek verir.
- **Rollback.** En zor: şema geri alımı + migration down + OpenAPI.

### Sayısal örnek (ZORUNLU)

**Senaryo.** 100 birim long, entry 100.00, `commission = 0.5` (round trip `2c = 1.00`),
üç exit lot'u 40 / 30 / 30 **birim** kapatıyor, pozisyon sonunda flat. Toplam **4 fill**
(1 entry + 3 exit). Spread/slippage = 0.

| Model | entry | lot1 (40 br) | lot2 (30 br) | lot3 (30 br) | **TOPLAM** | round trip cinsinden |
|---|---|---|---|---|---|---|
| **A** per-fill | 0.50 | 0.50 | 0.50 | 0.50 | **2.00** | 2.00 |
| **B** one round-trip allocation | 0.00 | 0.40 | 0.30 | 0.30 | **1.00** | 1.00 |
| **C** bps on notional (`rate = 5bps`) | 5.00 | 2.00 | 1.50 | 1.50 | **10.00** | — (oran) |
| **Sevk edilen**, 3. lot FULL close ise | 0.00 | 0.40 | 0.30 | **1.00** | **1.70** | 1.70 |

C satırı farklı bir birimde olduğu için doğrudan kıyaslanamaz; **kıyaslanabilir olan
özelliği** şudur: C'nin toplamı `rate × 2 × 10,000 = 10.00`'dır ve **parça sayısından
bağımsızdır** (B gibi), ama lot'lar arasında **miktara göre** dağılır (B'nin Ç2'yi çözmüş
hâli).

**Sevk edilen satırın uyarısı — bu senaryo V18 config'iyle İFADE EDİLEMEZ.**
`close_percentage` **tek bir alandır** (`engine.py:974`), yani üç partial farklı yüzde
taşıyamaz; üstelik `fraction` **kalan** boyuta uygulanır. Gerçekten ifade edilebilir en yakın
şekil `close_percentage = 40` + sonda bir full close'dur:

| lot | kapanan boyut | ücret | kalan |
|---|---|---|---|
| partial 1 | 40.0 | 0.40 | 60.0 |
| partial 2 | 24.0 | 0.40 | 36.0 |
| partial 3 | 14.4 | 0.40 | 21.6 |
| full close | 21.6 | 1.00 | 0 |
| **toplam** | 100.0 | **2.20** | — |

5 fill, **2.20** ücret. Per-fill (A) 2.50 derdi, tek round trip (B) 1.00 derdi. Ç2 burada
çıplak görünür: 2. lot 1. lot'un **%60'ı kadar** miktar kapatır ama **aynı** ücreti öder.

### "Hiçbir şey yapma" seçeneğinin bedeli

1. **K1 karşılanmamış kalır.** Master Ref `:7513` komisyon dağılımının manifestte açık
   olmasını ŞART koşar; `execution_content` böyle bir alan taşımaz. Bu, model seçiminden
   **bağımsız** bir kanon açığıdır ve "hiçbir şey yapma" onu kapatmaz.
2. **Kod içinde yanlış bir invariant sevk edilmeye devam eder.** `booking.py:82-83`
   docstring'i tutmayan bir garanti veriyor. Bir sonraki okuyucunun ona güvenmesi için hiçbir
   engel yok; bu, "belgelenmiş davranış" ile "sevk edilen davranış" arasında **kalıcı** bir
   ayrışmadır. Yalnızca docstring'i düzeltmek de bir karardır ve **imza ister** (sevk edilen
   davranışı kanonik ilan eder).
3. **Maliyet config'ten yeniden üretilemez.** Bir kullanıcı `commission = 0.5` ve dört fill
   görüp toplam ücreti hesaplayamaz; cevap `close_percentage`'a ve kaç kez partial
   tetiklendiğine bağlıdır (Ç2). Bu, Modül 15 §9223'ün `net_profit` tanımının
   ("engine tarafindan uygulanmis maliyetler dahil") denetlenebilirliğini zayıflatır.
4. **Yön güvenlidir, büyüklük değil.** Sapma her zaman **fazla** ücret alır (2.20 > B'nin
   1.00'i), yani sonuç **muhafazakâr**dır. Bu, aciliyeti düşürür ama doğruluğu vermez.
5. **Portfolio ledger'ı iki ayrı fee anlayışını taşımaya devam eder.**
   `book_trade(commission=...)` "round trip" derken (`portfolio_ledger.py:555`) `book_fee`
   "per-fill" der (`:578`). Shared-capital yolu açıldığında bu ikilik **composite** sayılara
   taşınır.

### Önerilen seçenek + gerekçe (BU BİR ÖNERİDİR, KARAR DEĞİL)

**Öneri: A (per-fill), + zorunlu bir manifest disclosure alanı.**

Gerekçe: (i) K4 (`:7738`) fill event'i başına maliyet uygulandığını söyleyen **tek doğrudan**
kanon cümlesidir; (ii) sevk edilen kodun **kendisi zaten** scale/stack/remainder fill'lerini
per-fill ücretlendiriyor (`engine.py:2953`, `:3133`, `booking.py:222`) — A bu üç yolu ana
yola **hizalar**, yeni bir kavram getirmez, ve bu hizalama B'de ikinci bir alt-karar olarak
geri gelir; (iii) A, Ç1'i ve Ç2'yi **birlikte** çözer (fraction denklemden çıkar); (iv) test
etkisi ölçüldü ve dardır — oracle ağacında sıfırdan farklı commission kullanan **3** çağrı
yeri var.

**A'nın karşı-argümanı dürüstçe:** K3 (`:3110`) kanonun **tek somut** komisyon örneğidir ve
oran bazlıdır — yani en "kanona sadık" seçenek aslında **C**'dir. A, sevk edilmiş sabit-tutar
şemasını korur; bu, ORTAK SÖZLEŞME'nin *"'Zaten böyle yapılmış' diye mevcut davranışı
canonical ilan etme"* yasağına **yakın** durur. Ayrım şudur: A, sevk edilen *dağılım
kuralını* (`×2 × fraction`) korumaz — onu **değiştirir**; koruduğu şey commission'ın *birimi*
ve o birim K2 (`:7425`, "sayısal giriş") ile uyumludur. Yine de ürün sahibi C'yi seçerse
gerekçe daha güçlüdür ve maliyet daha yüksektir; bu takas **bilinçli** olarak buraya yazıldı.

**Her seçenekte ZORUNLU ek (K1):** `execution_content`'e bir
`commission_model` alanı (`"per_fill" | "round_trip_allocated" | "bps_on_notional"`)
eklenmelidir. Bu, model seçiminden bağımsız olarak `:7513`'ün istediği "manifestte açık"
şartıdır ve `execution_key`'in içinde olmalıdır (aksi halde iki farklı ücret modeliyle
üretilmiş iki run aynı reprodüksiyon kimliğini paylaşır).

### İMZA SATIRI

**Karar 1 — commission modeli:**

`[ ] A (per-fill)`  `[ ] B (one round-trip allocation)`  `[ ] C (bps on notional)`
`[ ] D (hiçbir şey yapma — sevk edilen davranış imzalı sapma olarak kanonik ilan edilir)`

Zorunlu ek — `execution_content.commission_model` manifest alanı: `[ ] evet` `[ ] hayır (gerekçe: ______)`

karar veren: ________________  tarih: ____________

---

## Karar 2 — Research bundle shape (GH #558)

### Canonical ne diyor

- **doc 12 §9.1** (`12_..._v1_1.md:814`): *"Agent Data Bundle exact revision IDs, **usage
  scope and time policy** pinler. 'Latest approved' dynamic resolution forbidden."*
- **doc 12 §9.2** (`:834`), `BacktestEvidenceBundle` alan listesi **birebir**:
  `primary_market_dataset_revision_id` / `research_dataset_revision_ids[]` /
  `feature_definition_revision_ids[]` / `instrument_mapping_revision_ids[]` /
  `alignment_policy_versions[]` / **`available_time_policies[]`** /
  `missing_and_stale_policies[]` / `resolved_at, compiler_version, bundle_hash`.

Yani §9.1 Agent bundle'ı için time policy'yi **isimle** ister; §9.2 evidence bundle'ı için
`available_time_policies[]`'i **üst düzey bir dizi** olarak yazar.

### Kod şu an ne yapıyor (file:line)

Her iki compiler da üye başına **beş** alan pinliyor
(`application/jobs/research_data.py:507-515` ve `:539-547`):

```python
{"research_revision_id", "research_content_hash", "usage_scope",
 "market_dataset_revision_id", "market_content_hash"}
```

`_seal_bundle` (`:553-564`) gövdeyi `{bundle_kind, members, compiler_version, **extra}`
olarak kurar, `bundle_hash = manifest_hash(body)` hesaplar, sonra `resolved_at`'i **hash'ten
SONRA** ekler. `_BUNDLE_COMPILER_VERSION = "research-bundle-v1"` (`:58`).

Run manifest'i **başka bir kod** ile aynı bilgiyi pinliyor
(`application/commands/backtest_run_context.py:377-395`): `available_time_policy`,
`available_delay_seconds`, `event_time_semantics`, `frequency_policy`,
`source_timezone_mode`, `source_timezone_iana`, `linked_market_dataset_revision_id`,
`instrument_mapping_ref`, `field_definition_version`, `feature_definitions[]`.

`compile_backtest_evidence_bundle` time policy'yi **doğruluyor** ama **kaydetmiyor**:
`admit_bundle_member(..., for_execution=True)` → `_ensure_time_policy_valid(revision)`
(`:483`).

Pin: `tests/integration/test_research_point_in_time_parity.py:583`
`test_both_bundles_pin_the_available_time_policy`, `xfail(strict=True)` — **deponun tek
bilinçli strict xfail'i** (`CLAUDE.md`: *"Bilinçli `xfail(strict)` sayısı 1'dir"*).

### Çelişki tam olarak nerede

**İki execution-evidence yüzeyi bir "execution pin"in ne olduğu konusunda anlaşmıyor.**
Run manifest'i on alan pinler, evidence bundle'ı beş alan pinler, Agent bundle'ı da aynı beş
alanı pinler — halbuki §9.1 Agent bundle'ı için time policy'yi **açıkça** ister.

Asıl sonuç `bundle_hash`'tedir: hash **üye listesi üzerinden** hesaplanır ve o listede
zamanlama alanı yoktur → **`bundle_hash` bir time-policy değişimi altında değişmez.** Yani
bir bundle, **kendi içeriğinden**, hangi availability kuralı altında derlendiğini
kanıtlayamaz. `content_hash` bunu kapatmaz: o payload byte'larını kapsar, revision'ın
**zamanlama metadata**'sını değil.

**Ölçülen hafifletici (doğrulandı, `:58` ve `--` ile):** ADIM 13'ten beri onaylı bir
revision'ın time policy'si donmuştur (`domain/research_data/time_policy.py::ensure_time_policy_mutable`)
ve ADIM 54 bunu bir kabul testiyle pinledi. Yani drift **artık ulaşılabilir değil**; eksik
olan **pin'in kendisi**, yani provenance beyanı.

**Kalıcı tüketici ölçüldü, issue'nun tahmini DOĞRULANDI.** `grep -rn "bundle_hash" src/` →
yalnız **iki** satır, ikisi de `_seal_bundle`'ın kendi içinde (`:563`, `:564`). Hiçbir kolon
`bundle_hash` saklamıyor; `context_manifest_id` / `input_manifest_id` düz `String(40)`
kolonlarıdır (`infrastructure/postgres/models/agent_lab.py:96`, `:157`;
`agent_tool_gateway.py:60`) ve mühürlenmiş gövde hiçbir yerden yeniden okunmuyor.
**Sonuç: hash shape'i değiştirmek bugün kayıtlı hiçbir tüketiciyi kırmaz.**

### Seçenekler

#### Seçenek A — pinle

- **Tanım.** Time-policy alanları bundle üyesine girer. **İki alt-şekil, §9.1 ve §9.2 farklı
  şeyler söylediği için:**
  - **A1 (üye içinde, manifest'i aynala).** Her üye `available_time_policy`,
    `available_delay_seconds`, `event_time_semantics`, `frequency_policy`,
    `source_timezone_mode`, `source_timezone_iana` alanlarını taşır. §9.1'in
    (*"time policy pinler"*) doğrudan karşılığı; Run manifest'iyle **alan alan** aynı olur.
  - **A2 (üst düzey `available_time_policies[]`).** §9.2'nin **literali**. Ama dizi hangi
    üyeye ait olduğunu söylemez — üç üyeli bir bundle'da iki `fixed_delay` bir `no_delay`
    görürsünüz ve hangisinin hangisi olduğu **kaybolur**.
  - **Öneri (bu bir öneridir): A1 + A2 birlikte** — üyede tam alan seti (otorite),
    üst düzeyde `available_time_policies[] = sorted(set(...))` (§9.2'nin adı, türetilmiş).
    O-30 emsali: *iki ad, tek değer; biri kaldırılmaz, ikisi asla ayrışmaz.*
- **Hash shape değişir → mevcut kayıtlı bundle'lar ne olur?** **Hiçbiri yok** (yukarıdaki
  grep). Yine de gövde şekli değişiyorsa **`compiler_version` bump ZORUNLU**:
  `"research-bundle-v1"` → `"research-bundle-v2"`. `compiler_version` gövdenin **içinde** ve
  dolayısıyla hash'in içinde olduğu için bump, eski ve yeni hash uzaylarını **kendiliğinden**
  ayırır — ayrı bir versioned-hash mekanizmasına gerek yoktur.
- **Versioned hash mi, migration mı, dual-read mi?** **Üçü de değil — `compiler_version`
  bump'ı yeter.** Migration yok (kolon yok). Dual-read yok (okuyucu yok). Bu, A'yı beklenenden
  **ucuz** yapar ve bu ölçüm bu belgenin en somut bulgusudur.
- **Hangi alanlar dahil (tam liste önerisi).** Zorunlu: `available_time_policy`,
  `available_delay_seconds`, `event_time_semantics`, `frequency_policy`. Şiddetle önerilen:
  `source_timezone_mode`, `source_timezone_iana` (**Karar 3 ile doğrudan bağlı** — bir
  bundle'ın hangi zone varsayımı altında derlendiği, DST kararı değişirse tek denetlenebilir
  kanıttır). §9.2'nin kalan dört alanı (`feature_definition_revision_ids[]`,
  `instrument_mapping_revision_ids[]`, `alignment_policy_versions[]`,
  `missing_and_stale_policies[]`) **ayrı bir alt-karardır** — aşağıdaki imza satırında ayrı
  kutuları var, çünkü ilk ikisi verilerde mevcut (`instrument_mapping_ref`,
  `feature_definitions[]` manifest'te zaten pinli) ama son ikisinin arkasında sevk edilmiş
  bir alan **olmayabilir** ve bu durumda bunlar sınıf-D (uygulama boşluğu) olur.
- **Kod etkisi.** `research_data.py` içinde iki `members.append(...)` bloğu + `_seal_bundle`;
  `revision` nesnesi zaten elde (`admit_bundle_member` onu döndürüyor) → **ek sorgu yok**.
- **Test etkisi.** `test_research_point_in_time_parity.py:583` `xfail(strict=True)`
  **KALDIRILIR** ve normal assert olur → deponun **bilinçli strict xfail sayısı 1 → 0**.
  `CLAUDE.md` §Testler'deki "1'dir" ifadesi ve `#558` referansı güncellenir.
- **Historical compatibility.** Kayıtlı tüketici yok → **kırılma yok**. Ama daha önce
  **üretilmiş ve dışarıya verilmiş** (log/agent artifact içinde) bir `bundle_hash` yeniden
  üretilemez; `compiler_version` bunu **açıkça** söyler, sessiz bırakmaz.
- **Rollback.** Alanları geri çıkar + `compiler_version` **v3**'e bump (v1'e DÖNÜLMEZ).

#### Seçenek B — pinleme, imzalı sapma yaz

- **Tanım.** Bundle beş alanlı kalır; §9.1/§9.2 ile ayrışma bir **imzalı kalıcı sapma**
  olarak kaydedilir (D-10 emsali).
- **Neyi kaybederiz?** Bundle'ın **kendi içeriğinden** hangi zamanlama kuralı altında
  derlendiğini söyleyebilme yeteneği. Denetçi cevabı almak için canlı revision satırına
  gitmek zorundadır — ki bu tam olarak bir immutable bundle'ın **var olma sebebine** aykırıdır
  (§9.2: *"worker must not rely on a dropdown selection or a browser-held registry record"*).
- **Aynı hash iki farklı timing politikasıyla üretilebilir kalır mı?** **Bugün için HAYIR,
  yapısal olarak EVET.** Ölçülen gerçek: `admit_bundle_member(for_execution=True)` ACTIVE+
  APPROVED şartı koyar ve `ensure_time_policy_mutable` onaylı bir revision'ın politikasını
  dondurur → *aynı `revision_id` + aynı `content_hash`* ile iki farklı politika **bugün
  üretilemez**. Ama bu, bundle'ın **kendi garantisi değil**, iki uzaktaki komşu kuralın yan
  etkisidir; ikisinden biri gevşerse hash sessizce yalan söylemeye başlar ve **hiçbir test bunu
  yakalamaz**. Ayrıca Agent bundle'ı `for_execution=False` ile derlenir — orada APPROVED şartı
  **yoktur** (`:474`, DRAFT bir revision girebilir), yani §9.1'in istediği pin en zayıf
  olduğu yüzeyde eksiktir.
- **Bu bir provenance yalanı mı?** **Hayır, bir provenance eksikliğidir.** Bundle yanlış bir
  şey **beyan etmiyor**; §9.1/§9.2'nin beyan etmesini istediği şeyi **hiç beyan etmiyor**.
  Ayrım maddidir: yalan geri çekilir, eksiklik doldurulur. Ancak `bundle_hash`'in adı bir
  **tamlık** çağrışımı taşır ve bir denetçi onu "bu bundle'ın her şeyi" diye okur — B bu yanlış
  okumayı **kalıcı** kılar ve imza metninde bunun açıkça yazılması gerekir.
- **Kod/test/hash etkisi.** Kod değişmez. `xfail(strict=True)` **kalır** ve reason metni
  "GH #558 — imzalı sapma, karar tarihi ____" olarak güncellenir; **strict xfail sayısı 1
  kalır**. Hash shape değişmez.
- **Historical compatibility.** Tam. **Rollback.** Yok (değişiklik yok); geri dönüş A'yı
  uygulamaktır.

#### Seçenek C — kısmi pinleme (yalnız policy token'ları, delay değerleri hariç)

- **Tanım.** Üyeye yalnız `available_time_policy` (enum token'ı, ör. `"fixed_delay"`) girer;
  `available_delay_seconds` **girmez**.
- **Hangi soruyu cevaplar?** *"Bu bundle hangi availability KURALI altında derlendi?"* —
  §9.2'nin `available_time_policies[]` adının literal karşılığıdır ve hash'i o eksende
  duyarlı yapar.
- **Hangisini cevaplamaz?** *"Kural ne kadar geciktirdi?"* — ve bu, `fixed_delay` için
  **kuralın tamamıdır**. `fixed_delay` + 60s ile `fixed_delay` + 3600s aynı token'ı
  üretir, aynı hash'i verir ve **tamamen farklı** bir lookahead sınırı tanımlar
  (`funding.py:176-182`: `fixed_delay` pozitif ve sınırlı bir delay ZORUNLU kılar, yani token
  tek başına asla yeterli değildir). Bu yüzden C, `fixed_delay` politikasında B'den **anlamlı
  ölçüde daha iyi değildir**; yalnızca `no_delay` / `same_bar` gibi delay taşımayan
  politikalarda tam cevap verir.
- **Kod/test/hash etkisi.** A ile aynı mekanik (tek alan), aynı `compiler_version` bump'ı.
  `xfail` testi **bugünkü hâliyle geçer** (yalnız `available_time_policy == "fixed_delay"`
  assert ediyor) — yani C, testi yeşile çevirir ama sorunun yarısını açık bırakır.
  **Bu, C'nin en tehlikeli yanıdır: kapı yeşile döner, boşluk kapanmaz.**
- **Historical compatibility / rollback.** A ile aynı.

### Önerilen seçenek + gerekçe (BU BİR ÖNERİDİR, KARAR DEĞİL)

**Öneri: A1+A2 (üyede tam alan seti + üst düzey türetilmiş dizi), `compiler_version` →
`research-bundle-v2`.**

Gerekçe: (i) maliyet **ölçüldü ve düşük** — kalıcı tüketici yok, migration yok, dual-read yok,
ek sorgu yok; (ii) kanon **iki ayrı yerde** (§9.1 ve §9.2) bunu ismen istiyor, yani bu bir
yorum değil bir eksik; (iii) Run manifest'i **aynı bilgiyi zaten** pinliyor — A, üç
execution-evidence yüzeyini tek anlayışa getirir ve "en fakir yüzey" durumunu ortadan
kaldırır; (iv) C, `xfail`'i yeşile çevirip `fixed_delay`'in delay'ini pinlemeden bırakır,
yani **kapıyı yanlış yönde** hareket ettirir; (v) B'nin yapısal riski (iki komşu kuralın yan
etkisine dayanmak) Karar 3 ile birlikte ele alındığında büyür, küçülmez.

**§9.2'nin kalan dört alanı ayrı bir karardır** ve A'yı bekletmemelidir: ikisi
(`feature_definition_revision_ids[]`, `instrument_mapping_revision_ids[]`) mevcut veriden
türetilebilir, ikisi (`alignment_policy_versions[]`, `missing_and_stale_policies[]`) arkasında
sevk edilmiş bir alan olduğu **doğrulanmadı** — doğrulanmazsa bunlar sınıf-D'dir ve hiçbir
test kapatamaz.

### İMZA SATIRI

**Karar 2 — research bundle shape:**

`[ ] A1 (üyede tam alan seti)`  `[ ] A2 (üst düzey dizi)`  `[ ] A1+A2`
`[ ] B (pinleme, imzalı sapma)`  `[ ] C (yalnız policy token'ı)`

Alt-karar — `source_timezone_mode` / `source_timezone_iana` da pinlensin mi?
`[ ] evet` `[ ] hayır`

Alt-karar — §9.2'nin kalan dört alanı V1'de: `[ ] hepsi içeri` `[ ] yalnız türetilebilir ikisi` `[ ] dördü de V1 dışı`

karar veren: ________________  tarih: ____________

---

## Karar 3 — DST fold ve gap (GH #559) — KAPI MI, DEĞİL Mİ?

### Ölçülen izleme durumu (2026-08-13)

`#559` **OPEN** (`state_reason=reopened`), labels `product-decision` + **`blocks-mixed-zone-axis`**,
milestone **"ADIM 16-20 — unified clock programme"**. Prompt'un gözlemi doğrulandı.

### Canonical ne diyor

- **doc 12 §5.2** UTC normalizasyonu ister: *"Conversion failure blocks approval/run."*
- **doc 12 §8.4 rule 1** kaynak damgasının **kendi zone'unda** okunmasını ister.
- **Hiçbiri**, bir instant'a 1:1 eşlenmeyen bir yerel duvar saatinin ne anlama geldiğini
  söylemez. Her DST zone'unda böyle iki duvar saati vardır.
- **ADR 0002** (otorite sırası md. 2, koddan ÜSTTE) üç yerde hüküm veriyor:
  - `:289-292` — *"**DST.** Fold resolves to `fold=0` ... A merged axis spanning sources in
    different declared zones inherits this. The clock must not paper over it: **#559 is a
    prerequisite decision, not a consequence**."*
  - `:745` — *"**Prerequisites that are not part of ADIM 15–20** ...: GH **#559** (DST rule)
    **before the merged axis spans mixed-zone sources**."*
  - `:853` R-2 — *"close #559 **before the axis spans mixed-zone sources**"*

**ADR koşulu üç kez aynı şekilde daraltıyor: "merged axis MIXED-ZONE kaynakları kapsamadan
önce".** Eksenin var olmasından önce değil.

### Kod şu an ne yapıyor (file:line)

**Ölçüm 1 — merged clock ekseni HİÇBİR zone dönüşümü yapmaz.**
`domain/backtest/execution/clock.py:177-186`:

```python
def tick_key(timestamp: str) -> int | None:
    parsed = parse_utc(timestamp, source_zone=None)
    return int(parsed.timestamp() * 1000) if parsed is not None else None
```

`source_zone=None` iken **naive bir değer `None` döner** (`funding.py:89-92`, K-01
sözleşmesi: *"when `source_zone` is `None` a naive value is UNRESOLVABLE ... rather than
silently assumed to be UTC"*) → `UnplaceableBarTimestampError` → **fail closed**. Yani eksen
bir DST kararını **veremez**, çünkü hiç yerelleştirme yapmaz.

**Ölçüm 2 — motor tarafındaki YEDİ `parse_utc` çağrısının ALTISI `source_zone=None`.**
Tam sayım (`grep -rn "parse_utc(" src/`, `def` hariç):

| # | Çağrı yeri | `source_zone` | Zone dönüşümü yapar mı |
|---|---|---|---|
| 1 | `backtest/engine.py:701` | `None` | hayır |
| 2 | `backtest/engine.py:1822` | `None` | hayır |
| 3 | `backtest/execution/costs.py:75` | `None` | hayır |
| 4 | `backtest/execution/clock.py:185` | `None` | hayır |
| 5 | `backtest/execution/rules.py:44` | `None` | hayır |
| 6 | `backtest/execution/fills.py:350` | `None` | hayır |
| 7 | **`backtest/funding.py:193`** | **`source_zone`** | **EVET** |

**Run içinde zone dönüşümü yapan TEK yol `funding.py:193`'tür.** Diğer dört dönüşüm yolu
**ingest/validation** tarafındadır: `application/jobs/research_data.py:137`,
`application/jobs/market_data.py:183`, `domain/market_data/validation_rules.py:301`,
`domain/research_data/quality_rules.py:331`.

**Ölçüm 3 — MARKET DATA yolunda DST fold/gap zaten FAIL-CLOSED.**
`domain/market_data/validation_rules.py:282-283` ve `:333-353`:
- *"non-monotonic timestamp (out-of-order in delivered order) -> **BLOCKING_FAIL**"*
  (`TIMESTAMP_NON_MONOTONIC`)
- *"duplicate `instrument+timestamp+resolution` -> **BLOCKING_FAIL**"* (`DUPLICATE_TIMESTAMP`)
- *"Blocking findings force the revision to NEEDS_REVIEW (never auto-verified), so a corrupt
  series cannot reach APPROVED and feed the money-sizing engine."*

Bir **fold** (aynı yerel saat iki kez, `fold=0` ile ikisi de aynı UTC instant'ına düşer)
**hem** duplicate **hem** out-of-order üretir. Bir **gap** (02:30 → EST offset'iyle 07:30Z,
ardından 03:00 EDT → 07:00Z) **out-of-order** üretir. **İkisi de BLOCKING_FAIL'dir** → revision
APPROVED olamaz → **motora ve merged eksene hiç ulaşamaz.**

**Ölçüm 4 — RESEARCH DATA yolunda böyle bir kapı YOK.**
`domain/research_data/quality_rules.py`'da monotonluk kontrolü **hiç yok**; duplicate kontrolü
(`_check_duplicates`, `:148-181`) **tamamen özdeş native satırları** oran eşiğiyle ölçer
(≥%50 blocker, ≥%10 warning). Katlanmış bir saatin iki kopyası **farklı rate taşır**, yani
özdeş değildir → **yakalanmaz**. Ardından `build_funding_schedule` (`funding.py:193-204`)
satırları okur ve `records.sort(...)` (`:204`) ile sırasızlığı **sessizce düzeltir**. Sonuç:
aynı `event_at`'e sahip **iki** funding kaydı; ikisi de eligible; ikisi de ücretlendirilir.

**Ölçüm 5 — kapsam `custom` moduyla sınırlı, doğrulandı.**
`application/jobs/market_data.py:140-159` ve `application/jobs/research_data.py:91-110`:
`utc` → `ZoneInfo("UTC")` (DST yok), `custom` → stored IANA, **`exchange` → `None`**
(*"carries no identifier to resolve. `None` is FAIL-CLOSED"*). Yani DST yalnız
**`custom` + DST gözleyen IANA zone** kombinasyonunda ortaya çıkar.

### Çelişki tam olarak nerede

Sessiz çözüm iki noktada gerçekleşiyor ve **her ikisi de** `datetime.replace(tzinfo=zone)`'un
`fold=0` varsayılanına dayanıyor (`validation_rules.py:218`, `funding.py:108`):

| Vaka | Kaynak hücre (`America/New_York`) | Çözülür | İşaretlenir mi | Market Data'da | Research Data'da |
|---|---|---|---|---|---|
| **fold** | `2024-11-03T01:30:00` | `05:30Z` (**ilk**, EDT) | hayır | **BLOCKING_FAIL** (dup + non-monotonic) | **sessiz** |
| **gap** | `2024-03-10T02:30:00` | `07:30Z` | hayır | **BLOCKING_FAIL** (non-monotonic) | **sessiz** |

**Kalıntı (dürüst sınır).** Market Data kapısı bir **yan etki** olarak koruyor, DST'yi
bilerek değil. Sağlayıcı katlanmış saatin **yalnız bir** kopyasını verirse (çoğu sağlayıcı
kendi tarafında dedup eder) ne duplicate ne out-of-order oluşur → **bir saatlik veri sessizce
kayar** ve hiçbir kapı bunu görmez. Yani market yolu "kapalı" değil, "çoğu şekilde kapalı"dır.

### Hüküm

**(a) #559 BLOKLUYOR — ama ADR'nin yazdığı DAR koşulla, ve blokladığı yer eksenin
aritmetiği DEĞİL.**

Gerekçe, iki parça:

1. **Neden "bloklamıyor" DİYEMEM.** Otorite sırası md. 2 (ADR 0002) üç ayrı yerde #559'u bir
   **prerequisite decision** ilan ediyor ve `:291` açıkça *"The clock must not paper over
   it"* diyor. Bir ADR hükmünü kod ölçümüyle **iptal edemem** — kod ölçümü ancak hükmün
   **kapsamını** daraltabilir. Ayrıca ölçüm 4, bugün **gerçekten ulaşılabilir** bir sessiz
   yol buluyor (research → funding), yani hüküm boşta değil.
2. **Kapsamı KANITLA daraltıyorum.** Merged eksen (`clock.py`) hiçbir zone dönüşümü yapmaz
   (ölçüm 1) ve motor tarafındaki 6/7 okuyucu `source_zone=None`'dır (ölçüm 2). Dolayısıyla
   *"E4/E5 eksenin kendi aritmetiğini yazarken #559'un cevabına ihtiyaç duyar"* iddiası
   **YANLIŞTIR** — eksen naive damgada fail-closed'dır ve DST kararının çıktısı ona bir kod
   yolu olarak dokunmaz. #559'un ısırdığı yer **ingest** (research) ve **funding schedule**
   (`funding.py:193`) yüzeyleridir; eksen bunları **miras alır**, üretmez.

**Pratik sonuç — kapı hangi işi durdurur, hangisini durdurmaz:**

| İş | #559 kapı mı |
|---|---|
| `clock.py` ekseninin kendisi, `ItemParticipant` adaptörü, tick/merge aritmetiği | **HAYIR** — kanıt: ölçüm 1 + 2 |
| Tek zone'lu (veya `utc`/`exchange` modlu) kaynaklarla co-simulation | **HAYIR** — kanıt: ölçüm 5 |
| Eksenin **farklı `custom` zone'lardaki** kaynakları kapsaması | **EVET** — ADR `:745`, `:853` |
| Research/funding'in shared-pool run'ında ücretlendirilmesi | **EVET** — ölçüm 4 (bugün de sessiz) |

**Ordered plan için öneri (öneridir):** #559'u ön koşuldan **çıkarma**; onu bir **kapsam
kapısına** dönüştür — "merged axis mixed-zone kaynakları kapsayana kadar açık kalır" ve bu
sınır kodda **fail-closed** olarak ifade edilir (aşağıdaki Seçenek D). Böylece E4/E5'in eksen
işi #559 imzalanmadan ilerleyebilir, ama mixed-zone yüzeyi kaza eseri açılamaz.

### Seçenekler

#### Seçenek A — fold ve gap BLOCKER olur (§5.2'nin "conversion failure blocks" okunuşu)

- **Tanım.** Belirsiz (fold) veya var olmayan (gap) bir yerel damga bir **conversion
  failure**'dır → `TIME_POLICY_INVALID` / `RESEARCH_DATA_TIMEZONE_UNRESOLVED`.
- **Kod etkisi.** `validation_rules.py::_localize` ve `funding.py::parse_utc` içinde
  `fold=0`/`fold=1` karşılaştırması ile belirsizlik tespiti (`dt.replace(fold=0).utcoffset()
  != dt.replace(fold=1).utcoffset()` → ambiguous **veya** nonexistent). İki yer, tek kural,
  ortak bir yardımcı.
- **Test etkisi.** `tests/unit/test_research_point_in_time.py`'daki **üç karakterizasyon
  testi** (`test_an_ambiguous_dst_fold_string_resolves_to_the_first_occurrence`,
  `test_a_nonexistent_dst_gap_string_is_accepted_not_rejected`,
  `test_the_ingest_normalizer_and_the_funding_reader_agree_on_every_dst_case`) **tersine
  döner** — bu inversiyon kabul kanıtıdır, testler silinmez.
- **Historical compatibility.** **En pahalı yeri burası.** Zaten APPROVED olmuş, katlanmış
  saat içeren revision'lar bugün geçerli sayılıyor. Kural geriye dönük mü? → **§Kapsam
  alt-kararı** (aşağıda).
- **Hash/`ENGINE_VERSION` etkisi.** `ENGINE_VERSION` bump **gerekmez** (sayı değişmez;
  bazı run'lar artık **hiç başlamaz**). Ama Karar 2'yi A ile imzalarsanız
  `source_timezone_*` alanları bundle'a girdiği için **`compiler_version` zaten bump'lanır**.
- **Rollback.** Kapıyı kaldır; reddedilmiş revision'lar kendiliğinden geçerli olmaz (yeni
  revision gerekir).

#### Seçenek B — mevcut davranış kanonik ilan edilir (imzalı sapma)

- **Tanım.** *"Belirsiz bir duvar saati ilk (geçiş öncesi) oluşuma çözülür; var olmayan bir
  duvar saati geçiş öncesi offset ile normalize edilir."* Kanona bir **kural yazılır** ve
  imzalanır.
- **Kod etkisi.** **Sıfır** — yalnız docstring + manifest disclosure.
- **Test etkisi.** Üç karakterizasyon testi **olduğu gibi kalır** ve statüsü "pinlenmiş
  sapma"dan "pinlenmiş kural"a döner.
- **Neyi kaybederiz.** Yılda bir saat veri, **kaynak dosyadan adreslenemez** kalır: offset'siz
  bir string `fold=1`'i ifade edemez. Bu, bir **veri kaybı değil**, bir **ifade edilemezlik**
  sınırıdır ve imza metninde böyle yazılmalıdır.
- **Historical compatibility.** Tam. **Rollback.** Yok (değişiklik yok).
- **Uyarı.** B, ORTAK SÖZLEŞME'nin *"'Zaten böyle yapılmış' diye mevcut davranışı canonical
  ilan etme"* yasağının **tam hedefidir**. B meşrudur, ama yalnız **bilinçli bir imzayla**;
  varsayılan olarak seçilemez.

#### Seçenek C — offset ZORUNLU kılınır (belirsizliği kaynağa geri iter)

- **Tanım.** DST gözleyen bir `custom` zone bildiren bir revision'ın kaynak damgaları
  **offset taşımak zorundadır** (`+04:00` / `Z`); naive damga reddedilir. Motor tarafı zaten
  böyle çalışıyor (ölçüm 2: `source_zone=None` → naive = fail-closed) — C, **ingest'i motorla
  hizalar**.
- **Kod etkisi.** `revision_source_zone` + `_localize` civarında tek kural; `utc` ve
  `exchange` modları **etkilenmez**.
- **Test etkisi.** A'dan dar; üç karakterizasyon testi "bu girdi artık ingest'e giremez"
  şekline döner.
- **Neyi çözer.** Fold ve gap'in **ikisini birden** ve `fold=1`'in adreslenemezliğini de
  (offset'li bir string ikinci oluşumu **ifade edebilir**) — B'nin kaybını geri verir.
- **Bedeli.** Offset'siz CSV veren **her sağlayıcı** için ekstra bir hazırlık adımı. Bu bir
  **ürün ergonomisi** takasıdır, mühendislik takası değil.
- **Historical compatibility.** A ile aynı geriye-dönüklük sorusu.
- **Rollback.** Kapıyı kaldır.

#### Seçenek D — kapsam kapısı (mixed-zone ekseni fail-closed, DST kararı ertelenir)

- **Tanım.** DST sorusuna **cevap verilmez**; bunun yerine ADR'nin koşulu **kodda ifade
  edilir**: merged eksen, birbirinden farklı `custom` DST-zone'ları bildiren iki kaynağı aynı
  eksende birleştirmeyi **reddeder** (`ClockAxisError` alt sınıfı, `NET`'in
  `UnsupportedConflictPolicyError` emsali — `execution/arbitration.py:148-160`, sınıf `:296`).
- **Kod etkisi.** Eksende tek bir admission kontrolü; `clock.py`'ın aritmetiği değişmez.
- **Test etkisi.** Yeni bir fail-closed testi; üç karakterizasyon testi **dokunulmadan kalır**.
- **Neyi çözer.** ADR `:745`/`:853`'ün koşulunu **kanıtlanabilir** kılar ve E4/E5'in eksen
  işini serbest bırakır. **Neyi çözmez:** ölçüm 4'ün research→funding sessiz yolu **açık
  kalır** (o yol merged eksenden bağımsızdır ve bugün de vardır).
- **`ENGINE_VERSION` etkisi.** Yok. **Rollback.** Kontrolü kaldır.
- **Not.** D, A/B/C'nin **alternatifi değil**, onları erteleyen bir **kapıdır**. Tek başına
  imzalanırsa #559 **açık kalır** ve bu belgede öyle kaydedilmelidir.

### Önerilen seçenek + gerekçe (BU BİR ÖNERİDİR, KARAR DEĞİL)

**Öneri: D (şimdi, E4/E5'i açmak için) + C (kalıcı kural olarak).**

Gerekçe: (i) D, ADR'nin koşulunu kodda ifade eder ve ölçüm 1+2'nin gösterdiği gerçeği kullanır
— eksen aritmetiği DST kararına ihtiyaç duymaz, dolayısıyla E4/E5'i #559'un arkasında
bekletmek **kanıtsız bir maliyettir**; (ii) C, fold ve gap'i **tek kuralla** çözer, `fold=1`
adreslenemezliğini de kapatır ve **motorun zaten uyguladığı** sözleşmeyi (naive = fail-closed)
ingest'e taşır, yani yeni bir kavram getirmez; (iii) A, C'nin çözdüğünü çözer ama
`fold=1`'i adreslenemez bırakır; (iv) B en ucuzdur ama sessiz bir saati kalıcılaştırır ve
Karar 2/B ile birleştiğinde bundle'ın hangi zone varsayımı altında derlendiği **hiçbir yerde**
yazılı olmaz — iki "hiçbir şey yapma" birbirini besler.

**Geriye dönüklük (A veya C seçilirse) ayrı bir alt-karardır** ve K-01 emsali vardır:
`application/queries/timezone_audit.py` zaten "yanlış varsayımla saklanmış revision'ları
bulma" işini yapan bir yüzeydir. Yeni kural yalnız yeni revision'lara mı uygulanır, yoksa bu
denetim geriye doğru da koşturulur mu — imza satırında ayrı kutu.

### İMZA SATIRI

**Karar 3 — DST fold/gap:**

`[ ] A (fold+gap blocker)`  `[ ] B (mevcut davranış kanonik, imzalı sapma)`
`[ ] C (DST-zone custom kaynaklarda offset zorunlu)`  `[ ] D (kapsam kapısı — #559 AÇIK kalır)`
`[ ] D + C`  `[ ] D + A`

Alt-karar — kapsam: `[ ] yalnız yeni revision (ingest/approval)` `[ ] geriye dönük audit de (`timezone_audit.py`)`

**Hüküm onayı** — bu belgenin (a) hükmü kabul ediliyor mu (*#559 blokluyor, ama yalnız
mixed-zone kapsamını; eksen aritmetiğini değil*)? `[ ] evet` `[ ] hayır (gerekçe: ______)`

karar veren: ________________  tarih: ____________

---

## Bu belgenin kapsamadıkları (dürüst sınır)

- **Hiçbir kod değiştirilmedi.** Bu oturumda `backend/src`, `frontend/src`, migration ve test
  ağacına dokunulmadı.
- **Hiçbir issue kapatılmadı, açılmadı, etiketlenmedi.** #552 / #558 / #559 olduğu gibi
  bırakıldı.
- **Suite koşulmadı.** Bu belge yalnız `docs/` ekler; `Backend`/`Frontend` job'ları için
  otorite CI'dır.
- **Kabul borcu ratchet'i (`docs/audit/acceptance_coverage_baseline.json`) değişmedi** —
  hiçbir kabul kriteri kapanmadı, hiçbir sınıf taşınmadı, hiçbir tavan oynamadı.
- **A-08 blocker'ı bu belgeden etkilenmez.** Blocker sayısı **1** kalır, verdict **BLOCKED**.
- **P1-Gate3 kapanmadı.**
- **E1/E3/E4/E5'in slice tanımları hâlâ repoda değildir** (§"Bu belgede kanıt olarak
  kullanılmayan şeyler"). Yukarıdaki hükümler kod ve kanon yüzeylerine bağlıdır; bir slice
  adına değil.
