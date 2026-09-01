<!-- doc-status: historical -->
# ADIM 151 landed — oturum açık CLS dört rotada kaynağında düzeltildi; ADIM 148'in rezervi yeni dünyada kusurun kendisiydi

## Nerede duruyoruz

Taban `origin/main` @ `ac749c2a` (ADIM 150). **MIGRATION YOK** · `ENGINE_VERSION` değişmedi ·
OpenAPI değişmedi · golden el değmedi · **backend'de SIFIR SATIR** · Lighthouse
`floors`/`armed`/`policy` **el değmedi** (yalnız `provenance.cls_reserves_2026_09_01`).
Ürün: beş frontend dosyası, hepsi **yalnız loading dalları** (presentation-only).
**A-08 (#514) AÇIK, blocker DEĞİŞMEDİ (1) → BLOCKED.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `global.css` → `.panel-card-async` + beş modifier (`--users 112 · --actors 56 · --matrix 175 · --capabilities 322 · --library-pool 610`) | Kart başına **ölçülmüş** oturum açık settled rezervi; taban artık flex-ortalar ve `.state`'i kompaktlar. Yeni bir async yüzey eklerken kendi modifier'ınla buraya bağlan. |
| `CreatePackage.tsx` switcher loading → `p.cp-note[role=status]` | Loading settled'dan BÜYÜKSE min-height çare olamaz — kompakt markup deseni. |
| `src/test/clsReserves.test.tsx` | Üç DOM muhafızı + **kaynak-düzeyi değer pini** (jsdom stylesheet uygulamaz → sınıf-varlığı muhafızları min-height değerine kördür; pin global.css metnini okur). |
| `panelManagement.test.tsx` | Muhafız artık üç modifier'ı da pinler (eski sayaç modifier kaybına kördü — NC-4'te ölçüldü). |

## ASIL BULGU

Dört rota **tek kusur sınıfı, iki yön**: panel-management'te ADIM 148'in 244px rezervi
**oturumsuz settled** değeriydi ve oturum açık dünyada **rezervin kendisi shift kaynağı oldu**
(kartlar 306→174/118/237 küçülüyordu); library/future-dev'de kartlar otururken **büyüyor**
(910px liste Import kartını fold altına itiyordu); create-package'ta **loading settled'dan
büyük** → yön ters, min-height yapısal olarak çare olamaz. **Bir düzeltmenin DEĞERİ ölçüldüğü
dünyaya aittir; dünya değişince mekanizma değil değer eskir.**

Sonuç, doğrulanmış yerel harness'ta (yerel↔CI: 0.0949↔0.096 · 0.0680↔0.068 · 0.0581↔0.059 ·
maks 0.1475↔0.165): düzeltme sonrası **dört rota ≤ 0.0021**, kontrol rotası mainboard
**bayt bayt aynı**.

## Yöntem — bu slice'ın öğrettikleri

* **İki dünyada da kırmızı olan bir kontrol, kontrol değildir.** Değer pininin ilk yazımı
  `global.css?raw` ile kuruldu; vitest css boru hattı onu **boş dizeye** çevirdi → pin temiz
  ağaçta da kırmızıydı. Reddedildi, fs-okumasına çevrildi (ikinci tuzak: jsdom'da
  `import.meta.url` **http** şemasıdır).
* **CI'ın dünyası yerelde kurulabilir ve kullanılmadan önce DOĞRULANMALIDIR** — sayılar CI'a denk
  gelene kadar harness'a güvenilmedi (ADIM 148 emsalinin oturum açık hâli).
* **Docker VM CPU açlığı ölçümü zehirler:** 12 container'la login 60s'te dönmüyordu;
  worker/scheduler durdurularak teşhis dünyası bilinçli inceltildi (salt-okuma rotaları
  worker istemez; yerel sayılar zaten tavan değil).
* `| tail` exit-code tuzağı bu oturumda da bir kez ısırdı — exit code'u AYRI oku.

## Sıradaki adaylar

1. **#677 kapanış kararı — İNSAN.** Dört kesintinin dördü ele alındı (ADIM 145 iki ·
   ADIM 150 harness artefaktı · ADIM 151 oturum açık CLS). Post-merge CI Lighthouse koşusu
   dört rotada iyileşme raporlayacak; `tightened` önerisi çıkarsa **REDDET** (tek koşuyla
   sıkıştırma yok — `stability`).
2. **`RD-09.c4`** kabul borcu slice'ı (tavan oynatır).
3. **İmza kalemleri:** #854 (9 kutu) · #534 (4 kutu) · #547 (0 yorum) · #582 (öncülü bayat) ·
   **#514 A-08 — tek blocker, `human-only`**.

---

## Paste-ready resume prompt

```
Entropia — ADIM 152. Session START protokolünü uygula: önce `git fetch`,
`git log --oneline origin/main -6`, `gh pr list --state all` ile NE İNDİĞİNİ doğrula
(handoff STALE-BY-DEFAULT). Sonra oku: docs/ADIM151_LANDED_KICKOFF.md →
docs/STAGE2_HANDOFF.md ("landed" + "Next") → docs/PROJECT_HISTORY.md §ADIM 151 (hedefli).

DURUM: ADIM 151 oturum açık CLS'i dört rotada kaynağında düzeltti (panel-management
0.165→~0.002 · package-library 0.096→~0.0001 · create-package 0.068→~0.0001 ·
future-dev 0.059→~0.0002, yerel doğrulanmış harness; otorite CI). Tavanlar EL DEĞMEDİ;
muhafızlar clsReserves.test.tsx + panelManagement.test.tsx.

SIRADAKİ İŞ (öncelik sırasıyla):
  (a) #677 kapanış kararı — İNSAN. Post-merge CI Lighthouse koşusunu OKU: dört rotada
      iyileşme bekleniyor; `tightened` önerisi çıkarsa REDDET (tek koşuyla sıkıştırma yok).
  (b) RD-09.c4 — kabul borcu slice'ı (partial/debt_class.B tavanlarını oynatır, ratchet
      merged ağaçta YENİDEN ölçülerek dondurulur).
  (c) İmza kalemleri: #854 (9 kutu) · #534 (4 kutu) · #547 (0 yorum) · #582 (öncülü bayat) ·
      #514 A-08 (TEK BLOCKER, human-only).

KURALLAR: ölçmediğini iddia etme; bir kapı yanlış dünyayı ölçüyorsa bulduğu her kusur
şüphelidir; İKİ DÜNYADA DA KIRMIZI OLAN KONTROL KONTROL DEĞİLDİR; metin içeren heredoc
TIRNAKLI olmalı (<<'PY'); yeşil exit code kanıt değildir (exit code'u AYRI oku — `| tail`
tuzağı); tavanı ASLA yerel koşudan alma; vitest'i --no-file-parallelism ile koş; kapanış
ritüeli ZORUNLU; kickoff'lardan yalnız EN YÜKSEK numaralı olan `current` olabilir.
```
