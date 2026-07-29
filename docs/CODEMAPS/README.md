# CODEMAPS — Entropia mimari haritaları

Sıkıştırılmış, tablo ağırlıklı referans haritalar. Her biri tek ekranda taranabilir.
Kaynak: repo üzerinde **gözlemlenen** kod (route imzaları, model tanımları, aktör
dekoratörleri, frontend import/query-key'leri). Emin olunamayan yerlerde `?` var.

> **Son tazeleme: 2026-07-29** — `origin/main` @ `0995c37` (denetim sonrası dalga: O-serisi +
> I15A/I15B slice'ları + audit-doc19). Aşağıdaki sayıların **hepsi** o gün repodan sayıldı:
>
> | Olgu | Değer | Nasıl doğrulanır |
> |---|---|---|
> | Alembic head | **`0040_export_type_agent_pine`** (40 migration, tek head) | `ls backend/alembic/versions/*.py \| wc -l` |
> | HTTP endpoint | **196** (openapi operation sayısıyla birebir) | `BACKEND_ROUTES.md` başındaki tek satırlık python |
> | Postgres tablosu | **102** (30 model dosyası) | `grep -rh __tablename__ …/models/ \| sort -u \| wc -l` |
> | `ForeignKey(...)` bildirimi | **135** (25 dosyada) | `grep -rh "ForeignKey(" …/models/ \| wc -l` |
> | audit `event_kind` | **126 düz literal** (+ dolaylı yazımlar) | `JOBS_AND_EVENTS.md` §Audit kataloğu |
> | Frontend | **31 sayfa**, **40 `lib/*.ts`** | `ls frontend/src/pages/*.tsx \| wc -l` |

---

## Haritalar

| Dosya | Ne işe yarar | Ne zaman okunur |
|---|---|---|
| [`BACKEND_ROUTES.md`](BACKEND_ROUTES.md) | Her HTTP endpoint: path, route fonksiyonu, çağırdığı command/query, **OCC token biçimi**, Idempotency-Key, rol kapısı | Yeni endpoint bağlarken, frontend'e bir yüzey bağlarken, OCC/Idempotency sözleşmesini doğrularken |
| [`BACKEND_LAYERS.md`](BACKEND_LAYERS.md) | `application/commands`, `application/queries`, `application/jobs` ve `domain/` modül haritası — dosya başına tek satır | "Bu iş nerede yazılıyor?" sorusunda; katman sınırını (pure domain / I/O) ararken |
| [`DATA_MODEL.md`](DATA_MODEL.md) | Postgres tabloları: amaç, ana FK'ler, soft-delete, `row_version`/OCC kolonu + alembic head | Migration yazarken, OCC token'ının nereden geldiğini bulurken, silme semantiğini kontrol ederken |
| [`FRONTEND_MAP.md`](FRONTEND_MAP.md) | Sayfa → route path → `lib/*.ts` → react-query key prefix → backend endpoint grubu + `EVENT_QUERY_KEYS` | Frontend sayfası eklerken/değiştirirken, invalidation zincirini izlerken |
| [`JOBS_AND_EVENTS.md`](JOBS_AND_EVENTS.md) | dramatiq aktörleri, kuyruklar, scheduler sweep'leri, outbox→SSE fan-out, SSE taksonomisi | Async iş eklerken, "değişiklik neden UI'a düşmüyor?" derken, operator recovery'de |

---

## Okuma sırası (yeni gelen için)

1. `DATA_MODEL.md` — sistemin kalıcı gerçeği (root/revision omurgası).
2. `BACKEND_LAYERS.md` — kodun nasıl bölündüğü.
3. `BACKEND_ROUTES.md` — dış sözleşme (OCC + Idempotency burada).
4. `FRONTEND_MAP.md` — o sözleşmenin tüketicisi.
5. `JOBS_AND_EVENTS.md` — senkron olmayan taraf.

## Değişiklik yaparken

- Yeni endpoint → `BACKEND_ROUTES.md` satırı ekle (OCC biçimini **imzadan** doğrula, tahmin etme).
- Yeni tablo/migration → `DATA_MODEL.md` + head revision adını güncelle.
- Yeni sayfa/hook → `FRONTEND_MAP.md` satırı + query key prefix'i.
- Yeni aktör/kuyruk → `JOBS_AND_EVENTS.md`.

## Konvansiyonlar (bu haritalarda)

- `If-Match "rv-N"` — ETag taşıyıcı, `shared/concurrency.row_version_from_if_match` ile parse edilir.
- `body expected_*` — OCC token'ı gövdede; çoğu route'ta **body header'ı yener**.
- `X-*-Version` — düz integer header (ETag DEĞİL): `X-Registry-Version`, `X-Request-Version`.
- `yok` — imzada hiçbir OCC parametresi gözlenmedi (create/pure-read yolları).
- `?` — imzadan kesin çıkarılamadı; kodu aç ve doğrula.
- Rol kapısı sütunu **route katmanındaki** açık `require_*` çağrısını gösterir. Boşsa yetki
  kontrolü command/query katmanındadır (UI görünürlüğü asla yetki değildir).
