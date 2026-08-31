<!-- doc-status: current -->
# ADIM 146 landed — Lighthouse raporu kesintinin adını taşıyıp içeriğini atıyordu

## Nerede olduğumuz

Taban `origin/main` @ `f5f22504` (ADIM 145). **Tek dosya**: `frontend/e2e/specs/21-lighthouse.spec.ts`.
**Ürün kodunda SIFIR SATIR**, backend el değmedi, migration yok, `ENGINE_VERSION` değişmedi,
**kapı mantığı el değmedi**. **Blocker DEĞİŞMEDİ (1 — yalnız A-08) → BLOCKED.**

## Bu slice'ın bıraktığı çapalar

`frontend/e2e/specs/21-lighthouse.spec.ts`:
- `MAX_EVIDENCE_ITEMS` (5) · `MAX_EVIDENCE_CHARS` (300) — sınır, tercih değil gerekçeli
- `renderEvidence(item)` — **genel**; `description` ve `url`/`sourceLocation.url` önde
- `RouteScores.deductions[].evidence: string[]`

## ASIL BULGU

#677 *"read the actual console output"* diyordu; sevk edilen artefakt `{id,title,weight}`
tutup `audit.details`'i atıyordu → **talimat yerine getirilemiyordu**. ADIM 145'te iki
oturum yerel stack'te konsolu yeniden üretmeye harcandı. **Bir kusuru kanıtı olmadan
adlandırmanın bedeli budur.**

## KANIT OKUNDU — soruyu KESKİNLEŞTİRDİ, KAPATMADI

Run `33360933696`: 23/23 rota, 23 farklı satır, hepsi **401**. `/api/v1/events` **×46**;
20/23 rota kendi veri ucunda da 401.

**Ayrı tutuldu:** rotalar aynı ekranı render **etmiyor** (23 farklı LCP, 8 farklı CLS) →
*"hepsi oturumsuz kabuk"* okuması **desteklenmiyor**. SPA auth'u **localStorage'daki opak
Bearer** (`apiClient.ts:153`).
**HENÜZ BELİRLENMEDİ:** Lighthouse'un kendi sekmesi oturumu taşıyor mu (spec
`disableStorageReset` ile taşıdığını **iddia ediyor**), yoksa uygulama token eklenmeden
önce mi istek atıyor. **Düzeltmenin HARNESS'ta mı ÜRÜNDE mi olduğuna karar veren ölçüm budur.**

## DÜRÜST SINIR

- **#677 KAPATILMADI**, `errors-in-console` **DÜZELTİLMEDİ** — teşhis edilebilir kılındı.
- Yukarıdaki soru **açık bırakıldı ve iddia edilmedi**.
- CLS `panel-management` el değmedi; tavanı **98'de kalır**. Tavanlara dokunulmadı.
- Backend kapıları koşulmadı (sıfır satır) → otorite CI.
- **A-08 (#514) AÇIK** — tek blocker.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 146'NIN PR'ININ (#885) DURUMUNU ÖLÇ.

DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -3 && gh pr list --state open
  gh pr view 885 --json state,mergeStateStatus
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  gh issue view 677 --json state && gh issue view 514 --json state

DURUM: ADIM 146 `errors-in-console`'u TEŞHİS EDİLEBİLİR kıldı (her kesinti artık
`evidence: string[]` taşıyor). DÜZELTMEDİ. #677 AÇIK.

SIRADAKİ İŞ — FAZ 2, VE İLK ADIM BİR ÖLÇÜMDÜR, DÜZELTME DEĞİL:
  Kanıt: 23/23 rota 401; /api/v1/events ×46; 20/23 rota kendi veri ucunda da 401.
  AYIRT EDİCİ SORU: Lighthouse'un KENDİ SEKMESİ oturumu taşıyor mu?
    - Taşımıyorsa  -> kusur HARNESS'ta; kapı oturumsuz render'ı puanlıyor olabilir
      (bu, #677'den DAHA AĞIR bir bulgudur — abartma, ÖLÇ).
    - Taşıyorsa    -> kusur ÜRÜNDE: istekler token eklenmeden önce atılıyor
      (ve /events için ayrı bir mekanizma: EventSource özel başlık gönderemez).
  ÖLÇÜM YOLU: spec'e Lighthouse sekmesinde localStorage token'ının VARLIĞINI
  yazdıran bir satır ekle, ya da bir rotanın authenticated fetch'inin 200 döndüğünü
  aynı sekmede gözle. TAHMİN ETME.
  NOT: yerel stack bu işi iki kez yapamadı — API soğukken /meta 15 sn'yi aşıyor,
  ısınınca 0.36 sn. Isıt, sonra koş; ya da doğrudan CI'da ölç.

SONRA: CLS `panel-management` (gerçek layout işi, tavanı 98'de BIRAK).

DİĞER AÇIK KALEMLER: #703 (11 kutu BOŞ) · #854 (9 kutu BOŞ) · #534 (CLOSED ama
kapanış yorumu YOK, 4 kutu BOŞ) · #547 ("Blocked on a product decision", 0 yorum) ·
#582 (ÖNCÜLÜ BAYAT: containment ADIM 132'de kalktı) · #514 A-08 (TEK BLOCKER).

KURALLAR: ölçmediğini iddia etme; bir kesintiyi kapatmak daha ağırını açabilir
(ADIM 145'in öz golü); yeşil exit code kanıt değildir; host'tan curl tarayıcının
kanıtı değildir; vitest'i --no-file-parallelism ile koş; tavanı ASLA yerel koşudan
alma; kapanış ritüeli ZORUNLU.
```
