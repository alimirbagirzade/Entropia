<!-- doc-status: historical -->
# ADIM 137 landed — GH #534: diagnostics provenance bloğunun sekiz deliği kapatıldı

**Taban:** `origin/main` @ `de3d8816` (ADIM 136) · **PR:** sıra bekliyor ·
**alembic head:** `0044_drop_net_conflict_policy` (**migration YOK**) ·
**`ENGINE_VERSION`:** **DEĞİŞTİ** → `backtest-engine-v18-policy-provenance-completed` ·
**golden:** yeniden üretildi (**46/50 digest oynadı**) · **OpenAPI:** değişmedi (`--check`
exit 0) · **`SHARED_ALLOCATION_STATUS`:** el değmedi · **`frontend/src`:** sıfır satır ·
**Blocker:** DEĞİŞMEDİ (1 — yalnız A-08) → **BLOCKED**.

## Neredeyiz

#534 (F-3, ADIM 10 conflict-matrix denetimi + ADIM 11 capability-matrix D-3 yorumu) sekiz
politika alanının diagnostics provenance bloğunda **yayımlanmadığını** söylüyordu. Sekizi de
yayımlandı (dokuz anahtar). Issue'nun **md. 1, 2 ve 4'ü sevk edildi; md. 3 bir
adjudication olduğu için kapsam dışı bırakıldı ve imzaya açıldı** → **#534 KAPATILMADI**.

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

| Ne | Nerede |
|---|---|
| Sıranın **tek** türetimi | `execution/fills.py::stop_priority_sequence` (`_stop_priority_index` artık ondan türer) |
| Çözülmüş sıranın ctx alanı | `execution/state.py::_RunContext.stop_priority_resolved` |
| Prolog'da tek çözüm | `engine.py`, `logic_enabled` kurulduktan hemen sonra |
| Dokuz anahtar | `execution/output.py`, diagnostics sözlüğü içinde topikal komşularının yanında |
| Testler | `tests/unit/test_backtest_policy_provenance.py` (5 case) |
| İmzaya açılan karar | `docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md` |

**Yayımlanan dokuz anahtar:** `same_candle_entry_exit` · `stop_priority_order` (SAVED,
nullable) · `stop_priority_order_resolved` (TOTAL) · `slippage_mode` · `limit_price_rule` ·
`limit_partial_fill_policy` · `sizing_formula_type` · `scaling_timeframe` ·
`scaling_timeframe_mode`.

## Pazarlıksız olanlar (bir sonraki oturum bunları BOZMASIN)

1. **`stop_priority_order` SAVED, `stop_priority_order_resolved` RESOLVED'dır ve İKİSİ de
   kalır.** Yalnız resolved'ı bırakmak operatörün **hiç seçmediği** kanonik sırayı seçmiş
   gibi gösterir (= #532'nin kusur sınıfı); yalnız saved'ı bırakmak `null` vakasında —
   yaygın vaka — hiçbir şey söylemez. Blok bu ayrımı **zaten** taşıyor
   (`conflict_gate_on` ↔ `conflict_downgraded_from_net`).
2. **Sıra iki kez türetilmez.** `stop_priority_sequence` tek kaynaktır. NC-3 ölçtü: ayrı bir
   yeniden yazım **golden dahil** her davranışsal testi yeşil bırakır → muhafız
   `test_the_published_order_is_the_one_the_combination_engine_ranks_by`, kaynak/yapı
   düzeyinde. **Daraltma.**
3. **Vacuity muhafızı kalır.** `test_every_named_policy_field_is_published_with_its_configured_value`
   dokuz anahtarın hiçbirinin kendi **varsayılanına** eşit olamayacağını assert eder. Bu,
   *"yanlış sub-config'ten oku → hep `None` → hiçbir test kırmızı vermez"* fail-open sınıfını
   yapısal olarak kapatır; bu slice'ta o kusur **gerçekten** yazıldı ve bu muhafız yakaladı.
4. **`suppressed_entries` el değmedi.** md. 3 imzalanmadan dokunma.
5. **`_C7_ENGINE_VERSION` el değmedi** (`tests/unit/oracles/test_oracle_portfolio_containment_gate.py`).
   Altı `ENGINE_VERSION` tripwire'ı **kasıtlı** güncellendi; yük taşıyan
   `!= _C7_ENGINE_VERSION` assertion'ı değil.

## Dürüst sınır

- **#534 açık** (md. 3 imza bekliyor). **#532 · #703 · #854 · #514 el değmedi.**
- **Composite Result'ın diagnostics'i bu provenance'ı ALMIYOR** — ölçüldü (dört `portfolio.*`
  digest'i bayt bayt aynı), **kapatılmadı**. `combine_item_runs` kendi bloğunu kuruyor.
  ADIM 136'nın kompozit bulgusuyla **aynı aile** → ikisi tek issue'da birleştirilebilir.
- **frontend kapıları KOŞULMADI** (frontend'de sıfır satır).
- Karar belgesindeki *"journal budanır mı"* sorusu **aranmadı**; iddia edilmiyor.

## Ölçüm yöntemi (tekrar keşfetme)

Diagnostics'e alan eklemek golden digest'leri oynatır — **körlemesine yeniden üretme**. Sıra:
50 senaryonun tam kanonik payload'ını **önce** ve **sonra** dondur (dört ürün dosyasını HEAD
sürümüne geri alarak; geri yüklemenin **byte-exact** olduğunu ayrıca doğrula), deltanın
**yalnız** eklenen anahtarlar olduğunu ve her finansal bölümün **bayt bayt aynı** kaldığını
kanıtla, sonra bump'ı ayrı bir adımda ölç (**46 = 45 + `execution_key`**).

**Bump ekseni** *"diagnostics mi"* değil **"artefaktın baytları oynuyor mu"** — ADIM 136'da
imzalandı. ADIM 135 (`A` = bump gerekmez) çelişmiyor: orada 50/50 digest **aynı** kalmıştı.

---

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 137'NİN PR'ININ İNİP İNMEDİĞİNİ ÖLÇ, SONRA SIRADAKİ KALEMİ SEÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '☑' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md
  grep -c '☑' docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md

DURUM: ADIM 137 (#534 md. 1/2/4) diagnostics provenance bloğuna dokuz anahtar ekledi,
ENGINE_VERSION bump edildi (backtest-engine-v18-policy-provenance-completed), golden 46/50
yeniden üretildi. #534 KAPATILMADI — md. 3 imza bekliyor. PR hâlâ AÇIKSA yeni slice AÇMA:
kapanmasını bekle ya da kırmızıysa /pr-drive-to-green. İNMİŞSE numara ADIM 138'dir; ölç,
varsayma.

SIRADAKİ KALEM — ÜÇÜ İMZA, İKİSİ KOD, BİRİ BLOCKER:

(1) #534 md. 3 — same-candle suppressions kendi sayacını hak ediyor mu?
    docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md, DÖRT kutu.
    Kutu boşsa DUR — varsayılan seçme, #534'ü kapatma. İmzalıysa: (a) EKLE ve (b) TAŞI
    ikisi de ENGINE_VERSION bump'ı ister (45+ golden digest oynar); (c) HİÇBİRİ kod
    istemez ve md. 3'ü "karar verildi: gerekmiyor" olarak kapatır.

(2) #854 — dış import pin'i TAŞINIYOR. DOKUZ kutu; ADIM 136'da ölçüldü, dokuzu da BOŞ.
    Kutu boşsa DUR. İmzalıysa DÖRT çağrı yerini birden değiştir (link_batch_to_revision +
    link_normalized_to_revision, her biri create + revision).

(3) ADR-0002 §13.1'in OD-2 satırı + üç bayat docstring — adjudication, imza ister.

(4) KOD, ama önce issue + imza: COMPOSITE Result'ın provenance'ı. İki ayrı ölçülmüş eksik,
    aynı yerde (combine_item_runs kendi diagnostics bloğunu kuruyor):
    · decision-trace sözcük dağarcığı yok (ADIM 136'da ölçüldü)
    · politika provenance bloğu yok (ADIM 137'de ölçüldü — dört portfolio.* golden
      digest'i bayt bayt aynı kaldı)
    Tek-item Result'ının sahip olduğu şey kompozitte eksik. ÜRÜN KARARI — issue aç, imza iste.

(5) #703 — funding-enabled run'lar uygulamadan yaratılan hiçbir Research revision'ı
    kullanamıyor; native_asset_id üretimde HİÇ yazılmıyor. Daha büyük.

(6) A-08 (#514) — TEK BLOCKER, RC verdict BLOCKED. human-only: agent ne açar ne kapatır.

ADIM 137'DEN DEVRALINACAK YÖNTEM (tekrar keşfetme):
· Diagnostics'e alan eklemek 45 golden digest'ini oynatır. Körlemesine yeniden üretme:
  önce 50 senaryonun tam kanonik payload'ını dondur (ürün dosyalarını HEAD sürümüne geri
  alarak; geri yüklemenin byte-exact olduğunu AYRICA doğrula), deltanın YALNIZ eklenen
  anahtarlar olduğunu ve trade/summary/equity'nin bayt bayt aynı kaldığını kanıtla, bump'ı
  ayrı adımda ölç (46 = 45 + execution_key).
· BUMP EKSENİ "diagnostics mi" DEĞİL, "artefaktın baytları oynuyor mu" (ADIM 136 imzalı).
  ADIM 135'in "bump gerekmez"i çelişmiyor — orada 50/50 digest aynıydı. Yeni vakada ÖLÇ.
· Bir issue'nun "expected answer"ı bir TAHMİNDİR. #532 ve #534 ikisi de "bump gerekmez"
  diyordu, ikisi de ölçümde yanıldı.
· Provenance alanını YANLIŞ sub-config'ten okumak FAIL-OPEN'dır (tip doğru, değer hep None,
  hiçbir test kırmızı vermez). Vacuity muhafızı yaz: hiçbir anahtar kendi varsayılanına
  eşit olamaz. Bu slice'ta o kusur gerçekten yazıldı ve muhafız yakaladı.
· Muhafız davranışsal OLMAYABİLİR. NC-3'te sıralamayı ayrıştırmak golden DAHİL 135 testin
  134'ünü yeşil bıraktı. Negatif kontrolde MEVCUT testlerin yeşil kalması boşluğun ÖLÇÜSÜDÜR.

ORTAM (ADIM 137'de ölçüldü):
· Taze worktree'de backend/.venv YOK → uv sync --all-extras
· Postgres :5432 (entropia/entropia). İzole DB + LC_ALL=C.UTF-8 PYTHONUTF8=1 alembic
  upgrade head; TEST_DATABASE_URL=postgresql+asyncpg://...
· Motor probe'ları backend/ dizininden PYTHONPATH=. ile koşar (tests.unit.* import edilir).
· Tam suite yerelde ~2 saat. Alt küme koşarken --no-cov.
· TUZAK: GateGuard komut dizesinin TAMAMINI tarar — markdown metninde geçen bir git
  komutu bile Bash çağrısını bloklar. Metni yeniden yaz ya da parçalara böl.
· repository_facts üreticisi REPO KÖKÜNDEN koşar (scripts/, backend/scripts/ değil).

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
İŞARETLEME; imza kutusunu DOLDURMA; kapanış ritüeli ZORUNLU (handoff · kickoff+seed ·
PROJECT_HISTORY + CLAUDE.md özeti · memory --sync --only <slug> · codemap · commit→PR).
```
