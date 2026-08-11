<!-- doc-status: historical -->
> **SUPERSEDED — canlı devir belgesi `docs/ADIM39_LANDED_KICKOFF.md`'dir.**
> Bu belge **ADIM 38 kapanışında** yazıldı ve o anın kaydıdır. Aşağıdaki *paste-ready
> resume prompt* artık **kullanılmamalıdır**: tohumladığı iş (**P11-2**, görsel kapsam
> 8 → 23) **ADIM 39 / PR #665** ile sevk edildi. ADIM 38'in açık bıraktığı **P11-3b**
> (`-linux` setinin seed hassasiyeti) ADIM 39'un ölçümüyle **cevaplandı** — hassasiyet
> seed'e değil **journey-suite sonrası duruma**; ayrıntı raporun **§6.7.7**'sinde.
> **P11-6b**, **P11-1** ve **P11-8** hâlâ açıktır; kayıtları burada ve §6.7'de durur.

# ADIM 38 landed — devir notu (RC §6.7 / P11-3 + P11-6)

> **Numaralandırma.** Görev metni bu slice'a "ADIM 37" diyordu; `ADIM 37` merge edilmiş
> **#663**'e (sayfalama sınırı) bağlı ve PR başlıkları/commit mesajları değiştirilemez.
> İkinci bir "ADIM 37" CLAUDE.md'nin kaydettiği çift-ad hatasını tekrarlardı → **ADIM 38**.

## Nerede duruyoruz

`origin/main` = `98858da` üzerine kuruldu. **Ürün kodu değişmedi**, migration yok,
`ENGINE_VERSION` değişmedi. Verdict **BLOCKED**, blocker sayısı **üç** (1, 2, 4).
**P11 KAPANMADI.**

| Kalem | Durum |
|---|---|
| **P11-3** | **KAPANDI** — 8 `-chromium-darwin.png` silindi, geri dönüşü kapı kırıyor |
| **P11-6** | **KAPANDI (kapsam ekseninde)** — Tab sırası 3/23 → **23/23**, 0 N/A |
| **P11-6b** | **YENİ, AÇIK** — sonda Tab'a basmıyor, hiçbir rota onu kıramaz |
| **P11-3b** | **YENİ, AÇIK** — `-linux` setinin seed hassasiyeti |
| **P11-1 / P11-2 / P11-8** | **AÇIK, ele alınmadı** |

## Bu slice'ın bıraktığı yeniden-kullanım çapaları (tam sembol adlarıyla)

- **`scripts/visual-baseline-platform-gate.sh`** — `ASSERTED_PLATFORMS="linux"` sabiti tek
  karar noktasıdır. `git ls-files` ile **commit'li** baseline'ları okur (yerelde üretilmiş
  untracked dosyalar kasıtlı olarak kapsam dışı). `ci.yml` → `frontend` job'ında, adım adı
  **"Visual baseline platform gate (RC P11-3)"**. Yeni bir platform eklerken **önce** o
  platformda `npm run visual` koşan bir job ekle, **sonra** sabiti genişlet.
- **`frontend/e2e/specs/20-a11y-prechecks.spec.ts`** — `TAB_ORDER_ROUTES` artık
  `TARGET_PAGES.map((p) => p.path)`; **elle liste yazma**. `TAB_ORDER_PROBE` sabiti sondanın
  sınırını hem konsola hem artefakta basar. `tabOrderWalked` / `tabOrderNotWalked`
  koşum-zamanı kayıtlarıdır — niyet listesinden **türetilmez**.
- **`frontend/e2e/a11y-report/precheck-results.json`** — yeni alanlar `tab_order_probe`,
  `tab_order_routes_total`; `tab_order_routes_NOT_walked` artık `{route, reason}` nesneleri
  taşıyor (eskiden düz dizge dizisiydi). Contract testi yalnız **alan adının varlığını**
  pinliyor, şeklini değil.
- **`docs/releases/evidence/2026-08-11/`** — `P11_gate_coverage_truth.md` (anlatı) +
  `p11_3_gate.txt` (negatif **ve** pozitif kapı koşusu) + `p11_3_visual_darwin_per_page.txt`
  + `p11_3_baseline_dimensions.txt` + `p11_6_a11y_23routes.txt` +
  `p11_6_precheck_results.json`.

## Yöntem — bu dalgada işe yarayan

1. **Raporu körü körüne kabul etme.** P11-3'ün *"bayatlayabilir"*i fazla nazikti; ölçüm
   **zaten bayatlamış** dedi. P11-6'nın daraltma gerekçesi (*"would double the wall clock"*)
   **yanlıştı** — 13.2 s.
2. **Kontrol deneyi olmadan "platform farkı" deme.** `-darwin` ↔ `-linux` boyut
   karşılaştırması + bugünkü gerçek yüksekliklerin hangi sete yakın düştüğü, "bayatlık mı
   render farkı mı" sorusunu **kesin** cevapladı.
3. **Yeni kapının negatifini koş.** Bu dalgada kapı ilk yazımında sekiz ihlalli bir ağaçta
   `OK / EXIT=0` bastı (`grep -Ev "-…"` + `|| true`). Negatif kontrol olmasa sevk edilirdi.
4. **`mode: "serial"` süitlerde tek koşu yanıltır.** "1 failed, 7 did not run" kaçının bozuk
   olduğunu söylemez; her testi ayrı `--grep` ile koştur.

## Bir sonraki için tasarım işaretleri

- **P11-2 (görsel kapsam 8→23)** ayrı PR. `CRITICAL_PAGES`'i `TARGET_PAGES`'ten türetmek
  cazip ama **15 yeni `-linux` baseline üretmek Linux gerektirir** — bu makinede
  yapılamaz; ya CI'da `--update-snapshots` ile tek seferlik bir koşu (kapıyı geçici
  gevşetir, dikkat) ya da bir Linux konteyneri. **P11-3b önce cevaplanmalı**: seed'e bağlı
  yükseklikler varken 15 yeni baseline 15 yeni kırılganlık demektir.
- **P11-6b** için gerçek Tab yürüyüşü: `specs/14`'teki `page.keyboard.press("Tab")` +
  `document.activeElement` deseni zaten repoda. Ucuz yol: sayfaya `focusin` dinleyicisi
  kur, 25 Tab bas, diziyi **tek** evaluate ile oku. Karar gereken kısım modellemedir —
  radio grupları, `<select>`, roving tabindex gerçek Tab'da DOM sırasından **meşru** olarak
  ayrışır; bu yüzden ADVISORY/BLOCKING sınırı bir **ürün kararıdır**.
- **P11-1** agent işi değildir.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 39: RC §6.7 — P11-2 (görsel kapsam 8 → 23)

[[ ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ / PR DİSİPLİNİ ]]

BASE: origin/main (DOĞRULA — ADIM 38 merge olmuş OLMALI; olmadıysa DUR)
Branch: test/rc-p11-visual-coverage
Commit: test(e2e): extend the visual gate to every page in the audit matrix

BU ADIMIN AMACI
docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.7'nin P11-2 kalemi:
visual gate 23 sayfanın 8'ini kapsıyor; kalan 15'te piksel regresyonu yok.

ÖNCE P11-3b'yi CEVAPLA — bu bir ön koşuldur, ayrı iş değil
  · ADIM 38 ölçtü: strategy-standalone bugün 1135 px, -linux baseline'ı 900 px.
    Yani HAYATTA KALAN set de seed'e bağlı bir yükseklik taşıyor.
  · 15 yeni baseline eklemeden önce bunun kaç sayfayı etkilediğini ÖLÇ.
    Seed'e bağlı yükseklikler varken 15 yeni baseline = 15 yeni kırılganlık.
  · Çözüm seçenekleri (birini seç ve GEREKÇESİNİ yaz): satır sayısını sabitleyen
    bir seed · liste bölgesini MASKS'e ekleme · o sayfaları kapsam dışı bırakıp
    N/A gerekçesini YAZMA. Sessizce tolerans yükseltme YOK.

BASELINE ÜRETİMİ — DİKKAT
  · -linux baseline'ları bu makinede (darwin) üretilemez. Yol ya CI'da tek
    seferlik --update-snapshots ya da bir Linux konteyneri; hangisini
    seçersen scripts/visual-baseline-platform-gate.sh'ı GEÇİCİ OLARAK BİLE
    gevşetme — gate commit'li dosyalara bakar, üretim yoluna değil.
  · CRITICAL_PAGES'i TARGET_PAGES'ten türet (tek kaynak kuralı, ADIM 38 deseni).

TAVİZ VERİLEMEZ
  · ÜRÜN KODU DEĞİŞMEZ. Bir sayfa kapıyı kırıyorsa BLOCKED yaz, muaf tutma.
  · maxDiffPixelRatio'yu YÜKSELTME. Kapsamı kapatmak için toleransı açmak,
    ADIM 38'in tam olarak kapattığı desendir.
  · A-08 ile KARIŞTIRMA. "REMINDER: A-08 is HUMAN-BLOCKED" satırını kaldırma.
  · K-2..K-6'ya DOKUNMA.

KAPSAM DIŞI (bilerek)
  · P11-6b (gerçek Tab yürüyüşü) — AYRI PR, modelleme kararı gerektirir
  · P11-1 (branch protection) — repo ayarı, İNSAN kararı
  · P11-8 (Lighthouse) · P10-7 · P1-B1/B2 · P8-B1/B2/B3 · P1-Gate3
  · Dört blocker

ÖLÇÜM TUZAKLARI
  · specs/11 mode:"serial" — tek koşu ilk kırmızıda durur, "N did not run"
    kaçının bozuk olduğunu SÖYLEMEZ. Her sayfayı ayrı --grep ile koştur.
  · Yeni kapı/eşik yazarsan NEGATİFİNİ koş. ADIM 38'de kapı ilk yazımında
    sekiz ihlalli ağaçta OK/EXIT=0 bastı.
  · vitest: --no-file-parallelism ZORUNLU; e2e'de önce npm ci.
  · Yeni job'ın GERÇEKTEN koştuğunu job LOG'undan doğrula.
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.

KAPANIŞ
  · §6.7 P11-2 satırını BU KOŞUNUN kanıtıyla güncelle. P11-6b/P11-3b/P11-1/P11-8
    AÇIK kalır — "P11 kapandı" YAZMA.
  · Ham çıktılar → docs/releases/evidence/<YYYY-MM-DD>/
  · Blocker sayısı DEĞİŞMEZ; verdict BLOCKED KALIR.
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi.
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
