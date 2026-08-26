<!-- doc-status: current -->

# ADIM 119 landed — `C6`'nın OD-1/OD-6 yarısı sevk edildi; P2/P8'in kapıları BU PR AÇIKKEN İMZALANDI

**Taban:** `42352048` (ADIM 118 = #850). Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 119.
**Numara ÜÇ KEZ taşındı: `117` → `118` → `119`.** Bu slice `ADIM 117` yazıldı; **#849**
o adı aldı → `118`; sonra **#850** `118`'i aldı → **`119`**. Üçünde de sebep aynı: PR
açıkken main ilerledi ve **merge edilen ad kazanır**. Her seferinde numara **dosya
yoluyla** ölçüldü (`ls docs/ADIM11*_LANDED_KICKOFF.md`), başlıkla değil.
**Hiçbir kayıt silinmedi**; #849'un `117`'si ve #850'nin `118`'i olduğu gibi duruyor.

---

## Nerede olduğumuz

`C6` dört admission blocker'ı ister — **OD-1 · OD-6 · P2 · P8**. Bu slice **ikisini**
sevk etti; diğer ikisi **yazılmadı, çünkü ÖLÇÜLDÜĞÜ AN kapıları imzasızdı**.

> **DEĞİŞTİ — ve bu ölçümün bir ANLIK GÖRÜNTÜ olduğunun kanıtı:** kutular bu dalda
> `11:0x`'te boş ölçüldü, **#849** onları `11:51:09Z`'de imzaladı, yani bu PR açıkken.
> Ölçüm yanlış değildi, **bayatladı** (ADIM 100'ün dersi). Sevk edilen kod etkilenmez:
> OD-1/OD-6 ADR §13.1'e dayanır, `G11`/`G12`'ye **hiç dayanmıyordu**.

| Ön koşul | Konu | Sahip | Durum |
|---|---|---|---|
| **#13** | P2 — ertelenen fill / bekleyen limit | **insan** | ✅ `G11` **İMZALANDI (#849)** — sıradaki slice |
| **#14** | P8 — paylaşımlı koşuda scaling | **insan** | ✅ `G12` **İMZALANDI (#849)** — sıradaki slice |
| **#15** | OD-6(a) — non-executing kind sleeve tutamaz | E6 | ✅ **BU SLICE** |
| **#16** | OD-1(a) — mixed `record_time_basis` | E6 | ✅ **BU SLICE** |

**`SHARED_ALLOCATION_STATUS` = `future_dev` (KALDIRILMADI)** · `ENGINE_VERSION`
**değişmedi** · migration **YOK** · OpenAPI **değişmedi (ölçüldü)** · kabul tavanları
**el değmedi** (54/6 · A1 B21 C6 D32) · blocker **1** (yalnız A-08), **BLOCKED**.

---

## Bu slice'ın bıraktığı REUSE çapaları (tam sembol adlarıyla)

**Yeni modül — P2/P8 blocker'larının EVİ:**
`domain/allocation/shared_mode_admission.py`

- `EXECUTING_ITEM_KINDS` — **pozitif** küme (`{STRATEGY}`); yeni bir `MainboardItemKind`
  otomatik olarak non-executing sayılır (fail-closed). Tamamlayanını yazma.
- `non_executing_sleeve_holders(capital_execution) -> tuple[str, ...]` — OD-6
- `mixed_record_time_bases(data_time) -> tuple[str, ...]` — OD-1
- `declared_record_time_bases(...)` — OD-1'in yardımcısı; **`None` bir kova DEĞİL**
  (beyan yokluğu bir rakip konvansiyon değildir)
- Metin sabitleri: `NON_EXECUTING_ITEM_{MESSAGE,REMEDIATION,FIELD_PATH}` ·
  `MIXED_RECORD_TIME_BASIS_{MESSAGE,REMEDIATION,FIELD_PATH}`

**Wire yerleri:** `application/commands/backtest_run.py::_admit_run_body`, adım **3b**
(OD-6, snapshot'tan hemen sonra) ve **3c** (OD-1, `resolve_run_manifest_context`'ten
sonra, `new_id("btrun")`'dan **önce**). İkisi de containment guard'ının **arkasında**.

**Kodlar:** `domain/readiness/enums.py::ReadinessIssueCode` →
`ALLOCATION_SHARED_MODE_NON_EXECUTING_ITEM` ·
`ALLOCATION_SHARED_MODE_MIXED_RECORD_TIME_BASIS`

**İki-dünya lift fixture'ı** (P2/P8 testleri de buna MECBUR):
`tests/integration/test_shared_mode_admission.py::_lifted` —
`patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")`.

**Harness:** `_attach_ready_strategy(session, actor, workspace_id, *, basis=None)` —
`record_time_basis` set edebilen **tek** builder · `_two_strategy_composition` ·
`_enable_shared` · `_assert_nothing_admitted` (job sayımı **`backtest` KUYRUĞUNDA**,
toplamda değil — Trade Log import pipeline'ı kendi `import` job'ını meşru olarak yazar) ·
yerel `fake_object_store` fixture'ı.

**Motor tarafındaki kardeş tablo:** `domain/backtest/participant.py::_unsupported_shapes`
— P2/P8 satırları **orada zaten var** (`entry_timing`/`exit_timing`, order type, scaling,
stacking). `C6`'nın kalan yarısı yazılırken admission listesi **o tabloyla eşleşmeli**;
OD-1/OD-6 orada **yok ve olmamalı** (iki tablo farklı soru sorar — biri tek çözülmüş
koşuyu, diğeri kompozisyonun tamamını).

---

## Sıradaki hamle — KOD DEĞİL, İKİ İMZA

1. **`G11`** → `docs/decisions/closure_g11_deferred_fill_admission_2026-08-18.md` §Karar
   - dispozisyon (a) / (a-dar) / (b) / (c) · blocker adı · `field_path` · üç hüküm onayı
   - **ÖN KOŞUL:** imza kutusu üretim DB'sinden bir **sayı** istiyor (kaç `active`
     Strategy revizyonu erteleyen bir timing / bekleyen emir tipi taşıyor). **Bu sayı
     ALINMADI.** Repo fixture'ları vekil değildir.
2. **`G12`** → `docs/decisions/closure_product_decisions_2026-08-13.md` §Karar 6
   - A / B / C / D + (A ise) ret nerede görünür
   - ADIM 71'in ölçümü A'yı *"ölçülmüş zorunluluk"* yapıyor, **ama imza yerine geçmez**.

İmzalar düşerse `C6`'nın kalan yarısı yukarıdaki çapalarla **tek oturumda** yazılır.
İmzalar gelmezse sıradaki paralel kalem **`C7`** (A16 manifest split — `C4`+`C5`
bekliyor, `C6` ile paralel).

---

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **İmza kutusunu BÖLÜM bazında oku.** `closure_product_decisions` dosyasında işaretli
  kutular **var** ama hepsi başka kararlara ait; §Karar 6 aralığı boş. Dosya düzeyinde
  grep yanıltır.
- **Ön koşulu slice'ın PARÇALARI için ölç.** Defter
  (`closure_w0_containment_lift_preconditions_2026-08-17.md` §2) `#13/#14`'ü **insan**a,
  `#15/#16`'yı **E6**'ya veriyor.
- **Lift etmeden test yazma.** Containment açıkken bu guard'lar ULAŞILAMAZ; lift etmeyen
  bir test containment'ı kanıtlar, guard'ı değil.
- **NC harness'i belleğe geri yazsın**, versiyon kontrolünden geri alma **kullanmasın**
  (dosyalar commit'siz — geri alma onları siler) ve her turdan sonra `git status`
  okunsun (`finally` SIGTERM'de koşmaz).

---

## Paste-ready resume prompt

```
ENTROPIA — C6'nın kalan yarısı: P2 (G11) + P8 (G12) admission blocker'ları

ÖNCE DOĞRULA (handoff BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state all
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3

## ÖN KOŞUL KAPISI — ARTIK YEŞİL (#849, 2026-08-26). YİNE DE DOĞRULA.
  Kapılar imzalandı; kutuları YİNE DE kendin oku (bu slice'ın kendi dersi: ölçüm bayatlar).
  1. G11 -> closure_g11_deferred_fill_admission_2026-08-18.md §Karar
     İMZALI: [x] (a) admission blocker — entry VE exit, erteleyen timing + bekleyen emir tipi
     kod:  [x] ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED
     field_path: [x] "ikisi de" — lider alanı gösterir, details tümünü taşır (O-02)
     DİKKAT: "patlama yarıçapı" kutusu [x] SAYILAMADI olarak imzalandı; belge o sayı
     alınmadan imzalanmamasını istiyordu. Bu bir ÜRÜN SAHİBİ kararıdır, yeniden açma —
     ama P2 blocker'ının kapsamını genişletmek için gerekçe olarak da KULLANMA.
  2. G12 -> closure_product_decisions_2026-08-13.md §Karar 6
     İMZALI: [x] A (admission'da blokla)  +  [x] "ikisi de"
     => P8 TEK KATMAN DEĞİL: hem Ready Check blocker (Portfolio/Ready Check sayfasında
        görünür) HEM admission reddi. Yalnız admission yazmak imzayı EKSİK uygular.
        Ready Check yarısı domain/allocation/rules.py::validate_allocation'a, admission
        yarısı _admit_run_body'ye ait — OD-1/OD-6'nın aksine İKİ yer.

## ZATEN İNMİŞ (ADIM 119) — DUPLICATE FIX YAZMA
  OD-1(a) ve OD-6(a) blocker'ları SEVK EDİLDİ (ön koşul #15 + #16 kapandı).
  Ev: domain/allocation/shared_mode_admission.py
  Wire: application/commands/backtest_run.py::_admit_run_body adım 3b + 3c
  Kodlar: ReadinessIssueCode.ALLOCATION_SHARED_MODE_NON_EXECUTING_ITEM
          ReadinessIssueCode.ALLOCATION_SHARED_MODE_MIXED_RECORD_TIME_BASIS

## GÖREV (imzalar yeşilse)
  P2 ve P8 blocker'larını AYNI modüle ekle, aynı wire noktasından geçir.
  - Admission listesi participant.py::_unsupported_shapes ile ESLESMELI (P2/P8
    satırları orada zaten var: entry/exit timing, order type, scaling, stacking).
    OD-1/OD-6 orada YOK ve olmamalı — iki tablo farklı soru sorar.
  - Blocker adı + field_path İMZALANAN ŞIKKA GÖRE yazılır, kendin seçme.
  - NO-TOUCH: engine.py, portfolio_engine.py
  - Migration YOK · ENGINE_VERSION YOK · OpenAPI: readiness kodları openapi.json'da
    YAYIMLANMIYOR (ADIM 119'da ölçüldü) -> şema kıpırdamaz.

## TEST KURALLARI
  - Blocker başına BİR refüz + BİR negatif kontrol (yasal config admit EDİLMELİ).
  - LIFT ET: tests/integration/test_shared_mode_admission.py::_lifted. Lift etmeyen
    test containment'ı kanıtlar, guard'ı DEĞİL.
  - Harness hazır: _attach_ready_strategy / _two_strategy_composition / _enable_shared
    / _assert_nothing_admitted (job sayımı 'backtest' KUYRUGUNDA).
  - Refüzü exception SINIFIYLA pinleme — zarfın code/field_path'ini assert et.
  - NC belleğe geri yazsın, versiyon kontrolünden geri alma KULLANMA (dosyalar
    commit'siz); her turdan sonra git status oku.

## ORTAM
  cd backend && uv sync --all-extras
  export TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_c6
  Alt küme koşarken --no-cov; exit code'u AYRI oku; GateGuard'da 4 olguyu sun.
```
