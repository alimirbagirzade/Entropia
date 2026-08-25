<!-- doc-status: historical -->
> **DONMUŞ ÖLÇÜM — bu belge ölçtüğü anı dondurur.** Taban `e8a7196`
> (`origin/main`, 2026-08-25). Sonraki bir dalga bu satırları değiştirebilir; güncel
> gerçek için `CLAUDE.md` §Current position ve `docs/generated/repository_facts.md`.

# Financial closure evidence — #550 / #551 / #552

**Verdict: üç kusur da SEVK EDİLMİŞ. Bu dalgada ürün kodu DEĞİŞMEDİ (sıfır satır).**
Tek açık kalem bir kusur değil, **imzasız bir ürün kararıdır**: komisyonun **TABANI**
(§7, PO DECISION REQUIRED).

Bu belge bir *doğrulama* kaydıdır, bir onarım kaydı değil. Görev promptunun taban aldığı
`e2fa521` (2026-08-13) **~150 commit geridedir**; o tabanda üç kusur da canlıydı.

---

## 1. Issue-state truth (ölçüldü, iddia edilmedi)

`CLAUDE.md`'nin HARD RULE'u — *"Issue state kanıt değildir"* — bu dalgada **iki yönde**
uygulandı: kapalı olmaları düzeltildiklerini kanıtlamaz, ama kod ölçülünce **gerçekten**
düzeltilmiş çıktılar.

| Issue | GitHub state | Kapatan PR | Kodda ölçülen |
|---|---|---|---|
| #550 yüzde sizing | `closed` / `completed` (2026-08-14) | **#720 (MERGED)** | `_percent_of_capital` sevk edilmiş — §3 |
| #551 sıfır-boyut | `closed` / `completed` (2026-08-14) | **#720 (MERGED)** | `engine.py:1587` `size <= _ZERO` — §4 |
| #552 komisyon | `closed` / `completed` (2026-08-14) | **#720 (MERGED)** | `booking.py` per-fill — §5 |

`ENGINE_VERSION` = `backtest-engine-v18-percent-sizing-per-fill-commission`
(`manifest.py:145`), golden defterin `engine_version` alanı ile **birebir aynı**.

**Duplicate fix YAZILMADI.**

---

## 2. Acceptance matrisi

| # | Kabul kalemi | Verdict | Kanıt |
|---|---|---|---|
| 1 | `base=10` gerçekten capitalın %10'u | **PASS** | §3 fiyat süpürmesi |
| 2 | min/max aynı yüzde uzayında | **PASS** | §3.2 |
| 3 | zero-size trade sayısı 0 | **PASS** | §4 |
| 4 | 0-notional interval yok | **PASS** | §4 |
| 5 | commission fixture seçilen modelle birebir | **PASS** | §5 |
| 6 | old Results immutable | **PASS** | §6 |
| 7 | deterministic replay | **PASS** | §6.3 |
| 8 | full financial oracle suite green | **PASS** | 148 oracle + 2 golden = **150 passed** |
| 9 | no unrelated digest movement | **PASS** | üretim kodunda sıfır satır → 50 digest el değmedi |

---

## 3. #550 — yüzde semantiği

### 3.1 base_position_size

Kanonik okuma NOTIONAL'ı sabitler, birim sayısını fiyata bırakır; eski (birim) okuma
tersini yapardı. **100× fiyat süpürmesi** ikisini ayırt eder — `peak_notional`
`position_intervals`'tan, yani gerçek fill'den okundu (`base_position_size = 10`,
sermaye 10 000):

| fiyat | ölçülen `peak_notional` | ima edilen birim |
|---|---|---|
| 102 | `1000.00` | 9.803921568627450980392156863 |
| 1 000 | `1000.00` | 1.00 |
| 10 000 | `1000.00` | 0.10 |

Notional **değişmiyor**, birim sayısı değişiyor → **yüzde okuması sevk edilmiş**.
Bu tablo issue #550'nin *"canon notional"* sütununun **birebir** karşılığıdır
(orada da 102 → 9.8039 birim, 10 000 → 0.1 birim).

Eski okuma bu süpürmede `units == 10` sabit verirdi ve fiyat 10 000'de notional
**100 000** — hesabın **10 katı** — olurdu. Ölçülen değer o değil.

### 3.2 min / max aynı uzayda

| kurulum | p=102 | p=1 000 | p=10 000 | beklenen |
|---|---|---|---|---|
| `base=10`, limitsiz | `1000.00` | `1000.00` | `1000.00` | 1000 |
| `base=10`, `max=5` | `500.00` | `500.00` | `500.00` | 500 (%5) |
| `base=10`, `min=20` | `2000.00` | `2000.00` | `2000.00` | 2000 (%20) |

Cap ve floor **notional'ı sabit tutuyor** → limitler de yüzde uzayında.

> **Ölçüm tuzağı, kayda geçsin:** ilk koşumda üç satır da `1000.00` çıktı ve bu bir
> **FAIL gibi göründü**. Sebep üründe değil **probe'daydı**: şema anahtarı `limits` değil
> **`position_size_limits`** (`config.py:740`) ve pydantic fazladan anahtarı sessizce
> attı. Kusur olarak raporlanmadan önce şema okundu. *Yeşil bir negatif kontrol çoğu
> zaman hiç uygulanmamış bir kontroldür* — burada tersi: kırmızı görünen bir ölçüm hiç
> kurulmamış bir konfigürasyondu.

### 3.3 Geçiş kapısı (option A, madde 4)

Kayıtlı revizyon **taşınamaz** (`50` birim, 102 fiyatta hesabın %51'i, 10 000 fiyatta
%5000'i) → sessiz yeniden yorum yerine **görünür kapı**:

* `readiness/validators.py:471` → `STRATEGY_SIZING_SEMANTICS_UNCONFIRMED`, `BLOCKER`.
* Kapı **ALAN tabanlı, metot değil**: yalnız üç büyüklükten birini **taşıyan** revizyon
  bloklanır (`carries_magnitude`); limitsiz risk/Kelly stratejisi kullanıcının
  eyleme çeviremeyeceği bir gürültü almaz.
* **Kapı çıkışı var ve pinli** — `frontend/src/lib/strategyForm.ts:627` kaydederken
  `size_semantics: "percent_of_capital"` damgalar, `strategyForm.test.tsx:191` bunu
  assert eder. Çıkışı olmayan bir blocker kalıcı kilit olurdu; **değil**.

---

## 4. #551 — sıfır/negatif boyut fail-closed

`engine.py:1587` — guard `alloc_on`'dan **bağımsız** (eskiden yalnız allocation altında
koşuyordu, yani **varsayılan bağımsız mod** hayalet 0-boyut pozisyon açıyordu).

Dört yol **tek** bir kapıdan geçiyor; her biri için üç düzlem birden ölçüldü:

| kurulum | trade | interval | 0-notional iv | `entry_blocked` reason |
|---|---|---|---|---|
| `base = 0` | 0 | 0 | 0 | `size_resolved_to_zero` |
| `base = -10` (**negatif**) | 0 | 0 | 0 | `size_resolved_to_zero` |
| `min=20 > max=5` (boş pencere) | 0 | 0 | 0 | `size_resolved_to_zero` |
| `max = 0` | 0 | 0 | 0 | `size_resolved_to_zero` |
| **KONTROL** `base = 10` | **1** | **1** | 0 | — (`entry_fill`) |

* **Reason deterministik ve TEK**: dört yolun dördü de `detail.reason ==
  "size_resolved_to_zero"` yayımlıyor (`signal_events` → `entry_blocked`). Kontrol
  satırı fill'e gidiyor, yani kapı her şeyi engellemiyor.
* **`peak_notional = 0` cross-item conflict üretemez** — tek `PriorItemInterval`
  üreticisi `build_prior_intervals` ve pozitif olmayan pencereyi kapıdan **önce**
  düşürüyor; `test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional`
  yeşil (ayrıca koşuldu).
* **Negatif değer bilerek kapsam içinde**: saklanan `-5` eskiden −5 birimlik bir long
  açıp, pozisyonun **lehine** hareket eden barda ZARAR yazıyordu (boyutun işareti PnL'i
  ters çeviriyor). `<= _ZERO` bunu da kapsıyor.

**Ölçülmüş sınır (kapatılmadı):** `min > max` şemada **reddedilmiyor**, motorda
fail-closed çözülüyor. Prompt bunu *"mümkünse daha erken reddedilmeli"* diye
istiyordu; gözlenebilir sonuç (0 trade, 0 interval) kabul kalemlerini karşılıyor, ama
red **admission'da değil execution'da**. `risk_percentage_per_trade = 0` buna karşılık
**şemada** reddediliyor (`ValidationError`) — yani iki büyüklük iki ayrı katmanda
korunuyor. Bu bir **tutarsızlık kaydıdır**, sevk edilmiş bir kusur değil.

---

## 5. #552 — komisyon MODELİ (per-fill)

Issue'nun repro'su birebir koşuldu: 102'de long, `commission = 7`,
`close_percentage = 40`, aftermath `move_stop_to_entry`; %40 lot 99'da, kalan 30 birim
başabaş 102'de stop.

| model | partial lot | kalan | toplam komisyon | final_equity |
|---|---|---|---|---|
| eski (sevk edilen değil) | 14.00 × 0.4 = 5.60 | 14.00 | **19.60** | 9920.40 |
| tek round-trip (docstring iddiası) | — | — | **14.00** | — |
| **per-fill (SEVK EDİLEN, PD-2)** | 7.00 | 7.00 (+ giriş 7.00) | **21.00** | **9919.00** |

Ölçülen: `[t.pnl for t in out.trades] == [-67.00, -7.00]`, `final_equity == 9919.00`
→ **üç fill, üç komisyon**. `booking.py:111` artık düz `commission_lot =
costs.commission`.

Prompt'un TESTS maddesi — *"bug'ı pinleyen eski oracle isimlerini canonical
expectation'a dönüştür"* — **zaten uygulanmış**: eski
`..._pays_commission_in_proportion_but_the_final_close_pays_a_full_one` adı
`test_every_fill_pays_one_commission_entry_included` olarak yeniden yazılmış ve
docstring eski aritmetiği tarihsel kayıt olarak taşıyor.

---

## 6. Version boundary

| gereklilik | durum | kanıt |
|---|---|---|
| `ENGINE_VERSION` bump | **VAR** | `...-v18-percent-sizing-per-fill-commission` |
| execution-key namespace shift | **VAR, ölçüldü** | §6.1 |
| golden digest refresh | **VAR** | 50 digest, defterin `engine_version`'ı eşleşiyor |
| historical Results unchanged/readable | **VAR, ölçüldü** | §6.2 |

### 6.1 Namespace gerçekten kayıyor

`build_run_manifest` aynı girdilerle iki kez, yalnız `engine_version` değiştirilerek
çağrıldı:

```
shipped version : fb126e02b513c95bfb9b9f7e9ecd5fef1b9ebde202052f143483eef53acb5a95
other   version : a939d0016cbd5deaef57c761de1db7808e6796d9e6e43c914eebf86d4270b9e5
```

Farklı → sürüm anahtara **giriyor**, yani fix öncesi bir Result bir re-RUN için
**idempotent olarak yeniden kullanılamaz** (INF-04/INF-05). Bu bir docstring iddiası
olarak bırakılmadı, **ölçüldü**.

### 6.2 Eski Results okunabilir kalıyor

`grep` ile ölçüldü: `backend/src` içinde saklanan `engine_version`'ı **güncel sabitle
karşılaştıran tek bir eşitlik kapısı yok** (`engine_version ==` / `!= ENGINE_VERSION`
→ sıfır sonuç). Sürüm her Result'ta **kendi satırında** saklanıyor ve okuma yüzeyleri
(`results_history`, `panel_backtest_log`, `mainboard`, `backtest_run`) onu **geri
okuyor**. Yani eski Result kendi sürümü altında geçerli ve okunabilir; yenisiyle
**kıyaslanabilir değil** — istenen davranış bu.

### 6.3 Deterministic replay

Aynı girdiler, tekrarlanan koşular **ve farklı bar batch sınırları** (motor resumable
bir stepper'dır — batch sınırı bir gözlemlenebilir olsaydı burada görünürdü):

```
repeat  ×3 (batch=8) : 3c9b037b91b9b8e85cd97708b4625abd
batch=1 / 3 / 8 / 64 : 3c9b037b91b9b8e85cd97708b4625abd
```

Tek digest → **PASS**.

---

## 7. PO DECISION REQUIRED — komisyonun TABANI (Karar 1, #552)

> **Prompt'un talimatı:** *"ÖNCE canonical commission modelini kanıtla. Spec açık değilse
> KOD YAZMADAN STOP ve PO DECISION REQUIRED raporu üret. Model kararı yokken test
> expectation uydurma."* — Bu bölüm o raporu üretti ve **kod yazılmadan durdu**.
>
> **SONRA NE OLDU (aynı gün):** rapor ürün sahibine sunuldu ve **Karar 1 2026-08-25'te
> İMZALANDI** — `docs/decisions/closure_product_decisions_2026-08-13.md` §Karar 1 İMZA
> SATIRI. Yani aşağıdaki *"imzasız"* tespiti **bu belgenin yazıldığı ana aittir**; karar
> artık verilmiştir ve uygulaması bu PR'ın ikinci yarısıdır (§11). Bölüm **bilerek
> silinmedi**: kararın hangi ölçümlerin üzerine verildiğini o ölçümler gösterir.

**Ayrım kritik:** komisyonun **DAĞILIMI** (per-fill ↔ round-trip) karara bağlandı ve
sevk edildi (PD-2, #720, §5). Karara bağlanmayan şey **TABANDIR**: komisyon *neyin*
üzerinden hesaplanır.

| kaynak | ne diyor |
|---|---|
| Master Ref, Modül 4 §2.3 (`:3110`) | *"Commission rule … **Notional üzerinden bps bazlı** işlem komisyonu"* — kanonun **tek somut örneği ORAN bazlı** |
| Sevk edilen şema (`config.py:313`) | `commission: Decimal \| None = Field(default=None, description="Per-trade fee")` — **düz tutar**, oran değil |
| Master Ref, Modül 6 §6.2 (`:7425`) | komisyon *"sayısal giriş"*, **birimi konfigürasyonla açık olmalı** — birimi **seçmiyor** |
| Master Ref, Modül 6 §8 (`:7513`) | komisyon **dağılımı** manifestte açık olmalı — dağılımı şart koşar, **tabanı değil** |

Kanon ile sevk edilen şema **çelişiyor** ve kanon kendi içinde tabanı bağlamıyor.
`docs/decisions/closure_product_decisions_2026-08-13.md` §Karar 1 kutusu **BOŞ**
(2026-08-18 tablosunda da `İMZASIZ`).

**Neden sayısal olarak önemli:** düz `7` her işlemde 7'dir; bps tabanı notional ile
ölçeklenir. §3.1'in süpürmesinde notional sabit 1000 olduğu için ikisi orada
ayrışmaz — ama farklı sermaye/yüzde kombinasyonlarında **sınırsız** ayrışır ve
`commission` alanının **birimi** (para mı bps mi) bugün hiçbir yerde beyan edilmiyor.

**Karar verilene kadar hiçbir test beklentisi uydurulmadı.** Bu kalem, `booking.py`'nin
per-fill davranışını **etkilemez** — yalnız `costs.commission`'ın nasıl okunacağını
belirler.

---

## 8. Negatif kontroller — korumaların taşıyıcı olduğu ÖLÇÜLDÜ

Yeşil bir suite, korumanın **pinli** olduğunu kanıtlamaz. Üç koruma tek tek kaldırıldı;
her seferinde ağaç **bellekteki anlık görüntüden** geri yazıldı (`git checkout --`
KULLANILMADI — ADIM 111'de o, commit edilmemiş çalışmayı silmişti; `finally`'ye de
güvenilmedi — SIGTERM'de koşmaz, ADIM 100).

| kontrol | kaldırılan | oracle-only sonucu (golden HARİÇ) |
|---|---|---|
| NC-1 | `engine.py` `size <= _ZERO` guard'ı | **RED** — `test_oracle_sizing.py::test_an_unallocated_item_gets_no_sleeve_and_therefore_no_fill` |
| NC-2 | per-fill komisyon → eski `*2 if is_full else *2*fraction` | **RED** — `test_oracle_position_lifecycle.py::test_every_fill_pays_one_commission_entry_included` |
| NC-3 | `_percent_of_capital` → eski birim okuması | **RED** — `test_oracle_sizing.py::test_no_leverage_normalizes_to_one_x_whatever_multiplier_is_saved` |

**Golden defter bilerek kapsam dışı bırakıldı.** Üçü de 50-digest'lik golden testi
düşürüyor, ama bu tek başına zayıf bir kanıttır: blanket bir digest **her** değişikliği
yakalar ve hangi iddianın korunduğunu söylemez. Oracle-only koşuda **her kırmızı kendi
konu alanındaki hedefli bir assertion'a** düştü → korumalar yalnız digest'e değil,
**adlandırılmış davranış testlerine** de bağlı.

Her turdan sonra `git status` **boş** (ADIM 100'ün yamalı-ağaç dersi).

---

## 9. Koşulanlar ve DÜRÜST SINIR

**Koşuldu (bu container, taban `e8a7196`):**

* `tests/unit/oracles/` → **148 passed**
* `tests/unit/oracles/` + `test_backtest_engine_golden.py` → **150 passed**
* geniş finansal birim yüzeyi (`-k "backtest or sizing or booking or engine or portfolio
  or oracle or strategy_config"`) → **1185 passed, 1279 deselected**
* `test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional` → passed
* üç negatif kontrol + baseline (§8)

**KOŞULMADI — otorite CI:**

* **Tam backend suite ve coverage kapısı.** Bu dalgada `backend/src`'te **sıfır satır**
  değişti, ama *"tam suite yeşil"* iddiası **edilmiyor**. Alt küme koşuları `--no-cov`
  iledir; coverage yüzdesi ve **geçen** toplam sayının tek otoritesi bir CI koşusudur.
* **Integration / contract / e2e.** Postgres kurulmadı — bu dalga ürün kodu değiştirmediği
  için gerekmedi, ama sayı **iddia edilmiyor**.
* **Tüm frontend kapıları.** `frontend/src`'te sıfır satır değişti; `strategyForm.test.tsx`
  **okundu** (§3.3), **koşulmadı**.

**Bu dalganın diff'i yalnız bu dosyadır.** Ürün kodu, test kodu, migration, `ENGINE_VERSION`,
OpenAPI ve kabul borcu tavanları **el değmedi**.

---

## 10. Sonuç

* **#550 / #551 / #552: üç kusur da kapalı ve kapalılıkları ÖLÇÜLDÜ** — issue durumuna
  değil, sevk edilen davranışa bakılarak. Duplicate fix yazılmadı.
* **Dokuz kabul kaleminin dokuzu da PASS.**
* **Komisyonun tabanı (§7) bu oturumda İMZALANDI** ve uygulandı — §11.
* Paylaşımlı portföy wiring'ine **dokunulmadı** (promptun kapsam sınırı).


---

## 11. Karar 1 imzalandı ve uygulandı (2026-08-25, aynı oturum)

§7 bir **PO DECISION REQUIRED** raporuydu ve kod yazmadan durdu. Rapor sunuldu, ürün
sahibi kararı verdi; bu bölüm **kararın kendisini değil, uygulamanın ölçümlerini** kaydeder.
Kararın metni ve gerekçesi `docs/decisions/closure_product_decisions_2026-08-13.md`
§Karar 1'dedir (**otorite orasıdır**).

**İmzalanan:** eksen **İKİYE** ayrıldı — **dağılım** = per-fill (#720 zaten sevk etti, imza
onaylar) · **taban** = `commission_basis: flat|bps`, **varsayılan `flat`**.

**Neden tam bps değil:** tam C, saklanan `commission: 7`'nin anlamını değiştirirdi
(*7 para birimi* → *7 bps*) ve bu **mekanik olarak çevrilemez** — #550'nin birebir ikizi,
ki o bir Ready Check blocker'ı gerektirmişti. Varsayılanı `flat` olan bir mod alanı göçü
**gerektirmez**: her kayıtlı revizyon anlamını korur. Ayrıca #550'de UI `%` diyordu (4 kaynak
↔ 1 motor), burada **UI de mockup da birimi hiç söylemiyor** → kullanıcıya bps hiç vaat
edilmedi.

### Ölçümler

| iddia | ölçülen |
|---|---|
| varsayılan hiçbir sayıyı oynatmaz | komisyon fiyatlayan **iki** golden senaryo bayt bayt aynı → **`ENGINE_VERSION` bump'ı GEREKMEDİ** |
| `bps` kanonun formülünü uygular | giriş notional `1000.00` → `0.70`; çıkış `952.38` → `0.67`; **toplam `1.37`** (aynı büyüklük `flat` iken `14.00`) |
| oranda lineer | 7 bps → `1.37`, 50 bps → `9.76` |
| tek türetim | **altı** ücret yerinin altısı `FillCosts.fee()`'den geçer (3 `booking`, 3 `engine`: giriş / stacking / scale layer) |

### Negatif kontroller (üçü de ayırt edici)

| kontrol | kusur | kırmızı |
|---|---|---|
| NC-1 | varsayılan `bps`'e çevrildi | dört mevcut komisyon oracle'ı → **varsayılan taşıyıcı** |
| NC-2 | `flat` notional ile ölçeklendi | mevcutlar + yeni `flat` testi → **iki taban ayrı** |
| NC-3 | giriş yeri kendi tabanını inline etti | **yalnız iki yeni `bps` testi**; flat + golden **yeşil** |

**NC-3 asıl derstir:** böyle bir kusur `flat` altında **görünmez**, çünkü orada notional zaten
yok sayılır. Mevcut suite'in yeşil kalması boşluğun **ölçümüdür** — tek türetim kuralı bu
yüzden vardır ve #552'nin ilk kusuru (bir yerin kendi tabanını hesaplaması) tam bu şekildi.

### AÇIK KALAN — `execution_content.commission_model` (K1 rider'ı)

İmzanın zorunlu eki bu alanı **`execution_key` İÇİNDE** istiyor, gerekçesi: *"aksi halde iki
farklı ücret modeliyle üretilmiş iki run aynı reprodüksiyon kimliğini paylaşır."*
**Bu gerekçe ÖLÇÜLDÜ ve TUTMUYOR:** `_pinned_items` `selected_revision_id`'yi hash'ler,
`commission_basis` değişince yeni revizyon doğar → anahtar zaten ayrışır
(`a8d36214…` ≠ `b7c4a61b…`). Yani taban execution_key'e **transitif** ulaşıyor.

Alanı `execution_content`'e koymanın **ölçülmüş bedeli**: her execution_key kayar — hiçbir
sayı oynamadan, hiçbir sürüm bump'ı olmadan → **beyan edilmemiş** bir namespace kayması,
oysa bu depoda o kaymayı `ENGINE_VERSION` bildirir. K1'in istediği *"manifestte açık"* şartı
alan manifest'te olduğu sürece karşılanır; `mainboard_item_labels` tam bu emsaldir
(manifest'te, `execution_content` **dışında**, gerekçesi yazılı).

**Alan bu PR'da EKLENMEDİ** ve bu bir eksiklik değil, bir **bekleyen adjudication**'dır:
imzanın harfi ile ölçülen gerçek ayrıştı, ve bunu tek taraflı çözmek imzayı sessizce yeniden
yazmak olurdu. Üç seçenek ürün sahibine sunuldu (dışarı koy / içeri + bump / içeri + bump yok).

### Dürüst sınır

**Frontend'e `commission_basis` seçici EKLENMEDİ, bilerek:** v18 mockup görsel otoritedir
(`CLAUDE.md` §UI) ve `:5621` Commission'ı birimsiz tek bir input olarak çizer — mockup'ta
olmayan bir alan eklemek bir **sapmadır**. Bugün `bps` API üzerinden ayarlanır; UI'ye
taşımak bir mockup güncellemesi ister. **OpenAPI regen GEREKMEDİ** (ölçüldü: `CostsModel`
snapshot'ta yayımlanmıyor, drift kapısı `exit 0`) — imzanın maliyet tahmini bu kalemde
fazlaydı.
