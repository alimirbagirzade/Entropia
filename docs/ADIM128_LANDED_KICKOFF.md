<!-- doc-status: historical -->

# ADIM 128 — `C8`'in açık bıraktığı dört invariant worker'a çıktı + A4'ün çekişmeli yarısı ölçüldü · sıradaki kalem

> Bu belge **canlı** kickoff'tur. Bir önceki (`docs/ADIM127_LANDED_KICKOFF.md`) `historical`
> işaretlendi. Sayısal otorite bu belge DEĞİL — üretilmiş
> `docs/generated/repository_facts.md` ve tam kayıt `docs/PROJECT_HISTORY.md` §ADIM 128.

## Nerede duruyoruz

`origin/main` @ `853a61b7` (ADIM 127) üzerine inen bu slice **ürün kodu değiştirmedi** —
`backend/src` ve `frontend/src`'te **sıfır satır**. alembic head
`0044_drop_net_conflict_policy` (**migration yok**), `ENGINE_VERSION` değişmedi, OpenAPI
değişmedi, golden el değmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`. Blocker DEĞİŞMEDİ
(1 — yalnız A-08), **BLOCKED**.

ADIM 127 dürüst sınırında iki şey yazmıştı: A6/A7 ile A9/A10 worker düzeyine
**çıkarılmamıştı**, ve A4 **çekişmesiz** bir kompozisyonda ölçülmüştü. Bu slice ikisini de
ele aldı; **hiçbirini kapatmadı** ve kabul defterine dokunmadı.

## Bu slice'ın bıraktıkları (yeniden kullanım çapaları — TAM sembol adlarıyla)

Yeni modül: **`backend/tests/integration/test_shared_clock_capital_oracles.py`** (5 case);
toplanan test **3861 → 3866**, dosya **365 → 366**.

- **`_OVERSIZED = "150.0"`** — `position_sizing.base_position_size`, kapitalin YÜZDESİ.
  **Bu slice'ın tek fixture değişikliği ve dört invariant'ın da görünür olma sebebi:**
  `Ci(t)` yayımlanmış bir kolon değildir (Result `Ci(0)`'ı yayımlar), ama bir karar
  `remaining_sleeve` ile `capped` olduğunda `granted_notional` **sleeve'in kendisidir**.
  Stok %1 sizing'de istek sleeve'in iki büyüklük mertebesi altındadır ve hiçbir şey bağlamaz.
- **`_RESERVE_PERCENT = "10"`** · **`_SHARES = ("60", "40")`** — rezerv sıfırken taban `P0`'a
  eşittir ve rezervi yok sayan bir implementasyon her özdeşliği geçer; eşit paylar ise pay
  yapısını pin KONUMUNDAN dağıtan kusuru görünmez kılar (ADIM 127'nin ölçtüğü delik).
- **`_FLAT_COMMISSION_PER_FILL = Decimal("0.04")`** — `_strategy_payload`'ın komisyonu, ADIM
  114'ten beri fill başına **düz**. A10'un *"hiç doldurulmadı"* yarısının maddi kanıtı.
- **`_entry_ticks(session, result_id)`** — P4 kararlarını **instant'a göre gruplayıp** `seq`
  sırasında verir. Her iddia tek bir donmuş valuation hakkındadır.
- **`_oversized_shared_run(session, monkeypatch, *, compound, idempotency_key)`** — A6/A7
  ekseninin iki yakası; sermaye/rezerv/pay/bar/sizing **burada** sabitlenir, çağrı yerinde
  değil, yoksa eksen izole olmaz.
- **`_pool_equity_at_the_second_entry(session, result_id)`** — `E(t)`'yi **trade ledger'dan**
  yeniden türetir (`P0` + o ana kadar kapanan lotlar). Bunu oracle yapan şey budur: sleeve,
  sizing yolunun okumadığı bir artefakttan gelen bir figürle karşılaştırılır. Equity curve
  bu **intra-tick** anı yayımlamaz — P3 kitaplandıktan sonraki durumu değil, tick'in kendi
  valuation'ını taşır.

Genişletilen çapa helper'ları (**varsayılanlar bayt bayt aynı**, mevcut çağıranlar etkilenmedi):

- `test_shared_clock_worker_branch.py::_attach_strategy` / `::_composition` → **`size_percent`**
- `test_shared_clock_production_oracles.py::_enable_shared_pool_plan` → **`compound`**

## Ölçülmüş sayılar (tek fixture, `_e2e_bars` DEĞİŞTİRİLMEDEN)

`P0=50000`, rezerv %10 → `R0=5000`, `A0=45000`, paylar 60/40 → `Ci(0)=27000/18000`.
İki item 02-21'de girer, 02-22'de stop olur; o barda faz sırası **iki P3 çıkışını iki P4
girişinden önce** işler → ikinci giriş zaten para kaybetmiş bir havuza karşı kararlaşır.

| | değer |
|---|---|
| kapanan iki lot | **−298.56** ve **−199.05** → `E(t)=49502.39`, `A(t)=44502.39` |
| COMPOUND, tick 2 | `capped` **26701.43** / **17800.96** (= `A(t)×60` / `A(t)×40`) |
| A6 karşı-olguları (yadsınan) | `26820.86` (kendi lotu) · `26880.57` (kardeşin lotu) |
| FIXED, tick 2 | pin 0 `capped` **27000.00** · pin 1 **`rejected` 0/0 `ledger_insolvent`** |
| kesme yapılsaydı | **17502.39** (pozitif, ve 18000'den küçük) |
| FIXED + ters pin | reddedilen item **değişti** · bağlanan sermaye **27000 → 18000** · kapanış equity **49447.19 → 49465.58** |

## Sıradaki kalem

**Ön koşul 17 (OD-2 mark policy + `MARK_STALENESS_POLICY` flip) ve 18
(`CONTENTION_SELECTION_STATUS` flip) → sonra `C9`.** Defter (`docs/audit/
closure_w0_containment_lift_preconditions_2026-08-17.md` satır 90–91) ikisini de `E6`'ya
verir: `provenance.py` `"undefined_pending_od2"`, `arbitration.py`
`"recommended_pending_approval"`.

**Bu slice ön koşul 18 için KANIT ÜRETTİ ama onu İMZALAMADI.** 18'in beklediği şey
`pin_order_admission`'ın onaylanmasıdır; onaylayanın bilmek isteyeceği bedel artık ölçülü ve
sevk edilmiş bir Result üzerinde okunur: mainboard sırası **hangi item'ın reddedileceğini**,
**ne kadar sermaye konuşlandırılacağını** ve **havuzun kapanış equity'sini** belirler
(yukarıdaki son satır). İmza kutusuna dokunulmadı.

## Yöntem notu — bu slice'ta işe yarayan

1. **Yazmadan ÖNCE ölç.** Bir "probe" test dosyası kurulup worker'ın gerçekte ne persist
   ettiği basıldı (arbitration bloğu, equity curve, trade ledger, per-item attribution),
   sonra silindi. Testler o çıktıdan tasarlandı — `granted_notional`'ın sleeve olduğu,
   `arbitration` bloğunun `limits` **taşımadığı** ve çekişmenin yalnız fixed modda oluştuğu
   bu şekilde bulundu, tahmin edilmedi.
2. **Yeşil bir negatif kontrol bir BULGUDUR.** NC-3 ledger'ın solvency dalını kesti ve
   **yeşil geçti** → reddi veren guard'ın `arbitration._capacity_for`'un OD-3 dalı olduğu
   ortaya çıktı. Kontrol doğru yere kurulunca ayırt edici oldu.
3. **Kırmızının HANGİ satırda olduğunu oku.** NC-2'nin ilk yazımı kırmızı verdi ama hedefin
   assertion'ında değil, bir **ön koşulda** (`len(closed) == 2`) — reddedildi ve yeniden
   kuruldu. Ret bir yapısal gerçeği ölçtü: çekişme yalnız `sum(Ci_fixed)` `(A(t), A0]`
   aralığındayken vardır.
4. **Uzun bir suite koşarken `docs/` DÜZENLEME.** Tam suite'in tek kırmızısı
   `test_the_repository_itself_passes_the_documentation_truth_gate` oldu: o kapı çalışma
   ağacının **belgelerini** okur ve suite koşarken bu kapanış ritüeli tam o belgeleri
   yazıyordu — kapı kendi girdisi değişirken koştu (nihai ağaçta 38 passed / exit 0).
   Ayrıca: arka plan görevi *"exit 0"* raporladı, pytest **1** döndürmüştü — yeşil olan
   wrapper'ın `echo`'suydu; gerçek durum `FULL_SUITE_EXIT=$?` satırından okundu.
5. **Bir yardımcı, testin iddiasını yutabilir.** `_contended` reddedilen kararı önce
   **konumdan** alıyordu; NC-4 o zaman manşet iddia yerine bir ön koşulda düşüyordu. Karar
   artık **aranıyor** → kırmızı `control_refused != permuted_refused` satırına düşüyor.

## Paste-ready resume prompt

```
ENTROPIA — C9 öncesi: ön koşul 17 (OD-2 mark policy) + 18 (CONTENTION_SELECTION_STATUS)

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3

DURUM: ADIM 128'de A6/A7 + A9/A10 worker düzeyine çıktı ve A4'ün ÇEKİŞMELİ yarısı ölçüldü
(backend/src'te sıfır satır). A4 hâlâ `covered` DEĞİL — ölçüm, ADR §14'ün KOŞULSUZ A4
yazımının çekişme altında sağlanmadığını gösterdi ve ADR BİLEREK düzeltilmedi (adjudication).
Otorite: docs/PROJECT_HISTORY.md §ADIM 128 + docs/ADIM128_LANDED_KICKOFF.md.

GÖREV: ön koşul defterinin 17 ve 18. satırları
  (docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md, satır 90-91).
  17 → provenance.py MARK_STALENESS_POLICY = "undefined_pending_od2"
  18 → arbitration.py CONTENTION_SELECTION_STATUS = "recommended_pending_approval"
  ÖNCE ÖLÇ: bu ikisi KOD mu, İMZA mı? 18 bir ONAY bekliyor gibi duruyor — öyleyse
  DEFAULT SEÇME, sor. ADIM 119'un dersi: bir slice'ın ön koşulu PARÇALARI için ölçülür.

ÇAPALAR: tests/integration/test_shared_clock_capital_oracles.py içindeki
  _oversized_shared_run · _entry_ticks · _pool_equity_at_the_second_entry ·
  _OVERSIZED/_RESERVE_PERCENT/_SHARES · genişletilmiş _composition(size_percent=) ve
  _enable_shared_pool_plan(compound=)

YASAKLAR: capability.py DOKUNULMAZ (o C9). golden / migration / OpenAPI: hayır.
  ADR §14 invariant tablosunu YENİDEN YAZMA (adjudication). İmza kutusu doldurma.

TUZAKLAR (ADIM 128'de birinci elden ölçüldü):
  - Ci(t) yayımlanmış bir kolon DEĞİL; ancak `capped by remaining_sleeve` iken
    granted_notional olarak okunur. Stok %1 sizing'de hiçbir katman bağlamaz.
  - Çekişme yalnız FIXED modda oluşur (compound'da sleeve'ler tam A(t)'ye toplanır) ve
    yalnız sum(Ci_fixed) ∈ (A(t), A0] aralığında. Fixed tabanı oynatan bir NC çekişmeyi
    de götürür — bu ölçülmüş bir kısıt, tolere edilen bir kusur değil.
  - Reddi veren guard ledger'ın solvency dalı DEĞİL, arbitration._capacity_for'un OD-3 dalı.
  - Yeşil bir NC bir bulgudur; kırmızının HANGİ assertion'da olduğunu oku (ön koşulda
    kırmızı = kontrol REDDEDİLİR).
  - Alt küme koşarken --no-cov. Wrapper subshell'in exit code'u pytest'in DEĞİLDİR.

ORTAM: Postgres :5432 (entropia/entropia); TEST_DATABASE_URL ile izole DB kullan.
  backend/.venv yoksa `uv sync --all-extras`.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; her yeni assertion için
  AYIRT EDİCİ negatif kontrol; kapatmadığını `covered` İŞARETLEME; kapanış ritüeli ZORUNLU.
```
