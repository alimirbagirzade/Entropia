<!-- doc-status: current -->
# P1 — Repository truth gates (ADIM 29 / V18 RC verification)

**Tarih:** 2026-08-07 · **Dal:** `release/v18-rc-verification` (`origin/main` üzerinden açıldı)
**Kapsam:** base snapshot + üç repository-truth kapısı + beş codemap'in oku-doğrula kontrolü.
**Kod değişmedi.** Bu slice yalnızca kanıt üretir; hiçbir kaynak, test, migration veya CI
dosyasına dokunulmadı.

---

## 0. Karar: **NOT BLOCKED**

| Durdurma koşulu | Gözlem | Sonuç |
|---|---|---|
| Kirli çalışma ağacı | `git status --short` → boş çıktı, exit 0 | temiz |
| Açık production-fix PR | `gh pr list --state open` → **0 satır** | yok |
| Unmerged prior step | `HEAD == origin/main` (`git rev-list --left-right --count` → `0 0`); son adım #631 merge edilmiş | yok |

Üç koşulun hiçbiri tetiklenmedi → P1 çalıştırıldı.

---

## 1. Base snapshot

| Alan | Değer |
|---|---|
| Base SHA | `1f4b88b7370dd73929d068175885c05f65fd3b9a` (`1f4b88b`) |
| Base commit tarihi | `2026-08-07 14:36:32 +0300` |
| Base commit başlığı | `docs(a08): reconcile the record with #514 being closed unaudited (#631)` |
| `origin/main` | aynı sha — dal ondan açıldı, ileri/geri fark `0 / 0` |
| Yeni dal | `release/v18-rc-verification` |
| Çalışma ağacı | temiz (stash / silme YAPILMADI) |

### Açık PR'lar

`gh pr list --state open --limit 50` → **boş** (exit 0). Merge bekleyen üretim düzeltmesi yok.

### `human-only` etiketli issue'lar

`gh issue list --label human-only --state all --limit 50`:

| # | Durum | Başlık |
|---|---|---|
| 514 | **CLOSED** (2026-08-07T03:52:03Z) | A-08: Complete human NVDA/Firefox + VoiceOver/Safari acceptance audit |

> **Dürüst sınır (P1'i bloklamaz, kayıt için):** #514 kapalı ama A-08 denetim defteri
> (`docs/audit/a11y_screen_reader_audit_results.md`) BOŞ ve dört çıkış kriteri de ☐. Bu ayrışma
> ADIM 29'un docs dalgasında (PR #631) **kaydedildi, çözülmedi**; çözüm yolları (imzalı kalıcı
> sapma veya #514'ün yeniden açılması) insan işidir. Hiçbir RC belgesi A-08'i
> `Complete`/`PASS`/`Done` gösteremez.

---

## 2. Kapılar

Üçü de `backend/` içinden koşuldu. Her kapının stdout+stderr'i ayrı dosyaya yazıldı, exit code
**ayrı** bir `echo $?` ile okundu (`| tail` kullanılmadı — pipe exit code'u gizler).

### Gate 1 — documentation-truth (`repository_facts --check`)

```bash
cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```

| Alan | Değer |
|---|---|
| Exit code | **0** |
| Çıktı | [`gate1_repository_facts.txt`](gate1_repository_facts.txt) (5 satır) |
| Özet satırı | `documentation-truth gate OK — artefacts fresh, documents classified, no stale claims.` |

`docs/generated/repository_facts.md` çalışma ağacıyla **birebir**: alembic head
`0043_i08_registry_strategy_fks`, 43 revision (tek head), 104 tablo, 140 FK, 177 path /
196 operation, 29 frontend router path, `ENGINE_VERSION = backtest-engine-v18-gap-adjusted-stop-fill`,
`SHARED_ALLOCATION_STATUS = future_dev`. Bu değerlerle çelişen bir belge iddiası CI'da kırmızıdır.

### Gate 2 — OpenAPI drift

```bash
cd backend && uv run python -m entropia.apps.api.openapi_export --check
```

| Alan | Değer |
|---|---|
| Exit code | **0** |
| Çıktı | [`gate2_openapi_export.txt`](gate2_openapi_export.txt) (1 satır) |
| Özet satırı | `OpenAPI snapshot is up to date: docs/openapi.json` |

Yayımlanmış sözleşme canlı FastAPI uygulamasıyla aynı. `ErrorResponse` zarfı ve
`PurgeAcceptedResponse` gibi typed gövdeler şemada duruyor.

### Gate 3 — acceptance semantic scan

```bash
cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report
```

| Alan | Değer |
|---|---|
| Exit code | **0** |
| Çıktı | [`gate3_acceptance_semantic_scan.txt`](gate3_acceptance_semantic_scan.txt) (200 satır) |
| Özet satırı | `OK: 383 criteria / 1175 clauses validate against the live test tree` |

**Kriter seviyesi (383):**

| covered | partial | uncovered | deliberate_future_dev | not_applicable | product_decision_required |
|---|---|---|---|---|---|
| 229 | 131 | **8** | 8 | 7 | 0 |

**Clause seviyesi (1175):** covered 971 · partial 10 · **uncovered 155** · deliberate_future_dev 27 ·
not_applicable 12 · product_decision_required 0.

**Kanıt tipi başına kriter:** backend_integration 317 · backend_unit 131 · frontend_component 127 ·
backend_contract 70 · e2e 16.

**Kapsanmayan 8 kriter** (kapı bunları *bilinen ve gerekçelendirilmiş* saydığı için yeşil —
gizlenmiş değil, sayılmış):

| ID | Neden kapsanmıyor (kısa) |
|---|---|
| `AT-06` | Test edilecek uyumluluk kuralı **yok** — `strategy/compiler.py` böyle bir blocker üretmiyor. |
| `AT-07` | `strategyGraph.test.tsx` hiçbir entry block silmiyor; UUID korunumu iddiası asserted değil. |
| `AOS-02` | Spec'in istediği literal UI mesajı kod tabanında **hiç yok**. |
| `TL-18` | Expand/collapse'ın revision/audit/hash/readiness yazmadığını hiçbir test iddia etmiyor. |
| `CP-16` | Agent candidate-generation yüzeyi yok (ampirik olarak doğrulandı, haritadan devralınmadı). |
| `PC-15` | Tool Gateway'de Agent Pre-Check giriş noktası yok. |
| `AM-13` | Metrik taşıyan Agent yüzeyi yok. |
| `AM-15` | `metric_profile`, `domain/trash/page.py::TRASH_OBJECT_LOCATIONS` içinde **değil** (K-06 riski). |

> 131 `partial` kriterin her birinin gerekçesi kanıt dosyasının §"Partial criteria" bölümünde
> tam metin olarak duruyor. Bunlar **kapıyı düşürmez** ama RC kabul kararında okunmalıdır —
> aralarında `AT-04` (`MARKET_DATA_INSTRUMENT_MISMATCH` implementasyonsuz), `AOS-17`/`TS-17`
> (spec adı `ACTIVE_RUN_DEPENDENCY` ↔ sevk edilen kod `OBJECT_IN_ACTIVE_RUN`, **hiçbiri pinli
> değil**) ve `TL-20`/`AOS-18` (work-object soft-delete yolunda trash/audit/outbox satırı hiç
> sorgulanmıyor — K-06 tehlikesi) gibi sözleşme-adı ve K-06 kalemleri var.

---

## 3. Codemap oku-doğrula (`docs/CODEMAPS/` — üretim YOK, yalnız okuma)

Beş harita çalışma ağacındaki gerçek yapıya karşı okundu. Yöntem: her haritanın adlandırdığı
modül/route/aktör kümesi ile dosya sisteminden sayılan küme karşılaştırıldı; sayısal iddialar
`docs/generated/repository_facts.md` ile çapraz kontrol edildi.

| Harita | Sonuç | Doğrulanan |
|---|---|---|
| `BACKEND_ROUTES.md` | ✅ tutarlı | 30 route dosyası + `sse_router` = `main.py`'de **31** `include_router` ✓ · `@router.<method>` sayımı **196** = generated `HTTP operations 196` ✓ · 30 route modülünün **hepsi** haritada adlandırılmış ✓ · §DUAL-TOKEN'ın "12 çağrı yeri" iddiası ampirik olarak **12** ✓ |
| `DATA_MODEL.md` | ✅ tutarlı | Head iddiası `0043_i08_registry_strategy_fks` = generated head ✓ = `alembic/versions/` içindeki en son dosya ✓ · 43 revision dosyası = generated `43 (single head)` ✓ · tablo/FK sayılarını **bilerek** generated bloğa devretmiş (doğru desen) ✓ |
| `FRONTEND_MAP.md` | ✅ tutarlı | Çapa `App.tsx:39` gerçekten `const REAL_PATHS = new Set([` ✓ · rota aralığı `:73–:346` gerçekten ilk/son `<Route>` ✓ (dosya 350 satır) · route tablosu **29 satır** = generated `Frontend router paths 29` ✓ · `pages/*.tsx` **31**, `lib/*.ts` **40** = haritanın iddiası ✓ |
| `JOBS_AND_EVENTS.md` | ✅ tutarlı | `apps/worker/actors.py` içinde **13** `@dramatiq.actor` dekoratörü; **13'ünün de** adı haritada geçiyor ✓ |
| `BACKEND_LAYERS.md` | ⚠️ içerik tam, **başlık sayıları bayat** | 32 command / 38 query / 16 job / 26 domain paketinin **tamamı** tablolarda adlandırılmış — eksik modül **yok** ✓. Ama §başlıktaki "2026-07-29 ampirik" notu `queries **37**` ve `jobs **14**` diyor; gerçek **38** ve **16**. `commands 32` ✓ ve `domain 26 paket` ✓ doğru. |

### Bulgu B1 — `BACKEND_LAYERS.md` başlık sayıları 2 kalemde bayat

Harita kendi notunda "otomatik tazelenmez, bir modül eklendiğinde satırı da ekle" diyor ve
**satırlar eklenmiş** (hiçbir modül eksik değil) — yalnız özet sayı güncellenmemiş:

- `application/queries` → yazan **37**, gerçek **38**
- `application/jobs` → yazan **14**, gerçek **16**

Etki düşük (tablolar otorite, sayı süs) ama bu tam olarak generated-facts deseninin çözdüğü
bayatlama biçimi. **Düzeltilmedi** — P1 kod/doküman değiştirmez; ayrı bir docs slice'ına ait.

### Bulgu B2 — dual-token op sayısında CLAUDE.md ↔ codemap ayrışması

- `CLAUDE.md` §Conventions: "**16** mutating op token'ı hem gövdeden hem `If-Match`'ten kabul eder."
- `docs/CODEMAPS/BACKEND_ROUTES.md` §DUAL-TOKEN: "**17** mutating op" + açık bir düzeltme notu
  ("`trash.soft_delete` O-18'de dual olunca 16 → 17 oldu; başlık satırı güncellenmemişti").

Ampirik: `reconcile_occ_tokens` route katmanında **12 çağrı yeri** (10 dosya), yardımcılara
açıldığında codemap'in saydığı 17 op. Yani **codemap düzeltilmiş taraf, `CLAUDE.md` bayat taraf**.
Kural fonksiyonunun kendisi (`shared/concurrency.py::reconcile_occ_tokens`) tek yerde ve drift
etmiyor — ayrışma yalnızca anlatı sayısında. **Düzeltilmedi** (P1 kapsamı dışı), kayda geçirildi.

---

## 4. Üretilen dosyalar

| Dosya | İçerik |
|---|---|
| `gate1_repository_facts.txt` | Gate 1 ham çıktısı |
| `gate2_openapi_export.txt` | Gate 2 ham çıktısı |
| `gate3_acceptance_semantic_scan.txt` | Gate 3 ham çıktısı (tam kapsam raporu, 200 satır) |
| `P1_repository_truth.md` | bu dosya |

## 5. P1 sonucu

**Üç kapı da exit 0.** Beş codemap'ten dördü tam tutarlı, biri (`BACKEND_LAYERS.md`) içerik olarak
tam ama iki başlık sayısı bayat. İki bayatlama bulgusu (B1, B2) kaydedildi, **düzeltilmedi**.

**P1 yeşil.** Bu, RC'nin kabul edildiği anlamına gelmez — repository'nin **kendi** hakkında yazdığı
sayıların doğru olduğu anlamına gelir. Ürün kabulünü etkileyen açık sınırlar (A-08 denetimi
yapılmadı / #514 kapalı, K-2..K-6 ölçüldü-düzeltilmedi, Alertmanager yok, 8 uncovered + 131 partial
kriter) bu kapılarla **kapanmaz** ve sonraki P adımlarına taşınır.
