<!-- doc-status: current -->

# 27D — Unified portfolio production oracle + containment lift: **VERDICT = BLOCKED**

- **Tarih:** 2026-08-26
- **Ölçülen taban:** `origin/main` @ `8a1d52d8` (`test(backtest): pin the shared-clock branch's
  arbitration at the worker … (#839)`) — worktree bu commit'e ff edildi (0 ahead / 80 behind idi).
- **Yazarın rolü:** ölçüm. **Hiçbir karar verilmemiştir, hiçbir bayrak çevrilmemiştir.**
- **Sonuç:** `SHARED_ALLOCATION_STATUS` **`future_dev` KALIR**. `ENGINE_VERSION` **bump
  EDİLMEDİ**. Ürün kodunda **sıfır satır** değişti. `feat(backtest): activate canonical
  shared-capital portfolio execution` PR'ı **AÇILMADI** — planın kendi stop condition'ı bunu
  yasaklıyor (`final_closure_ordered_plan_2026-08-13.md:844`).

---

## §0 — Önkoşul yanlışı: görevin PRECONDITIONS bloğu ölçümle yanlışlandı

Görev *"27A, 27B, 27C merged"* ve *"#558/#559 … explicitly adjudicated"* diyordu.

| İddia | Ölçüm | Kanıt |
|---|---|---|
| #558 adjudicated | ✅ **DOĞRU** | `closure_product_decisions_2026-08-13.md` §Karar 2 — İMZALI (A1+A2, 2026-08-14) |
| #559 adjudicated | ❌ **YANLIŞ** | aynı belge, banner tablosu satır 3: *"3 — DST fold/gap (#559) — **İMZASIZ** — —"*. `gh issue view 559` → **OPEN / REOPENED**, `blocks-mixed-zone-axis` |
| ADR-required product decisions adjudicated | ❌ **YANLIŞ** | aşağıda §3; **G8, G10, G11, G12, G14 imzasız**; G10 **hiç talep edilmedi** |

**#559 tek başına lift'i tutar** ve bunu belge kendi sözüyle söylüyor: G8 satırının etki
sütunu **`C9 only`**'dir (`final_closure_ordered_plan…:287`). Yani görevin kendi
önkoşulu karşılanmamıştır ve FAIL CLOSED maddesi buradan tetiklenir.

---

## §1 — REMOVAL CONDITIONS, `capability.py`'nin kendi altı maddesi, güncel koda karşı

Kaynak: `domain/allocation/capability.py` §REMOVAL CONDITION md. 1–6.

| # | Koşul | Durum | Güncel koddan kanıt |
|---|---|---|---|
| **1** | Dış döngü **birleşik zaman ekseni**, item listesi değil | ✅ **KARŞILANDI** | `execution/clock.py:232 iter_ticks` — `sorted(union of decision_times)`, `groupby` ile instant başına bir `ClockTick`; sırasız girdi **fail-closed** (`:88`). Worker `backtest_engine.py:367` bu dala giriyor. |
| **2** | **TEK** paylaşımlı defter `P0`, `R0 = P0*r`, `U0` tutar | ✅ **KARŞILANDI** | `execution/portfolio_ledger.py:246-275` — `reserve_nominal` (R0) sabit nominal, `unallocated_initial` (U0) `__post_init__`'te türetilir, run başına **bir** plan. |
| **3** | Zorunlu olaylar ÖNCE, sonra **tam bir** `E(t)`; her item ona karşı `Ci(t)` | ✅ **KARŞILANDI (mekanik)** | `portfolio_engine.py:130 PHASE_ORDER = ("P1","P3","PV","P4",…)` — P3 (zorunlu) < PV (snapshot) < P4 (giriş). `portfolio_ledger.py:286 allocatable()` = `max(0, E - R0)`. Production yolunda pinli: `test_two_items_entering_at_the_same_tick_are_priced_against_one_frozen_pool`. |
| **4** | Arbitraj **simetrik**, deterministik id tie-break; engellenen payı **asla** devredilmez | ⚠️ **KISMİ — ÜRÜN KARARI EKSİK** | Deterministik tie-break **var** (`arbitration.py:369`, `(pin_ordinal, item_id)`), pay transferi **yok** (worker testinde sleeve toplamı = havuz). **AMA** seçim politikası kendini onaysız ilan ediyor: `arbitration.py:195 CONTENTION_SELECTION_STATUS = "recommended_pending_approval"` — *"**OD-3 is open.** … does not decide *which* of several individually-affordable intents is refused"*. `pin_order_admission` kıtlık altında **düşük pin'i kayırır**; "simetrik" iddiası bu yüzden **imzasızdır**. |
| **5** | doc 13 §14 test 11 geçer; bileşik eğri **yapı gereği** zaman-sıralı | ✅ **KARŞILANDI (paylaşımlı yolda)** | G13 **FOLD** olarak imzalandı (ADR §13.2, 2026-08-17) → `P10` `PHASE_ORDER`'da; A5 yapısal iddia olarak ayakta. Production yolunda: ters-liste, iki-kez-replay ve heterojen-timeframe case'leri (ADIM 115) — **koştu, yeşil** (aşağıda §5). |
| **6** | **`ENGINE_VERSION` bump edilmiş**, execution_key namespace kaymış | ❌ **KARŞILANMADI** | `manifest.py:145` = `"backtest-engine-v18-percent-sizing-per-fill-commission"` — **değişmedi**. `engine_golden_digests.json` içindeki `engine_version` **aynı literal**; 50 digest'in **9'u** `portfolio.*` ve **hiçbiri oynamadı**. |

**Altıda üç tam yeşil, biri kısmi (ürün kararı eksik), biri (md. 6) tanımı gereği lift'in
kendisi.** md. 6 kasten en sonda: bump, lift'in **eylemidir**, ön koşulu değil.

---

## §2 — 22 ön koşul (P-C2 §C.7), güncel koda karşı **YENİDEN** ölçüldü

`closure_w0_containment_lift_preconditions_2026-08-17.md` §2 tabanı **2026-08-17**'ydi ve
**22'de 2 yeşil** diyordu. O tarihten sonra `C3` (#777), `C4`/`E5` (#799 + #805) ve ADIM 115
(#839) indi → tablo **bayat**. Yeniden ölçüm:

| # | Ön koşul | 2026-08-17 | **8a1d52d8** | Güncel kanıt |
|---|---|---|---|---|
| 1 | E4a describe/book split | ✅ | ✅ | ADIM 71 (#735), 50 digest bayt bayt aynı |
| 2 | `_phase_tail` scaling ayrılabilir | ❌ | ❌ **AYRILAMAZ** | ADIM 71 ölçtü → `G12` **öneri değil zorunluluk** |
| 3 | `ItemParticipant.settle` + `.finalize` | ❌ | ✅ **YENİ** | `portfolio_engine.py:319`, `:334` |
| 4 | `iter_portfolio` generator formu | ❌ | ✅ **YENİ** | `portfolio_engine.py:628` |
| 5 | P10 + end-of-data equity kuralı | ❌ | ✅ **YENİ** | `PHASE_ORDER` P10 taşıyor; G13 FOLD imzalı (ADR §13.2) |
| 6 | `_EngineParticipant` adaptörü | ❌ | ✅ **YENİ** | `participant.py:193`, `:480 build_engine_participant` |
| 7 | Reconciliation invariant'ı | ❌ | ✅ **YENİ** | `ParticipantDivergenceError` (§C.3.6) + `attribution.py:137 realized_reconciled` |
| 8 | Sleeve-parity invariant'ı | ❌ | ✅ **YENİ** | `participant.py:110` — sleeve parity §C.3.5, `ParticipantDivergenceError` |
| 9 | `_use_unified_clock` dalı | ❌ | ✅ **YENİ** | `backtest_engine.py:159`, çağrı `:367` |
| 10 | Tick-strided cancellation (A21) | ❌ | ✅ **YENİ** | `_TICK_CHECKPOINT_STRIDE = 500`; iki case **koştu, yeşil** |
| 11 | Gate authorised-caller allowlist'e daraltılmış | ❌ | ✅ **YENİ** | `_AUTHORISED_LOOP_CALLERS` / `_LOOP_ENTRY_POINTS` |
| 12 | Bağımsız run'ların döngüye ulaşmadığının davranışsal kanıtı | ❌ | ✅ **YENİ** | `test_an_independent_multi_item_run_never_reaches_the_unified_loop` |
| **13** | **Deferred-fill / limit-order admission blocker (P2)** | ❌ | ❌ **İMZASIZ** | `closure_g11_deferred_fill_admission_2026-08-18.md` — kutular boş; belge kendisi *"`C9` (lift) öncesinde imzalanmak zorundadır"* diyor |
| **14** | **Scaling admission blocker (P8)** | ❌ | ❌ **İMZASIZ** | `G12` = `closure_product_decisions…` §Karar 6, kutular boş |
| **15** | **OD-6(a) blocker'ı** | ❌ | ❌ | `execution/intents.py:19` — *"whether a non-executing kind may hold a sleeve — that is **OD-6, still open**"* |
| **16** | **OD-1(a) blocker'ı (mixed `record_time_basis`)** | ❌ | ❌ | `execution/clock.py:38` — *"the clock … **does NOT branch on `record_time_basis`**"* |
| **17** | **OD-2 mark policy + `MARK_STALENESS_POLICY` flip** | ❌ | ❌ | `provenance.py:80` = **`"undefined_pending_od2"`** |
| **18** | **`CONTENTION_SELECTION_STATUS` flip** | ❌ | ❌ | `arbitration.py:195` = **`"recommended_pending_approval"`** |
| 19 | R-1 revizyon pin bayt eşleşmesi | ✅ | ✅ | `test_allocation_revision_pin.py` |
| **20** | **GH #544 (NET) kapalı** | ❌ | ❌ **OPEN/REOPENED** | canlı ölçüm, `blocks-adim-19`, `product-decision` |
| **21** | **GH #559 (DST) kapalı** | ❌ | ❌ **OPEN/REOPENED** | canlı ölçüm, `blocks-mixed-zone-axis` |
| **22** | **A15 bump + A16 manifest + A19 + A22** | ❌ | ❌ | `ENGINE_VERSION` değişmedi (§1 md. 6) |

**Sayı: 22'de 12 yeşil (2 → 12), 10 kırmızı.** Mühendislik tarafı büyük ölçüde bitmiş
durumda; **kırmızıların 10'unun 10'u da ya bir insan imzasıdır ya da imzasız bir ürün
kararının arkasındadır.**

---

## §3 — İnsan kapıları: lift'in bekledikleri

`C9`'un ön koşulu planın kendi sözüyle *"**All 22** … plus **G8 (#559)**, **G10 (ADR §16
Gate 2)**, **G14 (#544)**"*.

| Kapı | Konu | Durum | İmza yeri |
|---|---|---|---|
| **G8** | #559 DST fold/gap | ❌ **İMZASIZ** | `closure_g8_dst_fold_gap_2026-08-25.md` §Karar 1/2/3 — **üç kutunun üçü de boş** |
| **G10** | **ADR §16 Gate 2 — flag flip onayının kendisi** | ❌ **HİÇ TALEP EDİLMEDİ** | ADR §13.2: *"It also does **not** discharge §16's **Gate 2** (lifting containment), which **remains unrequested**"* |
| **G14** | #544 NET conflict policy | ❌ **İMZASIZ** | `closure_g14_net_conflict_policy_2026-08-25.md` §Karar 1/2/3 — **üç kutunun üçü de boş** |
| **G11** | Deferred-fill admission (P2) | ❌ **İMZASIZ** | `closure_g11_deferred_fill_admission_2026-08-18.md` |
| **G12** | Paylaşımlı koşuda scaling (P8) | ❌ **İMZASIZ** | `closure_product_decisions…` §Karar 6 |
| G9 | ADR §6/§8 amendment | ✅ İMZALI | ADR §13.2, 2026-08-17 |
| G13 | P10 equity noktası | ✅ İMZALI (FOLD) | ADR §13.2, 2026-08-17 |
| G16 | A-08 (#514) | ❌ **AÇIK** | 2/184 hücre, 0/10 akış, **0/4** çıkış kriteri — nihai RC verdict'ini bağımsız bloklar |

**G10 özel:** lift'i onaylayacak kapı **hiç talep edilmemiş**. ADR §16 kendi tarihini
kaydediyor: ADIM 15/17/19 `Proposed` statüsündeyken indi ve belge bunun *"ADIM 20 için
tutması gerektiğini"* — çünkü **sevk edilmiş bir sayıyı değiştiren ilk slice odur** —
açıkça yazıyor. Bu slice o kapıyı **kendi başına açamaz.**

---

## §4 — HARD GATE: istenen 20 production oracle'ın ölçülmüş durumu

Görev: *"Pure unit `portfolio_harness` is NOT sufficient"* — zincir
`API/admission → durable Job → real worker → real participant → run_portfolio → projection
→ persistence → readback` olmalı. Sevk edilen production-yolu suite'i
`tests/integration/test_shared_clock_worker_branch.py` (**14 case**, hepsi gerçek
`run_backtest` üzerinden).

| # | İstenen oracle | Production yolunda? | Karşılık |
|---|---|---|---|
| 1 | same-timestamp competing entries | ✅ | `..._priced_against_one_frozen_pool` |
| 2 | mandatory exits before snapshot | ✅ | `..._land_on_one_tick_in_phase_order` (`max(seq P3) < min(seq P4)`) |
| 3 | one shared `E(t)` | ✅ | aynı case — tek `reference_price`, eşit `granted_notional` |
| **4** | **reserve `R0`** | ❌ **YALNIZ UNIT** | worker-branch'te `R0`/`reserve_nominal` **0 eşleşme**; unit oracle'da 9+2 |
| **5** | **shared cash exhaustion** | ❌ **YALNIZ UNIT** | worker-branch'te `exhaust` **0 eşleşme** |
| **6** | **portfolio exposure cap** | ❌ **YALNIZ UNIT** | worker-branch'te `exposure` **0 eşleşme**; unit'te 21 |
| 7 | opposite-direction conflict | ⚠️ kısmi | faz-sırası case'i rakip ters girişi taşıyor; ayrık bir conflict oracle'ı yok |
| 8 | deterministic id tie-break | ⚠️ kısmi | `..._when_the_prepared_items_arrive_reversed` **sıra bağımsızlığını** pinler; `(pin_ordinal, item_id)` kayırmasının kendisi **OD-3 imzasız** (§1 md. 4) |
| 9 | heterogeneous timeframe alignment | ✅ | `..._walks_the_union_of_both_axes` (1D×22 ∪ 12h×43 = 65 tick) |
| 10 | available-time / no-lookahead | ⚠️ | A17 `test_research_point_in_time_parity.py` — **paylaşımlı yolda değil** |
| **11** | **fees / funding** | ❌ **YALNIZ UNIT** | worker-branch'te `fee`/`funding` **0 eşleşme**; unit'te 34/49 |
| **12** | **pending fills** | ❌ **YAZILAMAZ** | davranışı tanımlayan **G11 imzasız** — oracle'ın assert edeceği kanon yok |
| **13** | **same-direction scaling** | ❌ **YAZILAMAZ** | **G12 imzasız**; üstelik ADIM 71 `_phase_tail` scaling'in **ayrılamadığını** ölçtü |
| 14 | cancellation | ✅ | tick-içi iptal + checkpoint #4, ikisi de Result **yazmıyor** |
| 15 | per-item attribution | ⚠️ | `attribution.py` reconciliation sevk edilmiş; diagnostics **içerikçe** karşılaştırılıyor |
| 16 | Result persistence | ✅ | dört content checksum'ı üzerinden |
| 17 | manifest provenance | ⚠️ | dört policy alanı **var** ama **ikisi placeholder**: `undefined_pending_od2`, `recommended_pending_approval` |
| 18 | historical legacy Result readability | ✅ | `test_a_legacy_shared_pool_result_stays_readable_and_unmodified` |
| 19 | replay determinism | ✅ | `..._twice_produces_identical_artifacts` (A18) |
| 20 | reverse participant ordering metamorphic | ✅ | `..._when_the_prepared_items_arrive_reversed` |

**Sayı: 20'de 9 tam ✅, 5 kısmi ⚠️, 6 ❌.** Altı kırmızının **dördü** (4, 5, 6, 11) yalnız
unit `portfolio_harness` düzeyinde yaşıyor — görevin **açıkça yetersiz saydığı** düzey. Diğer
**ikisi (12, 13) yazılamaz**, çünkü assert edecekleri davranış henüz **karara bağlanmamıştır**.
Bir oracle imzasız bir politikayı pinlerse, kanonu doğrulamaz — **kaza eseri oluşmuş
davranışı kanonlaştırır.**

---

## §5 — Ne koşturuldu (dürüst sınır)

Bu container'da `uv sync --all-extras` yapıldı, Postgres `:5432` canlıydı, izole DB
`entropia_c9` kuruldu (`TEST_DATABASE_URL=postgresql+asyncpg://…`).

| Suite | Sonuç |
|---|---|
| `tests/unit/oracles/` (tam paket) | **152 passed**, exit **0** |
| `tests/unit/{oracles/test_oracle_portfolio_containment_gate,test_shared_clock_branch_predicate,test_shared_allocation_containment}.py` | **22 passed**, exit **0** |
| `tests/integration/test_shared_clock_worker_branch.py` + `test_shared_allocation_containment.py` | **21 passed**, exit **0** |

**KOŞULMAYANLAR:** tam backend suite (`--cov-fail-under=90`) ve frontend kapıları
**koşulmadı** → **A22 doğrulanmadı**; geçen sayının ve coverage yüzdesinin tek otoritesi bir
CI koşusudur. Exit code'lar `tail`'den değil **ayrı** okundu.

**Bu suite'lerin yeşili lift'in lehine bir kanıt DEĞİLDİR** — hepsi `future_dev` dünyasında
koşar; paylaşımlı case'ler bayrağı **testin kendisi** kaldırır. Yeşil olan şey *"dal
doğru çalışıyor"*tur, *"dal açılabilir"* değil.

---

## §6 — VERDICT

**BLOCKED.** Bayrak çevrilmedi, `ENGINE_VERSION` bump edilmedi, golden'lara dokunulmadı,
`backend/src`'te sıfır satır değişti.

**Eksik koşulların tam listesi (FAIL CLOSED'ın istediği kesinlikte):**

1. **G10 — ADR §16 Gate 2 hiç talep edilmedi.** Lift'i onaylayacak kapı yok.
2. **G8 / #559 (DST fold/gap) imzasız** — `C9`'a özel; issue OPEN/REOPENED.
3. **G14 / #544 (NET conflict policy) imzasız** — issue OPEN/REOPENED.
4. **G11 (deferred-fill admission, P2) imzasız** — belgesi `C9` öncesi zorunlu diyor.
5. **G12 (paylaşımlı koşuda scaling, P8) imzasız** — ADIM 71 ölçümüyle zorunlu.
6. **OD-2 açık** — `MARK_STALENESS_POLICY = "undefined_pending_od2"`.
7. **OD-3 açık** — `CONTENTION_SELECTION_STATUS = "recommended_pending_approval"`.
8. **OD-6 açık** — `intents.py:19`; OD-6(a) blocker'ı yok.
9. **OD-1 açık** — `clock.py:38`; mixed `record_time_basis` blocker'ı yok.
10. **Production-yolu oracle boşluğu** — R0, cash exhaustion, exposure cap, fees/funding
    yalnız unit düzeyinde; pending fills ve same-direction scaling **yazılamaz durumda**.
11. **A15/A22 karşılanmadı** — bump yok; tam suite bu ortamda koşmadı.
12. **G16 / A-08 (#514) açık** — nihai RC verdict'ini bağımsız olarak bloklar.

**ADR §15 R-5 bu sonucu kendi sözüyle önceden yazmış:** *"Lifting containment while OD-2/OD-3
are unanswered would re-introduce an undisclosed policy — **ADIM 20 must not merge until every
OD is recorded in the manifest as a versioned policy.**"* Bugün manifest o politikaların
**ikisini de** *"karar bekliyor"* diye yayımlıyor. Bayrağı çevirmek, o iki placeholder'ı
değiştirmeden, **imzasız bir politikayı kanonik bir Backtest Result'a sevk etmek** olurdu —
containment'ın var olma sebebinin ta kendisi.

**Sıradaki hamle kod değil, İMZADIR.** Sıra: `G8` + `G14` → `G11` + `G12` → `C6` → `G15`
(leg 3) → ön koşul 15–18 → **G10** → `C9`.
