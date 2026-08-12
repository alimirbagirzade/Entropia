<!-- doc-status: historical -->
> **SUPERSEDED by `docs/ADIM45_LANDED_KICKOFF.md` (ADIM 45, 2026-08-12).** Bu belge ADIM
> 43'ün kaydıdır ve o günkü durumu anlatır; canlı kickoff artık ADIM 45'inkidir.
> (ADIM 44 kendi kapanışında bu işareti düşürmeyi atlamıştı — `--check` onu ADIM 45'te
> yakaladı: aynı anda iki kickoff `current` olamaz.)
# ADIM 43 landed — kickoff / devam tohumu

> **ADIM 43 = RC §6.7 / P11-8 + P10-7.** İki kapı bağlandı. **P11-8 KAPANDI** (Lighthouse
> ratchet, 23/23 rota). **P10-7 KAPANDI** — ve bu bir sürprizdi: brief saati *başlatmayı*
> planlıyordu, ölçüm saatin **zaten dolmuş** olduğunu gösterdi. **Ürün kodu DEĞİŞMEDİ.**
> **P11 ve P10 KAPANMADI**, verdict **BLOCKED**, blocker sayısı **üç**.

---

## Neredeyiz

| | |
|---|---|
| Rapor kalemleri | **P11-8** (*"Lighthouse hâlâ bağlı değil"*) · **P10-7** (*"aktivasyon için 5 gecelik baseline gerekiyor"*) |
| P11-8 sonucu | İddia **doğruydu** → ratchet olarak bağlandı, **23/23 rota**, kapsanmayan **0** |
| P10-7 sonucu | İddianın ikinci yarısı **bayattı** → toplayıcı ADIM 24'ten beri koşuyordu, **altı** gece birikmişti |
| Ölçülen bant | `--max-ratio 2.5` (`1.5 × 1.62`, türetildi) |
| Lighthouse tabanı | perf **100**/22 rota, **98** `panel-management` · BP **96** · SEO **82** |
| Tekrar yayılımı | **0 puan**, üç kategoride de, 23 rotanın hepsinde |
| Verdict | **BLOCKED** (değişmedi), blocker **üç** (değişmedi) |

---

## Bu slice'ın bıraktıkları — reuse anchor'ları (tam sembol adlarıyla)

| Anchor | Ne işe yarar |
|---|---|
| `frontend/e2e/specs/21-lighthouse.spec.ts::CATEGORIES` | Hangi kategorilerin istendiği. **`accessibility` burada YOK ve olmayacak** — axe otoritesi |
| `…::REPEATS` / `…::median` | Gürültü cevabı: warm-up + medyan. Kapı çırparsa **burayı** büyüt, tabanı indirme |
| `…::METRIC_IDS` | Raporlanan ama **kapılmayan** ham metrikler (FCP/LCP/TBT/CLS/SI) |
| `…::floorFor` | Taban okuma; `null` = rota tabansız → **kırmızı** (boşluk, geçiş değil) |
| `…::deductions` | Puanı hangi ağırlıklı audit'in götürdüğü — donmuş kusurun görünmez olmasını engeller |
| `frontend/e2e/lighthouse-baseline.json::armed` | `false` = ölç-ama-kapıma (bootstrap). **Dosyanın yokluğu = sert hata** |
| `…::provenance.sensitivity_boundary` | performance'ın localhost'ta **doygun** olduğu uyarısı — sayıyla birlikte seyahat eder |
| `…::policy.performance_vs_loadgen` | İki performans otoritesinin ayrımı, tabanın kendi içinde |
| `docs/performance/baseline_ci.json` | Ratio kapısının dondurulmuş baseline'ı (altı gecenin medyanı) |
| `backend/tests/unit/test_loadgen.py::_BAND` / `::_OBSERVED_WORST_RATIO` | Bandın üç sahibinden biri |
| `…::test_the_nightly_actually_passes_the_band_this_file_pins` | Üç sahibi ayrışırsa kırmızıya çevirir |
| `scripts/loadgen.py::_ratio_gate` | Kontrol-normalize karşılaştırma (değişmedi, yalnız devreye alındı) |

---

## Pazarlıksız kurallar (bu slice'ın koyduğu)

1. **Lighthouse a11y kategorisi ASLA açılmaz.** Rakip bir a11y otoritesi yaratır. Ve
   **hiçbir Lighthouse çıktısı A-08 kanıtı değildir** — defterin §1/§2'sine yazılamaz.
2. **İki performans otoritesi birbirinin sorusuna cevap veremez.** `loadgen` = sunucu,
   Lighthouse = tarayıcı. Ayrım `performance/README.md` §1/§8'de ve
   `lighthouse-baseline.json::policy`'de yazılı.
3. **Taban indirilmez, bant genişletilmez.** Kapı gürültülüyse `LH_REPEATS`'i büyüt veya
   warm-up'ı değiştir. Ratio bandı üç yerde pinli; yalnız workflow'da genişletmek testle
   engelli.
4. **Rota listesi elle yazılmaz.** Tek kaynak `screenshotMatrix.ts::TARGET_PAGES`.
   Matriste olup tabanı olmayan rota **kırmızı** verir.
5. **Yeni bir gecelik toplayıcı eklersen** `cancel-in-progress` ifadesini kontrol et **ve
   koştuğunu job log'undan doğrula** — yeşil rozet yetmez.

---

## Dürüst sınırlar (devralan bunları bilmeli)

* **Lighthouse performance doygun.** Localhost + desktop preset'te 22/23 rota 100 alıyor.
  Taban 100 = *"hiç kötüleşemez"* (en katı ratchet), ama **gerçek cihazda hızlı olduğunun
  kanıtı değil**. Bu cümleyi silme.
* **BP 96 ve SEO 82 gerçek kusurdur, donduruldu — düzeltilmedi.** Ayrı PR'lar.
  `routes[].deductions` onları isimlendirmeye devam eder.
* **Ratio kapısı 2.5× altını görmez** ve **PR'da hiç koşmaz** (gecelik). Latency'yi 3×
  bozan bir PR yeşil merge olur, ertesi sabah yakalanır. Bu §1'in bilinçli takası.
* **Bant altı geceye dayanıyor**, tek runner class. Altı örnek bir kuyruğu sınırlayamaz.
* **A-08 hâlâ yapılmadı**, defter hâlâ **boş**, dört çıkış kriteri de ☐. Bu slice ona
  dokunmadı ve dokunamaz.
* **P11-1 (branch protection) agent işi değil** — repo ayarı, insan kararı. Bu yüzden
  Lighthouse kapısı da bugün *required status check* değil, yalnız bir job.

---

## Sıradaki iş

| Aday | Neden |
|---|---|
| **P11-1** | Branch protection — **insan kararı**. Bu olmadan hiçbir kapı merge'i mekanik engellemiyor |
| **BP 96 / SEO 82 kusurları** | `routes[].deductions`'tan oku, ayrı PR'lar |
| **P11-6b** | Tab-sırası sondası Tab'a hiç basmıyor |
| **P8-B3b** | `JOBS_AND_EVENTS.md` gövdesinde ~30 satır-numarası referansı |
| **P4-3** | 60 `modify_default`, ölçüldü/düzeltilmedi |
| **PR B** | `ItemParticipant` adaptörü — **ADR §16 insan kapısı** arkasında |

---

## Çalışma yöntemi (işe yarayan)

**Kod yazmadan önce ÖLÇ.** Bu slice'ın en değerli çıktısı bir satır kod değil, şu soruydu:
*"toplayıcı zaten var mı, kaç gece birikmiş?"* Cevap `gh run list --event=schedule` +
`gh api …/artifacts` ile 2 dakikada geldi ve planlanan ikinci PR'ı gereksiz kıldı.
Raporun kendi cümlesine güvenme; tarihini oku, sonra doğrula.

**Kapıyı UNARMED sevk et.** Ölçülmemiş bir eşik uydurmak yerine `armed: false` ile bootstrap
et, CI ölçsün, ikinci commit dondursun. Bu, "bugünkü skoru tavan yap" kuralını uydurmadan
uygulamanın tek dürüst yolu.

**Push etmeden önce koşan job'ı düşün.** PR ref'inde `cancel-in-progress: true` — ölçüm
koşusu sürerken push etmek onu iptal eder ve ölçümü kaybettirir.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 44

[[ ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ / PR DİSİPLİNİ
   bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 43 / PR #676 merge olmuş OLMALI; olmadıysa DUR)

Oku: docs/ADIM43_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (§ADIM 43 landed + Next)
     → docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.7 (P11-8 ve P10-7 artık
       KAPALI; §6.7.11 + §6.7.12 ölçümleri taşıyor)

ADIM 43'ün bıraktığı AÇIK işler (hiçbiri bu slice'ta kapatılmadı):
  · Lighthouse best-practices 96 / seo 82 — GERÇEK kusurlar, ölçülen değerinde
    donduruldu. Hangi audit'lerin puanı götürdüğü CI artefaktında:
    lighthouse-report/lighthouse-results.json → routes[].deductions. AYRI PR.
  · P11-1 branch protection — İNSAN KARARI, agent yapamaz.
  · P11-6b · P8-B3b · P4-3 · P10-B2'nin PO yarısı · P10-B3/B4/B5/B6.

ADIM 43'ün koyduğu ve KIRILMAMASI gereken kurallar:
  · Lighthouse a11y kategorisi ASLA açılmaz; hiçbir çıktısı A-08 kanıtı değildir.
  · loadgen = sunucu, Lighthouse = tarayıcı. Biri diğerinin sorusuna cevap veremez.
  · Taban indirilmez / bant genişletilmez. Gürültü → LH_REPEATS veya warm-up.
  · Rota listesi TARGET_PAGES'ten türer, elle yazılmaz.
  · Ratio bandı üç yerde pinli (workflow · test_loadgen.py · README §6); ayrışırsa
    test kırmızıya çevirir.

Verdict BLOCKED, blocker üç (1, 2, 4). "READY" YAZMA.
```
