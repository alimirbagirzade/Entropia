# ADIM 13 landed → F-26 kickoff

> **Etiket notu (2026-08-04):** bu belge yazıldığında sıradaki slice "ADIM 14" diye
> etiketlenmişti. O numara merge edilmiş **ADR 0002**'ye ait (kendini ADIM 14 sayar ve
> ADIM 15–20'yi unified-clock programına rezerve eder), bu yüzden frontend slice'ı
> **F-26** olarak yeniden etiketlendi. Slice **PR #564 ile landed** — aşağıdaki reçete ve
> resume prompt **tarihsel kayıttır, yeniden koşulmaz**.

**Nerede olduğumuz:** `origin/main` @ `f4e2fd3`. ADIM 13 (**PR #560**, commit `4110138`,
base `c610600`) merged; aynı gün **PR #555** de landed. Alembic head
`0043_i08_registry_strategy_fks` (tek head). **`ENGINE_VERSION` artık
`backtest-engine-v18-gap-adjusted-stop-fill`** — bunu #555 değiştirdi, ADIM 13 değil.

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 13 · kanıt matrisi:
`docs/audit/research_point_in_time_matrix.md` · handoff: `docs/STAGE2_HANDOFF.md`.

---

## ADIM 13 ne bıraktı — REUSE anchor'ları (tam sembol adlarıyla)

| sembol | dosya | ne işe yarar |
|---|---|---|
| `ensure_time_policy_mutable(*, state, revision_id)` | `domain/research_data/time_policy.py` | pinlenmiş kanıtın yerinde retime edilmesini 409 `LIFECYCLE_BLOCKED` ile durdurur. **Yeni bir in-place time-policy yazan yüzey eklersen buradan geçir**, kuralı kopyalama. |
| `time_policy_is_frozen(state)` | aynı | saf predikat; `None` fail-closed FROZEN. |
| `TIME_POLICY_FROZEN_STATES` | aynı | `approved` / `approval_revoked` / `deprecated`. Yeni bir lifecycle state eklenirse `test_the_frozen_set_is_exhaustive_over_the_lifecycle` kırılır. |
| `is_eligible_for_decision(...)` | aynı | engine'in **TEK** research eligibility kapısı (`available_at <= t` AND mapping). |
| `resolve_available_at(...)` / `time_policy_is_valid(...)` | aynı | politika çözümü + yapısal geçerlilik. |
| `_require_viewable_root(session, actor, revision, *, consumable_only)` | `jobs/research_data.py` | root-active + aktöre göre görünürlük + tüketilebilir-durum, **tek yerde**. #556'nın doğal çözüm dikişi burası. |
| `_has_approved_feature_definition(session, entity_id)` | aynı | Feature-Input-Only kapısının **sunucu tarafı** cevabı. #557'nin doğal çözümü gateway'i buna bağlamak. |
| `_seal_bundle(bundle_kind, members, *, extra)` | aynı | content-addressed bundle mühürleme; `bundle_hash` `resolved_at`'i **kapsamaz** → yeniden derleme byte-identical. #558 bu üye şeklini genişletmek demek. |
| `_research_entries(session, funding)` | `commands/backtest_run_context.py` | Run manifest'in research pini — zaman politikasını **pinleyen tek yüzey**. #558'de referans şekil budur. |
| `revision_source_zone(revision)` | `jobs/research_data.py` | beyan edilen zaman diliminin domain adaptörü; `exchange` → `None` (fail-closed). |
| `build_funding_schedule(...)` / `parse_utc(...)` | `domain/backtest/funding.py` | available-time-güvenli takvim + hücre okuma. |

**Testler:** `backend/tests/unit/test_research_point_in_time.py` (27) ·
`backend/tests/integration/test_research_point_in_time_parity.py` (13 pass + 4 `xfail(strict)`).
Dört xfail #556/#557/#558'e bağlı — **düzeltirsen marker'ı kaldırmak zorundasın**, aksi halde
strict xfail XPASS verip suite'i kırar. Bu bilinçli.

---

## F-26 — Strategy formu capability disclosure (#539 + #533, TEK slice)

İki issue **aynı mekanizmanın iki zıt yönde kusuru**. Ayrı düzeltmek diğerini üretir.
Backend tarafı **doğru ve testli**; kusur yalnız UI iddiasında. İkisi de `f4e2fd3` üzerinde
yeniden doğrulandı.

### #539 — yanlış-NEGATİF (15 satır çalışır görünüyor)

```
grep -c capabilityField frontend/src/components/StrategyConfigForm.tsx  -> 12
grep -c capabilityField frontend/src/components/StrategyGraphForm.tsx   ->  0
grep -rn engineCapabilityMatrix frontend/src | grep -v generated.ts:
    -> yalnız StrategyConfigForm.tsx:9 ve engineCapabilityMatrix.test.tsx:9
frontend/src/lib/strategyGraph.ts:229  MODELLED_FILTER_TYPES hâlâ elle bakımlı
```

Üretilen capability aynası "kullanıcı `future_dev` bir opsiyonun üzerine strateji **kurmadan
önce** onu devre dışı bırak" diye var (kendi docstring'i böyle diyor). `StrategyGraphForm`
onu hiç import etmiyor ve kendi `SelectField`'ini taşıyor (`:122-168`, `capabilityField`
parametresi yok). 22 `future_dev` satırından **15'i** sıradan seçilebilir görünüyor:

| alan | satır | yer |
|---|---:|---|
| `scaling_logic.timeframe` | 10 | `StrategyGraphForm.tsx:750-756` |
| `scaling_logic.timeframe_mode = increasing_by_layer` | 1 | `:757-763` |
| `restrictions_filters.filters.filter_type` | 4 | `:1018-1020` |
| **toplam** | **15** | |

> ⚠ **Sayı 11 DEĞİL, 15 — issue #539'un başlığı yanlış.** #539'un gövdesi "11 of the 22
> future_dev rows" diyor ama **kendi tablosu 10+1+4 = 15'e toplanıyor**. Matris `f4e2fd3`
> üzerinde yeniden ölçüldü: capability aynasına **bağlı 9 ConfigForm alanının** `future_dev`
> toplamı **7**; 22 − 7 = **15**. Aynı hatalı rakam `docs/STAGE2_HANDOFF.md` ve
> `docs/PROJECT_HISTORY.md`'nin **ADIM 11 tarihsel kayıtlarında** (D-1 bulgusu) da duruyor —
> o kayıtlar bilerek düzeltilmedi (geçmiş yeniden yazılmaz), ama **kabul ölçütünü 15 üzerinden
> ölç** ve PR gövdesinde issue'nun 11 rakamını düzelt.
>
> On `future_dev` timeframe değerinin **hepsi** `BLOCK_TIMEFRAME_OPTIONS` içinde (11 opsiyon;
> yalnız `same_as_base_tf` `active_v1`), dört filtre değerinin hepsi `FILTER_TYPE_OPTIONS`
> içinde render ediliyor — yani hiçbiri "opsiyon listesinde eksik olduğu için görünmez" değil.
>
> **Bugün zararsız ama latent iki alan:** `scaling_logic.method` ve
> `position_exit_logic.partial_aftermath` şu an **0** `future_dev` taşıyor; matris yeniden
> üretildiğinde biri `future_dev`'e dönerse **hiçbir şey** onu devre dışı bırakmaz. Aşağıdaki
> 5. kabul ölçütü tam olarak bunu yakalamak için var ve **#540**'ın (exhaustiveness guard
> 14 alanın yalnız 9'unu — yani tam olarak bağlı alanları — kapsıyor) doğal örtüşmesidir.
> **#540'ı F-26'ya ALMA**, ama testi kurarken kapsamı **14 alanın tamamı** olacak şekilde yaz.

Kullanıcı gerçeği ancak stratejiyi kurduktan **sonra** Ready Check'te öğreniyor
(`STRATEGY_SCALING_UNSUPPORTED`). **Yetki açığı değil** — sunucu koşuyu reddediyor, motor
pozisyon açmıyor. Bu bir **disclosure** kusuru ve hata yönü **güvensiz**.

### #533 — yanlış-POZİTİF (varsayılan konfigde sahte blocker)

Yepyeni bir stratejide, sevk edilen varsayılanlarla form şunu basıyor:
*"Not available in this build: Allow Hedge is saved but will not run — Ready Check blocks it."*
**Ready Check bloklamıyor.** Backend üçlü paritesi tam ve bilinçli —
`conflict_handling_is_modelled` (`engine.py:573-576`), `_read_opposite_hedge`
(`capabilities.py:638-645`), readiness blocker (`validators.py:644-655`): `exit_on_opposite_signal`
AÇIKKEN pozisyon hedge dalına ulaşmadan kapanır, kaydedilmiş `allow_hedge` **inert**tir ve
doğru olarak bloklamaz.

```
DEFAULT (allow_hedge + exit_on_opposite_signal=True):
  future_dev_selections()       = []
  conflict_handling_is_modelled = True    -> blocker YOK; koşu trade eder
HEDGE   (allow_hedge + exit_on_opposite_signal=False):
  future_dev_selections()       = ['conflict_position_handling.opposite_direction_hedge=allow_hedge']
  conflict_handling_is_modelled = False   -> blocker; motor pozisyon açmaz
```

`backend/tests/unit/test_capability_matrix.py:444` (`test_inert_allow_hedge_stays_runnable`)
bunu zaten kanıtlıyor. Frontend `SelectField` notu **yalnız değere** bakıyor;
`exit_on_opposite_signal`'a erişimi yok (`StrategyConfigForm.tsx:152-162`, not metni
`:190-201`). Form varsayılanı `opposite_direction_hedge=allow_hedge`
(`strategyForm.ts:365`), backend varsayılanı `exit_on_opposite_signal=true` → sahte not
**varsayılan** render. Notun kendi dependency cümlesi preamble'ı ile çelişiyor.
Severity MEDIUM: hata yönü **güvenli** (aşırı-uyarı), ama her yeni stratejide sahte blocker
iddiası capability notlarına güveni aşındırıyor.

### Tuzak — bunu atlama

#539'un naif düzeltmesi (**değere** bakıp kapıla) tam olarak #533'ü çoğaltır. Backend
okuyucular değere değil **erişilebilirliğe** bakıyor:

* `_read_filter_types` (`capabilities.py:633-635`) → `enabled=false` filtreyi **inert** sayar
* `_read_opposite_hedge` (`capabilities.py:638-645`) → `exit_on_opposite_signal`'a bakar

Ortak çözüm: `SelectField`'e *"bu `future_dev` değer şu an inert, çünkü …"* predicate'ini
**çağıran kart** sağlar; not, blocker iddiası yerine inertlik açıklaması olur. Gerçekten
bloklanan hâl için mevcut sert ifade **aynen** korunur.

### Reçete

1. `SelectField`'e opsiyonel inert-reason / reachability parametresi ekle
   (`StrategyConfigForm.tsx:126-207`'deki `capabilityField` sözleşmesini genişlet:
   `blockedValues` mevcut değeri **hariç** tutar, `disabled`,
   `— not available in this build` son eki, dependency notu `aria-describedby` ile bağlı).
2. `ConflictCard` `exit_on_opposite_signal`'ı geçirsin (#533).
3. Aynı `capabilityField`'i `StrategyGraphForm`'un `SelectField`'ine ver ve üç alanı bağla;
   `scaling.enabled` / `filter.enabled` ile kapıla — **değerden değil** (#539).
4. `MODELLED_FILTER_TYPES`'ı sil, `ENGINE_CAPABILITY_MATRIX`'ten türet **+ parity testi ekle**
   (şu an elle bakımlı 3 elemanlı kopya, sessizce sapabilir — D-6).

### Kabul ölçütleri

* Varsayılan strateji (`allow_hedge` + `exit_on_opposite_signal=true`): "Ready Check blocks it"
  **iddiası yok**; yerine inertlik açıklaması.
* `exit_on_opposite_signal=false`: gerçek blocker ifadesi **aynen** korunur.
* 3 GraphForm alanının herhangi birinde **kaydedilmiş** bir `future_dev` değeri
  disabled-ama-seçilebilir render edilir, dependency notuyla.
* `scaling.enabled=false` / `filter.enabled=false` iken **ne** not **ne** disable çıkar.
* Matrix'in herhangi bir alanındaki bir `future_dev` satırı capability muamelesi görmeden bir
  forma ulaşırsa test **kırılır**.
* "Kaydedilmiş değer seçilebilir kalır" sözleşmesi korunur
  (`engineCapabilityMatrix.test.tsx:107-125` bunu kilitliyor).

### Test boşluğu (doğrulandı)

`engineCapabilityMatrix.test.tsx` şu an **yalnız** `DataExecutionCard` ve `PositionSizingCard`
render ediyor. `ConflictCard` ve `StrategyGraphForm` hiçbir capability testinde **yok**. Her
ikisi için de her iki dalı (inert / gerçekten bloklu) kapsayan test ekle.

### Sınır

Yalnız sunum. **Dokunma:** `domain/backtest/capabilities.py`, `_read_opposite_hedge`,
`CAPABILITY_MATRIX` satırları, `engineCapabilityMatrix.generated.ts` (**üretilmiş** — bir
backend parity testi onu byte byte pinliyor; reçetenin 4. maddesi onu **tüketmek** demek,
düzenlemek değil), readiness validator ve `opposite_direction_hedge`'in sevk edilen
**varsayılan değeri** (ayrı ürün kararı — F-4 issue'su). Ayrıca route path, react-query key,
OCC token, Idempotency-Key, hooks, SSE taksonomisi, API çağrıları ve `lib/*.ts` veri mantığı
değişmez. Migration / OpenAPI / engine **yok**. V18 mockup
(`docs/spec/index_guncellenmis_duzeltilmis_v18.html`) görsel referans.

---

## Çalışma yöntemi (bu slice için)

1. **Önce üret, sonra düzelt.** Hiçbir edit'ten önce ikisini de yeniden üret:
   (a) backend — varsayılan `StrategyConfig` ile `future_dev_selections(config) == ()` ve
   `conflict_handling_is_modelled(config) is True`; (b) frontend — `ConflictCard`'ı varsayılan
   form state'iyle render edip sahte notun **göründüğünü**, `StrategyGraphForm`'da üç alanın
   disabled opsiyonunun **boş** olduğunu göster (`scaling_logic.enabled=true`,
   `timeframe="1h"`, `timeframe_mode="increasing_by_layer"`).
2. Direct-author; Workflow yok. Kod-review CRITICAL/HIGH bulgularını **ampirik doğrula**.
3. Doğrulama: `cd frontend && npm run typecheck && npm run lint && npm run coverage`
   (vitest için `--no-file-parallelism` **zorunlu**; worktree'de `node_modules` yoksa önce
   `npm ci` — ilk koşudaki `ERR_MODULE_NOT_FOUND` test hatası değil).
   Backend'in dokunulmadığını `git diff --stat` ile **kanıtla**.
4. PR aç, **merge etme** — self-merge kapalı, merge kullanıcıdan istenir.

---

## Sıraya girmeyen açık kalemler

| # | konu |
|---|---|
| #550 / #551 / #552 | ADIM 12 engine uyuşmazlıkları (ürün kararı + fix karışık) |
| #556 / #557 | agent gateway parity — doğal çözüm iki yüzeyi **TEK** resolver'a bağlamak (`_require_viewable_root`, `_has_approved_feature_definition`) |
| #558 / #559 | ürün kararı bekliyor (bundle time-policy pini; DST fold/gap) |
| #514 | ekran okuyucu (NVDA/VoiceOver) denetimi — **kapatma yetkisi insanda**, agent kapatamaz |

---

## Paste-ready resume prompt (TÜKETİLDİ — F-26 landed, PR #564)

> Bu prompt **koşuldu ve slice landed**. Yeni bir oturuma **yapıştırma**; burada
> yalnız tarihsel kayıt olarak duruyor. Sıradaki iş için `docs/STAGE2_HANDOFF.md`
> §Next'e bak.

```
ENTROPIA — F-26: Strategy formu capability disclosure (#539 + #533, TEK slice)

Session START protokolü: git fetch --all --prune ; git status --short (kirliyse DUR) ;
origin/main'i doğrula ; her iki issue'nun da AÇIK olduğunu teyit et.
Sonra docs/ADIM13_LANDED_KICKOFF.md'yi oku — reçete, kabul ölçütleri ve sınır orada.

Branch: fix/strategy-form-capability-disclosure
Commit: fix(strategy-form): make capability notes reachability-aware in both forms
(AI attribution YOK)

ÖNCE ÜRET, SONRA DÜZELT — hiçbir edit'ten önce:
 (a) backend: varsayılan StrategyConfig ile future_dev_selections(config) == () ve
     conflict_handling_is_modelled(config) is True olduğunu göster;
 (b) frontend: ConflictCard'ı varsayılan form state'iyle render edip
     "Ready Check blocks it" notunun GÖRÜNDÜĞÜNÜ göster; StrategyGraphForm'da
     scaling_logic.timeframe / timeframe_mode / filters.filter_type alanlarının
     disabled opsiyonlarının BOŞ olduğunu göster (scaling_logic.enabled=true,
     timeframe="1h", timeframe_mode="increasing_by_layer").
İkisi de gösterilmeden tek satır kod yazma.

TUZAK: #539'u DEĞERE bakarak kapılarsan #533'ü çoğaltırsın. Backend okuyucular
ERİŞİLEBİLİRLİĞE bakıyor (scaling.enabled, filter.enabled, exit_on_opposite_signal).
Ortak çözüm: SelectField'e inert-reason predicate'ini ÇAĞIRAN KART sağlar.

DOKUNMA: capabilities.py, _read_opposite_hedge, CAPABILITY_MATRIX satırları,
engineCapabilityMatrix.generated.ts (üretilmiş, backend parity testi byte byte pinliyor),
readiness validator, opposite_direction_hedge'in sevk edilen VARSAYILAN DEĞERİ (F-4).
Route path / react-query key / OCC token / Idempotency-Key / hooks / SSE taksonomisi /
API çağrıları / lib/*.ts veri mantığı DEĞİŞMEZ. Migration/OpenAPI/engine YOK.

Test: ConflictCard ve StrategyGraphForm şu an hiçbir capability testinde YOK
(engineCapabilityMatrix.test.tsx yalnız DataExecutionCard + PositionSizingCard).
Her ikisi için de inert / gerçekten-bloklu iki dalı da kapsa.

Doğrulama: cd frontend && npm run typecheck && npm run lint && npm run coverage
(vitest --no-file-parallelism ZORUNLU; node_modules yoksa önce npm ci).
Backend'in dokunulmadığını git diff --stat ile kanıtla.

PR aç ve DUR — merge etme, merge kullanıcıdan istenir.
```
