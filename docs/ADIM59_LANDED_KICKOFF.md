<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 59 LANDED — P-A1 shared portfolio erişilebilirlik denetimi · sıradaki slice için kickoff

> **NUMARA NOTU — bu slice BİR KEZ taşındı: 58 → 59.** Denetim PR'ı (`#707`) **ADIM 58**
> adıyla yazılmış ve merge edilmişti; kapanış PR'ı (`#718`) merge sırasını beklerken main
> **`#715`**'i aldı ve o PR **`feat(adim-58)`** adıyla indi — kendi kickoff'unu,
> `PROJECT_HISTORY` kaydını ve handoff girdisini yazarak. Kural değişmedi: **numaralar
> yeniden atanmaz, merge edilmiş ad kazanır**; taşınan taraf hep **merge edilmemiş**
> olandır, bu turda o benim. Branch adı ve commit mesajları `stage-58` yazmaya devam eder;
> **slice'ın adı ADIM 59'dur.** `#715`'in üç kaydına **dokunulmadı** — yalnız kickoff'unun
> `doc-status` işareti düşürüldü, çünkü aynı anda tek belge `current` olabilir.
>
> **Yeni olan ne:** önceki taşımalar (48→50, 54→57) *yeşili elle beklemekten* doğuyordu ve
> çare **auto-merge** olarak kaydedilmişti. Bu taşıma **auto-merge'ün kapatamadığı** artık
> penceredir: denetim PR'ı `#707` auto-merge ile sorunsuz indi (üç main ilerlemesine
> rağmen numara taşınmadı — çare çalışıyor), ama **kapanış** PR'ı `Backend`'in ~50 dk'sı
> boyunca açık kalmak zorunda ve o pencerede **paralel bir oturum** aynı numarayı
> alabiliyor. **Ders: numarayı PR'ı AÇARKEN değil, kapanış commit'ini YAZARKEN doğrula —
> ve merge'den hemen önce `grep '^## ADIM' docs/PROJECT_HISTORY.md` ile BİR KEZ DAHA.**

---

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** ADIM 59 bunu **değiştirmedi** ve
değiştirmeyi hedeflemedi — salt-okunur bir denetim slice'ıydı.

- **Ürün kodu DEĞİŞMEDİ.** `backend/src` · `frontend/src` · `backend/alembic` ·
  `backend/tests` → `git diff --stat origin/main` = **0 satır**. Migration yok,
  `ENGINE_VERSION` sabit, `SHARED_ALLOCATION_STATUS = "future_dev"` (containment KAPALI).
- **Sevk edilen tek artefakt:** `docs/audit/closure_w0_shared_portfolio_2026-08-13.md`
  (579 satır, `doc-status: historical`).
- **A-08 DEĞİŞMEDİ:** defter **2 / 184** hücre, SR-1 hiç başlamadı, çıkış kriterleri
  **0 / 4**, `#514` **açık**.

---

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam adlarıyla)

| Anchor | Nerede | Ne için |
|---|---|---|
| `closure_w0_shared_portfolio_2026-08-13.md` | `docs/audit/` | §0 doğrulama tablosu · iki mermaid akış · importer haritası · tripwire assert-assert analizi · A1–A22 KARŞILANAN/KARŞILANMAYAN · en riskli beş seam |
| `_ItemStepper` | `domain/backtest/engine.py:756` | adapter'ın oturacağı substrat (faz-bölünmüş bar) |
| `_build_stepper` | `domain/backtest/engine.py:793` | stepper'ı kuran fabrika; `run_engine` (`:3279`) onun dokuz satırlık sürücüsü |
| `_phase_carry` / `_phase_held` / `_phase_entry` | `engine.py:1913` / `:2264` / `:2448` | describe/book ayrımının **tam olarak** dokunacağı üç yer |
| `ItemParticipant` | `domain/backtest/portfolio_engine.py:238` | adapter'ın karşılaması gereken üç hook |
| `run_portfolio` | `domain/backtest/portfolio_engine.py:518` | faz döngüsü — üretimde **çağrısız** |
| `_ScriptedParticipant` / `simulate` | `tests/unit/oracles/portfolio_harness.py:156` / `:210` | adapter'ın **şekil** referansı (davranış referansı DEĞİL) |
| containment gate | `tests/unit/oracles/test_oracle_portfolio_containment_gate.py` | E5'in kıracağı beş assert: `:180` `:184` `:218` `:222` `:125`/`:129` |
| iki fail-closed kapısı | `commands/backtest_run.py:542` · `domain/allocation/rules.py:154` | tek doğruluk kaynağı `domain/allocation/capability.py:105` |

---

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **Containment-gate'in YEŞİLİ ters okunur.** Geçmesi shared engine'in aktif olduğunu
   **değil**, üretimin `run_portfolio`'ya **ulaşmadığını** kanıtlar. İki merkezi assert
   negatiftir (`assert callers == []`); `5000.00` fixture'ı da sevk edilen fold **hâlâ
   yanlış** olduğu için geçer. `3000.00` raporladığı gün düşer — **o düşüş kabul kanıtıdır.**
2. **E5 tripwire'ı SİLMEZ, DARALTIR.** Boş beklenti → pinli çağıran allowlist'i
   (`_AUTHORISED_LOOP_CALLERS` / `_AUTHORISED_PROJECTION_CALLERS`) + `:182-184`/`:222`'yi
   bayrağa koşullu yapmak + *"hiçbir şey çağırmıyor"*un yerine geçecek asıl assert:
   worker'ın `shared_allocation_is_executable` / `shared_allocation_requested`'tan geçtiği.
   **`:225-233` ve `:103` E5'te DEĞİŞMEZ** — onlar *lift* kapısıdır. Bir E5 kendini
   `:230` ya da `:125`'i düzenlerken bulursa sessizce **ADIM 20 olmuştur**.
3. **`combine_item_runs` BAĞIMSIZ modun da yoludur** (`jobs/backtest_engine.py:348-372`).
   Doc 13 §1.1 bağımsız modu **birinci sınıf** ilan eder. Tüm çok-item koşularını faz
   döngüsüne yönlendiren bir wiring, **bayraksız, `ENGINE_VERSION` bump'sız ve kullanıcıya
   görünmeden** her bağımsız-mod kompozit Result'ını yeniden fiyatlar. Dal **tek** yerde
   ve `alloc_probe is not None and shared_allocation_is_executable()` olmalı.
4. **Tripwire bir METİN taramasıdır, AST değil.** `:180` bare `"run_portfolio(" in text`
   eşler → bir üretim modülündeki **yorum satırı** bile kırmızıya çevirir. `:222` çıplak
   `"portfolio_projection"` alt dizisini eşler. Mevcut docstring'ler yalnız parantezsiz
   ``run_portfolio`` yazdıkları için hayatta.
5. **Adapter'ı `execution/` İÇİNE koymak importer kontrolünü (`:170`) yapısal olarak
   çözer** (`path.parent.name == "execution"` muaf), **1-5'i çözmez**.
6. **Alt küme koşarken `uv sync --all-extras` ÖNCE.** Soğuk venv'de
   `uv run pytest -q --no-cov …` **exit 4** verir:
   `unrecognized arguments: --cov=entropia … --no-cov`. Test hatası değil, ortam hatası.
7. **Bayat tabanlı bir denetim ölçümlerini KOPYALAMAZ.** Bu slice'ın prompt'u `31ed27d`
   diyordu, main `0d8bf8f`'ti; dokuz ölçümün ikisi **yol** olarak, biri **anlam** olarak
   yanlıştı. Kopyalanan ölçüm denetim değil **yankıdır**.

---

## Açık kalanlar (ADIM 59 bunları KAPATMADI)

- **`ItemParticipant` adapter'ı + worker call site — YAZILMADI.** Tek kalan engel (b).
- **A1 · A2 · A3 · A4/A18 · A5 · A9 · A15 · A16 · A21** — hepsi KARŞILANMIYOR.
- **GH #544 (NET)** ve **#559 (DST)** — ikisi de **açık** `product-decision`.
- **GH #582** — **açık**; durumu doğru, **gövdesi üç iddiada bayat** (`run_portfolio`
  artık var · stepper artık var · A17 xfail 4 → **1**). **Düzeltilmedi: insan kaydı.**
- **Containment gate docstring `:146`** — hâlâ stepper için *"was never written"* diyor;
  ADR §12 AMENDMENT (#602) bunu geçersiz kılar. **Düzeltilmedi: denetim salt-okunurdu.**
- **A-08** · **K-5** (22/23) · **K-6a** · **K-7** — hiçbirine dokunulmadı.
- **P1-Gate3** kapanmadı.

---

## Sıradaki iş

**İki yol var, ikisi de meşru — ama biri kapıya bağlı.**

**(A) Adapter'ın saf-refactor yarısı (kapı gerektirmez).** `_phase_carry` / `_phase_held` /
`_phase_entry`'i describe/book olarak ayır: her biri ne yapacağını **döndürsün**, book
etme ayrı bir çağrı olsun. **Kabul ölçütü tektir: 46 golden digest'in HİÇBİRİ oynamayacak**
ve `backend/tests/unit/engine_golden_digests.json` dosyası değişmeyecek. Kendi PR'ında
inisin. **Digest oynarsa DUR** — o bir re-price'tır, restructure değil (ADR §15 R-4).

**(B) Wiring (ADR §16 insan kapısı GEREKİR).** Adapter + `run_portfolio` call site +
tripwire daraltması + A21 checkpoint yeniden konumlandırması + `PriorItemInterval`
emekliliği. **#544 açıkken lift edilmez** (ADR §9.4 onu ADIM 19'dan önce/onunla istiyordu).

**Seam sıralaması (en riskliden):** (1) faz describe/book ayrımı · (2) tripwire'ın beş
assert'i · (3) `combine_item_runs`'ın bağımsız-mod yolu · (4) cancellation checkpoint'leri
item→tick · (5) `PriorItemInterval` ↔ kanonik arbitrasyon çifte adjudication'ı.
Gerekçeler: `docs/audit/closure_w0_shared_portfolio_2026-08-13.md` §"Top 5 riskiest seams".

---

## Paste-ready resume prompt

```
[ORTAK SÖZLEŞME bloğunu buraya yapıştır]

ENTROPIA — ADIM 60 (ADIM 59'un ardından)

Session START protokolünü uygula. Otorite sırası:
  1. docs/ADIM59_LANDED_KICKOFF.md  (bu belge — sen buradan devam ediyorsun)
  2. docs/audit/closure_w0_shared_portfolio_2026-08-13.md  (P-A1 denetimi, ölçülmüş)
  3. docs/STAGE2_HANDOFF.md §"Stage — ADIM 59" + §Next
  4. docs/adr/0002-unified-clock-portfolio-simulation.md §12 / §13.1 / §14 / §16
  5. docs/generated/repository_facts.md  (SAYISAL OTORİTE)

DURUM (doğrula, kopyalama):
  - Blocker 1 (yalnız A-08), verdict BLOCKED. SHARED_ALLOCATION_STATUS = future_dev.
  - run_portfolio / project_portfolio_run / build_portfolio_manifest: üretimde ÇAĞRISIZ.
  - ItemParticipant'ın üretim implementasyonu YOK.
  - İlk sapma: application/jobs/backtest_engine.py:299 (for prepared in prepared_items:)
  - CLAUDE.md §4.1 (a) KAPALI: _ItemStepper engine.py:756, E(t) girişi
    _phase_entry(bar, *, equity) engine.py:2448. Kalan tek engel (b).

İŞ — İKİSİNDEN BİRİNİ SEÇ VE GEREKÇESİNİ YAZ:

(A) SAF REFACTOR, kapı gerektirmez — engine.py'nin üç fazını describe/book olarak ayır:
    _phase_carry (:1913) -> CarryCharges döndürsün
    _phase_held  (:2264) -> MandatoryExit döndürsün
    _phase_entry (:2448) -> ItemIntent döndürsün
    book etme AYRI bir çağrı olsun.
    KABUL ÖLÇÜTÜ TEK: 46 golden digest'in hiçbiri oynamayacak ve
    backend/tests/unit/engine_golden_digests.json DEĞİŞMEYECEK.
    Digest oynarsa DUR ve raporla — o bir re-price'tır (ADR §15 R-4).
    run_portfolio'ya çağıran EKLEME; containment gate yeşil kalmalı.

(B) WIRING — ADR §16 İNSAN KAPISI GEREKİR, kapıdan geçmeden BAŞLAMA.
    Kapı açıksa: adapter + call site + tripwire daraltması + A21 + PriorItemInterval.
    #544 (NET) açıkken LIFT ETME.

YASAK:
  - ENGINE_VERSION bump (o ADIM 20'dir)
  - SHARED_ALLOCATION_STATUS flip
  - containment gate'i SİLMEK (daraltmak serbest, silmek değil)
  - test_the_containment_flag_and_engine_version_are_both_untouched (:225-233) ve
    test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock (:103) düzenlemek
  - `-X theirs` ile strateji çözümü
  - #514 / #582 / #544 / #559 issue durumuna dokunmak

YEREL DOĞRULAMA: ORTAK SÖZLEŞME §YEREL DOĞRULAMA (tam suite, gerçek exit code'ları yaz).
Alt küme koşarken --no-cov ve ÖNCE uv sync --all-extras.

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin ALTI maddesi.
Dal: docs/stage-60-landed (docs) veya feat/stage-60-<slug> (kod).
Commit: <type>(stage-60): <subject>. AI attribution YOK. PR aç, MERGE ETME.
```
