<!-- doc-status: current -->
# ADIM 149 landed — GH #703'ün yazıcısı sevk edildi ve ölçüm imzanın öngördüğünden geniş çıktı

## Nerede duruyoruz

`instrument_mapping_ref` artık **üretim tarafından yazılıyor**. #703'ün dört imzalı kararının
uygulaması indi: **§Karar 1 = `(b)` LİNK'TEN TÜRET**, **§Karar 1a = `(b2)` FAIL-CLOSED DÜZ**,
**§Karar 2 = `A` HARNESS ÜRETİM ŞEKLİNE ÇEKİLSİN**, **§Karar 3 = `A`** (`RD-09.c4` `partial`
kalır). Karar belgesi: `docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md`.

**Taban** `origin/main` @ `5e271b45` (ADIM 148). Yazıldığı taban `6d50b6be` (#886) idi;
ADIM 147 (#887) ve ADIM 148 (#888) bu PR yazılırken indi ve dal ikisinin üzerine
**REBASE edildi** — *"Update branch"* düğmesi KULLANILMADI (ADIM 61). İki belge
çakışması **iki taraf da korunarak** çözüldü ve bir **başlık-kaybı muhafızı** ile
doğrulandı (`PROJECT_HISTORY` 163 başlık = 162 + ADIM 149); üretilmiş olgular doğru
birleşti (backend **3909**, frontend **733**, E2E **84**).

**MIGRATION YOK** (kolon zaten vardı) · `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** ·
golden **el değmedi** · **`frontend/` içinde sıfır satır**.

**Ölçülen sonuç imzanın hedeflediğinden geniş:** #703'ün **İKİNCİ** kapısı da kapandı.
ADIM 138 *"başlıktaki iddia ikinci kapı yüzünden ayakta"* diye bir dürüst sınır bırakmıştı;
`resolve_funding_schedule` app-created bir funding revizyonunu artık **hiç reddetmiyor**
(ADIM 138'in kendi testi `DID NOT RAISE` verdi ve **kasıtlı** tersine çevrildi).

## Bu slice'ın bıraktığı yeniden kullanım çapaları (birebir sembol adlarıyla)

| Çapa | Ne yapar |
|---|---|
| `application/commands/research_data.py::_instrument_mapping_ref_for` | Tek türetim noktası. Linkli market revizyonunun `instrument_id`'sini **kopyalar**; boşsa `DependencyBlocked`. **Yeni bir link-pinleyen yüzey eklersen kendi kodunu yazma, buradan geçir.** |
| `infrastructure/postgres/repositories/research_data.py` | İki yazıcı da opsiyonel `instrument_mapping_ref` alır (varsayılan `None` → pin yoksa tutarlı çift). |
| `tests/integration/test_instrument_mapping_ref_writer.py` | `(b2)`'nin dört case'i: refüz + zarf · **anahtar yakılmıyor** · **ikinci yüzey (revise)** · **link yok → null ref** (kuralın genişlemediğinin ölçüsü). |
| `tests/integration/test_readiness_research_production_shape.py` | ADIM 140'ın ayrışma dosyası, **eksenleri korunup tersine çevrildi**: üretim şekli admit edilir ve run yazar; elle tohumlanan şekil artık ayrışmıyor. |
| `tests/integration/test_readiness_research_data.py::_seed_research_revision` | §Karar 2 = `A`: seeder artık **iki yarıyı da** yazar (`md_rev_1` + `BTCUSDT`). |
| `tests/integration/test_research_data_persistence.py::_approved_market` | `instrument_id="instr_seed_btcusdt"` — on test dosyasının ortak market kaynağı. |

## Sıradaki adayları seçerken ÖNCE ÖLÇ (bu slice'ın öncülleri iki kez çürüdü)

1. **`RD-09.c4` artık kapatılabilir** — üretimin ürettiği bir ref var. Ama kapatmak bir **kabul
   borcu slice'ıdır**: `partial` sayısını ve `debt_class.B` tavanını oynatır, ratchet yeniden
   dondurulur. Bu slice **kabul defterine dokunmadı** (§Karar 3 = `A`).
2. **§Ön koşul PRE-1 KOŞULMADI ve koşulamaz** — karar belgesi sorguyu **ilk gerçek deploy'a**
   bağlar; bu depoda hâlâ **0 tag / 0 release / 0 deploy eden workflow**. `(b2)` bu yüzden
   *"doğrulanmış"* SAYILAMAZ. **Sayıyı İKAME ETME** (ADIM 109).
3. **#703'ü kapatmak insan kararıdır** — kusur düzeldi, issue durumu değişmedi.
4. **İmza kalemleri (ölçülmeden girme):** #854 (9 kutu) · #534 (issue `CLOSED` ama kapanış
   yorumu YOK, 4 kutu) · #547 (0 yorum, gövdesi imza bekliyor) · #582 (öncülü **bayat**) ·
   **#514 A-08 — tek blocker, `human-only`.**
5. **#677 açık kalanları:** `errors-in-console` (23/23) **teşhis edilmedi**; Lighthouse
   **harness düzeltmesi** (ADIM 147 oturumun sekmeye taşınmadığını ölçtü) 23 skoru oynatır ve
   tavanların **CI'dan** yeniden dondurulmasını zorunlu kılar.

## Yöntem — bu slice'ın öğrettiği üç şey

* **`git diff --stat` bir RESTORE KONTROLÜ DEĞİLDİR.** NC koşucusu SIGTERM'de ağacı yamalı
  bıraktı ve diff **temiz göründü**, çünkü eksik satır bu slice'ın *kendi* eklediği satırdı.
  Yamalayan her harness geri yüklemeyi **`sha256` ile** doğrulamalı (+ SIGTERM/`atexit` handler).
  Doğrulanmamış tabana karşı ölçülen NC sayıları **atıldı ve baştan koşuldu**.
* **Bir NC kırmızı verdiği hâlde reddedilebilir.** İlk NC-1 `ref`'i sabit yaptı → **iki ekseni
  birden** kırdı (kimlik + fail-closed). Ayırt edici sürüm fail-closed'ı sağlam bırakır.
* **Bir fixture'ın ELLE YAZDIĞI da bir iddiadır.** ADIM 138 `instrument_mapping_ref`'i elle set
  ediyordu; bugün o satır üretimin yazdığının üzerine yazıyordu → kaldırıldı.

---

## Paste-ready resume prompt

```
Entropia — ADIM 150. Session START protokolünü uygula: önce `git fetch`,
`git log --oneline origin/main -6`, `gh pr list --state all` ile NE İNDİĞİNİ doğrula
(handoff STALE-BY-DEFAULT). Sonra sırasıyla oku: docs/ADIM149_LANDED_KICKOFF.md →
docs/STAGE2_HANDOFF.md ("landed" + "Next") → docs/STAGE_BUILD_PLAN.md →
docs/PROJECT_HISTORY.md §ADIM 149 (hedefli).

Durum: GH #703'ün YAZICISI İNDİ (ADIM 149). `instrument_mapping_ref` artık üretim
tarafından yazılıyor — `commands/research_data.py::_instrument_mapping_ref_for`,
linkli market revizyonunun `instrument_id`'sini KOPYALAR, kaynak boşsa
`DependencyBlocked` (fail-closed, iki yazma yüzeyinde de). #703'ün İKİNCİ kapısı da
kapandı: `resolve_funding_schedule` app-created revizyonu artık hiç reddetmiyor.

AÇIK ve ölçülmüş:
- §Ön koşul PRE-1 KOŞULMADI (0 tag / 0 release / 0 deploy eden workflow → "üretim"
  gözlenebilir bir olay değil). `(b2)` "doğrulanmış" SAYILAMAZ. Sayıyı İKAME ETME.
- `RD-09.c4` `partial` KALDI (§Karar 3 = `A`); kabul defteri ve tavanlar EL DEĞMEDİ.
  Kapatmak artık mümkün ama ayrı bir KABUL BORCU slice'ıdır (ratchet yeniden dondurulur).
- #703 KAPATILMADI — insan kararı.
- A-08 (#514) AÇIK, tek blocker, `human-only` → RC verdict BLOCKED.

Bir aday seçmeden ÖNCE ÖLÇ: bu slice'ın öncülleri iki kez çürüdü. İmza kalemlerine
(#854 · #534 · #547 · #582) kutuları GREP'LEYEREK bak, bölüm bazında — dosya düzeyinde
grep yanıltır (ADIM 119). Kod yazmadan önce dokunacağın alanın docs/CODEMAPS/ haritasını
oku. Kapanışta ritüelin ALTI maddesini de uygula.
```
