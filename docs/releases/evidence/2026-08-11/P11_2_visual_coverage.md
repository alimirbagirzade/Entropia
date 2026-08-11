<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Bir ölçüm koşusunun
> donmuş kaydıdır. Güncel otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md`.

# P11-2 — görsel regresyon kapsamı 8 → 23 (ölçüm: 2026-08-11)

RC §6.7 kalemi: *"Visual gate 23 sayfanın **8'ini** kapsıyor; kalan 15'te piksel
regresyonu koruması **yok**."* Bu belge o kalemin kapatılışının ham kaydıdır.

**Verdict ve blocker sayısı DEĞİŞMEDİ.** P11-2 blocker değildi; §8 hâlâ **BLOCKED**,
açık blocker sayısı hâlâ **üç** (1, 2, 4). **P11 KAPANMADI** — **P11-1** (branch
protection, repo ayarı → **insan kararı**), **P11-6b**, **P11-3b** ve **P11-8**
(Lighthouse) bu dalgada **ele alınmadı**.

---

## 1. Ölçüm ortamı

| | |
|---|---|
| Base | `ed83688` (ADIM 38, #664 merge'li) |
| Stack | `docker compose up -d --build`, `.env` = `.env.example` + CI'ın iki `sed`'i |
| Seed | `SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1` (e2e.yml ile birebir) |
| Tarayıcı | `mcr.microsoft.com/playwright:v1.55.1-noble` (Linux konteyneri) |
| Hedef | `http://localhost:8080` (konteyner içi TCP forwarder → `web:8080` / `api:8000`) |

`-linux` baseline üretmek için Linux gerekiyordu; bu makine darwin. ADIM 38'in kararı
(`ASSERTED_PLATFORMS="linux"`) **izlendi, yeniden açılmadı**.

## 2. Konteyner CI'a karşı KALİBRE EDİLDİ — varsayılmadı

Konteynerin GitHub runner'ıyla aynı pikseli ürettiği **iddia edilmedi, ölçüldü**.
Kalibrasyon numunesi: mevcut sekiz baseline **yeniden adlandırıldı ama byte-identical
bırakıldı**. Geçmeleri gerekiyordu — **8/8 geçtiler**. Onbeşini burada üretme yetkisi
budur.

**Kalibrasyonun SINIRI ölçüldü.** Konteyner 23 sayfanın **22'sini** runner ile birebir
üretti; **`analysis-lab` üretmedi**: konteynerde `1440x1496`, `ubuntu-latest`'te
`1440x1490`. Bu **jitter değil** — runner iki ardışık denemede **byte-identical** çıktı
verdi (`md5 12388809a12a21ac61bcb773a7a12640`); kararlı ~6 px'lik bir reflow, sebebi o
sayfanın boş-durum sembol glifleri (◇, ⧗) iki imajda **farklı fontlara** düşüyor. O
sayfanın baseline'ı bu yüzden **CI artefaktından** alındı (`playwright-report` →
`test-results/**/analysis-lab-actual.png`). Yani: Linux gerekli ama **yeterli değil**;
otorite runner'dır.

Rename saf rename olarak kaydedildi (`git show --stat` → `Bin`, byte farkı yok):

```
strategy-standalone      -> strategy-details
trading-signal-standalone-> trading-signal
trade-log-standalone     -> trade-log
run-result               -> run-results
```

## 3. YAZILI OLMAYAN ÖNKOŞUL — baseline'lar salt-seed stack'i tarif ETMİYOR

İlk kalibrasyon **4/8 düştü**. Sebep repoda hiçbir yerde yazmıyordu:
**`e2e.yml` görsel kapıyı `npm test`'ten SONRA koşuyor**, yani kapının fotoğrafladığı
sayfalar journey suite'inin az önce yarattığı strateji / package request / kullanıcı /
backtest sonuçlarını içeriyor.

Aynı commit, aynı imaj, tek fark DB durumu:

| Sayfa | Baseline | Salt seed | `npm test` sonrası |
|---|---|---|---|
| mainboard | 929 | **900 ✘** | ✓ |
| ready-check | 947 | **900 ✘** | (§6) |
| create-package | 1411 | **1396 ✘** | ✓ |
| strategy-details | 900 | **1135 ✘** | ✓ |
| trading-signal / trade-log / market-data / run-results | — | ✓ | ✓ |

Ham çıktı: `p11_2_seed_only_calibration.txt`.

> **P11-3b'yi netleştirir.** P11-3b `strategy-standalone`'u macOS'ta **1135** ölçmüş ve
> bunun `-linux` (900) ile uyuşmamasını açık soru bırakmıştı. **Linux'ta da 1135.**
> Yani platform artefaktı değil; DB durumu farkı. P11-3b'nin *"`-linux` setinin seed
> hassasiyeti"* sorusu böylece cevaplanıyor: set seed'e değil, **journey suite sonrası
> duruma** duyarlı — ve CI o durumu her koşuda üretiyor.

Yeniden üretim sırası artık `frontend/e2e/README.md`'de yazılı.

## 4. Kararlılık — bir koşu değil, İKİ tam döngü

Her iki döngü de **volume'lar yok edilerek** başladı (`down -v` → `up --build` → seed →
`npm test` → `npm run visual`). Dolayısıyla ikinci döngü **taze ULID'ler, taze
timestamp'ler ve taze rastgele kullanıcı adları** gördü.

| Döngü | Nerede | Journeys | Görsel kapı |
|---|---|---|---|
| 1 | yerel konteyner | 39 passed (3.0 dk) | 7 passed · **15 yazıldı** · 1 failed (5.2 dk) |
| 2 | yerel konteyner | 39 passed (3.5 dk) | **22 passed** · 1 failed — `ready-check`, §6 (4.5 dk) |
| 3 | **GitHub runner** `a75f5e7` | 39 passed | **22 passed** · 1 failed — `analysis-lab`, §2 (4.2 dk) |
| 4 | **GitHub runner** `fa0c6a2` | 39 passed | **23 passed** (4.0 dk) |
| 5 | **GitHub runner** `fa0c6a2` — **rerun, AYNI commit**, taze stack + taze seed | 39 passed | **23 passed** (4.0 dk) |

Prompt'un *"aynı commit'te ikinci kez koştur ve GEÇTİĞİNİ göster"* şartı **runner'da**
karşılandı (döngü 4 ↔ 5): `gh run rerun 31515121099`, aynı `fa0c6a2`, volume'lar yeniden
kuruldu, seed yeniden koştu → **23/23**. Ham çıktı:
`p11_2_ci_visual_run2.txt` ve `p11_2_ci_visual_run3_same_commit.txt`.

**Onbeş yeni baseline'ın onbeşi de ikinci döngüyü geçti.** Ham çıktılar:
`p11_2_visual_cycle1.txt`, `p11_2_visual_cycle2.txt`, `p11_2_journeys_cycle2.txt`.

Döngü 1'in 16 failure'ının **15'i** *"A snapshot doesn't exist … writing actual"*,
**0'ı** piksel diff'iydi (`grep -c` ile sayıldı) — yani sekiz mevcut sözleşmenin hiçbiri
bozulmadı.

## 5. Maskelenmemiş oynak içerik — ÖLÇÜLDÜ, maskelenmedi

Altı yeni baseline oynak kimlik/zaman taşıyor. Bunlar **maskelenmedi**: maske eklemek
yeni bir stabilizasyon deseni icat etmek olurdu ve bu slice bunu bilerek yapmıyor.
Bunun yerine ölçüldü — satır **sırası** ve **sayısı** deterministik olduğu için değişen
yalnız glif'ler ve hepsi %2 toleransının altında kalıyor (döngü 2 kanıtı).

| Sayfa | Oynak içerik |
|---|---|
| `panel-logs` | `btres_…` ULID + `YYYY-MM-DD HH:MM UTC` |
| `results-history` | `btres_…` ULID + tarih |
| `pre-check` | 2 × `pkgreq_…` ULID + timestamp |
| `portfolio` | `mbws_…` (Composition) + `mbi_…` (Add item adayı) |
| `rationale-families` | 6 × `Created (UTC)` |
| `panel-management` | 14 × rastgele kullanıcı adı (sıra prefix'e göre **sabit**) |

`panel-management`'ın sırası prefix'ten geliyor (`auth_…`, `createpkg_…`, `libval_…`),
rastgele kısım sonda — bu yüzden satırlar **yeniden sıralanmıyor**. Sıralansaydı diff
toleransı aşardı.

## 6. `ready-check` — YEREL salınım, CI'da ÜRETİLEMEDİ

Bu bölümün ilk yazımı yanlıştı ve düzeltildi. Ölçüm şuydu: **bu makinede**
`/backtest/ready-check` fullPage yüksekliği **946 / 947 / 950** arasında salınıyor,
üstelik salınım **tek bir test içinde**, Playwright'ın kendi retry'ları arasında:

```
- Expected an image 1440px by 947px, received 1440px by 950px.
- Expected an image 1440px by 950px, received 1440px by 946px.
      Expected an image 1440px by 947px, received 1440px by 946px.
```

Bu iki yerel döngünün ikisinde de tekrarlandı. **Ancak GitHub runner'ında sayfa GEÇTİ**
(`p11_2_ci_visual_run1.txt`, satır `✓ 14 … visual: ready-check (10.9s)`). Dolayısıyla:

- Bu **CI'da bir flake DEĞİL** ve öyle raporlanamaz. İlk taslak öyle diyordu; yanlıştı.
- Gözlem yerel konteyner/OrbStack ortamına özgü. Ürün kusuru olduğu **kanıtlanmadı**.
- Baseline **değiştirilmedi**, tolerans **genişletilmedi**, rota **atlanmadı**.

Kayda geçirilmesinin sebebi, bu ortam farkının `-linux` setini CI-dışı bir Linux
host'unda yeniden üretmeye çalışan bir sonraki kişiyi yanıltacak olması (§2'deki
`analysis-lab` bulgusuyla aynı sınıf). **Ölçüldü, düzeltilmedi, yeni kalem AÇILMADI** —
CI'da görünmeyen bir davranış için §6.7'ye kalem eklemek defteri şişirirdi.

## 7. v18 uyum incelemesi — 15 baseline, TEK TEK

Referans: `docs/spec/index_guncellenmis_duzeltilmis_v18.html` (kanonik v18 mockup),
`frontend/e2e/screenshots/prototype/<slug>--1440.png` ve **adjudicated defter**
`docs/implementation/v18_visual_deviations.md` (A-06 derin kıyas, 2026-07-30, D-1 imzalı).

**Toplu onay YOK.** Hiçbir YENİ, imzasız sapma dondurulmadı.

| # | Sayfa | v18 uyumu | Karar |
|---|---|---|---|
| 1 | `outsource-signal` | Chooser + "About this surface" + "What this surface does not do". Prototipte screenshot **yok** (defterde kayıtlı); kıyas doc 03 §1'e. | **SIGNED-DEVIATION (D-1)** — ek route/help yüzeyi. Statik, oynak içerik yok. |
| 2 | `pre-check` | "My requests" tablosu; doc 07 §3 Pre-Check'i Create Package içine gömer, uygulama ayrıca history/deep-link sunar. | **SIGNED-DEVIATION (D-1)**. Ham `pkgreq_…` + timestamp **kabul edildi ve §5'te yazıldı**. |
| 3 | `package-library` | Filtre süperseti + Import panel = defter 8.1/8.4. | **PO-APPROVE**. **F-2 AÇIK ve donduruldu**: `indicator v1`, `embedded_system v1`, küçük harf `active/passed/approved`, adsız seed paketleri `—`. |
| 4 | `embedded-packages` | Trusted resolver registry, 12 canonical key, **insan-okur "active revision pinned"**. | **F-7 FIXED doğrulandı** — ham `pkgrev_…` **yok**. Yapısal fark D-1. Deterministik. |
| 5 | `rationale-families` | 6 family kartı + assignment tablosu. | **SIGNED-DEVIATION (D-1)** — metadata süperseti. `Created (UTC)` §5'te. |
| 6 | `research-data` | 5 adımlı workflow + status legend + **gerçek boş registry**. | **PASS** — prototip örnek satır gösteriyor, uygulama gerçek empty-state; defter bunu *"fixture farkı sapma sayılmaz"* diye kaydetmiş. |
| 7 | `portfolio` | 4 bölüm + checkbox defter 13.1 ile **birebir**. | **PO-APPROVE**. **F-4 AÇIK ve donduruldu**: "+ Add item" adayı ham `mbi_…` ULID (defter 13.2). |
| 8 | `results-history` | Sıralama, Compare selected (0/2), View/Delete, sayfalama. | **PO-APPROVE** (defter 16.1). **Not:** kapalı satır artık **Net/ROMAD/DD/Win Rate gösteriyor** → defterin **F-5**'i (16.2) görünüşe göre kapanmış; ham `btres_…` + tarih kalıyor (§5). |
| 9 | `arrange-metrics` | 9 seçili metrik, registry v1, future-version metrikleri. | **SIGNED-DEVIATION (D-1)** — açıklama süperseti. Tam deterministik. |
| 10 | `analysis-lab` | Alpha Agent şeridi, Lab Context, conversation, work queue, task history, hypothesis board — hepsi **gerçek boş durum**. | **PASS** — defterdeki fixture farkı. Tam deterministik. |
| 11 | `panel-management` | Registered users + system actors + role scope matrix + operator recovery. | **SIGNED-DEVIATION (D-1)** — operasyonel süperset. Rastgele kullanıcı adları §5'te. |
| 12 | `panel-logs` | Immutable event log; prototip yalın "All User Backtest Logs" tablosu. | **SIGNED-DEVIATION (D-1)**. **BİLİNEN, İZLENEN KUSUR DONDURULDU:** satır ham `btres_…` ULID basıyor (F-07 kalıntısı sınıfı, `pages/PanelLogs.tsx`). Sessizce dondurulmadı — burada ve PR gövdesinde yazılı. |
| 13 | `trash` | Başlık + Admin-only açıklaması + tür filtresi + arama + `(0 recoverable)` + boş durum metni. | **PO-APPROVE (minör)** — defter 20.1. Oynak içerik **yok**. |
| 14 | `user-manual` | İki kolon document/search + continuous guide + Admin document controls. | **SIGNED-DEVIATION (D-1)** — yönetim/meta süperseti. |
| 15 | `future-dev` | Capability Registry, 7 placeholder, `Operational: no`, "No output history". | **PASS** — doc 22 canonical; prototipte karşılık yok. |

**Yeni sapma bulunmadı.** D-10 (45 accent-blue düşük kontrast düğüm, 2026-07-30 imzalı
kalıcı sapma) baseline'larda **beklendiği gibi** görünür; yeniden dosyalanmadı.

Nav'daki "Future Dev" öğesinin vurgulu görünmesi **23 sayfanın hepsinde** aynı →
aktif-durum hatası değil, kalıcı stil. Kontrol edildi, bulgu değil.

## 8. Süre etkisi

| | Sayfa | Süre |
|---|---|---|
| CI, 2026-08-07 kanıtı (`p11_visual_gate.txt`) | 8 | **1.4 dk** |
| **CI, bu PR (ölçülen)** | 23 | **4.2 dk** |
| Bu makine, döngü 2 | 23 | 4.5 dk |

**`e2e` job'ına gerçek etki: ≈ +2.8 dk** (1.4 → 4.2). Test başına CI'da 10.5 s → 10.9 s;
maliyet neredeyse tamamen rota sayısından geliyor, rota başına maliyetten değil. Kapsam
**kısılmadı**, paralelleştirmeye de gerek görülmedi.

## 9. Sınırlar

- Bu bölümün **hiçbir çıktısı A-08 değildir.** Piksel karşılaştırması ekran-okuyucu
  kanıtı **değildir** ve `docs/audit/a11y_screen_reader_audit_results.md` §1/§2'ye
  **yazılamaz**; defter BOŞ, dört kriter de ☐, #514 durumu değişmedi.
- K-2..K-6'ya dokunulmadı.
- Ürün kodu değişmedi: route, react-query key, OCC token, Idempotency-Key, hook, SSE
  taksonomisi, `lib/*.ts`, `app/nav.ts` — hiçbiri.
- Kapı **bloklayıcı** kaldı; advisory'ye düşürülmedi.

## 10. Kapanış durumu

| | |
|---|---|
| Kapsam | **8 → 23** (`TARGET_PAGES` türevi) |
| Yeni baseline | **15** (14'ü Linux konteynerinden, `analysis-lab` **CI artefaktından**) |
| Yeniden üretilen mevcut baseline | **0** — sekizi yalnız **rename** edildi (byte-identical) |
| Runner'da sonuç | **23/23**, **iki kez, aynı commit'te** (`fa0c6a2`) |
| `e2e` job süresi | 1.4 dk → **4.0 dk** (+2.6) |
| Tolerans / maske / kapı sertliği | **değişmedi** (`maxDiffPixelRatio 0.02`, bloklayıcı) |
| Ürün kodu | **değişmedi** |
| Blocker sayısı | **üç** — değişmedi. §8 verdict **BLOCKED** |

**P11 KAPANMADI.** Açık kalanlar: **P11-1** (branch protection — repo ayarı, **insan
kararı**, agent işi değil), **P11-6b** (tab sondası Tab'a basmıyor), **P11-8**
(Lighthouse). **P11-3b** bu ölçümle **cevaplandı** (§3).
