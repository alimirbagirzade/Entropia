<!-- doc-status: current -->
# ADIM 117 LANDED — G11 + G12 imzalandı → sıradaki slice C6 (kickoff)

> **Bu belge ADIM 117'nin (G11+G12 imza slice'ı) kapanış kickoff'udur.** Tam kayıt:
> `docs/PROJECT_HISTORY.md` §ADIM 117. Önceki canlı kickoff (`ADIM116_LANDED_KICKOFF.md`)
> bu belgeyle `historical` oldu.

## Neredeyiz (2026-08-26, taban `bda4aba8` / #840)

- **İki imza atıldı, ürün kodu SIFIR satır değişti:**
  - **G11** → **(a) tam admission blok (entry + exit)**; kod
    `ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED`; `field_path` **ikisi de** (O-02);
    üç hüküm onayı evet. Ön koşul `sayılamadı` — belgenin kendi kuralı ürün sahibince
    **bilinçli geçersiz kılındı**, imzalı sapma notu kutunun altında.
  - **G12 (Karar 6)** → **A (admission'da blokla)**; ret **ikisi de** (Ready Check + admission).
- **`C6`'nın tüm ön koşulları tamam:** plan §6 `C6 = C4 + G11 + G12`; `C4` inmişti
  (#777/#799/#805). `SHARED_ALLOCATION_STATUS = future_dev` KALDI; `ENGINE_VERSION`,
  OpenAPI, migration: değişmedi. Blocker 1 (yalnız A-08), BLOCKED.
- **#847 (G8/DST) bu slice'ın CI'ı koşarken MERGE OLDU** ve `G8`'i imzaladı (`A1+B2+C1`,
  `closure_g8_dst_fold_gap_2026-08-25.md`); C9 verdict belgesi artık ağaçta, `historical`
  işaretli. #847 kendi ADIM kaydını yazmadı — kaydı sahibinin borcu (ADIM 97/109 emsali).

## Sıradaki slice: C6 — iki imzanın uygulaması (TEK slice, birlikte)

G11 §Ölçüm 5: iki kapı bağımsız değil → **birlikte uygulanır.**

1. **G11 blocker'ı:** erteleyen timing (`next_candle_open` / `next_candle_close` /
   `intrabar_touch`) **ve** bekleyen emir tipi (`order_config.type` `limit_order` /
   `stop_limit_order`) paylaşımlı modda → readiness blocker
   `ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED` (doc 14 §9.1: kod + message +
   remediation + field_path) **ve** `commands/backtest_run.py` admission guard'ında
   fail-closed tekrar (`shared_allocation_requested` emsali — bayat readiness state geçmesin).
   Yüzey **iki alandır** (G11 §Ölçüm 3): timing + emir tipi.
2. **G12 blocker çifti:** scaling-enabled Strategy içeren paylaşımlı koşu → Ready Check
   blocker + admission reddi; sevk edilen emsal çift `ALLOCATION_SHARED_MODE_NOT_IN_BUILD`
   (`backtest_run.py`) + `SHARED_MODE_NOT_IN_BUILD` (`domain/allocation/rules.py`).
3. **`_phase_tail` scaling dışlaması:** adaptör scaling bölümünü HİÇ çağırmamalı; ADIM 71
   ölçümü — dört bitişik üst-düzey blok, "scale ladder hariç" yapısal olarak ifade edilebilir.
   `_phase_tail` (3d) (`next_candle_close` ertelemesi) G11 §Ölçüm 4'ün ikinci book yüzeyidir —
   yalnız `open_fills`'i kesmek YETMEZ; (a) bloku sayesinde böyle Strategy adaptöre zaten
   ulaşmaz, ama negatif kontrol iki yüzeyi de adlandırmalı.
4. **Zorunlu negatif kontroller (G11 md. 4):** erteleyen timing'li Strategy ile paylaşımlı
   koşu **gerçekten** reddedilir · blocker kaldırılınca test **kırmızı** · **bağımsız mod aynı
   Strategy ile koşmaya DEVAM eder** (blok fazlasını kapatmasın) · sessiz downgrade hiçbir
   yerde yok (`fills.py` kuralı).

## REUSE çapaları

- Blocker deseni: `commands/backtest_run.py::_readiness_blocked` + `ALLOCATION_SHARED_MODE_NOT_IN_BUILD`.
- Timing haritası: `execution/fills.py::_fill_schedule` (+ `execution_timing_is_modelled` — o kapı
  BU ekseni tutmaz, G11 §Ölçüm 7).
- Telemetri hazır: `_Ledger.deferred_entry_fills` / `deferred_exit_fills` (G11 §Ölçüm 9) — yeni altyapı yok.
- Scaling koşma-anı reddi: `portfolio_engine.py`'daki `UnsupportedIntentKindError` — C6'da admission
  kapısı gelince bu **kaldırılmaz** (derinlik savunması; kaldırmak ayrı karar ister).

## Sonrası (sıra, görev promptundan)

`C6` → `G15` (leg 3 kazananı) → OD-1/2/3/6 (ön koşul 15–18) → `G10` (Gate 2, hiç talep edilmedi)
→ **EN SON `C9`**.

## Paste-ready resume prompt

```
ENTROPIA — C6: G11+G12 imzalarının uygulaması (admission blockers, TEK slice)

ÖNCE DOĞRULA: git fetch && git log --oneline origin/main -6 && gh pr list --state all
  (#847 G8/DST inmiş mi? ADIM sayısı kaç? Açık PR'lar ADIM<n> yolu ekliyor mu?)

İMZALAR (ADIM 117, 2026-08-26 — ikisi de imzalı, yeniden tartışma):
  - G11 = (a) tam admission blok; kod ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED;
    field_path "ikisi de" (O-02). Belge: docs/decisions/closure_g11_deferred_fill_admission_2026-08-18.md
  - G12 = A + ret "ikisi de" (Ready Check + admission). Belge:
    docs/decisions/closure_product_decisions_2026-08-13.md §Karar 6

GÖREV: docs/ADIM117_LANDED_KICKOFF.md §"Sıradaki slice: C6" maddelerini uygula —
  G11 blocker'ı (readiness + admission fail-closed tekrar, İKİ alan: timing + order_config.type),
  G12 blocker çifti, _phase_tail scaling dışlaması, dört zorunlu negatif kontrol.
  SHARED_ALLOCATION_STATUS = future_dev KALIR; ENGINE_VERSION, OpenAPI'ye yeni yüzey dışında
  dokunma; bağımsız modun davranışı HER seçenekte aynen korunur (P-C2 §C.4, pazarlıksız).

KURALLAR: her CRITICAL/HIGH bulguyu ampirik doğrula; alt küme koşarken --no-cov;
  exit code'u AYRI oku; GateGuard'da 4 olguyu sun; kapanış ritüeli ZORUNLU.
```
