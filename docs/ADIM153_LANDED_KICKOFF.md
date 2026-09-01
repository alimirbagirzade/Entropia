<!-- doc-status: historical -->
# ADIM 153 landed — GH #677 insan eliyle kapandı; kayıt düşüldü, tavan takibi koşula bağlı kaldı

## Nerede duruyoruz

Taban `origin/main` @ `c30a390d` (ADIM 152). **DOCS-ONLY** — ürün kodunda, testte, migration'da
sıfır satır · ratchet el değmedi (54/6 · A1 B21 C6 D32) · **A-08 (#514) AÇIK, blocker
DEĞİŞMEDİ (1) → BLOCKED.**

#677 `2026-09-01T05:56:44Z`'de ürün sahibi tarafından **CLOSED/COMPLETED + yazılı dispozisyonla**
kapatıldı; ADIM 90'ın üç ölçümü (issue durumu · yazılı karar · imza düzlemi) ayrışmıyor →
kapanış geçerli. Devir prompt'unun (a) kalemi böylece İNSAN tarafından çözüldü.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `PROJECT_HISTORY.md` §ADIM 153 | #677 kapanış dispozisyonunun ve tavan-takip koşulunun tek kayıtlı özeti; #534 karşıt emsali yan yana. |
| Kapanış yorumundaki koşul metni | *"repeat runs show a stable 100 median"* — tavan sıkıştırmanın ön koşulu; ölçümü `gh run list --branch main --workflow e2e.yml` + Lighthouse artefaktı. |
| NC-4 sınıflaması | Worker ref-yeniden-doğrulaması = imza-kapılı (i703 imzası o kuralı taşımıyor; ADIM 149 emsali). Kod yazmadan önce imza iste. |

## ASIL BULGULAR

1. **Bir issue kapanışı ancak üç düzlem birden ölçülünce kayda geçer** (ADIM 90): #677 üçünde de
   tutarlı → kapandı; #534 aynı kuralla **açık kalır**. İki zıt sonuç aynı kuralın kanıtıdır.
2. **Kapanış yorumu bir iş TANIMLAYABİLİR:** tavan takibi artık issue'da değil, koşulda yaşıyor —
   koşul ölçüldü (post-fix koşu = 1), sağlanmadı, tavanlara dokunulmadı.
3. **İmzasız ilerlenebilir kod işi YOK** — açık issue'lar + defter bulguları yeniden ölçüldü;
   hepsi imza/insan bekliyor.

## Sıradaki adaylar

1. **İmza kalemleri:** #854 (9 kutu) · #534 (4 kutu) · #547 (0 yorum) · #582 (öncülü bayat) ·
   #535/#542/#543/#545/#546 (`product-decision`) · **#514 A-08 — tek blocker, `human-only`**.
2. **Tavan takibi:** koşu korpusu biriktikçe *"stable 100 median"* yeniden ölçülür.
3. **NC-4 (worker ref doğrulaması):** imza gelirse kod işi; gelmeden GİRME.

---

## Paste-ready resume prompt

```
Entropia — ADIM 154. Session START protokolünü uygula: önce `git fetch`,
`git log --oneline origin/main -6`, `gh pr list --state all` ile NE İNDİĞİNİ doğrula
(handoff STALE-BY-DEFAULT). Sonra oku: docs/ADIM153_LANDED_KICKOFF.md →
docs/STAGE2_HANDOFF.md (son "## Next") → docs/PROJECT_HISTORY.md §ADIM 153 (hedefli).

DURUM: #677 ürün sahibi tarafından yazılı dispozisyonla KAPANDI (ADIM 153 kaydetti).
Tavan takibi koşula bağlı: "repeat runs show a stable 100 median" — post-fix koşu sayısını
`gh run list --branch main --workflow e2e.yml` ile ölç; sağlanmadıysa tavanlara DOKUNMA.
İmzasız ilerlenebilir kod işi YOK; testle kapanabilir sınıf-B satır KALMADI.

SIRADAKİ İŞ (öncelik sırasıyla):
  (a) İmza kalemleri (ölçmeden girme): #854 · #534 · #547 · #582 · product-decision beşlisi ·
      #514 A-08 (TEK BLOCKER, human-only). Taze imza var mı: karar belgelerinde işaretli kutu
      grep'i + issue yorumları.
  (b) Tavan takibi koşulu: koşu korpusu yeterliyse (kararlı 100 medyanı) tavanları o PR'ın
      KENDİ CI artefaktından sıkıştır; tek koşuyla ASLA.
  (c) İmzasız kalem ararken açık issue'ları VE defter bulgularını YENİDEN ölç (ADIM 152/153
      dersi: öncüller defterin kendisinde doğrulanır).

KURALLAR: ölçmediğini iddia etme; bir öncülü defterin/haritanın KENDİSİNDE doğrula; yeşil exit
code kanıt değildir (exit code'u AYRI oku — `| tail` tuzağı); tavanı ASLA yerel koşudan alma;
vitest'i --no-file-parallelism ile koş; kapanış ritüeli ZORUNLU; kickoff'lardan yalnız EN YÜKSEK
numaralı olan `current` olabilir.
```
