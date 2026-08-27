<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# P-E6 / C8 — containment lift ön koşul ölçümü + iki-dünya kapısı

**Ölçüm tabanı:** `origin/main` @ `0f0651d` (2026-08-17).
**Prompt'un beklediği taban `31ed27d`'ydi; main o commit'in 8 commit ilerisindedir**
(`31ed27d` bir ata). Aşağıdaki her satır `0f0651d`'ye karşı yeniden ölçülmüştür.

**VERDICT: `SHARED_ALLOCATION_STATUS` DEĞİŞTİRİLMEDİ — `future_dev` kalır.**
22 ön koşulun **2'si** yeşil. Prompt'un kendi durdurma koşulu (*"Bir tanesi bile eksikse
FLAG'E DOKUNMA"*) uygulandı.

> ## ⚠ ÖLÇÜMDEN ~20 DAKİKA SONRA DEĞİŞTİ — `G9` ve `G13` İMZALANDI
>
> Bu belge `0f0651d`'yi ölçtü ve **`G9`/`G13` imzasız** buldu (§1, §2 satır 3/4/5, §3).
> **PR #753 (`9fc5580`, 2026-08-17T21:54Z) o iki kapıyı kapattı:** ürün sahibi ADR §16
> **Gate 1**'i oturum içinde imzaladı → **`G9` APPROVED as stated**, **`G13` = FOLD**
> (aynı `t_ms`'te `commit_tick`; append **reddedildi**, A5'in by-construction iddiasını
> koruyor). Kayıt: `docs/adr/0002-…md` §6 madde 6–7, §8.2 P10, **§13.2 amendment tablosu**.
>
> **Denetim satırları BİLEREK GÜNCELLENMEDİ** — bir denetim belgesi ölçtüğü anı dondurur
> (ADIM 65 emsali). Aşağıdaki *"imzasız"* ifadeleri `0f0651d`'de **doğruydu**; bugünkü
> otorite ADR §13.2'dir.
>
> **Ölçülen etkisi (yeniden sayıldı):**
> - **Ön koşul sayısı DEĞİŞMEDİ: hâlâ 2/22.** Madde #5 bir **bileşiktir** — *"P10 appended
>   to `PHASE_ORDER`; end-of-data equity-point rule decided"*. Kural artık **karara bağlı**
>   (FOLD), ama P10 **sevk edilmedi**: amendment kendi ağzıyla *"**No product code ships
>   with this amendment**"* diyor ve `PHASE_ORDER` hâlâ sekiz faz taşıyor.
> - **Ama kritik yolun ŞEKLİ değişti: `C2` artık BLOKLU DEĞİL.** ADIM 72'den beri geçerli
>   olan *"sıradaki hamle bir İMZADIR"* tespiti **artık geçerli değil** — sıradaki hamle
>   **koddur** (`C2` / E4b: `settle` + `finalize` + P10 + `iter_portfolio`).
> - **`G10` (ADR §16 Gate 2 — lift onayı) HÂLÂ TALEP EDİLMEDİ**, ve amendment bunu açıkça
>   söylüyor. **`G11` (P2), `G12` (P8), `G8` (#559), `G14` (#544) açık.** `participant.py`
>   için importer-allowlist incelemesi de açık. **Flag'e dokunmak hâlâ yasak.**

---

## §1 — Sert ön koşul: E5 (= plan `C4`) merge edilmedi, ve **kurulamaz**

Prompt *"P-E5 merged mı? Shared kod yolu tamam mı?"* diye soruyor. Ölçüm:

| Sembol | Beklenen yer | `0f0651d`'de |
|---|---|---|
| `_EngineParticipant` (plan `C3`) | `domain/backtest/participant.py` | **YOK** — `backend/src`'te sıfır eşleşme |
| `_use_unified_clock` (plan `C4`/E5) | `application/jobs/backtest_engine.py` | **YOK** |
| `ItemParticipant.settle` / `.finalize` (plan `C2`) | `portfolio_engine.py:270` Protocol | **YOK** — Protocol `carry`/`mandatory_exit`/`entry` taşır |
| `iter_portfolio` (plan `C2`) | `portfolio_engine.py` | **YOK** |
| `P10` | `PHASE_ORDER` | **YOK** — `("P1","P3","PV","P4","P5","P6b","P7","P9")` |

`C2` **imzaya bloklu**: `G9` (ADR §6/§8 amendment'ı) ve `G13` (P10 end-of-data equity
noktası) imza blokları **#750 ile YARATILDI** ama **imzalanmadı** — her kutu `[ ]`,
`karar veren:` boş (`docs/decisions/closure_product_decisions_2026-08-13.md:834`, `:911`).
Belge bunu kendi ağzıyla söylüyor (`:929`): *"Karar 4 ve Karar 5 yalnız İMZA BLOĞUDUR …
Bir ajan bu iki kapıyı kapatamaz (ADR §16)."*

Zincir: **`G9`+`G13` → `C2` → `C3` → `C4` → `C6`/`C7` → `C8` → `C9`.**
Yani prompt'un 1–3. maddeleri (**gerçek worker üzerinden oracle**, manifest namespace)
için **üretimde bir shared kod yolu yok**; onları şimdi yazmak ya boş (vacuous) bir test
olur ya da imzasız kapıların arkasındaki `C2`/`C3`/`C4`'ü bu slice'ta inşa etmek olurdu.
**İkisi de yapılmadı.** Yapılan: prompt'un **5. maddesi** — flag'i okuyan yüzeylerin
**iki dünyada** da anlamlı olduğunun kanıtı (§3).

---

## §2 — 22 ön koşul, tek tek ölçülmüş (P-C2 §C.7)

| # | Ön koşul | Sahip | `0f0651d` | Kanıt |
|---|---|---|---|---|
| 1 | E4a describe/book split, digest'ler oynamamış | E4a | ✅ **YEŞİL** | `engine.py:2087` `_compute_carry` / `:2143` `_book_carry` / `:2453` `_evaluate_held` sevk edilmiş (ADIM 71, #735; 50 digest bayt bayt aynı) |
| 2 | `_phase_tail` scaling bölümü ayrılabilir | E4a | ❌ **ÖLÇÜLDÜ: AYRILAMAZ** | ADIM 71: guard `position` + `led.trades` okur, stacking ikisini de yazar → **`G12` öneri değil ölçülmüş zorunluluk** |
| 3 | `ItemParticipant.settle` + `.finalize` | E4b (`C2`) | ❌ | Protocol `portfolio_engine.py:270` — üye yok |
| 4 | `iter_portfolio` generator formu | E4b (`C2`) | ❌ | sıfır eşleşme |
| 5 | P10 + end-of-data equity kuralı | **insan** | ❌ **İMZASIZ** | `PHASE_ORDER` P10 taşımaz; `G13` bloğu `decisions:911` boş |
| 6 | `_EngineParticipant` adaptörü | E4c (`C3`) | ❌ | sıfır eşleşme |
| 7 | Reconciliation invariant'ı | E4c (`C3`) | ❌ | portföy↔item defter mutabakatı için assertion yok |
| 8 | Sleeve-parity invariant'ı | E4c (`C3`) | ❌ | yok |
| 9 | `_use_unified_clock` dalı | E5 (`C4`) | ❌ | sıfır eşleşme |
| 10 | Tick-strided cancellation checkpoint (A21) | E5 (`C4`) | ❌ | `portfolio_engine.py`'de cancel yok; worker'ın checkpoint'i **item arası** (`backtest_engine.py:301`), tick değil |
| 11 | Containment gate authorised-caller allowlist'e daraltılmış | E5 (`C4`) | ❌ | gate hâlâ `callers == []` biçiminde (`test_oracle_portfolio_containment_gate.py:223`) |
| 12 | Bağımsız run'ların döngüye hiç ulaşmadığının davranışsal kanıtı | E5 (`C4`) | ❌ | `C4` inmedi |
| 13 | Deferred-fill / limit-order admission blocker (P2) | **insan** | ❌ **İMZASIZ** | `G11` brief edilmedi. **2026-08-26: İMZALANDI** (#849, dispozisyon (a) — entry + exit, erteleyen timing + bekleyen emir tipi). **2026-08-27: KOD İNDİ** (ADIM 125) — `execution/shared_shapes.py::unsupported_shared_shapes` → `ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED`, Ready Check + admission adım 3d. Containment'ın arkasında, sevk edilen build'de ULAŞILAMAZ. |
| 14 | Scaling admission blocker (P8) | **insan** | ❌ **İMZASIZ** | `G12`; md. 2 gereği artık zorunlu. **2026-08-26: İMZALANDI** (#849, Seçenek A + ret "ikisi de"). **2026-08-27: KOD İNDİ** (ADIM 125) — aynı predicate → `ALLOCATION_SHARED_MODE_SCALING_UNSUPPORTED`, `field_path=scaling_logic.enabled`. |
| 15 | OD-6(a) blocker'ı | E6 | ❌ | `execution/intents.py:19` — *"OD-6, still open"*. **2026-08-26: KOD İNDİ** (ADIM 119) — `shared_mode_admission.py::non_executing_sleeve_holders`, admission adım 3b. |
| 16 | OD-1(a) blocker'ı (mixed `record_time_basis`) | E6 | ❌ | `execution/clock.py:38` — *"does NOT branch on `record_time_basis`"*. **2026-08-26: KOD İNDİ** (ADIM 119) — `shared_mode_admission.py::mixed_record_time_bases`, admission adım 3c. |
| 17 | OD-2 mark policy + `MARK_STALENESS_POLICY` flip | E6 | ❌ | `provenance.py:80` = `"undefined_pending_od2"` |
| 18 | `CONTENTION_SELECTION_STATUS` flip | E6 | ❌ | `arbitration.py:195` = `"recommended_pending_approval"` |
| 19 | R-1: pinlenen config revizyon satırıyla bayt eşleşir | ayrı PR (`C5`) | ✅ **YEŞİL** | `tests/integration/test_allocation_revision_pin.py` (ADIM 72: zaten sevk edilmişti, negatif kontrolle doğrulandı) |
| 20 | GH **#544** (NET semantiği) kapalı | **insan/ürün** | ❌ **AÇIK** | `state: open`, `state_reason: reopened`. **2026-08-27: kararın KODU indi** — Karar 1'in `B` yarısı (`0044_drop_net_conflict_policy`: `NET` enum'dan düştü + kolon CHECK'i eklendi, `B3` halt guard'ı ile). Ön koşulun istediği şey issue'nun **kapanmasıdır** ve kapatma `human-only`; kalan tek eylem odur. |
| 21 | GH **#559** (DST kuralı) kapalı | **insan/ürün** | ❌ **AÇIK** | `state: open`, `state_reason: reopened`, `blocks-mixed-zone-axis` |
| 22 | A15 bump + A16 manifest + A19 + A22 | E6 (`C9`) | ❌ | `ENGINE_VERSION` değişmedi; manifest dört policy alanını taşımıyor (`test_oracle_portfolio_containment_gate.py:246`) |

**Sayı: 22'de 2 yeşil (#1, #19).** — *bu sayı `0f0651d`'ye aittir ve DONMUŞTUR;*
*satırlara sonradan eklenen tarihli notlar kolonu değiştirmez. Taze sayım için*
*`docs/PROJECT_HISTORY.md`'nin en son ADIM kaydına bak (ADIM 121: 18/22; ADIM 125*
*ile `C6`'nın dört blocker'ı da indi).* Ek olarak plan §2'nin `C9`'a özel üç kapısı:
**`G8`** (#559) ❌ · **`G10`** (ADR §16 Gate 2 — flag flip onayı) ❌ *talep edilmedi* ·
**`G14`** (#544) ❌. Ve **`G16`** (A-08, #514) açık → nihai RC verdict'i zaten bloklu.

---

## §3 — Bu slice'ın ölçtüğü İKİ YENİ BULGU

### Bulgu 1 — containment kapısı **TEK DÜNYALI** bir kapıydı

Ölçüm: `backend/tests` içinde `SHARED_ALLOCATION_STATUS`'u `"active_v1"`'e çeviren
**tek** test var — `test_backtest_portfolio_mode.py:160` — ve o testin **amacı** Result
resolver'ının flag'i **görmezden geldiğini** kanıtlamaktır. Yani flag'i okuyan **üç
üretim yüzeyinin hiçbiri** lift'in yarattığı dünyada hiç koşulmamıştı:

| Yüzey | Dosya:satır | Lifted dünyada test | Şimdi |
|---|---|---|---|
| Ready Check blocker'ı | `domain/allocation/rules.py:154` | **YOKTU** | `test_the_flag_gates_exactly_one_readiness_issue` |
| Run-admission guard'ı | `application/commands/backtest_run.py:542` | **YOKTU** | `test_the_admission_guard_refuses_in_exactly_one_of_the_four_cells` |
| Capability bloğu (UI) | `application/queries/allocation_plan.py:59` | **YOKTU** | `test_the_capability_texts_do_not_follow_the_flag` |

Frontend'de de aynı: `frontend/src/test/portfolio.test.tsx:43` `SHARED_MODE_CAPABILITY`
fixture'ı `available: false` **sabittir**; `Portfolio.tsx:358`'in
`containmentActive = enabled && !capability.available` dalının `true` tarafı hiç
render edilmemişti.

**Sonuç: flag'i çeviren PR, o üç yüzeyin ne yaptığını öğrenen ilk yer olurdu.**
Kapatıldı — `future_dev` pinlerinin **hiçbiri gevşetilmedi** (onlar kapının kendisidir ve
`C9` onları bilerek günceller); eksik olan **ikinci dünya** eklendi.

### Bulgu 2 — **flag bir reddetmedir, bir motor değildir** (ölçülmüş)

`jobs/backtest_engine.py:299` her item'ı **bağımsız** replay eder ve `:364`
`combine_item_runs` ile sırayla katlar. `capital_execution`'ı yalnız havuzun başlangıç
sermayesini seçmek ve kompozisyonu `shared_pool` diye **etiketlemek** için okur —
`shared_allocation_is_executable`'ı **hiç çağırmaz** (kaynak düzeyinde assert edildi).

Yani **bugün flag çevrilse**: Ready Check blocker'ı düşer, admission guard reddetmeyi
bırakır, ve worker shared-capital Result'ı **sıralı yaklaşımla** üretir — containment
mesajının *"portfolio drawdown ve ondan türeyen her metrik yanlış olurdu"* dediği
sayılarla. Ölçülmüş biçimi: **5000 drawdown**, gerçeği **3000**
(`test_shared_allocation_containment.py::test_composite_portfolio_curve_is_not_time_ordered`
bunu contained dünyada ölçüyor; yeni
`test_lifting_the_flag_alone_still_folds_the_sequential_curve` **lifted** dünyada aynı
yanlış sayıyı pinliyor).

**Okuru koruyan tek şey `portfolio_mode.py`'nin flag-bağımsızlığıdır** — Result
`legacy_sequential` etiketini ve `LEGACY_SEQUENTIAL_RESULT_NOTE`'unu **iki dünyada da**
korur (A19, yeni testte iki dünya birden). Ama bu bir teselli değil: sayı yine yanlış,
yalnız dürüstçe etiketli.

**Bu, `C9`'un neden SON slice olduğunun ölçülmüş gerekçesidir.**

### Bulgu 3 (küçük, sınıf: `C9` borcu) — capability bloğu lifted dünyada **kendi kendisiyle çelişir**

`shared_allocation_capability_view()` `status` ve `available`'ı flag'ten türetir ama
`message` / `remediation` / `dependency`'yi **koşulsuz sabit** olarak döner. Lifted
dünyada yayımlanan blok (ölçüldü):

```
available: true
message:      "Shared capital allocation is not available in this build. …"
remediation:  "Turn the Portfolio Allocation toggle off …"
dependency:   "… re-opens when the unified-clock multi-item co-simulation lands"
```

Bugünün Portfolio sayfası **etkilenmez** — `Portfolio.tsx:358` üç metni de
`!capability.available` arkasına alır. Ama blok **yayımlanan sözleşmedir**
(`allocation_plan.py` onu bilerek verbatim döner; ilke: *"the browser renders SERVER
state"*), ve `available`'ı kontrol etmeden `message` okuyan ikinci bir tüketici bir
**yanlış** basar. **#559 emsaliyle characterization olarak pinlendi**; `C9` bu üç metni
flag-aware yaptığında **o test kırmızıya döner ve bu kasıtlıdır** — metinler lift'in
parçasıdır.

> **Yeniden sınıflandırma YAPILMADI.** Bu bulgu bir `debt_class` taşımıyor ve kabul borcu
> ratchet'ine (`acceptance_coverage_baseline.json`) dokunulmadı: yeni test **var olan bir
> kabul kriterini kapatmıyor**, kapının **ikinci dünyasını** açıyor.

---

## §4 — Bu belgenin kapsamadıkları (dürüst sınır)

- **`SHARED_ALLOCATION_STATUS` DEĞİŞMEDİ.** `capability.py:105` `future_dev`.
  `ENGINE_VERSION`, golden digest'ler, `MARK_STALENESS_POLICY`,
  `CONTENTION_SELECTION_STATUS`, manifest ve OpenAPI **el değmedi**.
- **Üretim kodu DEĞİŞMEDİ** — `backend/src` ve `frontend/src/lib`, `frontend/src/pages`
  içinde sıfır satır. Bulgu 3 **ölçüldü, onarılmadı** (`capability.py` = `C9`'un dosyası;
  plan `C8` için *"no-touch: all production trees"* diyor).
- **Gerçek worker üzerinden oracle YAZILMADI** ve bu bir eksiklik değil bir **ölçüm
  sonucudur**: üretimde shared bir kod yolu yok (§1). Yazılan şey flag yüzeylerinin
  iki-dünya kapısıdır.
- **Hiçbir issue kapatılmadı/açılmadı/etiketlenmedi.** #514 / #544 / #558 / #559 olduğu
  gibi. **`G9`/`G13`/`G10` imzasız bırakıldı** — ADR §16 gereği bir ajan bunları kapatamaz.
- **A4 NOT EVALUABLE olarak kalır** (plan `C8`'in stop condition'ı): `mainboard_items`
  permütasyonunun gerçek bir Result üzerinde aynı digest'i vermesi bu commit'te
  ölçülemez. **`covered` işaretlenMEDİ.**
- **Postgres bu container'da yok** (`pg_isready` → no response) → integration suite
  yerelde koşmadı; **otorite CI**.
