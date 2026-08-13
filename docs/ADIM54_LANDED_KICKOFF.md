<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 54 LANDED — K-3 adjudicated (imzalı karar D-11) · sıradaki slice için kickoff

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** ADIM 54 **kod yazmadı** — RC §6.5'in
K-3 kalemini bir **imzalı PO kararıyla** kapattı. Migration yok, OpenAPI değişmedi,
`ENGINE_VERSION` değişmedi.

RC §6.5'in durumu artık şu: **K-2 / K-4 kodla kapandı** (#685) · **K-6b kodla kapandı**
(#688) · **K-3 kod yazmadan kapandı** (D-11) · **K-5 + K-6a yalnız A-08 ile kapanır** ·
**K-7 ölçüldü, düzeltilmedi**.

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `docs/implementation/a11y_ci_ratchet_and_adjudication.md` §4b `Karar # : D-11` | İmzalı a11y kararlarının **sicili** (D-10 kontrast + D-11 landmark). Yeni karar **aynı bloğa** yazılır; **imzalayan adı olmadan yazılmaz** |
| `docs/implementation/a11y_screen_reader_audit_checklist.md` **A-2** | Beklenti **ÜÇ** landmark. Denetçi bunu okur — dört arayan bir denetçi yanlış `FAIL` yazar |
| `docs/audit/…audit_results.md` §1 A-2 metni · route 1 dipnotu **ᴷ³** · §6 K-3 | Üçü **aynı** gerçeği söyler; biri değişirse üçü değişir |

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **Ölçümü susturmak bir çözüm değildir.** K-3'ün advisory'si 23 rotada çıkmaya devam
   eder. Karar **dispozisyonu** belirler, ölçümü değil. Boş/gizli footer seçeneği tam bu
   yüzden **reddedildi**: sayacı memnun eder, rotor kullanıcısına hiçbir şey vermez.
2. **Bir kalem üç şekilde kapanabilir** — kod düzelir · **beklenti düzelir** · insan
   duyar. Dördüncüsü yok. K-3, ikinci yolun ilk örneğidir: kusur üründe değil
   checklist'in kendi cümlesindeydi.
3. **"İmzalı sapma" iki farklı şeyi anlatabilir, karıştırma.** D-10 **gerçek** bir ihlali
   (1.4.3, 45 düğüm) imzalar → ürün o ölçüt için uyumlu **değildir**. D-11 **olmayan bir
   yükümlülüğü** kaydeder → hiçbir SC contentinfo istemiyor. İkisini aynı torbaya koymak
   D-10'un ağırlığını hafifletir.
4. **İnsan gözlemi tek rotadan genellenmez** ama yönü doğrulayabilir. SR-2 route 1'in
   "kozmetik" yargısı karara **tek başına** yetmedi; makine sayısıyla aynı yöne baktığı
   için kayda geçti.
5. **Çift kayıt sessizce yaşar.** Audit §6'nın tablosunda K-4/K-5/K-6 satırları iki
   kezdi ve ikinci küme bayattı — iki slice'ın aynı tabloyu düzenlemesinden kalmış bir
   merge artefaktı. Aynı tabloya dokunan bir sonraki slice **tekrar sayı** kontrolü yapsın.

## Açık kalanlar (ADIM 54 bunları KAPATMADI)

- **A-08 / #514** — tek blocker. Defter **2 / 184** hücre (yalnız SR-2), **SR-1 hiç
  başlamadı**, çıkış kriterleri **0 / 4**, issue **açık**. **İnsan kapısı.**
- **K-5** (22 / 23 route) — maliyeti ölçülü: **204 başlık / ~40 dosya + 5 tag-scoped CSS
  kuralı**. Denetim "sıçrama yanılttı mı?" sorusuna cevap vermeden **outline yeniden
  kesilmez**. SR-2 route 1'de bu hücre bilerek `—` bırakıldı (denetçi "fark etmedim"
  dedi; bu K-5'e cevap değil).
- **K-6a** — halkanın görünürlüğü; precheck programatik odak kullandığı için **kanıt
  üretemez**. Yalnız A-08.
- **K-7** — ilk DOM'da `aria-live` yok (21 / 23). Ölçüldü, düzeltilmedi.
- **Memory checkpoint** — ADIM 53 `agentmemory` ile hafızayı türetilir yaptı; bu slice
  onu kullanmadı. Bir sonraki oturum **önce ölçsün** (bağlı mı), sonra yazsın.

## Sıradaki iş

Değişmedi: **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site**;
ADR §16 insan kapısından geçmeden başlanmaz. RC §6.7'de açık kalemler: P4-3 · P10-B6 ·
P11-6b · P11-3b · P8-B3b · P1-Gate3 · P10-B3/B4/B5.

---

## Paste-ready resume prompt

```
ENTROPIA — ADIM 54 sonrası devam

CLAUDE.md §Session START protokolünü uygula (fetch + origin/main log + PR listesi;
handoff STALE-BY-DEFAULT'tur — aynı gün DÖRT paralel oturumun aynı numarayı aldığı
görüldü, numaraları doğrulamadan yazma).

ÖNCE OKU (otorite sırası)
  1. docs/ADIM54_LANDED_KICKOFF.md (bu belge)
  2. docs/STAGE2_HANDOFF.md → "## Stage — ADIM 54" + "## Next"
  3. docs/PROJECT_HISTORY.md §ADIM 54
  4. docs/generated/repository_facts.md (SAYISAL OTORİTE — CLAUDE.md'deki sayı değil)

DURUM (doğrula, güvenme)
  · Blocker sayısı 1 (yalnız A-08), verdict BLOCKED. "READY" YAZMA.
  · RC §6.5: K-2/K-4/K-6b kodla, K-3 D-11 ile kapandı; K-5 + K-6a A-08 bekler; K-7 açık.
  · A-08 defteri 2/184 hücre, SR-1 hiç başlamadı, 0/4 kriter, #514 AÇIK.

ÖNCELİK: birini seç
  (a) A-08'in SR-1 (NVDA/Firefox/Windows) yarısı — İNSAN işi, agent koşamaz. Yalnız
      hazırlık/kayıt tarafına dokunulabilir.
  (b) Memory checkpoint: ADIM 53'ün agentmemory mekanizması bağlı mı ÖLÇ, sonra yaz.
  (c) §6.7'nin açık kalemleri (P10-B6, P8-B3b, P4-3, P1-Gate3, P11-6b/3b, P10-B3/B4/B5).
  (d) PR B (ItemParticipant) — ADR §16 insan kapısından geçmeden BAŞLAMA.

TAVİZ VERİLEMEZ
  · OCC (If-Match / expected_*_version / X-*-Version), Idempotency-Key, route YOLLARI,
    react-query key'leri, ENGINE_VERSION, app/nav.ts DEĞİŞMEZ.
  · UI işi v18 mockup'ı referans alır (docs/spec/index_guncellenmis_duzeltilmis_v18.html).
  · A-08 / #514'ün durumunu DEĞİŞTİRME — insan kapısı. Defteri agent doldurmaz.
  · İmzalayan adı verilmeden imzalı karar (D-xx) YAZMA.
  · Advisory/ölçüm SUSTURMA — karar dispozisyonu belirler, sayıyı değil.
  · Yeşile zorlama YOK: kapı kırılıyorsa BLOCKED yaz.

ÖLÇÜM TUZAKLARI (bu repoda gerçekten yaşandı)
  · a11y precheck sayısını TEK KOŞUYLA tazeleme — ilk koşu soğuktur, EKSİK raporlar.
  · vitest: --no-file-parallelism ZORUNLU. pytest'i | tail'e BORULAMA.
  · Host'ta docker YOKSA @a11y / @visual / @lighthouse yerelde KOŞMAZ → otorite CI.
  · main'e merge 16 ZORUNLU check ister (ruleset 20765617) — Backend ~50 dk.
    Merge sırasında main ilerlerse çakışma çıkar; BAŞKASININ slice kaydını yeniden
    düzenleme, yalnız kendi numaranı boş olana taşı.
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.
  · Aynı tabloya iki slice dokunduysa TEKRAR SATIR ara (K-tablosunda yaşandı).

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin 6 maddesi +
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  (bu belgeyi doc-status: historical'a düşür, yeni kickoff'u current yap — TEK current)
```
