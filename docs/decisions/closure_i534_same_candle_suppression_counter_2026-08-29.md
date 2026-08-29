<!-- doc-status: current -->

# Kapanış kararı — GH #534 md. 3: same-candle bastırmaları kendi sayacını hak ediyor mu?

**Açan slice:** ADIM 137 (GH #534, provenance yarısı sevk edildi)
**Durum:** **İMZASIZ — kutular BOŞ.** Bu belge bir karar değil, kararın **sorulduğu** yerdir.
**Kapsam:** yalnız md. 3. #534'ün md. 1/2/4'ü ADIM 137'de sevk edildi ve **bu karara bağlı
değildir** — ikisi ayrı eksendir.

---

## Neden ajan karar vermedi

#534 md. 3 kelimesi kelimesine *"decide explicitly and state the decision"* diyor. Seçeneklerden
ikisi **sevk edilmiş bir sayacın anlamını değiştirir** (`suppressed_entries` bugün üç yola
toplanıyor ve yayımlanmış bir Result alanı). Deponun kuralı: sevk edilmiş bir sayının
semantiğini yeniden yazmak **adjudication**'dır (ADIM 42 emsali; sınıf taşımanın tavanı
yükseltmesiyle aynı şekil). O yüzden ölçüm yapıldı, karar **açıldı**.

---

## §Ölçüm 1 — sayaca kaç yol yazıyor, ve hangileri

`grep -rn 'suppressed_entries' backend/src/entropia/domain/backtest/` ile **üç** yazma yolu:

| # | Yer | Sebep | Yaydığı olay |
|---|---|---|---|
| 1 | `engine.py:2065` (doğrudan `+= 1`) | **flat-position same-candle entry+exit çakışması** (§5.9) | `entry_exit_collision`, `detail.resolution = "ambiguous_entry_suppressed"` |
| 2 | `engine.py:2730` (`_LedgerEffect`) | `direction_restriction` — **plan modu** (6a) | `filtered_no_entry`, `detail.reason = "direction_restriction"` |
| 3 | `engine.py:2750` (`_LedgerEffect`) | `direction_restriction` — **breakout-proxy modu** (6b) | `filtered_no_entry`, aynı `reason` |

**#534'ün gövdesindeki satır numaraları (`engine.py:2427`, `:2447`) BAYAT** — mekanizma
ADIM 71'in (`C1`) describe/book ayrımına taşındı, sayaç artık `_LedgerEffect.counter`
üzerinden basılıyor. **İddia bayatlamadı:** üç yol, tek sayaç.

**Ayrım, sayılırken kaybolan şey:** 2 ve 3 *aynı sebeptir, iki moddur*; 1 **başka bir
kuraldır**. Yani `suppressed_entries = 7` cümlesi bugün "yediye kadar herhangi bir karışım"
demektir ve hiçbir yüzey bunu ayrıştırmaz.

## §Ölçüm 2 — bu bilgi bugün BAŞKA bir yerden kurtarılabiliyor mu? **EVET**

Ölçüldü: karar izinde **kesme/tavan yok** (`output.py`/`state.py`'de cap arandı, bulunmadı),
ve `entry_exit_collision` ADIM 136'da **yayımlanan taksonomiye kaydedildi**. Yani okuyucu
bugün ikisini de sayabilir:

- same-candle bastırması = `resolution == "ambiguous_entry_suppressed"` taşıyan
  `entry_exit_collision` olayları
- direction restriction = `detail.reason == "direction_restriction"` taşıyan
  `filtered_no_entry` olayları

**Bu, md. 3'ü bir DOĞRULUK boşluğu olmaktan çıkarır.** Kayıp toplamdır, bilgi değil — ve
kararın gerçek ekseni budur: *"bir toplam, türetilebilir olduğu hâlde yayımlanmayı hak eder mi"*.

## §Ölçüm 3 — her şıkkın ölçülmüş bedeli

`suppressed_entries` `output.py:539`'da yayımlanır; `diagnostics` **golden digest'e girer**
(ADIM 137'de ölçüldü: bir üye eklemek 45 payload'ı oynatır). Yani:

| Şık | Golden etkisi | `ENGINE_VERSION` | Sevk edilmiş sayı oynar mı |
|---|---|---|---|
| (a) statüko | **0 digest** | bump yok | hayır |
| (b) YENİ sayaç ekle, `suppressed_entries` **el değmez** | 45 payload (yalnız eklenen üye) | **bump** (ADIM 136/137 kuralı: bayt oynuyor) | **hayır** — toplam aynı kalır |
| (c) YENİ sayaç ekle **ve** same-candle'ı `suppressed_entries`'ten **düş** | 45 payload + **değer** oynar | **bump** | **EVET** — sevk edilmiş bir sayının anlamı değişir |

**(c)'nin bedeli ayrıca geriye dönüktür:** saklanmış eski Result'ların
`suppressed_entries`'i yeni tanıma göre okunamaz ve hiçbir alan hangi tanımda yazıldığını
söylemez. (b) bu sorunu doğurmaz çünkü eski toplam olduğu gibi kalır.

---

## §Karar — same-candle bastırmaları için ayrı bir sayaç

☐ **(a) STATÜKO.** Sayaç paylaşılmaya devam eder. Ayrım karar izinden türetilir (§Ölçüm 2).
   Bedeli: bir okuyucu toplamı yanlış atfetmeye devam edebilir.

☐ **(b) EKLE, TOPLAMI BOZMA.** Yeni `same_candle_suppressed_entries` yayımlanır;
   `suppressed_entries` **bugünkü anlamını korur** (üçünün toplamı). İki sayı birlikte
   direction-restriction payını da çıkarılabilir kılar.

☐ **(c) EKLE VE DÜŞÜR.** Yeni sayaç eklenir, `suppressed_entries` yalnız
   direction-restriction sayar. **Sevk edilmiş bir sayının anlamı değişir** (§Ölçüm 3).

☐ **Başka:** ______________________________________________

**İmza:** ____________________  **Tarih:** ____________

> Şıklardan biri işaretlenirse: `execution/state.py::_Ledger` + `execution/output.py`
> değişir, golden **yeniden üretilir** ve `ENGINE_VERSION` (b)/(c)'de **bump edilir**
> (bayt oynuyor → ADIM 136'nın imzalı kuralı). `docs/generated/repository_facts.md`
> tazelenir. (c) seçilirse ayrıca **eski Result'ların okunabilirliği** ayrı bir kalem olarak
> açılmalıdır — bu belge onu çözmez.

---

## Dürüst sınır

- **#534 KAPATILMADI.** md. 1/2/4 indi, md. 3 bu belgede **açık**.
- Bu belge **hiçbir kutuyu doldurmaz** ve varsayılan seçmez.
- §Ölçüm 2'nin *"kesme yok"* bulgusu `output.py`/`state.py` üzerinde arandı; **persist
  katmanında** bir sayfalama/limit olup olmadığı bu slice'ta ölçülmedi.
