<!-- doc-status: current -->
# ADIM 145 landed — GH #677: iki bütün-uygulama Lighthouse kesintisi kaynağında düzeltildi

## Nerede olduğumuz

Taban `origin/main` @ `bfce3e32` (ADIM 144). Bu slice **iki frontend dosyası** sevk etti:
`backend/` içinde **sıfır satır**, migration yok, `ENGINE_VERSION` değişmedi, OpenAPI
değişmedi, golden el değmedi. **Blocker DEĞİŞMEDİ (1 — yalnız A-08) → RC verdict BLOCKED.**

`#677` **KAPATILMADI** — dört donmuş kesintinin **ikisi** düzeltildi.

## Sevk edilen

- `frontend/index.html` — `<meta name="description">`. Metin README'nin **kendi** ürün
  tarifi, kırpılmış; pazarlama metni değil.
- `frontend/public/robots.txt` — `User-agent: * / Disallow: /`.

## ASIL BULGU: iki kesinti de sayfa kusuru değil, KABUK kusuruydu

Rota sayısının **23/23** olmasının sebebi buydu ve ölçülerek gösterildi:

```
GET /robots.txt  ->  status=200  content_type=text/html
<!doctype html> …
```

Dosya yoktu, nginx'in SPA kuralı (`try_files $uri $uri/ /index.html`) kabuğu döndürüyordu
ve Lighthouse bunu **geçersiz robots dosyası** olarak okuyordu. `try_files` gerçek dosyayı
fallback'e tercih ettiği için `public/robots.txt` → `dist/robots.txt` çözümü yeterli.
Build çıktısında kanıtlandı: `dist/robots.txt` var, `dist/index.html` tag'i taşıyor.

**`Disallow: /` bir tedbir değil, DOĞRU politika** — her rota login'in arkasında, indekslenecek
public içerik yok. Audit **geçersiz** dosyada düşer, **kısıtlayıcı** dosyada değil.

## İKİNCİ BULGU: tavanı yerelden sıkıştırmak bir PROVENANCE İHLALİ olurdu

`lighthouse-baseline.json`'ın kendi `provenance`'ı ölçümü **2-vCPU GitHub runner**'a
bağlar, `sensitivity_boundary` ise skorun **yalnız kendi runner sınıfı içinde**
karşılaştırılabilir olduğunu yazar. Apple Silicon'da ölçülen `tightened.json`'ı commit
etmek, bir sonraki CI koşusunda **çırpınan bir kapı** kurardı — issue'nun
`panel-management` için zaten uyardığı `do_not_tighten` tuzağının **genel hâli**.

Bu yüzden tavanlar **PR'ın kendi CI artefaktından** alınır, ikinci bir commit'te.

## ÜÇÜNCÜ BULGU (ölçüm dersi): `curl` sessizce IPv6'ya kaçar

Yerel teşhis sırasında `curl http://localhost:8000` **200** dönerken tarayıcı
ulaşamıyordu. `-4`/`-6` ayrı ayrı sürülünce görüldü. Ama asıl kök **o değildi**:
ekran görüntüsü kesin cevabı verdi — `NETWORK_UNAVAILABLE: Request timed out after 15s`.
API **soğukken** `/meta` 15 sn'lik istemci zaman aşımını aşıyor (seed + 12 container
aynı anda kalkarken), ısındıktan sonra aynı çağrı **0.36 sn**.
**Ders: host'tan atılan bir `curl`, tarayıcının gördüğü şeyin kanıtı değildir.**

## DÖRDÜNCÜ (yeniden doğrulandı): `--no-file-parallelism` ZORUNLU

Düz `npm run test` **8 hata / 3 dosya** verdi. Aynı üç dosya seri kipte **42 passed / 0
failed**. Hatalar yük kaynaklı timeout'tu, regresyon değil — **varsayılmadı, ölçüldü**.

## BEŞİNCİ BULGU: ilk düzeltmem bir ÖZ GOLdü ve ratchet yakaladı

`robots.txt` önce `Disallow: /` ile indi. CI ölçtü (run `33333765655`): seo **82 → 63**,
çünkü ağırlığı 1 olan iki audit kapanırken ağırlığı **4.04** olan `is-crawlable` açıldı →
net **−19**, taban altı, job **kırmızı**. Boş `Disallow:` ile düzeltildi.
**Ders: bir kesintiyi kapatmak daha ağır bir başkasını açabilir; "düzeltme" ancak NET
etkisi ölçülünce düzeltmedir.** Audit **geçersiz** dosyada düşer, kısıtlayıcıda değil.

## DÜRÜST SINIR — kapatılmayanlar

- **`errors-in-console` (23/23) TEŞHİS EDİLMEDİ.** Issue *"read the actual console output"*
  diyor; yerel stack kimliği doğrulanmış bir sayfaya sürülemedi (yukarıdaki soğuk-API
  zaman aşımı). **Kaydedilen ipucu, sonuç DEĞİL:** ulaşılabilen oturumsuz sayfalarda konsol
  hataları `/api/v1/events` (SSE) ve `/api/v1/manual/stream` üzerinde **401**'di.
  Audit'in puanladığı **oturumlu** vaka bu değildir.
- **CLS / `panel-management` EL DEĞMEDİ**; performans tavanı **98'de KALMALI**.
- **Tavanlar bu commit'te sıkıştırılmadı** (yukarıdaki gerekçe).
- Route / react-query key / OCC token / `Idempotency-Key` / SSE taksonomisi / `lib/*.ts`
  **el değmedi**; görsel değişiklik yok (v18 presentation-only sınırı korundu).
- **A-08 (#514) AÇIK** — tek blocker, `human-only`, çıkış kriterleri 0/4.

## Çalışma yöntemi (bu slice'ta işe yarayanlar)

- **Devir prompt'unun aday listesi bayattı.** Açık issue listesi tarandığında onun
  saymadığı iki kalem çıktı (`#582`, `#547`) — ADIM 139'un aynı dersi.
- **Bir öncül ölçülerek çürütüldü:** `#582` *"containment cannot be lifted"* diyor, oysa
  `SHARED_ALLOCATION_STATUS = "active_v1"` (ADIM 132'de kalktı). O issue **bayat**.
- **`#547` kendi gövdesinde imza bekliyor** (*"Blocked on a product decision"*, 0 yorum).
- **Yeşil exit code kanıt değildir:** ilk Lighthouse wrapper'ım `echo EXIT=$?` yüzünden
  `exit 0` raporladı, oysa koşu düşmüştü. Çıktıyı oku.
- **Ekran görüntüsü, log'dan daha hızlı teşhis koyabilir.**

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 145'İN PR'ININ (#884) DURUMUNU ÖLÇ.

DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  gh pr view 884 --json state,mergeStateStatus
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  gh issue view 677 --json state && gh issue view 514 --json state

DURUM: ADIM 145 GH #677'nin DÖRT kesintisinden İKİSİNİ düzeltti (meta-description +
robots.txt, ikisi de KABUK kusuru, 23/23). #677 KAPATILMADI.

SIRADAKİ İŞ — #884 HÂLÂ AÇIKSA:
  Lighthouse job'ının `lighthouse-report` artefaktını indir, içindeki
  `lighthouse-baseline.tightened.json`'ın `floors`'unu `frontend/e2e/lighthouse-baseline.json`
  içine kopyala ve İKİNCİ COMMIT olarak it. PAZARLIKSIZ: `panel-management.performance`
  **98'de KALIR** (`provenance.do_not_tighten`) — tightened map 100 önerse bile.
  Tavanı ASLA yerel bir koşudan alma (provenance 2-vCPU runner'a pinli).

SONRA — #677'nin KALANI:
  - `errors-in-console` (23/23): CI'ın kendi artefaktından `routes[].deductions` oku;
    yerel stack soğuk API yüzünden oturumlu sayfaya sürülemedi. İPUCU (sonuç değil):
    oturumsuz sayfalarda 401 / `/api/v1/events` + `/api/v1/manual/stream`.
  - CLS `panel-management`: gerçek layout işi; tavanı 98'de bırak.

DİĞER AÇIK KALEMLER — ÜÇÜ İMZA, BİRİ BAYAT, BİRİ BLOCKER:
  #703 (11 kutu `☐` BOŞ) · #854 (9 kutu `☐` BOŞ) · #534 (CLOSED ama kapanış yorumu YOK,
  4 kutu `[ ]` BOŞ → ADIM 90 gereği AÇIK) · #547 (gövdesi "Blocked on a product decision",
  0 yorum) · #582 (ÖNCÜLÜ BAYAT: containment ADIM 132'de kalktı, kapatmak insan kararı) ·
  #514 A-08 (TEK BLOCKER, human-only, 0/4).

KURALLAR: her iddiayı ampirik doğrula; devir listesini açık issue listesiyle ÇAPRAZ OKU
(ADIM 145'te iki kalem eksikti); yeşil exit code kanıt değildir (çıktıyı oku); host'tan
curl tarayıcının gördüğünün kanıtı değildir; vitest'i `--no-file-parallelism` ile koş;
kapatmadığını covered İŞARETLEME; kapanış ritüeli ZORUNLU.
```
