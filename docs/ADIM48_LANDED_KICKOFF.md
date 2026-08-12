<!-- doc-status: current -->
# ADIM 48 LANDED — RC §6.5'in iki PO kalemi (K-2 + K-4) · sıradaki slice için kickoff

> **Bu belge ADIM 48 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 48.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** ADIM 48 hiçbir blocker'a dokunmadı;
PO'nun 2026-08-12 tarihli **§6.5 kararını** uyguladı: **K-2 ve K-4 FIX**, K-3 kapsam dışı,
K-5/K-6 A-08'i bekler. Presentation-only: migration yok, `ENGINE_VERSION` değişmedi,
`docs/openapi.json` değişmedi, backend'e hiç dokunulmadı.

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam sembol adlarıyla)

| Anchor | Ne için |
|---|---|
| `frontend/src/app/Layout.tsx` — `.skip-link` + `<main id="main-content" tabIndex={-1}>` | Shell'in a11y iskelesi. Link `.app-shell`'in **ilk çocuğu** olmak zorunda; `<main>`'in `id` + `tabIndex` ikilisi **birlikte** taşıyıcı |
| `frontend/src/styles/global.css::.skip-link` / `::.skip-link:focus-visible` | Üç kısıtın kesişimi: akış dışı (baseline'lar) + `absolute` değil `fixed` (probun `offsetParent` filtresi) + clip/1px (tab sırası + a11y ağacı) |
| `frontend/src/test/a11ySkipLink.test.tsx` | K-2'nin **kapısı** (advisory değil). `TABBABLE` sabiti precheck probundan birebir kopya |
| `userManual.test.tsx::"names itself with a level-1 heading (K-4)"` | Seviye **ve** `.page-title` sınıfı birlikte assert edilir |
| `docs/releases/evidence/2026-08-12/adim48_ci_a11y_measured.txt` | **CI'da ÖLÇÜLEN** precheck profili (run `31626856387`): skip link **0**, no-`<h1>` **0**, heading outline **22**, toplam **67**; axe ratchet 45/45 |
| `docs/releases/evidence/2026-08-12/adim48_ci_visual_measured.txt` | **CI'da ÖLÇÜLEN** görsel kapı: **23/23, sıfır baseline diff**. Skip link'i akışta bırakan bir tasarım burada 23 satırı birden kırardı |
| `docs/releases/evidence/2026-08-12/adim48_k2_k4_precheck_derivation.txt` | Koşudan ÖNCE yayımlanan türetme; altı sınıfın altısı da ölçümle tuttu. Ölçemediğinde bunu yap — **"ölçtüm" yazma** |

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **Skip link `<a href="#...">` olmak zorunda.** Prob ilk tabbable'ı `/^a\[href=#/` ile
   eşliyor; `<button onClick>` işlevsel görünür ama ölçümü asla yeşile çevirmez.
2. **`position: fixed` skip link'i ÖLDÜRÜR** — `offsetParent` null döner, prob linki hiç
   görmez. `display:none`/`visibility:hidden` de olmaz (tab sırasından düşer). Akışta yer
   kaplayan bir çözüm ise 23 görsel baseline'ı birden kaydırır. Üçünün kesişimi tektir:
   iki durumda da `absolute` + clip/1px.
3. **`.page-title` gibi sınıf-tabanlı bir başlıkta etiket değişimi görünümü DEĞİŞTİRMEZ** —
   ama tersi de doğru: sınıfı düşürürsen bozar. Etiketi değiştirirken **sınıfa dokunma**.
4. **Sınıf değişmediği için seviyeyi assert etmek ZORUNLU.** `<h1>` sessizce `<h2>`'ye
   dönse ekranda hiçbir fark olmaz — yalnız seviye assert'i yakalar.
5. **Advisory kapı değildir.** Precheck K-2'yi ADIM 28'den beri **ölçüyordu** ve hiçbir şey
   kırmadı. Bir bulgu kapandığında advisory'yi **silme** — regresyon dedektörü olarak tut,
   `note`'unu yeniden yaz.
6. **Yan etkiyi ölç ve YAZ, düşürme.** K-4'ün fix'i K-5'i **bir rota genişletti** (21 → 22).
   Tek sayfanın outline'ını yeniden keserek sayıyı kurtarmak, 22 rotanın hepsinde aynı olan
   çareyi denetimin verdicti gelmeden uygulamak olurdu.
7. **Ölçemiyorsan "ölçtüm" yazma — ama TÜRET, yayımla ve sonra doğrula.** Bu oturumda
   audit stack ayağa kalkmadı; sayılar **türetildi**, her yerde öyle etiketlendi, ve CI
   koşunca **altı sınıfın altısı da tuttu**. Türetmenin koşudan ÖNCE yayımlanmış olması
   onu bir tahmin değil bir **öndeyi** yapar; sonradan yazılsaydı hiçbir şey kanıtlamazdı.
8. **Yeşil bir CI koşusu bir sınıfın varyansını İPTAL ETMEZ.** K-5'in 22'si ölçüldü ama
   koşu soğuktu; §6 soğuk koşunun eksik raporladığını kayıt altına alıyor. Bu kez üst
   uçtan örnekledi — bu iyi şans, kural değil.

## Açık kalanlar (ADIM 48 bunları KAPATMADI)

- **A-08 / #514** — tek kalan blocker. Defter **boş** (0/4). İki yapısal önkoşul iyileşti,
  **hiçbiri duyulmadı**. İnsan kapısı; agent kapatamaz.
- **K-3 (`contentinfo` yok, 23/23)** — PO **kapsam dışı** dedi.
- **K-5 (başlık outline, artık 22/23)** ve **K-6 (odak göstergesi)** — A-08'in cevaplaması
  gereken sorular.
- **`npm run a11y` ve `npm run visual` CI'da koştu; ikisi de YEŞİL.** Görsel: **23/23,
  sıfır diff**. CI yine de **tek ve soğuk** bir koşudur: K-2/K-4 kapandı, **K-5'in 22'si
  ±1 çekincesini korur** ve ılık ≥2 koşuyla yeniden ölçülmelidir.
- **Memory checkpoint (ritüel md. 4) EKSİK — ARKA ARKAYA İKİNCİ SLICE.** `ecc` ve
  `claude-mem` MCP sunucuları bu oturumda da bağlı değildi. **ADIM 47 + ADIM 48 için
  birlikte yazılmalı.**
- **§6.7 tablosu: 24 satırda 10 AÇIK** — P4-3 · P10-B6 · P11-1 · P11-6b · P11-3b ·
  P8-B3b · P1-Gate3 · P10-B3/B4/B5.

## Sıradaki iş

Değişmedi: **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py` item döngüsü
call site**. ADIM 35 §4.1'in **(c)** engelini kapattı; kalan **(a)** faz-bölünmüş bar ve
**(b)** book-etmeyen değerlendirme girişi `run_engine`'in gövdesine dokunur → **ADR §16
insan kapısı + ADR amendment'ı** gerekir, o kapıdan geçmeden başlama.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 49

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — `git fetch && git log --oneline origin/main -6`)
ADIM 48 landed: RC §6.5'in K-2 (skip link) ve K-4 (/user-manual h1) kalemleri
KAPANDI — presentation-only, PO kararı 2026-08-12.

ÖNCE OKU (otorite sırası)
  1. docs/ADIM48_LANDED_KICKOFF.md (bu belge)
  2. docs/STAGE2_HANDOFF.md → "## Stage — ADIM 48" + "## Next"
  3. docs/PROJECT_HISTORY.md §ADIM 48
  4. docs/generated/repository_facts.md (SAYISAL OTORİTE — CLAUDE.md'deki sayı değil)

DURUM (doğrula, güvenme)
  · Blocker sayısı 1 (yalnız A-08), verdict BLOCKED. "READY" YAZMA.
  · K-2/K-4 kapandı; K-3 kapsam dışı; K-5 (artık 22/23) ve K-6 A-08'i bekliyor.
  · K-5'in 22'si TÜRETİLMİŞ. Stack ayağa kalkarsa ILIK ve ≥2 KEZ ölç, sonra
    a11y_screen_reader_audit_results.md §6 + RC §6.5'teki türetilmiş sayıları
    ÖLÇÜLENLE DEĞİŞTİR. (İlk koşu soğuktur ve EKSİK raporlar.)

ÖNCELİK: ilk maddeden BİRİNİ seç, hepsini birden alma
  (a) RİTÜEL BORCU: ecc + claude-mem memory checkpoint'i — ADIM 47 VE ADIM 48
      için. İki oturumdur MCP sunucuları bağlı değildi. Önce bağlı mı ÖLÇ.
  (b) ADIM 48'in CI sonucunu OKU: e2e.yml'in `a11y` ve visual job'ları. Görsel
      baseline'da diff varsa BASELINE'I GÜNCELLEME — .skip-link CSS'ini düzelt
      (akış dışı kalmalı).
  (c) §6.7'nin açık kalemlerinden biri — P8-B3b (belge, düşük risk) ya da
      P10-B6 (4 uç etkin sayfa boyutunu yankılamıyor).
  (d) PR B (ItemParticipant) — ama ADR §16 insan kapısından geçmeden BAŞLAMA.

TAVİZ VERİLEMEZ
  · OCC (If-Match / expected_*_version / X-*-Version), Idempotency-Key, route
    YOLLARI, react-query key'leri, ENGINE_VERSION DEĞİŞMEZ.
  · Frontend'e dokunuyorsan görsel referans docs/spec/index_guncellenmis_duzeltilmis_v18.html.
  · Skip link `.app-shell`'in İLK ÇOCUĞU kalmalı ve CSS'te İKİ DURUMDA DA
    position:absolute olmalı (fixed → offsetParent null → prob göremez;
    akışta → 23 baseline kayar).
  · A-08 / #514'ün durumunu DEĞİŞTİRME — insan kapısı.
  · Yeşile zorlama YOK: kapı kırılıyorsa BLOCKED yaz.

ÖLÇÜM TUZAKLARI (bu repoda gerçekten yaşandı)
  · pytest'i | tail'e BORULAMA — exit code tail'in olur.
  · Alt küme koşarken --no-cov EKLE; tam suite TEK çağrıda.
  · vitest: --no-file-parallelism ZORUNLU; worktree'de önce `npm ci`.
  · a11y precheck: İLK KOŞU SOĞUK ve EKSİK raporlar — en az iki kez koş.
  · Postgres/docker YOKSA (remote container) DB ve stack testleri koşmaz —
    otorite CI'dır, "geçti" YAZMA. Docker Hub 429 / blob CDN 403 bu ortamda
    ölçüldü; workaround aranmaz, raporlanır.
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin 6 maddesi +
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
