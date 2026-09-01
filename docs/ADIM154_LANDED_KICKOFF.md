<!-- doc-status: current -->
# ADIM 154 landed — on karar tek oturumda imzalandı; beş issue kapandı, üç kod işi imzalı kuyruğa girdi

## Nerede duruyoruz

Taban `origin/main` @ `1ac56232` (ADIM 153). **DOCS + GitHub dispozisyonları + tek satır CVE
yaması** — backend/test/migration'da sıfır satır; `frontend/Dockerfile` kapsamlı `apk upgrade`
listesine `libexpat` aldı (CVE-2026-66046 · CVE-2026-76641, HIGH, fix 2.8.4-r0 — SBOM kapısı
PR açıkken kırmızıya döndü, openssl satırının emsaliyle kapatıldı; fix varken allowlist
yazılmaz) · ratchet el değmedi (54/6 · A1 B21 C6 D32) · **A-08 (#514) AÇIK, blocker
DEĞİŞMEDİ (1) → BLOCKED.**

Ürün sahibi 2026-09-01'de on kararı interaktif imzaladı (toptan yetki ≠ imza; şıklar bedelleriyle
tek tek soruldu, ADIM 66 emsali). Kapanan issue'lar: #582 · #535 · #542 · #543 · #545 (+#534'ün
üç düzlemi hizalandı). Kod bekleyen açıklar: #854 · #547 · #546. **#514 imzayla kapatılmadı** —
denetim karar değildir.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `PROJECT_HISTORY.md` §ADIM 154 | On kararın tablosu + imza yerleri (belge kutusu ↔ issue dispozisyonu ayrımı) |
| `closure_i854_…` §Karar 1 ☑(b) | Set-once slice'ının imza dayanağı; Karar 2 konusuz-notu |
| `closure_i534_…` ☑(c) | #534'ün kapanış kaydı — üç düzlem hizalı |
| İzleyici dersi (§ADIM 154) | Koşu izleyicisinde "farklı id ≠ yeni id"; yalnız sayısal BÜYÜK id kabul et |

## Sıradaki iş (imzalı kuyruk, önerilen sıra)

1. **#854 set-once slice'ı (en küçük):** `repositories/trade_log.py::link_batch_to_revision` +
   `repositories/trading_signal.py::link_normalized_to_revision` yalnız kolon `None` iken yazar;
   `tests/integration/test_external_import_pin_stability.py` **kasıtlı** ters çevrilir (yeni
   dünyayı pinler — pin N'de KALIR, kompozisyon READY kalır; N+1 repin edilirse blocker oraya
   taşınır, bu da bir case olarak pinlenir). Slice #854'ü kapatır (Closes #854).
2. **#546 matrix slice'ı:** `restrictions_filters.filters.action` capability matrix'e →
   structured provenance'ta görünür; ADIM 139'un iki muhafız ekseni hazır; TS aynası
   `backend/tools/export_capability_matrix.py` ile yeniden üretilir. Davranış DEĞİŞMEZ.
   Slice #546'yı kapatır.
3. **#547 feature slice'ı:** Increasing Timeframe by Layer — issue'nun "Required work" listesi
   madde madde (`layer_timeframe`/`layer_bucket` yeniden kullanımı · exhaustion =
   custom_sequence emsali · matrix satırı `active_v1` + TS aynası · bayat remediation cümlesi
   kalkar · `test_backtest_scaling_timeframe_mode.py` aynası). `ENGINE_VERSION` PR'da açıkça
   değerlendirilir. Slice #547'yi kapatır.
4. **Tavan takibi:** post-fix korpus 3/3 kusursuz (69/69 × 3 koşu, artefaktlardan okundu);
   4. ardışık kusursuz koşu inince sıkıştırma slice'ı — tavanlar o PR'ın KENDİ CI
   artefaktından, yerelden ASLA.

---

## Paste-ready resume prompt

```
Entropia — ADIM 155. Session START protokolünü uygula: önce `git fetch`,
`git log --oneline origin/main -6`, `gh pr list --state all` ile NE İNDİĞİNİ doğrula
(handoff STALE-BY-DEFAULT). Sonra oku: docs/ADIM154_LANDED_KICKOFF.md →
docs/STAGE2_HANDOFF.md (son "## Next") → docs/PROJECT_HISTORY.md §ADIM 154 (hedefli).

DURUM: ADIM 154 on kararı imzaladı (tablo §ADIM 154'te). Kod kuyruğu İMZALI:
  (1) #854 set-once — link_batch_to_revision + link_normalized_to_revision yalnız kolon None
      iken yazar; test_external_import_pin_stability.py KASITLI ters çevrilir. En küçük iş,
      buradan başla. Closes #854.
  (2) #546 — restrictions_filters.filters.action capability matrix'e (davranış değişmez,
      TS aynası yeniden üretilir). Closes #546.
  (3) #547 — Increasing Timeframe by Layer (exhaustion = custom_sequence emsali;
      ENGINE_VERSION PR'da açıkça değerlendirilir). Closes #547.
Tavan takibi: post-fix korpus 3/3 kusursuz; 4. kusursuz koşu inince sıkıştırma slice'ı
(tavanlar o PR'ın KENDİ CI artefaktından). #514 A-08 TEK BLOCKER, human-only.

KURALLAR: ölçmediğini iddia etme; öncülü defterin/haritanın KENDİSİNDE doğrula; yeşil exit
code kanıt değildir (exit code'u AYRI oku); vitest --no-file-parallelism; alt küme pytest'te
--no-cov; kapanış ritüeli ZORUNLU; kickoff'lardan yalnız EN YÜKSEK numaralı olan current
olabilir; self-merge bloklu — yeşilde merge'ü kullanıcıdan iste.
```
