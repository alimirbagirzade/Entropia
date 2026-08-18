<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM77_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 76 LANDED — P-E6/C8: containment kapısının ikinci dünyası · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 76. Bu belge **devam noktasıdır**, kayıt değil.
> Ön koşul ölçümü: `docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md`.

## Neredeyiz

Base **`0f0651d`** · alembic head **`0043_i08_registry_strategy_fks`** · `ENGINE_VERSION`
**değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` = **`future_dev`
(DEĞİŞMEDİ)** · migration **YOK** · **ürün kodu değişmedi**. **Blocker sayısı DEĞİŞMEDİ
(1 — yalnız A-08), verdict BLOCKED.**

Kabul borcu tavanlarına bu slice **dokunmadı**. **Buraya sayı yazma — canlı otorite
`docs/audit/acceptance_coverage_baseline.json`**: tabanda A=1 · B=69 · C=6 · D=32 / açık
**108** idi, **#757 (ADIM 75) arada indi** ve B **66** / açık **105** oldu.
`total_criteria` **383** (taban) değişmedi. Bu slice bir kabul kriteri kapatmadı — **ratchet'e
dokunulmadı** (bilinçli: yeni testler kriter kapatmıyor, kapının ikinci dünyasını açıyor).

Üretilmiş olgular tazelendi: backend collected **3625 → 3635**, frontend call site
**722 → 723** (delta +10 / +1; taban ölçümü 3610 → 3620 / 718 → 719 idi). **Sayıya değil
`docs/generated/repository_facts.md`'ye güven.**

## Bu slice'ın öğrettikleri (tekrar etmemek için)

1. **`and`/`or` üzerine kurulu bir kapıyı BİLEŞİK sonucuyla test etmek kısa devrenin
   arkasını ölçmez.** Negatif kontrolüm bunu canlı gösterdi: `shared_allocation_requested`'ı
   flag-aware yapan perturbasyon truth-table testimi **hiç kırmadı**, çünkü lifted dünyada
   guard ilk terimde kısa devre yapıyor. Çare: **hücre başına iki conjunct'ı ayrı assert et.**
   Bir docstring'in iddia ettiği şeyi testin gerçekten ölçtüğünü **negatif kontrol** söyler.
2. **Prompt'un tabanı bayat olabilir, SHA'ya güven.** Prompt `31ed27d` bekliyordu, main
   **8 commit ileride** (`0f0651d`) idi. Ölçümler yeniden yapıldı.
3. **`| tail` exit code'u yutar** — `ruff check . | tail` **exit=0** gösterdi, gerçek **1**'di.
4. **Test ekleyen slice `repository_facts` üretmek ZORUNDA** (ADIM 60'ın dersi): kapı
   `Backend` job'ının erken adımı, ~50 saniyede kırmızı yapar.
5. **Postgres bu container'da kurulu (PG16) ama koşmuyor.** Kaldırma reçetesi: `initdb`
   **root olarak koşmaz**, ve scratchpad yolu `nobody` için **traverse edilemez** →
   cluster'ı `/var/tmp`'de kur:
   `su nobody -s /bin/bash -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/entropia-pg -U entropia --auth=trust"`
   sonra `pg_ctl -D … -o '-p 5432 -k /var/tmp' start` + `createdb … entropia`. Tam suite
   ve coverage kapısı böylece **yerelde** koşar.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- **`backend/tests/unit/test_shared_allocation_two_world_gate.py`** — 10 test, hepsi
  negatif kontrolden geçmiş. İçindeki `_lifted(monkeypatch)` **test-owned lift fixture**'ıdır
  (`monkeypatch.context()` + `capability.SHARED_ALLOCATION_STATUS`); lifted bir dünyada bir
  şey ölçmek isteyen her slice **bunu** kullanmalı, ikinci bir idiom icat etmemeli.
  Neden çalıştığı docstring'inde: `rules.py`/`backtest_run.py` **fonksiyon** referansı tutar,
  fonksiyonun `__globals__`'ı `capability`'nin dict'idir.
- `test_the_lift_fixture_actually_moves_the_world` — **anti-vacuity**. İki dünyalı bir
  dosyada ilk test bu olmalı, yoksa altındaki her şey sessizce no-op olabilir.
- `test_the_worker_fold_never_consults_the_capability_flag` — **`C4` bu testi kıracak** ve
  kırması doğrudur: `_use_unified_clock` inince bu dosya wiring'in parçası olarak güncellenir.
- `test_shared_allocation_containment.py::_item_run` / `_plan` / `_refs` /
  `_capital_execution` — iki-dünya dosyası bunları **import ediyor**, kopyalamıyor.
- Frontend: `portfolio.test.tsx` içindeki *"drops the containment notice when the server
  reports the mode available"* — `SHARED_MODE_CAPABILITY`'yi **spread edip** `available: true`
  yapar; shipped fixture'a **dokunmaz**.

## BULGU — `C9`'un devraldığı iki kalem (kapatmaya çalışma, ikisi de `C9`'un dosyalarında)

1. **Capability metinleri flag'i izlemiyor.** `shared_allocation_capability_view()` lifted
   dünyada `available: true` ile *"not available in this build"* mesajını **birlikte**
   yayımlar. `test_the_capability_texts_do_not_follow_the_flag` bunu **characterization**
   olarak pinler (#559 emsali) — `C9` metinleri flag-aware yapınca **o test kırmızıya döner,
   bu kasıtlıdır**. Bugünün sayfası korunuyor (`Portfolio.tsx:358` `!available` arkasında) ve
   yeni frontend testi bunu pinler.
2. **`MARK_STALENESS_POLICY`** (`provenance.py:80` = `"undefined_pending_od2"`) ve
   **`CONTENTION_SELECTION_STATUS`** (`arbitration.py:195` = `"recommended_pending_approval"`)
   hâlâ çevrilmedi — ön koşul #17/#18.

## Sıradaki tasarım işaretleri

> **⚠ BU BÖLÜM SLICE KAPANIRKEN DEĞİŞTİ (PR #753, `9fc5580`, 21:54Z).** Ölçüm anında
> (`0f0651d`) `G9` ve `G13` **imzasızdı**; kapanış yazılırken ürün sahibi ADR §16 **Gate 1**'i
> oturum içinde **imzaladı**: **`G9` APPROVED**, **`G13` = FOLD**. Kayıt `docs/adr/0002-…md`
> **§13.2**. Yani ADIM 72'den beri taşınan *"sıradaki hamle bir İMZADIR"* cümlesi **artık
> yanlış — sıradaki hamle KODDUR (`C2`)**. Ön koşul sayısı **değişmedi (2/22)**: madde #5
> bileşiktir ve P10 **sevk edilmedi** (*"No product code ships with this amendment"*).

**Kritik yol artık `C2` ile başlıyor.** `docs/decisions/closure_product_decisions_2026-08-13.md`
+ **`docs/adr/0002-unified-clock-portfolio-simulation.md` §13.2**:

| Kapı | Blok | Durum | Kimi bloklar |
|---|---|---|---|
| **`G9`** | ADR **§13.2** — §6/§8 amendment'ı (`settle`+`finalize`+P10+`iter_portfolio`) | ✅ **İMZALANDI (2026-08-17, #753)** — *APPROVED as stated*; `settle`/`finalize` **zorunlu** Protocol üyesi, `hasattr` probe'u **yasak** (fail-open) | **artık hiçbir şeyi bloklamıyor** |
| **`G13`** | ADR **§13.2** — P10 end-of-data equity noktası | ✅ **KARARA BAĞLANDI: FOLD** — aynı `t_ms`'te `commit_tick`; append **reddedildi** (A5'in by-construction iddiasını korur) | **artık hiçbir şeyi bloklamıyor** |
| **`G10`** | ADR §16 Gate 2 — flag flip + `ENGINE_VERSION` bump onayı | **TALEP EDİLMEDİ** | `C9` |
| **`G11`/`G12`** | P2 (deferred fill) / P8 (scaling) admission blocker'ı | **İMZASIZ.** `G12`'nin imza bloğu **#752 ile YARATILDI** (yer açtı, karar vermedi) ve ADIM 71'in *"scaling ayrılamaz"* ölçümünü `001a4c7`'de **yeniden doğruladı** (guard `engine.py:3253` `position`/`led.trades` okur, stacking `:2998-:3252` ikisini de yazar) → **ölçülmüş ZORUNLULUK**. `G11` hâlâ brief edilmedi. | `C6` |
| **`G8`/`G14`** | #559 / #544 | **İKİSİ DE AÇIK** (`reopened`) | `C9` |

**Kalan kapıları bir ajan kapatamaz (ADR §16).** Ama `C2`'nin önündeki iki kapı **artık
açık**, o yüzden sıradaki slice **kod yazabilir**.

**SIRA: `C2` (E4b) — ARTIK BAŞLANABİLİR.** ADR §13.2'nin imzaladığı sözleşme:
1. `ItemParticipant.settle(view, admitted) -> None` — **admission callback**, P5/P6
   arbitrasyonundan SONRA; bir item'ın kendi intent'ine karşı sermaye book edebileceği
   **tek** nokta. `entry()` içinde book etmek arbitrasyondan ÖNCE taahhüt olurdu (`C6`'nın
   adlandırdığı sessiz-degradasyon şekli).
2. `ItemParticipant.finalize(view) -> MandatoryExit | None` — end-of-data kapanışı, **P10**
   tarafından koşulur.
3. **İkisi de ZORUNLU Protocol üyesi** — `hasattr` ile probe etmek **yasak** (fail-open;
   `settle`'ı unutan participant sessizce düz koşar). mypy yapısal olarak zorlayamıyorsa
   plan `C2`'nin stop condition'ı geçerli: **dur ve seam'i yeniden düşün.**
4. `PHASE_ORDER` → `("P1","P3","PV","P4","P5","P6b","P7","P9","P10")`; sabit **değer olarak**
   yayımlanır, faz-sırası testi onunla birlikte taşınır (bilerek).
5. **P10 döngüden SONRA BİR KEZ** koşar, `(pin_ordinal, item_id)` sırasıyla; ardından
   **G13/FOLD**: son tick'in **aynı** `t_ms`'inde `commit_tick`. **Yeni nokta EKLEME** —
   bir `t_ms`'e iki nokta A5'i kırar.
6. `iter_portfolio` = `run_portfolio`'nun tick-sürülebilir generator formu; **aynı faz
   sırası, ikinci bir booking politikası YOK**.

Sonra: `C3` (`_EngineParticipant` + reconciliation/sleeve-parity invariant'ları) → `C4`
(worker dalı + A21 tick checkpoint + tripwire daraltma) → `C6`/`C7` → **`C8` (gerçek worker
oracle'ları — BU slice onu yazamadı, çünkü yolun kendisi yoktu)** → `C9` (lift).

**`C9` hâlâ uzakta:** `G10` (Gate 2) **talep edilmedi**, `G11`/`G12`/`G8`/`G14` açık,
`participant.py` için **importer-allowlist incelemesi** insan işi (sicilde 17 kapı, 16'sı açık).

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki slice
ROL: Entropia V18 Principal Engineer ve Release Closure Owner.

SESSION START (atlamadan):
  git fetch --all --prune ; git status --short  -> kirliyse DUR
  git switch main ; git reset --hard origin/main ; git rev-parse HEAD
  Beklenen taban: ADIM 76 sonrası main. FARKLIYSA durma, farkı RAPORLA ve
  bu kickoff'un her sayısını yeniden ölç (kickoff'un ETİKETİNE değil SHA'sına güven).

OKUMA SIRASI: (1) docs/ADIM76_LANDED_KICKOFF.md  (2) docs/PROJECT_HISTORY.md §ADIM 76
  (3) docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md  (§2 = 22 ön koşul)
  (4) docs/implementation/final_closure_ordered_plan_2026-08-13.md §PACKAGE C
  (5) docs/generated/repository_facts.md = SAYISAL OTORİTE

DURUM: SHARED_ALLOCATION_STATUS = future_dev. 22 containment ön koşulundan 2'si yeşil.
  G9 + G13 ARTIK İMZALI (ADR-0002 §13.2, PR #753) -> C2 AÇILDI.
  G10 (Gate 2 / lift) talep EDİLMEDİ; G11/G12/G8/G14 açık. Blocker 1 (A-08), BLOCKED.

İLK İŞ: C2 / E4b. Sözleşme ADR-0002 §6 madde 6-7 + §8.2 P10 + §13.2'de YAZILI:
  - settle(view, admitted) = admission callback (arbitrasyondan SONRA book et)
  - finalize(view) -> MandatoryExit | None = end-of-data kapanışı, P10 koşar
  - İKİSİ DE ZORUNLU Protocol üyesi; hasattr probe'u YASAK (fail-open)
  - PHASE_ORDER -> (...,"P9","P10"); P10 döngüden sonra BİR KEZ
  - G13 = FOLD: aynı t_ms'te commit_tick. YENİ NOKTA EKLEME (A5 kırılır).
  - iter_portfolio = run_portfolio'nun generator formu; ikinci booking politikası YOK
  Kabul: 25 oracle KIPIRDAMASIN, 50 golden digest BAYT BAYT AYNI kalsın.
  mypy settle/finalize'ı yapısal olarak zorlayamıyorsa -> DUR, seam'i yeniden düşün.

PAZARLIKSIZ:
  - SHARED_ALLOCATION_STATUS'u değiştirmek 22 ön koşul + G8/G10/G14 ister ve ADR §16
    insan onayıdır. Kendi başına açma.
  - future_dev containment pinlerini GEVŞETME; onlar kapının kendisi.
  - Lifted bir dünya ölçeceksen test_shared_allocation_two_world_gate.py::_lifted kullan.
  - Her assertion'ı NEGATİF KONTROLDEN geçir; and/or kapılarında terimleri AYRI pinle.
  - Test eklediysen: cd backend && uv run python ../scripts/generate_repository_facts.py --root ..
  - Alt küme koşarken --no-cov ; `pytest | tail` KULLANMA ; exit code'u AYRI oku.
  - Kapanış ritüeli 6 madde (CLAUDE.md §Session CLOSING). Yeni kickoff `current`,
    ADIM76 `historical` — İKİSİ BİRLİKTE.
```
