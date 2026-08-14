---
name: entropia-canonical-rules
description: >
  Entropia'nın PAZARLIKSIZ, adjudicated backend invariant'ları: hata zarfı
  (O-02), OCC dual-token (O-12), Idempotency-Key (O-13), purge 202 gövdesi
  (O-30), upload dosya-tipi kapısı (K-07), trash tip kataloğu (K-06), typed
  response kuralı ve katman deseni. Backend'de endpoint / komut / hata sınıfı /
  soft-delete / upload / mutating op eklerken ya da değiştirirken, "bu alanı
  sadeleştirebilir miyim" diye sorarken, code-review bulgusu bu alanlara
  dokunduğunda oku. Bunlar tekrar gibi görünür ama karara bağlanmıştır.
license: MIT
---

# Entropia canonical rules — adjudicated invariant'lar

Bu dosyadaki her kural, **iki spec arasındaki bir çelişkinin insan eliyle karara
bağlanmış** hâlidir. "Gereksiz tekrar", "iki alan aynı şeyi söylüyor", "bunu tek
yere indirelim" refleksi burada **yanlıştır** — biri silinince bir sözleşme
kaybolur. Sadeleştirmeden önce bu dosyayı oku; hâlâ gereksiz görünüyorsa
**kullanıcıya sor**, kendi başına kaldırma.

Otorite sırası: `docs/spec/NN_*` → `CLAUDE.md` → bu dosya (özet + işaretçi).

---

## O-02 — Hata zarfı = tek şekil

Her HTTP hatası `shared/responses.py::ErrorBody`:

- **Module 19 orijinali, isimleri ASLA değişmez:**
  `code, message, details, request_id, correlation_id`
- **Recovery bloğu:** `category, retryable, suggested_action, remediation,
  scope_type, scope_id, field_path`

Karara bağlanan iki isim çatışması:

| Spec | Bizde |
|---|---|
| doc 01 §11.2 `field_issues` | = sevk edilmiş `details` (aynı anlam, **sevk edilen ad kazanır**) |
| doc 01 `suggested_action` vs doc 04 §11.1 `remediation` | **İKİ AYRI ALAN kalır** — ilki makine token'ı (`"rerun_ready_check"`), ikincisi insan metni. Birleştirmek birini kaybettirir. |

Kurallar:

- `category` / `retryable` hata **sınıfında** bildirilir
  (`shared/errors.py::ErrorCategory`).
- `scope_type` / `scope_id` / `field_path` / `remediation` hem sınıfta hem
  **raise yerinde** pinlenebilir.
- **Sınıflandırılmamış hata asla `retryable=true` reklamı yapmaz.**
- Readiness blocker'ında lider blocker'ın `remediation`/`field_path`/`scope_id`'si
  zarfa yükseltilir (`commands/backtest_run.py::_readiness_blocked`); `details`
  yine tüm issue'ları taşır.
- Yeni hata sınıfı eklerken **kategorisini bildir**. Zarf
  `docs/openapi.json` → `components.schemas.ErrorResponse` altında yayımlanır;
  drift guard onu korur.

---

## O-12 — OCC dual-token = TEK kural, çelişki 409

16 mutating op versiyon token'ını hem gövdeden (`expected_*`) hem `If-Match`'ten
kabul eder. Bunlar **tek değerin iki yazımıdır**, iki bağımsız önkoşul değil
(doc 15 §11, doc 20 §14 "Do not treat them as interchangeable fields", doc 21 §7).

Tek yer: `shared/concurrency.py::reconcile_occ_tokens`

- İkisi de verilmiş ve **ÇELİŞİYORSA → 409 `OCC_TOKEN_CONFLICT`**
  (`shared/errors.py::OccTokenConflictError`, `category=concurrency_or_preflight`,
  **`retryable=false`** — aynı çelişkiyi tekrar göndermek hep aynı hatayı verir;
  `details` iki değeri de yankılar).
- Biri verilmişse **o kazanır**; anlaşıyorlarsa gövde geçer →
  **tek-token çağıranlar (frontend dahil) etkilenmez.**
- Yeni dual-token uç eklerken kuralı route'a **KOPYALAMA**, bu fonksiyondan geçir.
- `rationale.revise_family` **bilerek dışarıda**: oradaki `If-Match` atıldı ve
  farklı eksendi (ETag = row_version, token = revision id) → parametre kaldırıldı.

Tam liste: `docs/CODEMAPS/BACKEND_ROUTES.md` §DUAL-TOKEN.

---

## O-13 — Idempotency-Key = `run_idempotent`, yeni altyapı YOK

Kalıcı satır yazan **her** mutating op `Idempotency-Key` okumalı ve komut
gövdesini `application/idempotency.py::run_idempotent` ile sarmalı.

- **Fingerprint'e komutun KENDİSİNİN değiştirdiği durumu koyma** (head pointer,
  `row_version`) — retry farklı hash'lenir ve sonsuza dek 409 verir. Girdileri
  hash'le: `op`, id'ler, payload, çağıranın gönderdiği `expected_*`.
- ORM döndüren komutlarda `_op()` JSON `response_ref` döner; satır o referanstan
  **yeniden okunur** → replay aynı kaynağı, aynı tipte döner.
- Idempotency-Key okumayan 16 op **gerekçelidir** (salt-okuma POST, oturum
  işlemi, OCC korumalı soft-delete, geçici opener). Yeni bir istisna eklemeden
  önce gerekçeyi yaz.

---

## O-30 — Purge 202 gövdesi = iki ad, tek değer

Doc 20 kendi içinde çelişir: §7 literali `root_lifecycle_state: 'soft_deleted'`,
§9.2 state machine'i `soft_deleted --purge request--> PURGE_PENDING`.

**Adjudicated:** DEĞER'de §9.2 kanonik (satır gerçekten `purge_pending` olur;
`PURGE_PENDING -> restore` yasaktır — `'soft_deleted'` reklamı "restore hâlâ
açık" yalanı olurdu). AD'da §4/§7 kanonik.

Bu yüzden `commands/deletion.py::request_purge` gövdesi **`deletion_state` ve
`root_lifecycle_state` anahtarlarının İKİSİNİ birden** `"purge_pending"`
değeriyle döndürür. Biri kaldırılmaz, ikisi asla ayrışmaz.

- Gövde `run_idempotent` zarfında birebir saklanır → replay aynı şekli verir.
- `frontend/src/lib/trash.ts::PurgeResult` bu sözlüğü **verbatim** aynalar.
- Gövde `routes/trash.py::PurgeAcceptedResponse` ile **şemada yayımlanır**;
  `test_purge_202_publishes_both_state_field_names` bunu kilitler.
- O-30 ÖNCESİ yazılmış Idempotency-Key kayıtları bu alanı taşımaz →
  `request_purge` replay'de `deletion_state`'ten **backfill** eder
  (**kopyalayarak** — `response_ref` JSON kolonu mutate EDİLMEZ).

---

## K-07 — Upload dosya-tipi kapısı = fail-closed

Ortak kapı: `domain/importing/source_file.py::assert_supported_source_file`

- **filename yok/boş → RED.** "Atla" seçeneği yoktur.
- Uzantı iddiası **içerik sniff'i** ile desteklenir.
- **Dört komut yüzeyi de** bu tek kapıyı çağırır: `trade_log`,
  `trading_signal`, `market_data`, `research_data`. Yeni bir upload yüzeyi
  eklerken kendi koduna değil, buraya bağla.

Hata kodu **sayfa taksonomisine göre ayrışır** (adjudicated — aynı kusuru
anlatırlar, her sayfanın kendi §-taksonomisi otoritedir):

| Sayfa | Kod | Spec |
|---|---|---|
| Trade Log | `UNSUPPORTED_SOURCE_FILE_TYPE` | doc 05 §12.1 |
| Trading Signal | `FILE_TYPE_NOT_ALLOWED` | doc 04 §11 |
| Create Package baseline | `UNSUPPORTED_SOURCE_FILE_TYPE` | doc 06 §8.3 |
| Market Data | `MARKET_DATA_FILE_TYPE_NOT_ALLOWED` | doc 11 |
| Research Data | `RESEARCH_DATA_FILE_TYPE_NOT_ALLOWED` | doc 12 |

---

## K-06 — Trash tip kataloğu = yazılmış yol

`domain/trash/page.py::TRASH_OBJECT_LOCATIONS` içindeki **her** tipin
soft-delete yolu `trash_repo.add_trash_entry` **yazmak zorundadır** — aksi hâlde
nesne aktif projeksiyondan çıkar ama Admin Trash'e hiç ulaşmaz; restore/purge'ün
dayanacağı entry olmaz.

- Registry kökü olmayan tipler (`backtest_result`, `manual_document`,
  `hypothesis_artifact`) kendi satırlarındaki `deletion_state` üzerinden yürür →
  `commands/deletion.py` + `jobs/purge.py` + `queries/trash.py` içinde
  **`entity_type` dalı**. Yeni tip eklerken **üçünü birden** ekle.
- Agent artifact: soft delete owner-Agent/Admin (doc 20 §11); restore/purge
  **Admin-only**; purge preflight **canlı source task**'ta `PURGE_NOT_ELIGIBLE`
  verir (doc 20 §10).

---

## Typed response kuralı

Mutating route gövdesi **typed model** olarak bildirilir. `dict[str, Any]`
dönüşü drift guard'ı yeşil tutarken sözleşmeyi OpenAPI şemasından **gizler** —
bu O-30'da gerçekten oldu.

---

## Katman deseni — kopyalanır, birleştirilmez

`application/commands/` · `application/queries/` · `domain/<alan>/` ·
`apps/api` ayrımı korunur. Önceki slice'ın desenini aynala:

- modül seviyesi **async** command
- **tek transaction, commit yok**
- `run_idempotent` sarmalı
- `session.refresh(..., with_for_update=True)`
- yan etkiler `_audit_and_outbox` üzerinden

"Daha az dosya" gerekçesiyle bu katmanlar birleştirilmez.

---

## Kapsam dışı (bilerek — eksik sanıp ekleme)

- retention auto-purge (doc 20 §16 — "Production V1'de kapalı")
- LLM generation (Future-Dev)
- Graphic View renderer (doc 22 — V18 statik placeholder kalır)
- `SHARED_ALLOCATION_STATUS = future_dev` → containment KAPALI
