<!-- doc-status: current -->
# ADIM 150 landed — Lighthouse artık OTURUM AÇIK ölçüyor; #677'nin baş kesintisi bir HARNESS ARTEFAKTI çıktı

## Nerede duruyoruz

Taban `origin/main` @ `be92c28e` (ADIM 149). **PR #890**, iki commit. **Ürün kodunda SIFIR SATIR** —
backend ve `frontend/src` el değmedi; dokunulan iki dosya
`frontend/e2e/specs/21-lighthouse.spec.ts` ve `frontend/e2e/lighthouse-baseline.json`.
**MIGRATION YOK** · `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · golden **el değmedi**.
**A-08 (#514) AÇIK, blocker DEĞİŞMEDİ (1) → BLOCKED.**

ADIM 147 kusuru ölçmüş ve düzeltmeyi **bilerek** ayrı bir slice'a bırakmıştı. Bu o slice.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `specs/21-lighthouse.spec.ts` → `chromium.launchPersistentContext(userDataDir, …)` | Login **varsayılan** bağlamda olur = Lighthouse'un sekmesinin okuduğu bölüm. Bir daha `launch()` + `newContext()`'e dönme. |
| `::lighthouseTabSeesSession()` | Canlı probe; artık **gate** (`expect(...).toBe(true)`), uyarı değil. |
| `lighthouse-baseline.json` → `provenance.refrozen_2026_08_31` | Dünya değişimi yeniden dondurmasının gerekçesi + hangi tavanın neden oynadığı. |
| `provenance.session_carried_2026_08_31` | Mekanizmanın ölçülmüş zinciri. |

## ASIL BULGU

**#677'nin baş kesintisi bir ürün kusuru değildi.** `best-practices` **96 → 100, 23 rotanın
23'ünde**, çünkü **`errors-in-console` oturum açıkken SIFIR rotada düşüyor**. ADIM 146'nın
yakaladığı konsol hataları **oturumsuz kabuğun 401'leriydi**. ADIM 145 iki oturumu bu kusuru
yerelde yeniden üretmeye harcamıştı — **hiç var olmayan bir ürün kusuru aranıyordu.**

## Sıradaki adayları seçerken ÖNCE ÖLÇ

1. **Oturum açık CLS — ilk kez görünür, DÜZELTİLMEDİ.** `panel-management` **0.165** ·
   `package-library` 0.096 · `create-package` 0.068 · `future-dev` 0.059 (hâlâ 100 medyanlıyor).
   **TUZAK (ADIM 148'in kendi tuzağı):** suçluyu adlandıran `layout-shifts` audit'inin **ağırlığı
   0** olduğu için `deductions` listesinde **görünmez** — ham `lighthouse-results.json`'dan oku.
   **ADIM 148'in `.panel-card-async` düzeltmesi geri alınmadı ve bunu kapsamıyor** (o oturumsuz
   shift içindi, 0.0898 → 0.0000516).
2. **#677 kapatılabilir mi** — dört kesintiden **üçü kapalı**, biri açık. **İnsan kararı.**
3. **`RD-09.c4`** kapatılabilir bir **kabul borcu** slice'ı (`partial`/`debt_class.B` tavanlarını
   oynatır, ratchet yeniden dondurulur).
4. **İmza kalemleri, kutuları BÖLÜM bazında grep'le** (dosya düzeyinde grep yanıltır, ADIM 119):
   #854 (9 kutu) · #534 (4 kutu) · #547 (0 yorum) · #582 (öncülü **bayat**) ·
   **#514 A-08 — tek blocker, `human-only`**.

## Yöntem — bu slice'ın öğrettiği üç şey

* **Bir kapı yanlış dünyayı ölçüyorsa, bulduğu her kusur şüphelidir.** İki oturum var olmayan bir
  konsol hatasını kovaladı. Kusuru aramadan önce **kapının neyi ölçtüğünü** doğrula.
* **Metin içeren heredoc TIRNAKLI olmalı.** `<<PY` kabuğun metnimdeki backtick'leri çalıştırmasına
  izin verdi ve `` `stability` `` sessizce **boş dizeye** döndü. Sayılar bozulmadı (JSON'dan
  geliyordu), **proza bozuldu**; yakalayan şey kabuğun kendi hata satırıydı.
* **Tavanı dünya değişiminde yeniden dondurmak "yeşil olsun diye indirmek" değildir** — ama bunu
  söyleyebilmek için dosyanın **kendi sözleşmesinin** tavanları dünya-kapsamlı ilan etmiş olması
  gerekir. Ediyordu (`session_state_2026_08_31`), yoksa bu bir adjudication olurdu.

---

## Paste-ready resume prompt

```
Entropia — ADIM 151. Session START protokolünü uygula: önce `git fetch`,
`git log --oneline origin/main -6`, `gh pr list --state all` ile NE İNDİĞİNİ doğrula
(handoff STALE-BY-DEFAULT). Sonra sırasıyla oku: docs/ADIM150_LANDED_KICKOFF.md →
docs/STAGE2_HANDOFF.md ("landed" + "Next") → docs/PROJECT_HISTORY.md §ADIM 150 (hedefli).

DURUM: Lighthouse kapısı artık OTURUM AÇIK uygulamayı ölçüyor (ADIM 150, PR #890).
`chromium.launchPersistentContext` ile login varsayılan bağlamda yapılıyor; bayrak
(`session_carried_into_lighthouse_tab`) artık bir GATE. Tavanlar CI'dan yeniden donduruldu.

ASIL BULGU: #677'nin baş kesintisi `errors-in-console` (23/23) BİR ÜRÜN KUSURU DEĞİLDİ —
oturum açıkken SIFIR rotada düşüyor; oturumsuz kabuğun 401'leriymiş. best-practices
96 -> 100, 23/23.

SIRADAKİ İŞ: OTURUM AÇIK CLS — ilk kez görünür oldu, DÜZELTİLMEDİ.
  panel-management 0.165 · package-library 0.096 · create-package 0.068 · future-dev 0.059
  TUZAK: suçluyu adlandıran `layout-shifts` audit'inin AĞIRLIĞI 0, o yüzden `deductions`
  listesinde GÖRÜNMEZ (ADIM 148 bunu bir kez yaşadı) — ham lighthouse-results.json'dan oku.
  ADIM 148'in .panel-card-async düzeltmesi GERİ ALINMADI ve bunu KAPSAMIYOR.
  Tavan `panel-management/performance` = 93; TEK bir yüksek koşuyla SIKIŞTIRMA (`stability`).

DİĞER AÇIK KALEMLER: #677 kapatılabilir mi (3/4 kesinti kapalı, insan kararı) ·
RD-09.c4 (kabul borcu slice'ı, tavan oynatır) · #854 (9 kutu) · #534 (4 kutu) ·
#547 (0 yorum) · #582 (öncülü bayat) · #514 A-08 (TEK BLOCKER, human-only).

KURALLAR: ölçmediğini iddia etme; bir kapı yanlış dünyayı ölçüyorsa bulduğu her kusur
şüphelidir; metin içeren heredoc TIRNAKLI olmalı (<<'PY'); yeşil exit code kanıt değildir
(exit code'u AYRI oku); tavanı ASLA yerel koşudan alma; vitest'i --no-file-parallelism ile
koş; kapanış ritüeli ZORUNLU.
```
