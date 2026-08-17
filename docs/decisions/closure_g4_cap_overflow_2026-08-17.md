# Max Single Position cap taşması — hangi disposition? (G4)

> **Bu belge KARAR BEKLİYOR.** G4, `final_closure_ordered_plan_2026-08-13.md` §2'nin
> *"imzalanacak bir bloğu olmayan iki kapı"*sından biridir. Diğeri G15'ti; **o blok
> 2026-08-17'de yaratıldı** (`closure_g15_external_row_winner_2026-08-17.md`, PR #747).
> Bu belge **kalan** bloğu yaratır ve **hiçbir seçeneği seçmez**.
> `closure_product_decisions_2026-08-13.md` §Karar 1/2/3 ile aynı yapıdadır; G15 belgesiyle
> aynı disiplini uygular: seçenek elenmez, **"önerilen" yazılmaz**.

- **Tarih:** 2026-08-17
- **Base:** `origin/main` @ `0f0651d5d97136bc8879f44606f5da1642039307`
  (`docs(closure-g15): brief which external-import row Ready Check must read (#747)`)
- **Branch:** `docs/closure-g4-cap-overflow-brief`
- **Kapsam:** `max_position_size` cap'i **entry yolunda** aşıldığında ne olacağı
- **Yazarın rolü:** hazırlık. **Bu belgede hiçbir karar verilmemiştir.**
- **İlgili kapı:** G4 (ordered plan §2) = STOP-GATE 4 (`closure_design_financial_research_2026-08-13.md` §5).
  **Bloklar:** slice **F2** (ordered plan §3: *"Prerequisites: G4 — and G4 has no signature
  block yet. A brief must be written first. **Do not start.**"*)
- **Numara verilmedi, bilerek.** `closure_product_decisions_2026-08-13.md` bugün **beş** karar
  taşıyor (Karar 4 = G9, Karar 5 = G13, ikisi de 2026-08-17'de eklendi) ve G15 belgesi kendi
  bloğunu *"Karar 4"* diye numaralandırdı — yani **"Karar 4" adı bu depoda zaten iki ayrı şeye
  işaret ediyor.** Üçüncü bir çakışma üretmemek için bu blok **kapı koduyla (G4)** adlandırıldı.

---

## Taban notu (dürüstlük)

Bu slice'ın brifing talebi tabanı **`df7df92`** olarak veriyordu. Ölçülen taban **`0f0651d`** —
sekiz commit ileride. **Fark bu belge için maddidir**, çünkü G4'ün tamamı kod yüzeyine bağlıdır.
Bu yüzden **aşağıdaki her ölçüm `0f0651d` üzerinde yeniden yapılmıştır**; hiçbiri P-C1
tasarımından, ordered plan'dan veya slice talebinden **kopyalanmamıştır**. Devralınan üç iddia
**yanlışlandı** — §"Bu belgenin düzelttiği devralınmış iddialar".

Satır numarası **bilerek yazılmamıştır** (`CLAUDE.md` §Conventions: sembol adı yaz). Bu belgedeki
her kod göndermesi bir **sembol** adıdır; her kanon göndermesi bir **bölüm** adıdır.

## Bu belgede kanıt olarak kullanılmayan şeyler

- **Üretim veritabanı.** Bu oturumun üretim verisine erişimi **yoktur** ve yerelde koşan bir
  Postgres de yoktur. §ÖLÇÜM 2 bunu bir tahminle doldurmaz; **sayılamadığını ve neden
  sayılamadığını** yazar.
- **Test adları.** Aşağıdaki hiçbir hüküm bir test adına dayanmaz.
- **Suite.** Ürün kodu değişmediği için `pytest` **koşulmadı** (§"Bu belgenin kapsamadıkları").
- **`_clamp_to_limits`'in docstring'i.** Davranışı **doğru** tarif ediyor (*"pulled DOWN to
  `max`"*). Bir niyet beyanı değil, bir tarif — ama yine de **kanon değildir** ve §10.2'nin
  *"clamp değil"* hükmünü karşılamaz. Kodun kendi yorumu kendi meşruiyetini üretmez.

## Bu belgenin düzelttiği devralınmış iddialar

Üçü de yeniden ölçüldü ve **yanlış çıktı**. Kaydedilir, çünkü ikisi imza maliyetini
**olduğundan pahalı** gösteriyordu.

| # | Devralınan iddia | Kaynak | Ölçülen gerçek |
|---|---|---|---|
| 1 | *"OpenAPI: yalnız (B) — `PositionSizeLimits` yayımlanmış bir component."* | P-C1 §2.1, slice talebi | **YANLIŞ.** `docs/openapi.json`'da **157 schema** var; `PositionSizeLimits`, `PositionSizing`, `StrategyConfig` **hiçbiri yok** (grep = 0). Strateji config'i API sınırını `payload` / `initial_payload` olarak, `additionalProperties: true` ile geçiyor. **Hiçbir disposition OpenAPI drift guard'ını tetiklemez.** |
| 2 | *"Karar dokümanı ÜÇ brifing taşıyor."* | slice talebi | **BAYAT.** Bugün **beş** taşıyor: Karar 4 (G9, ADR §6/§8 amendment) ve Karar 5 (G13, P10 equity noktası) 2026-08-17'de eklendi. Üçü değil, **beşinin** yapısı aynalandı. |
| 3 | *"Açık kalan: G15 — HÂLÂ sahipsiz."* | slice talebi | **BAYAT.** G15'in imza bloğu **bu belgeden önce yaratıldı** (`closure_g15_external_row_winner_2026-08-17.md`, PR #747, bu belgenin tabanı). G15 **hâlâ imzasızdır** ama artık **sahipsiz değildir** — imzalanacak bir yeri vardır. G4 bu tarifin geçerli olduğu **son** kapıydı. |

**Devralınıp DOĞRULANAN her şey** ayrıca ölçüldü ve aşağıda ölçüm olarak geçer: `ENGINE_VERSION`
üçünde de bump'sız, migration üçünde de yok, `size_semantics` emsali, ve ölçülmüş yokluk
(`grep -rn max_position_size backend/src/entropia/domain/readiness/` → **tek hit**, o da
`carries_magnitude` predicate'i).

---

## Karar — Max Single Position cap taşması (G4)

### Canonical ne diyor

Kanon bu soruyu **beş yerde** ele alıyor. Dördü aynı yönü gösteriyor; **çelişki sanılan şey
bir kaynak farkı değil, bir suskunluk farkıdır.**

| # | Kaynak | Literal (alıntı, parafraz değil) | Ne söyler |
|---|---|---|---|
| K1 | **Master Ref §10.2**, *Max Single Position* satırı, Validation kolonu | *"Base veya formula sonucu bu limiti aşarsa **clamp değil** blocker veya explicit cap policy uygulanır."* | Taşmanın dispozisyonunu **adıyla** sınırlar: clamp **değil**. İki meşru sonuç bırakır: **blocker** ya da **explicit** cap policy. |
| K2 | **Master Ref §10.1**, *Base Position Size* satırı, Kesin kurallar kolonu | *"Resolved capitalın yüzdesi. Pozitif olmalı; **Max Single Position ve Max Total Exposure ile uyumlu olmalı**."* | **Base alanının kendisine** bir uyumluluk şartı koyar. Bu bir **statik** kural okunuşudur — yani bir Ready Check karşılaştırması. P-C1 bu satırı **hiç alıntılamamıştı**; disposition (A)'nın en doğrudan kanon dayanağıdır. |
| K3 | **doc 02**, alan tablosu | *"`sizing.base_position_size.percent` or typed unit; **<= Max Single Position** and subject to allocation/exposure cap."* | Yine **statik** bir kısıt (`<=`), runtime clamp'i değil. K2'yi ikinci bir belgede tekrar eder. |
| K4 | **doc 02**, ⓘ *Max Single Position* paneli | *"Tek bir pozisyonun ulaşabileceği maksimum büyüklüğü sınırlar. Base Position Size, Risk Per Trade veya Custom Formula daha büyük bir miktar hesaplamış olsa bile **bu sınır aşılmaz**. Örnek: Max Single Position %25 ise … tek pozisyon equity'nin %25'inden büyük açılamaz."* | **Yalnız sonucu** şart koşar (*sınır aşılmaz*), **yolu** söylemez. Sessiz bir clamp bu cümleyi **karşılar**. Kanonun tek suskun yeri budur. |
| K5 | **Master Ref**, Equity Allocation sleeve satırı | *"Bir Strategyin talep ettigi size, bu sleeve sinirini asiyorsa motor sizei **caplar veya orderi reddeder**; kullanicinin veya Agentin niyet ettigi risk kurali sessizce asla asilir."* | **Cap'lemeye izin SLEEVE'e açıkça VERİLMİŞTİR.** K1 aynı izni Max Single Position'dan **esirger**. Yani *"motor zaten başka yerde clamp'liyor"* bir argüman **değildir** — o clamp'in izni ayrıca yazılmıştır. |

**Ve kanon aynı hükmü ALTINCI kez, başka bir eksende tekrar ediyor** — bu belgenin ölçtüğü ve
P-C1'in kaydetmediği şey:

| # | Kaynak | Literal | Ne söyler |
|---|---|---|---|
| K6 | **Master Ref §11.4**, *Exposure bağlanması* | *"Exposure limitini aşan layer **otomatik olarak "kırpılıp" açılmaz**; strategy policy açıkça partial layer desteklemiyorsa **candidate reddedilir ve ledgerda reason kaydedilir**."* | Aynı refleks, ölçek ekseninde: **kırpma yok; reddet ve SEBEBİ KAYDET.** |

> **Hüküm (a) — kanon çelişmiyor; kanon iki kez aynı şeyi söylüyor ve bir kez susuyor.**
> K1 (§10.2) ve K6 (§11.4) **aynı hükmü** verir: sessizce küçültme, reddet ve sebebi kaydet.
> K2/K3 bunu statik bir alan kuralı olarak tekrar eder. **Yalnız K4 susar** ve sessiz clamp
> yalnız o suskunluğa sığar. Slice talebinin *"iki kanon kaynağı çelişiyor"* çerçevesi bu
> ölçümle **daralır**: çelişen iki kaynak değil, **dört açık hüküm ve bir suskunluk** vardır.

### Kod şu an ne yapıyor (sembol)

**Sizing zinciri — tek yol, tek clamp noktası:**

```
execution/sizing.py::planned_size
  -> ::_effective_fill              (spread + slippage ÖNCE)
  -> ::_position_size
     -> ::_raw_position_size        -> ::_percent_of_capital   (base -> quantity)
     -> * ::_leverage_multiplier * strength                    (KALDIRAÇ BURADA)
     -> ::_clamp_to_limits          -> ::_percent_of_capital   (cap -> quantity)
  -> ::_cap_to_sleeve               (yalnız allocation)
```

`_clamp_to_limits` gövdesi, taşma dalı **birebir**:

```python
if maximum is not None:
    cap = _percent_of_capital(maximum, equity, entry_price)
    if cap is not None and size > cap:
        size = cap
```

**Bir atama. Dönüş değeri bir `Decimal`. Emitilen event yok, sayaç yok, restriction-trace
token'ı yok, diagnostics warning'i yok.** Çağıran `planned_size` de bir `Decimal` döndürür.
Cap'in bağladığı bilgi **fonksiyondan çıkmaz**.

**Karşılaştıran validator — ölçülmüş yokluk (yeniden ölçüldü):**

```
grep -rn "max_position_size" backend/src/entropia/domain/readiness/
  -> domain/readiness/validators.py: TEK hit
     ve o hit `carries_magnitude` predicate'i (size_semantics geçiş kapısının kapsamı)
grep -rn "position_size_limits" backend/src/entropia/domain/readiness/
  -> TEK hit, aynı predicate'in okuduğu satır
```

**`base_position_size`'ı `max_position_size` ile karşılaştıran hiçbir validator yoktur.**
K2 ve K3'ün istediği statik uyumluluk kuralı **hiçbir yerde uygulanmıyor.**

**Geçiş kapısı emsali (disposition (B)'nin `None` sorusunun bire bir emsali):**
`domain/strategy/config.py::PositionSizing.size_semantics` —
`Literal["percent_of_capital"] | None`, ve `domain/readiness/validators.py`
`Code.STRATEGY_SIZING_SEMANTICS_UNCONFIRMED` (`Sev.BLOCKER`, `Scope.STRATEGY`) `None`'ı
*"bu soru sorulmadan önce kaydedilmiş"* diye okuyup **RUN'ı bloklar**, sessizce
varsaymaz.

---

### ÖLÇÜM 1 — motor bu cap'i ÜÇ yolda bağlıyor ve **ÜÇÜ AYNI ŞEYİ YAPMIYOR**

**Bu belgenin çekirdek bulgusu budur ve hiçbir belge bunu yazmıyor.** Tek bir config alanı —
`position_size_limits.max_position_size` — üç ayrı yerde bağlanır. **İkisi reddeder ve sebebi
kaydeder; biri sessizce kırpar.**

| Yol | Cap'i okuyan sembol | Taşmada ne olur | Gözlemlenebilir mi | Kanon dayanağı |
|---|---|---|---|---|
| **Entry** (ana yol) | `sizing.py::_clamp_to_limits` | **SESSİZ CLAMP** — `size = cap` | **HAYIR** — hiçbir event, sayaç veya token yok | K1 bunu **yasaklıyor** |
| **Scaling ladder** | `sizing.py::max_position_size_cap` → `scaling.py::resolve_scale_rejection` | **REDDEDER** — `("position_size_limit", str(cap))` | **EVET** — `engine.py` `_emit("scale_layer_rejected", …)` + `state.py::_Ledger.scale_layers_rejected` sayacı, `output.py` ile **Result'a çıkar** | K6 (§11.4) |
| **Stacking tranche** | `sizing.py::max_position_size_cap` | **REDDEDER** — `stack_reject = "position_size_limit"` | **EVET** — `_emit("stack_entry_rejected", …)` `detail` içinde `reason` + `cap` + `candidate_size`, `_Ledger.stack_entries_rejected` sayacı | K6 (§11.4) |

`scaling.py::resolve_scale_rejection` docstring'i bunu **kendi kaydediyor**:

> *"An over-cap layer is **REJECTED, never auto-trimmed to fit** (§11.4 exposure binding)."*

> **Hüküm (b):** *"§10.2'nin istediği disposition motorda yok"* **YANLIŞTIR.** O disposition
> motorda **zaten var, sevk edilmiş ve test edilmiş durumda** — yalnız **entry yolunda
> uygulanmıyor**. Bu, G4'ü *"kanonun istediği yeni bir davranışı tasarla"* sorusundan
> *"sevk edilmiş bir davranışı üçüncü yola da uygula mı"* sorusuna **indirger**.
>
> **İki doğrudan sonucu var ve ikisi de imza maliyetini değiştirir:**
> 1. **Yeni kavram, yeni altyapı, yeni sözlük GEREKMEZ.** `position_size_limit` reason
>    token'ı, emit mekanizması, ledger sayacı ve Result yüzeyi **hepsi sevk edilmiş**.
> 2. **Disposition (C) — "sevk edileni kanonik ilan et" — artık tek bir davranışı değil, bir
>    TUTARSIZLIĞI kanonik ilan eder.** İmzalanırsa imzalanan cümle şudur: *"aynı config alanı,
>    aynı run içinde, hangi yolda bağlandığına göre bir kez sessizce kırpar, iki kez reddeder;
>    bu böyle kalsın."* Bu meşru bir imzadır ama **bedeli budur** ve imza metninde böyle
>    yazılmalıdır.

### Çelişki tam olarak nerede

Üç ayrı çelişki var; ordered plan ve P-C1 yalnız birincisini adlandırıyor.

**Ç1 — §10.2'nin *"clamp değil"*i entry yolunda ihlal ediliyor.** K1 iki meşru sonuç veriyor
(blocker / **explicit** cap policy); sevk edilen üçüncü bir şey yapıyor: **implicit** cap.
K4'ün suskunluğu bunu **karşılar**, K1 **karşılamaz**.

**Ç2 — motor kendi içinde tutarsız (§ÖLÇÜM 1).** Ordered plan ve P-C1'de **yok**; burada
ölçüldü. Kanon (K1 + K6) tutarlı; **sapan taraf koddur** ve üçte ikisi zaten kanona uyuyor.

**Ç3 — K2/K3'ün statik kuralı hiç uygulanmıyor.** İki kanon kaynağı `base <= Max Single
Position`'ı bir **alan kuralı** olarak yazıyor. Bu ne entry'de (orada runtime clamp var), ne
Ready Check'te (orada karşılaştırma **yok**) uygulanıyor. **Bu, disposition (A)'nın kapattığı
ve (B)/(C)'nin kapatmadığı ayrı bir açıktır** — bir cap policy runtime'da doğru davransa bile
K2'nin *"uyumlu olmalı"* şartı bir **kaydetme-zamanı** şartıdır.

---

### ÖLÇÜM 2 — BLAST RADIUS (disposition A) → **SAYILAMADI**

**Disposition (A) imzalanırsa bugün clamp'lenerek koşan kaç kayıtlı revizyon Ready Check'te
düşer? — Bu oturum bunu sayamadı.**

**Neden sayılamadı (tahmin edilmedi, gerekçesi yazıldı):**

1. Bu oturum **efemer bir container**'da koşuyor; **üretim veritabanına erişimi yok** —
   `DATABASE_URL` / `POSTGRES_*` **tanımsız** (ölçüldü), ağ yolu ve kimlik bilgisi yok.
2. **Yerelde koşan bir Postgres de yok** — `pg_isready -h localhost -p 5432` → *"no response"*
   (ölçüldü). G15 belgesinin yaptığı gibi boş bir şema kurup **davranış** probe'u koşmak bu
   soruya zaten cevap **veremezdi**: soru bir davranış değil, bir **veri sayımı**dır.
3. Repoda bu sayıyı taşıyan **üretilmiş bir artefakt yok**: `docs/generated/repository_facts.md`
   şema/route/test **sayılarını** üretir, saklanan **satır** sayılarını değil.

**Sayının imzadan ÖNCE alınması gerekir. Sorgu şudur** (salt-okuma; `strategy_revision.payload`
JSONB'dir ve `StrategyConfig`'i taşır — `infrastructure/postgres/models/strategy.py::StrategyRevision`):

```sql
SELECT count(*) AS newly_blocked
FROM strategy_revision
WHERE (payload -> 'position_sizing' ->> 'size_semantics') = 'percent_of_capital'
  AND (payload -> 'position_sizing' ->> 'base_position_size') IS NOT NULL
  AND (payload -> 'position_sizing' -> 'position_size_limits' ->> 'max_position_size') IS NOT NULL
  AND (payload -> 'position_sizing' ->> 'base_position_size')::numeric
      > (payload -> 'position_sizing' -> 'position_size_limits' ->> 'max_position_size')::numeric;
```

**`size_semantics = 'percent_of_capital'` şartı ihmal edilemez ve blast radius'u ÖLÇÜLEBİLİR
şekilde daraltır** — bu, sayı alınmadan bile bilinen bir gerçektir ve kaydedilir:

> `size_semantics IS NULL` olan **her** revizyon **bugün de** `STRATEGY_SIZING_SEMANTICS_UNCONFIRMED`
> (BLOCKER) ile **zaten bloklu**. Böyle bir revizyona (A) **ikinci** bir blocker ekler, ama onu
> READY'den BLOCKED'a **taşımaz** — verdict'i zaten BLOCKED'dır. Yani (A)'nın **artımlı** blast
> radius'u yalnız *"geçiş kapısını geçmiş **ve** base'i cap'in üstünde olan"* revizyonlardır.
> Üstteki sorgu tam olarak bu kesişimi sayar.

**DÜRÜST SINIR — bu sorgu ALT sınırdır, tam sayı değildir.** Ölçülen üç sebep:

1. **Yalnız `method = "base_position_size"` yolunu görür.** `risk_based_sizing` ve Kelly
   (`_kelly_capital_fraction`) sonuçları **fiyata ve equity'ye bağlıdır** — hangi revizyonun
   cap'i **çalışma anında** aşacağı saklanan payload'dan **hesaplanamaz**. K1 *"Base **veya
   formula sonucu**"* diyor; SQL yalnız base'i görebilir.
2. **Kaldıracı görmez.** Clamp kaldıraçtan **sonra** uygulanır (§ÖLÇÜM 3), yani `base <= cap`
   olan bir revizyon `base × leverage > cap` yüzünden **bugün clamp'leniyor** olabilir.
   Kaldıraç dahil edilirse sorgu `base × leverage`'ı karşılaştırmalıdır — ve bu, (A)'nın
   **hangi büyüklüğü** karşılaştıracağı sorusunu doğurur (imza satırında ayrı kutu).
3. **Ladder'ın `add_size_value`'sunu görmez.** `config.py::ScalingLogic.add_size_value`
   yapılandırılmışsa toplam boyut cap'i ayrıca aşabilir — ama o yol **zaten reddediyor**
   (§ÖLÇÜM 1), yani (A) oraya bir şey eklemez.

> **Bu yüzden §İMZA SATIRI'nın ilk kutusu bir seçenek değil, bu SAYIdır** — G15 belgesinin
> kurduğu emsalin aynısı. (A) bu sayı alınmadan imzalanamaz. (B), (C) ve (D) sayıdan
> **bağımsız** imzalanabilir.

### ÖLÇÜM 3 — İKİNCİ MERTEBE SONUÇ: cap'in üstünde **kaldıraç ATIL**

**Hiçbir belge bunu yazmıyor.** Ölçüldü: `sizing.py::_position_size` önce
`_leverage_multiplier` ile çarpar, **sonra** `_clamp_to_limits` çağırır. Yani clamp
**kaldıraçtan SONRA**dır.

**Sayısal örnek (ZORUNLU).** Equity 10.000, entry price 100, `base_position_size = %10`,
`max_position_size = %25`:

| Kaldıraç | Clamp öncesi boyut | Nominal | Clamp sonrası | Efektif kaldıraç |
|---|---|---|---|---|
| 1x | 10 birim | 1.000 (%10) | **10** (cap bağlamaz) | 1.0x |
| 2.5x | 25 birim | 2.500 (%25) | **25** (tam cap'te) | 2.5x |
| 5x | 50 birim | 5.000 (%50) | **25** | **2.5x** |
| 10x | 100 birim | 10.000 (%100) | **25** | **2.5x** |
| 20x | 200 birim | 20.000 (%200) | **25** | **2.5x** |

**2.5x'in üstünde kaldıraç alanı tamamen ATILDIR.** Kullanıcı kaldıracı 5x'ten 20x'e çıkarır,
**hiçbir sayı değişmez** — ne boyut, ne PnL, ne exposure. Ve **hiçbir yerde hiçbir işaret
yoktur**: ne bir warning, ne bir Result alanı, ne bir Ready Check bulgusu.

> **Bu davranış BUGÜN DOĞRUDUR.** K4 (*"bu sınır aşılmaz"*) ve K1'in *"nominal/sermaye yüzdesi
> limiti"* ifadesi post-leverage nominal'i bağlamayı **destekler**. Yani kaldıracını artırıp
> hiçbir şeyin değişmediğini gören kullanıcı **doğru davranışa** bakıyor — ama bunu
> **öğrenmesinin hiçbir yolu yok**. Sessizlik ile doğruluk burada aynı ekranda duruyor.
>
> **(A) veya (D) imzalanırsa** o kullanıcı sessizlik yerine bir **hata / işaret** alır —
> §10.2'nin *"clamp değil"* ile istediği tam olarak budur. **(C) imzalanırsa** bu sessizlik
> kanonik ilan edilmiş olur.
>
> **Kaldıraç sırasının kendisi bu kararın konusu DEĞİLDİR** ve bu belge onu açmaz: P-C1 onu
> *"bir kanon isminden türetme, bir kanon cümlesinden değil"* diye kaydetti ve öyle bırakıldı.

### ÖLÇÜM 4 — `execution_key`: alan **zaten** pinli; ikinci kez yayımlamak **her** anahtarı kaydırır

Devralınan iddia: *"execution_key: yalnız (B) kaydırır (`execution_content`'e yeni anahtar) →
hiçbir saklanan Result yeniden kullanılmaz."* **Yarısı doğru; eksik olan yarısı imza
maliyetini değiştiriyor.**

Ölçülen yapı (`domain/backtest/manifest.py`):
`execution_key = manifest_hash(execution_content)` ve `execution_content` **dokuz** anahtar
taşır: `composition_fingerprint`, `mainboard_items`, `capital_execution`,
`result_artifact_context`, `engine_version`, `tick_data`, `strategy_package_context`,
`external_object_context`, `data_time_context`.

**Kritik ölçüm:** `mainboard_items`'ın her girdisi
(`application/commands/backtest_run_context.py`) **`strategy_revision_id`'yi pinler**. Strateji
revizyonları **immutable**'dır (`StrategyRevision`: *"Immutable per-revision snapshot … Never
UPDATEd"*), yani **bir config alanının değeri değişirse revision id de değişir.**

> **Sonuç: `overflow_policy` bir `StrategyConfig` alanı olarak eklenirse, iki farklı politikayla
> koşan iki run ZATEN farklı `execution_key` alır** — çünkü `strategy_revision_id` farklıdır.
> Reprodüksiyon kimliği **kendiliğinden** doğrudur. Alanı ayrıca `execution_content`'e yayımlamak
> bir **doğruluk** gereği değil, bir **disclosure** tercihidir (Karar 1'in `commission_model`
> addendum'unun aynı sınıfı).

**Ve o tercihin ölçülmüş bedeli asimetriktir** — bu yüzden (B) imza satırında **iki alt-şekle**
ayrılmıştır:

| (B)'nin şekli | `execution_key` etkisi | Saklanan Result'lar |
|---|---|---|
| **B-i** — alan yalnız `StrategyConfig`'te | **Kayma YOK.** Politikayı değiştiren revizyon zaten yeni bir `strategy_revision_id` üretir | Etkilenmez; idempotent yeniden kullanım **çalışmaya devam eder** |
| **B-ii** — alan ayrıca `execution_content`'te yayımlanır | **HER `execution_key` kayar** — yeni anahtar her manifest'te bulunur, canonical JSON değişir | **Hiçbir** saklanan Result bir re-RUN için idempotent olarak yeniden kullanılmaz |

**B-ii precedented'tir** (INF-04/INF-05; `manifest.py` bu namespace kaymalarının tarihçesini
taşıyor) **ama PR'da BEYAN EDİLMELİDİR**, keşfedilmemelidir.

**Saklanan `BacktestResult` her iki şekilde de IMMUTABLE'dır** — hiçbir artefakt yeniden
hesaplanmaz; yalnız hangi Result'ın yeniden **seçilebileceği** değişir.

---

### Dispozisyonlar

**Slice talebi üçünü adlandırdı. Ölçüm (§ÖLÇÜM 1) dördüncüyü açtı** — G15 belgesinin
*"ölçüm dördüncüyü açtı"* emsalinin aynısı. **Hiçbiri seçilmemiştir.**

**Üçünde (dördünde) de ORTAK, yeniden ölçülmüş gerçekler:**

- **`ENGINE_VERSION`: DÖRDÜNDE DE BUMP YOK.** Bugünkü değer
  `"backtest-engine-v18-percent-sizing-per-fill-commission"` (`manifest.py`). Gerekçe:
  **reddetmek yeniden fiyatlama değildir.** Reddedilen bir run **Result üretmez**; koşmaya
  devam eden her run **aynı sayıları** verir. `engine_golden_digests.json`'ın 50 senaryosunun
  **hiçbiri oynamaz**. **Bu, brifingin en güçlü zamanlama argümanıdır:** G4, `ENGINE_VERSION`
  bump'ı gerektiren hiçbir şeyin arkasında **beklemek zorunda değildir** ve tek başına inebilir.
- **migration: DÖRDÜNDE DE YOK.** `StrategyConfig` bir JSONB `payload` olarak saklanıyor
  (`StrategyRevision.payload`), yeni bir opsiyonel alan **DDL istemez**. alembic head
  `0043_i08_registry_strategy_fks` olarak kalır.
- **OpenAPI: DÖRDÜNDE DE ETKİ YOK** (§"düzeltilen iddialar" #1). `PositionSizeLimits` yayımlanmış
  bir component **değildir**; config API sınırını tipsiz `payload` olarak geçer. Drift guard
  (`entropia.apps.api.openapi_export --check`) **hiçbir disposition'da** yeni dosya istemez.
- **historical Result: DÖRDÜNDE DE IMMUTABLE.** Hiçbir saklanan artefakt yeniden hesaplanmaz.

#### (A) BLOCKER — Ready Check'te base'i cap'e karşı karşılaştır

- **Tanım.** `validators.py`'ye, `STRATEGY_SIZING_SEMANTICS_UNCONFIRMED`'ın yanına yeni bir Ready
  Check kontrolü: `base_position_size` (ve yapılandırılmışsa ladder'ın `add_size_value`'su)
  `max_position_size`'a karşı karşılaştırılır; taşma **BLOCKER** üretir. **Motor DEĞİŞMEZ** —
  `_clamp_to_limits` bayt bayt aynı kalır. K1'in *"blocker"* şıkkının ve **K2/K3'ün statik
  kuralının** birlikte karşılığıdır (**Ç3'ü kapatan tek disposition**).
- **Dokunulacak semboller.** `domain/readiness/validators.py` (yeni kontrol),
  `domain/readiness/enums.py::Code` (yeni kod, ör. `STRATEGY_SIZING_EXCEEDS_MAX_POSITION`).
  Mevcut `ReadinessIssue` + `Sev.BLOCKER` + `Scope.STRATEGY` tesisatı **yeniden kullanılır**;
  yeni modül yok. **Motor sembolü sıfır.**
- **Uyumluluk etkisi.** **En pahalı yeri burası.** Bugün clamp'lenerek koşan kayıtlı revizyonlar
  Ready Check'te **düşer** — geçiş kapısını **geçmiş** olanlar dahil. Yani #550'nin
  `size_semantics` kapısını temizlemiş bir revizyon **YENİ** bir blocker kazanır.
  **Kaç tane? → §ÖLÇÜM 2: SAYILAMADI.**
- **`ENGINE_VERSION` / migration / OpenAPI / `execution_key`.** Dördü de **etkisiz**. Reddedilen
  run Result üretmez; koşan run aynı fiyatlanır; manifest şekli değişmez.
- **Geri alma maliyeti.** **En ucuz.** Validator'ı revert et; **hiçbir veriye dokunulmaz**,
  hiçbir namespace kaymaz. Reddedilmiş revizyonlar kendiliğinden geçerli olur (yeni bir Ready
  Check koşusu yeterlidir — reddedilme bir **durum** değil, bir **hesaplama**dır).
- **Riski.** (i) **Geriye dönük geçerlilik iptali** — aylardır koşan stratejiler imza gününde
  BLOCKED olur ve blast radius **ölçülmemiştir**. (ii) **Hangi büyüklüğün** karşılaştırılacağı
  bir alt-karardır: yalnız `base` mi, `base × leverage` mi (§ÖLÇÜM 3 — kaldıraç dahil edilmezse
  kural entry'de gerçekte bağlayan büyüklüğü **ölçmez**), risk/Kelly yolları hiç mi
  karşılaştırılmasın (saklanan payload'dan **hesaplanamaz**). (iii) Bir Ready Check kuralı
  **runtime'ı bağlamaz**: (A) tek başına imzalanırsa motor **hâlâ sessizce clamp'ler** — yalnız
  o duruma ulaşabilen konfigürasyon kümesi daralır. **(A), Ç1'i entry runtime'ında KAPATMAZ.**

#### (B) EXPLICIT CAP POLICY — politikayı yapılandırılabilir ve okunabilir yap

- **Tanım.** `config.py::PositionSizeLimits`'e
  `overflow_policy: Literal["cap","block"] | None`; `sizing.py::_clamp_to_limits`'te **okunur**;
  `"block"` ise entry açılmaz, `"cap"` ise bugünkü clamp uygulanır. K1'in *"explicit cap policy"*
  şıkkının doğrudan karşılığı — cap'i **yasaklamaz**, onu **beyan edilmiş** hâle getirir.
- **Dokunulacak semboller.** `domain/strategy/config.py::PositionSizeLimits` (yeni alan);
  `domain/backtest/execution/sizing.py::_clamp_to_limits` (politikayı oku);
  **B-ii seçilirse** ayrıca `domain/backtest/manifest.py` (`execution_content`'e anahtar).
  `"block"` dalının bir refüzü **gözlemlenebilir** kılması için `sizing.py::SIZE_RESOLVED_TO_ZERO`
  yanında bir F-10 restriction-trace token'ı gerekir — **aksi hâlde `"block"` de sessizdir**
  (ölçüldü: `blocked_reason` bu vokabülerin sevk edilmiş yeridir).
- **Uyumluluk etkisi.** Saklanan **her** revizyonda alan `None` olur. **Bu, bu belgedeki tek
  gerçek tuzaktır** — aşağıda ayrı bölüm.
- **`ENGINE_VERSION`.** **Bump YOK.** `"cap"` bugünkü sayıyı verir; `"block"` reddeder ve
  reddetmek yeniden fiyatlama değildir.
- **`execution_key`.** **B-i: kayma YOK. B-ii: HER anahtar kayar** (§ÖLÇÜM 4). Precedented
  (INF-04/INF-05) ama PR'da **beyan edilmeli**.
- **migration / OpenAPI.** Yok / yok.
- **Geri alma maliyeti.** **B-i:** alanı geri çıkar; `overflow_policy` taşıyan saklanmış
  payload'lar geçerli JSON olarak kalır ve eski model tarafından **yok sayılır** — P-C1 bunu
  *"pydantic bilinmeyen anahtarları yok sayar — **güvenmeden önce doğrula**"* uyarısıyla
  kaydetmişti ve **bu belge de doğrulamadı; imzadan önce doğrulanmalıdır.**
  **B-ii:** ek olarak `execution_key` eski namespace'ine döner, yani revert **sonrası** run'lar
  ara dönemde üretilmiş Result'larla eşleşmeyi bırakır. **En ucuz geri alma, alanı imzalanana
  kadar hiç sevk etmemektir.**
- **Riski.** (i) `None` varsayılanı (aşağıdaki tuzak). (ii) `"block"` dalı bir restriction-trace
  token'ı olmadan sevk edilirse **sessiz clamp yerine sessiz refüz** gelir — sessizlik yer
  değiştirir, kaybolmaz. (iii) B-ii'nin namespace kayması **her** kullanıcının bir sonraki
  re-RUN'ını cache-miss yapar.

#### (C) SEVK EDİLEN CLAMP'İ KANONİK İLAN ET (imzalı sapma)

- **Tanım.** *"Max Single Position taşmasında motor boyutu sessizce cap'e indirir; bu, §10.2'nin
  istediği **explicit cap policy**'dir ve bu imza onu explicit yapar."* **Sıfır kod.** Teslimat
  imzalı bir sapma paragrafıdır — D-10/D-11 emsali, `a11y_ci_ratchet_and_adjudication.md` biçimi.
- **Dokunulacak semboller.** **Sıfır üretim sembolü.** Yalnız docstring'ler
  (`_clamp_to_limits`) + bu belgedeki imza.
- **Uyumluluk etkisi.** **Yok.** Hiçbir revizyon durumu değişmez, hiçbir run farklı koşar.
  **Bu, (C)'nin tek gücüdür.**
- **`ENGINE_VERSION` / `execution_key` / migration / OpenAPI.** Dördü de **etkisiz**.
- **Geri alma maliyeti.** **Yok** (değişiklik yok); geri dönüş (A), (B) veya (D)'yi uygulamaktır.
- **Riski — DÜRÜST OL.** (i) **ORTAK SÖZLEŞME'nin *"'Zaten böyle yapılmış' diye mevcut davranışı
  canonical ilan etme"* yasağının tam hedefidir** (Karar 3/Seçenek B ve G15/Seçenek C ile aynı
  konum): meşrudur, ama **yalnız bilinçli bir imzayla**; varsayılan olarak seçilemez.
  (ii) **§ÖLÇÜM 1 nedeniyle (C) tek bir davranışı değil bir TUTARSIZLIĞI kanonik ilan eder** —
  aynı alan bir yolda kırpar, iki yolda reddeder. (iii) K1 *"clamp değil"* derken *"explicit"*
  kelimesinin sessiz bir clamp'i kapsadığını savunmak gerekir; **imza metni bu savı açıkça
  yazmalıdır**, aksi hâlde bir sonraki okuyucu imzayı §10.2'nin ihlali sanar. (iv) §ÖLÇÜM 3'ün
  atıl kaldıracı **kalıcı ve işaretsiz** olur.

#### (D) GÖZLEMLENEBİLİR CLAMP — **ölçümün açtığı dördüncü şekil**

> **Bu şekli slice talebi adlandırmadı; §ÖLÇÜM 1 açtı ve kaydedilmemesi bir eksiklik olurdu.**
> G15 belgesinin dördüncü seçeneği de böyle doğdu. **Bir öneri değildir** — imzalanacak
> seçenekler kümesini **tam** hâle getirir.

- **Tanım.** Clamp **kalır**, ama **sessiz olmaktan çıkar**: bağladığında ladder/stack yollarının
  **zaten kullandığı** `position_size_limit` reason'ı ile bir event emit edilir ve bir ledger
  sayacı artar. Boyut değişmez, davranış değişmez; **görünürlük** değişir. K1'in *"explicit cap
  policy"*'sinin en dar okunuşu: policy = cap, ama **explicit**.
- **Dokunulacak semboller.** `sizing.py::_clamp_to_limits`'in bağladığını çağırana bildirmesi
  (dönüş şekli veya bir yan kanal), `engine.py`'ın entry yolunda `_emit(...)`,
  `execution/state.py::_Ledger`'a bir sayaç, `execution/output.py`'de yayımlanması. **Yeni
  vokabüler yok** — `position_size_limit` token'ı sevk edilmiş.
- **Uyumluluk etkisi.** **Hiçbir revizyon düşmez, hiçbir run reddedilmez.** Result artefaktına
  **yeni bir alan** eklenir (sayaç), yani `result_artifact_context` üzerinden bir artefakt-şekli
  sorusu doğar — **imzadan önce ölçülmelidir** (bu belge ölçmedi).
- **`ENGINE_VERSION`.** **Bump YOK** — hiçbir PnL sayısı oynamaz. **`execution_key`:** yeni sayaç
  `execution_content`'e **girmediği** sürece kayma yok. **migration / OpenAPI:** yok / yok.
- **Geri alma maliyeti.** Emit + sayacı revert; veri dokunulmaz.
- **Riski.** (i) **§10.2'yi karşılar mı?** *"clamp değil"* literal okunursa **HAYIR** — clamp
  devam eder. *"explicit cap policy"* okunursa **EVET**. **Bu ayrım bir yorumdur ve imza metni
  onu yazmalıdır.** (ii) (D) Ç3'ü (statik kural) **kapatmaz**. (iii) Bir sayaç bir blocker
  değildir: kullanıcı Result'ı **okumazsa** sessizlik pratikte sürer.

### Karşılaştırma

| | Entry'de clamp | Ready Check cevabı değişir | Motor sembolü | `ENGINE_VERSION` | `execution_key` | migration | OpenAPI | Geri alma | Ç1 | Ç2 | Ç3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** blocker | **kalır** | **EVET — yeni BLOCKER** | 0 | yok | kaymaz | yok | yok | validator revert | kısmen | hayır | **EVET** |
| **B-i** cap policy | politikaya bağlı | hayır | 2 | yok | **kaymaz** | yok | yok | alan revert | **EVET** | hayır | hayır |
| **B-ii** + manifest | politikaya bağlı | hayır | 3 | yok | **HER anahtar kayar** | yok | yok | alan + namespace | **EVET** | hayır | hayır |
| **C** kanonik ilan | **kalır** | hayır | **0** | yok | kaymaz | yok | yok | — | imzayla | **kanonikleşir** | hayır |
| **D** gözlemlenebilir clamp | **kalır** | hayır | 3-4 | yok | kaymaz | yok | yok | emit revert | yoruma bağlı | kısmen | hayır |

**A ve B birbirini dışlamaz** (statik kural + runtime politikası birlikte imzalanabilir; A
kaydetme zamanında, B çalışma zamanında bağlar). **A ve D de birlikte imzalanabilir.**
**C ile A/B/D bir arada imzalanamaz** — C *"bugünkü davranış doğrudur"*, diğer üçü *"değiştirilmeli"*
der. Bu yüzden imza satırında kombinasyonlar **açıkça** listelenmiştir.

### TUZAK — (B)'nin `None` varsayılanı (ayrı kutu, imza satırında ayrıca sorulur)

`overflow_policy` sevk edilirse **saklanan her revizyonda `None`** olacaktır. `None`'ın anlamı
bir uygulama ayrıntısı **değil**, ikinci bir üründür:

| `None` şu demekse | Sonuç | Bedeli |
|---|---|---|
| **`"cap"`** (geriye dönük uyumlu) | **Sessiz clamp YENİ BİR ADLA geri gelir.** Bugünkü davranış, artık *"policy budur"* diye **imzalanmış** olarak sürer; §10.2'nin *"clamp değil"*i eskisi gibi ihlal edilir — yalnız artık bir alan adı vardır. Pratikte (C)'nin (B) kılığındaki hâlidir. | Sıfır geçiş maliyeti, **sıfır kazanç** |
| **`"unconfirmed"`** (dürüst okuma) | **İKİNCİ bir geçiş kapısı** doğar: `None` taşıyan her revizyon Ready Check'te bloklanır ve kullanıcı politikayı **açıkça** seçene kadar RUN edemez. | #550'nin `size_semantics` kapısının **birebir aynısı** — o kapı bugün de canlı, yani kullanıcı **iki** onay ekranı görür |

**Emsal ölçüldü ve birebir uygulanabilir:** `PositionSizing.size_semantics`
(`Literal["percent_of_capital"] | None`) tam olarak bu şekli taşıyor — `None` =
*"bu soru sorulmadan önce kaydedildi"*, ve `STRATEGY_SIZING_SEMANTICS_UNCONFIRMED` onu
**sessizce varsaymak yerine bloklar**. `size_semantics`'in kendi alan açıklaması gerekçeyi
yazıyor: *"`None` marks a revision saved BEFORE the cutover … Ready Check blocks it … rather
than re-interpreting the value silently."*

> **Bu ikilem (B)'nin İÇİNDE bir alt-karar değildir; (B)'nin NE OLDUĞUNU belirler.**
> `None = "cap"` imzalanırsa (B) bir **disclosure** değişikliğidir. `None = "unconfirmed"`
> imzalanırsa (B) bir **geçiş programı**dır. İkisinin kullanıcı maliyeti aynı büyüklükte
> değildir.

### Bu belgenin ÖNERMEDİĞİ şey

Karar 1/2/3/4/5'in aksine burada **"Önerilen seçenek" başlığı YOKTUR ve bu bilinçlidir** —
G15 belgesiyle aynı gerekçe. Ordered plan G4'ü *"kimsenin sahiplenmediği"* iki kapıdan biri
olarak kaydediyor ve *"neither can be substituted by an agent's judgement"* diyor. Ölçüm dört
şekli **eşit ölçüde belgelenmiş** hâle getirdi; aralarındaki seçim bir
**doğruluk / geriye-dönük geçerlilik / kullanıcı maliyeti** takasıdır ve **ürün sahibinindir**.

**Not (dürüstlük):** slice talebi *"Karar 1/2/3 de seçmiyor"* diyordu. Ölçüldü ve bu **yanlış**:
Karar 1, 2, 3, 4 ve 5'in **hepsinde** *"Önerilen seçenek + gerekçe (BU BİR ÖNERİDİR, KARAR
DEĞİL)"* başlıklı bir bölüm var. Bu belge o bölümü **bilerek taşımaz** — yapı aynalanırken bu
tek sapma **kasıtlıdır** ve G15'in emsalini izler.

---

### İMZA SATIRI

**ÖN KOŞUL — önce bu sayı alınmalı (§ÖLÇÜM 2):**

(A) imzalanırsa Ready Check'te **yeni** düşecek kayıtlı revizyon sayısı
(`size_semantics = 'percent_of_capital'` **ve** `base_position_size > max_position_size`): ______

`[ ] sayıldı ve 0`   `[ ] sayıldı ve > 0 (sayı: ____)`   `[ ] sayılamadı`

> **(A) bu sayı alınmadan imzalanamaz.** (B), (C) ve (D) sayıdan bağımsız imzalanabilir.
> Sayının **alt sınır** olduğunu ve neyi görmediğini (risk/Kelly yolları, kaldıraç) §ÖLÇÜM 2
> yazıyor.

**Karar — Max Single Position cap taşması dispozisyonu (G4):**

`[ ] A (Ready Check blocker — motor değişmez)`
`[ ] B-i (overflow_policy alanı; execution_content'e YAYIMLANMAZ)`
`[ ] B-ii (overflow_policy + execution_content — HER execution_key kayar)`
`[ ] C (sevk edilen clamp kanonik ilan edilir — imzalı sapma, sıfır kod)`
`[ ] D (gözlemlenebilir clamp — boyut aynı, sessizlik kalkar)`
`[ ] A + B-i`   `[ ] A + D`   `[ ] A + B-ii`

**TUZAK — yalnız B-i veya B-ii imzalanırsa ZORUNLU** (§TUZAK):
`overflow_policy = None` ne demektir?
`[ ] "cap" (geriye dönük uyumlu — sessiz clamp yeni bir adla sürer)`
`[ ] "unconfirmed" (ikinci bir geçiş kapısı; size_semantics emsali)`

**Alt-karar — yalnız (A) imzalanırsa:** karşılaştırılacak büyüklük hangisi?
`[ ] yalnız base_position_size`
`[ ] base_position_size × leverage (entry'de gerçekten bağlayan büyüklük — §ÖLÇÜM 3)`
Ladder'ın `add_size_value`'su da karşılaştırılsın mı? `[ ] evet` `[ ] hayır`
> Risk-based ve Kelly yolları **saklanan payload'dan hesaplanamaz** (§ÖLÇÜM 2, dürüst sınır);
> hiçbir kutu onları kapsamıyor.

**Hüküm onayı (a)** — *kanon çelişmiyor: §10.2 ve §11.4 **aynı hükmü** veriyor (kırpma yok,
reddet ve sebebi kaydet); K2/K3 bunu statik alan kuralı olarak tekrar ediyor; **yalnız doc 02'nin
ⓘ paneli susuyor** ve sessiz clamp yalnız o suskunluğa sığıyor* — kabul ediliyor mu?
`[ ] evet` `[ ] hayır (gerekçe: ______)`

**Hüküm onayı (b)** — *motor bu cap'i üç yolda bağlıyor ve **ikisi zaten reddedip sebebi
kaydediyor** (`position_size_limit`); sapan tek yol entry'dir, dolayısıyla hiçbir disposition
yeni bir kavram/altyapı gerektirmez ve **(C) tek bir davranışı değil bir tutarsızlığı** kanonik
ilan eder* — kabul ediliyor mu? `[ ] evet` `[ ] hayır (gerekçe: ______)`

**Hüküm onayı (c)** — *cap'in üstünde kaldıraç **atıldır ve işaretsizdir** (%10 base × 5x = %50
→ %25'e clamp; 5x ile 20x aynı sonucu verir); bu bugün **doğru** davranıştır ama kullanıcının
öğrenmesinin **hiçbir yolu yoktur*** — kabul ediliyor mu? `[ ] evet` `[ ] hayır (gerekçe: ______)`

**Ayrı kalem onayı** — §ÖLÇÜM 4'ün ölçtüğü *"`overflow_policy` `strategy_revision_id` üzerinden
**zaten** `execution_key`'e pinlidir, dolayısıyla `execution_content`'e yayımlamak bir doğruluk
gereği değil disclosure tercihidir"* tespiti kabul ediliyor mu?
`[ ] evet` `[ ] hayır (gerekçe: ______)`

karar veren: ________________  tarih: ____________

---

## Bu belgenin kapsamadıkları (dürüst sınır)

- **Hiçbir karar verilmedi.** Dört şeklin hiçbiri seçilmedi, elenmedi, "önerilen" işaretlenmedi.
- **Hiçbir kod değiştirilmedi.** `backend/src`, `frontend/src`, `backend/migrations` ve **hiçbir
  test ağacına** dokunulmadı. Bu commit yalnız `docs/decisions/` altına **bir yeni dosya** ekler.
- **Hiçbir issue açılmadı, kapatılmadı, etiketlenmedi.** **#550 `closed` / `completed`
  (2026-08-14, ölçüldü)** ve **öyle bırakıldı**. O kapanış #720'nin **sizing yarısına** aittir —
  issue'nun kendi başlığı bunu söylüyor: *"base_position_size / min / max execute as unit counts
  while the shipped UI labels them percent"*. **Cap taşması AYRI ve AÇIK bir sorudur** ve
  #550'nin gövdesinde karara bağlanmamıştır. **Emsal aynı gün ölçüldü:** **#552 de `closed` /
  `completed`** olduğu hâlde G1/G2/G3 kapıları **hâlâ imzasızdır** (ordered plan §2). Bu deponun
  kuralı ORTAK SÖZLEŞME'de yazılı: ***"Issue CLOSED != çözüldü."***
- **Suite koşulmadı.** Ürün kodu değişmediği için `pytest` **çalıştırılmadı** — bu **bilinçli**
  ve burada açıkça yazılıyor. Bu belgenin ölçümleri suite'ten değil, **doğrudan sevk edilmiş
  sembollerin ve kanon metinlerinin okunmasından** gelir. Koşulan tek kapı doküman-gerçeği
  kapısıdır (`scripts/generate_repository_facts.py --check`).
- **Blast radius ÖLÇÜLMEDİ** ve **tahmin edilmedi** (§ÖLÇÜM 2, üç gerekçesiyle). Sorgu yazıldı;
  sayı imzadan önce alınmalıdır.
- **(D)'nin Result artefaktı üzerindeki şekil etkisi ölçülmedi** — yeni bir sayaç
  `result_artifact_context` üzerinden bir artefakt-şekli sorusu doğurur; bu belge onu **açtı,
  ölçmedi**.
- **(B)'nin geri alma varsayımı doğrulanmadı:** *"pydantic bilinmeyen anahtarları yok sayar"*
  P-C1'in kendi uyarısıyla *"güvenmeden önce doğrula"* diye kaydedilmişti; **bu belge de
  doğrulamadı.**
- **Kaldıraç sırası (clamp'in kaldıraçtan sonra gelmesi) bu kararın konusu değildir.** Ölçüldü ve
  ikinci mertebe sonucu kaydedildi (§ÖLÇÜM 3); **üzerine gidilmedi.**
- **`docs/performance/query_budgets.json` ve kabul borcu ratchet'i değişmedi.** Hiçbir kriter
  kapanmadı, hiçbir sınıf taşınmadı, hiçbir tavan oynamadı.
- **A-08 bu belgeden etkilenmez.** Blocker sayısı **1** (yalnız A-08), verdict **BLOCKED**.
- **G15 bu belgenin konusu değildir.** Ordered plan'ın *"iki sahipsiz kapı"* tarifi artık
  yalnız tarihsel olarak doğrudur: G15'in bloğu PR #747'de yaratıldı, G4'ünki budur.
  **İkisi de imzasızdır.**
