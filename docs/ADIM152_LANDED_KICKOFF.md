<!-- doc-status: current -->
# ADIM 152 landed — RD-09.c4'ün kanıtı üretimin yazdığı ref'e taşındı; "tavan oynatır" öncülü defterin kendisinde çürüdü

## Nerede duruyoruz

Taban `origin/main` @ `4581c281` (ADIM 151). **MIGRATION YOK** · `ENGINE_VERSION` değişmedi ·
OpenAPI değişmedi · golden el değmedi · **ÜRÜN KODUNDA SIFIR SATIR** (NC yamaları sha256-doğrulamalı
geri alındı) · frontend sıfır satır. Diff **iki dosya**: successor-manifest harness'ı + harita notu.
**A-08 (#514) AÇIK, blocker DEĞİŞMEDİ (1) → BLOCKED.**

Ayrıca devir prompt'unun (a) kalemi koşuldu: **post-merge Lighthouse 23/23 rota × 3 kategori hepsi
100** (run `33469911470`); `tightened` önerisi üç çiftte çıktı ve **REDDEDİLDİ**. #677'nin ölçüm
tarafı eksiksiz — kapatmak insan kararı.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `test_research_successor_manifest_immutability.py::_approved_funding_revision` | Funding-enabled run harness'ı artık ÜRETİM ŞEKLİNDE: `instrument_mapping_ref` elle SET EDİLMEZ, iki eksende ASSERT edilir (varlık + market satırının kendi `instrument_id`'siyle kimlik). Yeni funding fixture'ı yazarken buradan türet. |
| Aynı dosyada manifest-feed ref pinleri | `feed["revision"]["instrument_mapping_ref"]`'i üretimin yazdığı değere pinler (finished + QUEUED). |
| `scratchpad nc_runner` deseni (commit edilmedi, kayıtta) | Yamalayan NC harness'ı: patch → koş → `finally` restore → **sha256 doğrula**. ADIM 149'un kuralı ilk gerçek sınavını geçti (PATH tuzağında düşen koşu bile temiz restore verdi). |

## ASIL BULGULAR

1. **Bir devir öncülü ancak defterde ölçülerek doğrulanır.** Dört slice'ın kaydı (138/140/149/151)
   ve i703 §Karar 3'ün kendi metni `RD-09.c4`'ü "partial" sanıyordu; harita onu **ADIM 68'den beri
   `covered`** tutuyor. Hiçbir tavan oynamadı ve oynayamazdı — ratchet 54/6 · A1 B21 C6 D32 aynı.
2. **Statüsü doğru olan bir satırın DÜNYASI yanlış olabilir.** Covered atıfı, ADIM 149'dan beri
   üretimin yazdığının üzerine yazan bir hand-set'in dünyasındaydı; kapanışın işi statüyü değil
   kanıtın dünyasını taşımaktı.
3. **NC-4 yan bulgusu:** worker, manifest bloğundaki `instrument_mapping_ref` DEĞERİNİ yeniden
   doğrulamıyor (blanked ref ile koşu tamamlandı) — kaydedildi, üzerine gidilmedi.

## Sıradaki adaylar

1. **#677 kapanış kararı — İNSAN.** Ölçüm tamam (23/23 hepsi 100). `tightened` çıkarsa REDDET.
2. **İmza kalemleri:** #854 (9 kutu) · #534 (4 kutu) · #547 (0 yorum) · #582 (öncülü bayat) ·
   **#514 A-08 — tek blocker, `human-only`**.
3. **Testle kapanabilir sınıf-B satır KALMADI** — 21 satırın hepsi kayıtlı bulgu taşıyor; sıradaki
   kod işi bir imzanın arkasından çıkar.

---

## Paste-ready resume prompt

```
Entropia — ADIM 153. Session START protokolünü uygula: önce `git fetch`,
`git log --oneline origin/main -6`, `gh pr list --state all` ile NE İNDİĞİNİ doğrula
(handoff STALE-BY-DEFAULT). Sonra oku: docs/ADIM152_LANDED_KICKOFF.md →
docs/STAGE2_HANDOFF.md ("landed" + son "## Next") → docs/PROJECT_HISTORY.md §ADIM 152 (hedefli).

DURUM: ADIM 152 RD-09.c4'ün kanıtını üretimin yazdığı ref'e taşıdı (hand-set kaldırıldı, iki
eksenli dürüst-harness assertion'ı + manifest-feed pinleri; 4 NC, restore'lar sha256). Statü
covered→covered, HİÇBİR TAVAN OYNAMADI (kickoff öncülü defterde çürüdü). Post-merge Lighthouse
okundu: 23/23 rota × 3 kategori 100 — #677'nin ölçüm tarafı tamam.

SIRADAKİ İŞ (öncelik sırasıyla):
  (a) #677 kapanış kararı — İNSAN. Yeni bir `tightened` önerisi çıkarsa REDDET.
  (b) İmza kalemleri (ölçmeden girme): #854 (9 kutu) · #534 (4 kutu) · #547 (0 yorum) ·
      #582 (öncülü bayat) · #514 A-08 (TEK BLOCKER, human-only).
  (c) Testle kapanabilir sınıf-B satır KALMADI — kod işi bir imzanın arkasından çıkar; imzasız
      ilerlenebilir bir kalem ararken önce açık issue'ları VE defter bulgularını YENİDEN ölç.

KURALLAR: ölçmediğini iddia etme; bir öncülü defterin/haritanın KENDİSİNDE doğrula (dört slice'lık
"partial" inancı yanlış çıktı); yamalayan her NC harness'ı restore'u sha256 ile doğrular; yeşil
exit code kanıt değildir (exit code'u AYRI oku — `| tail` tuzağı); tavanı ASLA yerel koşudan alma;
vitest'i --no-file-parallelism ile koş; kapanış ritüeli ZORUNLU; kickoff'lardan yalnız EN YÜKSEK
numaralı olan `current` olabilir.
```
