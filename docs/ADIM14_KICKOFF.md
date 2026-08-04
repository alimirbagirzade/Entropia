# ADIM 14 kickoff — Frontend capability disclosure (#539 + #533, TEK tur)

> Bu belge **ADIM 14'ün açılış handoff'udur** — henüz landed bir slice yok. En altta
> **paste-ready resume prompt** var. Kanıtlar `origin/main` @ `f4e2fd3` üzerinde
> **2026-08-04'te yeniden ölçüldü**; ADIM 12/13 ve PR #555/#560 bu yüzeye dokunmadı.

## Nerede duruyoruz

| | |
|---|---|
| Base | `origin/main` @ **`f4e2fd3`** (PR #560 merge sonrası) — working tree temiz |
| Alembic head | `0043_i08_registry_strategy_fks` — **migration YOK** |
| OpenAPI | 196 operation / 151 schema — **değişmeyecek** |
| `ENGINE_VERSION` | `backtest-engine-v18-same-candle-entry-exit` — **değişmeyecek** |
| Capability matrix | **62 satır / 22 future_dev / 14 fieldPath** — **değişmeyecek** |
| Dokunulan katman | **yalnız frontend sunum** (`components/`, `lib/strategyGraph.ts`, testler) |
| Kapsam | **#539 + #533 AYNI turda** (aşağıdaki tuzak maddesi sebebiyle ayrılamaz) |

## Neden bu iki issue tek turda

**#539 yanlış-NEGATİF:** üretilen capability aynası "kullanıcı `future_dev` bir opsiyonun
üzerine strateji KURMADAN ÖNCE onu devre dışı bırak" diye var — kendi docstring'i böyle
diyor (`engineCapabilityMatrix.generated.ts:10-12`). `StrategyConfigForm` bunu kullanıyor;
`StrategyGraphForm` **hiç import etmiyor** ve kendi `SelectField`'ini taşıyor. Etkilenen
satırlar sıradan seçilebilir opsiyon gibi görünüyor; kullanıcı gerçeği ancak stratejiyi
kurduktan **sonra** Ready Check'te öğreniyor.

**#533 yanlış-POZİTİF:** `StrategyConfigForm`'un notu değeri **tek başına** okuyor ve her
yeni stratejinin varsayılan `allow_hedge` konfigürasyonunda "Ready Check blocks it" diye
**yanlış** iddia ediyor (backend `exit_on_opposite_signal=true` iken değeri INERT sayıp
bloklamıyor).

**Bağlantı — bunu atlama:** #539'un naif düzeltmesi (değere bakıp disable etmek) tam olarak
#533'ü çoğaltır. Backend okuyucular değere değil **erişilebilirliğe** bakıyor:
`capabilities.py::_read_filter_types` (`:633-635`) `enabled=false` bir filtreyi **INERT**
sayar. Bu yüzden ikisi aynı turda ele alınmalı.

**Yetki açığı DEĞİL:** sunucu koşuyu `STRATEGY_SCALING_UNSUPPORTED` /
`STRATEGY_CAPABILITY_NOT_IN_BUILD` ile reddediyor, motor pozisyon açmıyor. Bu bir
**disclosure** kusuru. #556/#557/#558/#559'dan farklı olarak **ürün kararı BEKLEMİYOR.**

## Kanıt — tek komutla yeniden üretilir (f4e2fd3'te ölçüldü)

```
grep -c capabilityField frontend/src/components/StrategyConfigForm.tsx   -> 12
grep -c capabilityField frontend/src/components/StrategyGraphForm.tsx    ->  0
grep -rn engineCapabilityMatrix frontend/src | grep -v generated.ts:
    -> yalnız StrategyConfigForm.tsx:9 ve engineCapabilityMatrix.test.tsx:9
frontend/src/lib/strategyGraph.ts:229  MODELLED_FILTER_TYPES hâlâ elle bakımlı
```

## ⚠ DÜZELTME — sayı **11 değil, 15**

Issue #539'un başlığı ve gövdesi "11 of the 22 future_dev rows" diyor, ama **kendi
tablosu 10+1+4 = 15'e toplanıyor.** Matris ölçüldü, tablo doğru, başlık yanlış:

| fieldPath | toplam satır | future_dev | forma bağlı mı |
|---|---:|---:|---|
| `data.execution.entry_timing` | 6 | 0 | ✅ ConfigForm |
| `data.execution.exit_timing` | 6 | 0 | ✅ ConfigForm |
| `data.order_config.limit.price_rule` | 4 | 1 | ✅ ConfigForm |
| `data.order_config.limit.partial_fill_policy` | 5 | 0 | ✅ ConfigForm |
| `data.costs.slippage_mode` | 2 | 1 | ✅ ConfigForm |
| `position_sizing.formula_based.formula_type` | 2 | 1 | ✅ ConfigForm |
| `position_sizing.signal_strength_adjustment` | 4 | 2 | ✅ ConfigForm |
| `position_sizing.leverage_mode` | 3 | 1 | ✅ ConfigForm |
| `conflict_position_handling.opposite_direction_hedge` | 3 | 1 | ✅ ConfigForm (**ama #533**) |
| **`scaling_logic.timeframe`** | 11 | **10** | ❌ GraphForm `:750-756` |
| **`scaling_logic.timeframe_mode`** | 3 | **1** | ❌ GraphForm `:757-763` |
| **`restrictions_filters.filters.filter_type`** | 7 | **4** | ❌ GraphForm `:1018-1020` |
| `scaling_logic.method` | 2 | 0 | ❌ GraphForm (**bugün zararsız**) |
| `position_exit_logic.partial_aftermath` | 4 | 0 | ❌ hiçbir yerde |

**Açığa çıkan `future_dev` satırı: 15/22.** Bağlı 9 alanın `future_dev` toplamı 7; 22−7 = 15.
On `future_dev` timeframe değerinin **hepsi** `BLOCK_TIMEFRAME_OPTIONS` (11 opsiyon; yalnız
`same_as_base_tf` `active_v1`) içinde render ediliyor, dört filtre değerinin hepsi
`FILTER_TYPE_OPTIONS` içinde — yani hiçbiri opsiyon listesinde eksik olduğu için "görünmez"
değil. Kabul ölçütünü **15** üzerinden ölç; PR gövdesinde issue'nun 11 rakamını düzelt.

**Son iki satır bugün zararsız ama latent:** `scaling_logic.method` ve
`position_exit_logic.partial_aftermath` şu an 0 `future_dev` taşıyor. Matris yeniden
üretildiğinde biri `future_dev`'e dönerse **hiçbir şey** onu devre dışı bırakmaz. 3. kabul
ölçütü (aşağıda) tam olarak bunu yakalamak için var — ve bu, **#540**'ın (exhaustiveness
guard 14 alanın yalnız 9'unu kapsıyor — yani tam olarak bağlı 9 alan) doğal örtüşmesidir.
#540'ı ADIM 14'e ALMA, ama testi yazarken kapsamı 14 alanın tamamı olacak şekilde kur.

## Reuse anchor'ları (tam sembol adlarıyla)

| Anchor | Nerede | Ne verir |
|---|---|---|
| `SelectField({ …, capabilityField })` | `StrategyConfigForm.tsx:126-207` | **Kopyalanacak referans uygulama:** `blockedValues` (mevcut değeri HARİÇ tutar), `disabled`, `— not available in this build` son eki, `dependency` notu `aria-describedby` ile bağlı |
| `capabilityOption(field, value)` · `isFutureDev(field, value)` · `CapabilityOption` | `lib/engineCapabilityMatrix.generated.ts` | Matris okuma API'si — **enumerate edilmemiş alan/değer `undefined` döner, bu bir RED değildir** |
| `ENGINE_CAPABILITY_MATRIX` | aynı dosya | 62 satırın tamamı; `MODELLED_FILTER_TYPES`'ın türetileceği kaynak |
| `SelectField({ …, panel })` | `StrategyGraphForm.tsx:122-168` | Düzeltilecek hedef |
| `MODELLED_FILTER_TYPES` | `lib/strategyGraph.ts:229-233` | Silinecek; tek tüketici `StrategyGraphForm.tsx:935` |
| `capabilityNoteFor(select)` | `test/engineCapabilityMatrix.test.tsx` | Not okuma yardımcısı — yeni testlerde yeniden kullan |
| `_read_filter_types` | `backend/.../capabilities.py:633-635` | **Aynalanacak semantik:** `enabled=false` → INERT |

## Tuzaklar

1. **Erişilebilirlikten kapıla, değerden DEĞİL** (reçete md. 3). Atlanırsa #533 çoğalır.
2. **İki `SelectField` prop şekli AYNI DEĞİL.** ConfigForm `panelKey?: keyof typeof
   STRATEGY_INFO_PANELS` + `FieldHead` alt bileşeni kullanıyor; GraphForm `panel?:
   InfoPanelContent` alıp `<span className="field-head">`'i inline basıyor. `capabilityField`
   mantığını taşı, **imzayı bütün olarak kopyalama** — düz kopya GraphForm'un panel
   yüzeyini bozar.
3. **`engineCapabilityMatrix.generated.ts` ÜRETİLMİŞ dosyadır.** `test_capability_matrix.py`
   onu byte-byte yeniden render edip eşitlik iddia ediyor; elle düzenlemek CI'ı kırar.
4. **`MODELLED_FILTER_TYPES`'ın mevcut notu değer üzerinden ateşliyor** (`:935`,
   `filter.filter_type !== ""` kontrolü var ama `filter.enabled` kontrolü YOK) — yani
   `enabled=false` bir filtrede de uyarıyor. Silerken bu davranışı taşıma, düzelt.

## Reçete

1. `StrategyGraphForm`'un `SelectField`'ine `StrategyConfigForm.tsx:126-207`'deki
   `capabilityField` parametresini ver (tuzak 2'ye dikkat).
2. Üç alanı bağla: `scaling_logic.timeframe` (`:750-756`),
   `scaling_logic.timeframe_mode` (`:757-763`),
   `restrictions_filters.filters.filter_type` (`:1018-1020`).
3. **Backend okuyucular gibi erişilebilirlikten kapıla:** iki scaling alanı için
   `scaling.enabled`, filtre alanı için `filter.enabled`.
4. `MODELLED_FILTER_TYPES`'ı **sil**, `ENGINE_CAPABILITY_MATRIX`'ten türet + parity testi
   ekle (şu an sessiz sapabiliyor — D-6). Tek tüketici `StrategyGraphForm.tsx:935`.
5. **#533 aynı turda:** `StrategyConfigForm`'un notunu koşul-farkında yap — çağıran kart
   (`ConflictCard`) `exit_on_opposite_signal`'ı geçirsin; değer `future_dev` ama **INERT**
   ise not inertliği açıklasın ve "Ready Check blocks it" **demesin**. Gerçekten bloklu
   dal (`exit_on_opposite_signal=false`) mevcut ifadeyi korusun. Detaylı gerekçe ve ölçülmüş
   backend çıktısı issue #533 gövdesinde.

## Kabul ölçütleri

- Üç alanın **herhangi birinde** KAYDEDİLMİŞ bir `future_dev` değeri **disabled-ama-
  seçilebilir** render edilir, `dependency` notuyla.
- `scaling.enabled=false` (veya `filter.enabled=false`) iken **NE not NE disable** çıkar.
- Matris'in **14 alanının herhangi birindeki** bir `future_dev` satırı capability muamelesi
  görmeden bir forma ulaşırsa **test KIRILIR** (bugün 0-`future_dev` olan `scaling_logic.method`
  ve `position_exit_logic.partial_aftermath` dahil — latent regresyon yüzeyi).
- "Kaydedilmiş değer seçilebilir kalır" sözleşmesi korunur —
  `engineCapabilityMatrix.test.tsx:107-125` bunu kilitliyor.
- **#533:** varsayılan yeni strateji (`allow_hedge` + `exit_on_opposite_signal=true`)
  "Ready Check blocks it" **demez**; `exit_on_opposite_signal=false` dalı der. Her iki dal
  da testli — `ConflictCard` şu an **hiçbir** capability testinde render edilmiyor.

## Sınır

Yalnız sunum. **DEĞİŞMEZ:** route path, react-query key, OCC token (`If-Match` /
`expected_*_version` / `X-*-Version`), `Idempotency-Key`, hooks, SSE taksonomisi, API
çağrıları, `lib/*.ts` veri mantığı, `CAPABILITY_MATRIX` ve status literal'leri,
`engineCapabilityMatrix.generated.ts`, `_read_opposite_hedge`, readiness validator,
`opposite_direction_hedge`'in sevk edilmiş varsayılanı (ayrı ürün kararı — #535/F-4).
**Migration / OpenAPI / engine YOK.** Backend'e dokunulmadığını `git diff --stat` ile kanıtla.
V18 mockup (`docs/spec/index_guncellenmis_duzeltilmis_v18.html`) görsel referans.

## Doğrulama

```bash
cd frontend && npm run typecheck && npm run lint && npm run coverage
```

`vitest` için **`--no-file-parallelism` ZORUNLU**; worktree'de `frontend/node_modules` yoksa
önce `npm ci` (ilk koşudaki `ERR_MODULE_NOT_FOUND` test hatası değil). Eşikler
`frontend/vite.config.ts` — **kapıdır, rapor değil**; düşen sayıyı indirme, eksik testi yaz.
Backend suite'i koşmaya gerek yok (dokunulmuyor), ama `git diff --stat` ile ispatla.

## ADIM 14'e ALINMAYAN açık kalemler (sırala, dokunma)

| # | Konu | Neden dışarıda |
|---|---|---|
| #550 | `base_position_size` birim mi yüzde mi | ürün kararı + saved-revision migration'ı gerektirir |
| #551 | üç sizing yolu phantom 0-size trade açıyor | engine, ayrı slice |
| #552 | kısmi kapanan pozisyon 1.4 komisyon round trip ödüyor | engine, ayrı slice |
| #556 / #557 | agent gateway parity | doğal çözüm iki yüzeyi **TEK resolver**'a bağlamak |
| #558 / #559 | available-time politikası · DST fold/gap | **ürün kararı bekliyor** |
| #540 | exhaustiveness guard 14 alanın 9'unu kapsıyor | ADIM 14'ün 3. kabul ölçütü örtüşüyor ama kapatma ayrı |
| #514 | ekran okuyucu (NVDA/VoiceOver) denetimi | **kapatma yetkisi insanda — agent kapatamaz** |

---

## Paste-ready resume prompt

```
Entropia — ADIM 14: frontend capability disclosure (#539 + #533, TEK tur).

Session START protokolü önce: git fetch, `git log --oneline origin/main -6` ile gerçek
HEAD'i doğrula, `gh issue view 539` ve `gh issue view 533` ile ikisinin de OPEN olduğunu
teyit et. Sonra docs/ADIM14_KICKOFF.md'yi TAMAMEN oku — reuse anchor'ları, dört tuzak ve
"11 değil 15" düzeltmesi orada.

DÜZELTMEDEN ÖNCE üç şeyi ÖLÇ ve göster:
 (a) grep -c capabilityField frontend/src/components/StrategyGraphForm.tsx  -> 0
 (b) scaling_logic.enabled=true, timeframe="1h", timeframe_mode="increasing_by_layer" ile
     StrategyGraphForm render probe: disabled opts = [] ve aria-describedby = null
 (c) ConflictCard varsayılan form state ile render: "Allow Hedge is saved but will not run
     — Ready Check blocks it" notu GÖRÜNÜYOR (bu #533'ün yanlış iddiası)
Üçü de düzenlemeden önce kanıtlanmalı.

Sonra kickoff'un 5 maddelik reçetesini uygula. Kritik: erişilebilirlikten kapıla
(scaling.enabled / filter.enabled), DEĞERDEN değil — atlanırsa #539'un düzeltmesi #533'ü
çoğaltır. İki SelectField'in prop şekli aynı değil (ConfigForm panelKey+FieldHead,
GraphForm panel+inline field-head): mantığı taşı, imzayı düz kopyalama.

Testler: üç alan için disabled-ama-seçilebilir + dependency notu; enabled=false iken NE not
NE disable; 14 fieldPath'in TAMAMINI kapsayan exhaustiveness guard'ı (bugün 0-future_dev
olan scaling_logic.method ve position_exit_logic.partial_aftermath dahil); ConflictCard'ın
iki dalı (inert vs gerçekten bloklu). MODELLED_FILTER_TYPES silinip matristen türetilecek +
parity testi.

DOKUNMA: engineCapabilityMatrix.generated.ts (üretilmiş — backend parity testi byte-byte
pinliyor), CAPABILITY_MATRIX, status literal'leri, capabilities.py, _read_opposite_hedge,
readiness validator, opposite_direction_hedge'in sevk edilmiş varsayılanı, route path,
react-query key, OCC token, Idempotency-Key, hooks, SSE taksonomisi, lib/*.ts veri mantığı.
Migration / OpenAPI / engine YOK. Backend'in temiz kaldığını git diff --stat ile ispatla.

Doğrula: cd frontend && npm run typecheck && npm run lint && npm run coverage
(vitest --no-file-parallelism ZORUNLU; node_modules yoksa önce npm ci).

Branch feat/stage-14-capability-disclosure, commit
`fix(strategy-form): disclose future_dev capabilities in the graph form`, AI attribution YOK.
PR aç, MERGE ETME — self-merge bloklu, kullanıcıdan merge iste.

ADIM 14'e ALMA: #550 #551 #552 #556 #557 #558 #559 #540 #514.
```
