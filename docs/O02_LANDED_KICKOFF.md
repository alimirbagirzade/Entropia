# O-02 landed — devam kickoff'u (hata zarfı sözleşmesi)

> Bu belge O-02 slice'ının kapanış handoff'udur. En altta **paste-ready resume prompt** var.

## Nerede duruyoruz

`main` = `5ba6c0c` (PR #400 merged). Alembic head **değişmedi**: `0035_portfolio_rules` — O-02'de
migration yok, tablo yok, endpoint yok. CI 6/6 yeşil (Backend lint/type/test 26m56s dahil).

O-02, `docs/spec/01_..._Mainboard_..._v1_1.md` §11.2 ve `docs/spec/04_..._Trading_Signal_..._v1_1.md`
§11.1'in dayattığı **makine-okur recovery zarfını** sevk edilen `ErrorBody`'ye taşıdı. Kilit gözlem
doğrulandı ve kapatıldı: `ReadinessIssue` `remediation`/`field_path`/`scope_id`'yi zaten üretiyordu,
RUN admission'ın 422'si onları düşürüyordu.

## O-02 ne bıraktı — REUSE anchor'ları (tam sembol adlarıyla)

| Sembol | Dosya | Ne için |
|---|---|---|
| `ErrorCategory` | `shared/errors.py` | 12 üyeli StrEnum; wire sözleşmesi, üye adı asla değişmez |
| `AppError.category` / `.retryable` | `shared/errors.py` | **sınıf düzeyinde** bildirilir — hata tipinin özelliği |
| `AppError.__init__(..., remediation=, suggested_action=, scope_type=, scope_id=, field_path=)` | `shared/errors.py` | **raise yerinde** pinleme; keyword-only, hepsi defaultlu |
| `ErrorBody` | `shared/responses.py` | 12 alanlı zarf; ilk 5 alan Module 19 orijinali, adları sabit |
| `_Recovery` / `_Recovery.from_app_error` | `apps/api/errors.py` | zarfı besleyen value object |
| `_STATUS_CATEGORIES` / `_status_recovery` | `apps/api/errors.py` | framework kaynaklı yanıtların (404/405/422/429) kategori türetimi |
| `_publish_error_schema` | `apps/api/errors.py` | zarfı `components.schemas`'a yayımlar → drift guard kapsamı |
| `_readiness_blocked` | `commands/backtest_run.py` | lider blocker'ın remediation/field_path/scope_id'sini zarfa yükseltir |
| `ENVELOPE_KEYS` / `LEGACY_KEYS` | `tests/contract/test_error_envelope_contract.py` | yeni hata sınıfı eklerken kopyalanacak assert seti |

## Yeni hata sınıfı eklerken (zorunlu adım)

1. Sınıfta **`category` bildir** (`ErrorCategory` üyesi). Bildirmezsen taban sınıfın kategorisi
   geçerli olur; `AppError` doğrudan türetilirse `internal` + `retryable=False` kalır.
2. Gerçekten yeniden denenebilirse `retryable = True` **ve** bir `suggested_action` token'ı ver.
   Emin değilsen bırakma — sınıflandırılmamış hata asla retryable reklamı yapmamalı.
3. Sabit bir alan/nesne kusuruysa `scope_type`/`field_path`/`remediation`'ı sınıfta bildir
   (örn. `SignalEventMappingRequiredError`); değişkense raise yerinde pinle.
4. `make openapi` çalıştır — zarf şeması `docs/openapi.json`'da, drift guard onu korur.

## Adjudication (bağlayıcı, CLAUDE.md §Conventions'ta da var)

- doc 01 §11.2 `field_issues` → sevk edilmiş **`details`**. Frontend ve contract testleri onu okuyor.
- doc 01 `suggested_action` (makine token'ı) ile doc 04 §11.1 `remediation` (insan metni)
  **iki ayrı alan** kaldı — spec örneklerinde içerikleri farklı, birleştirmek birini kaybettirirdi.

## Bilinen tuzaklar (O-02'de bedeli ödendi)

1. **Paylaşılan test DB'si + öldürülen koşu = sahte 51 hata.** `tests/integration/conftest.py`
   şemayı **her test için** drop/create ediyor; başka bir bağlantı lock tutuyorsa DDL
   `ACCESS EXCLUSIVE` lock-wait'e düşüp "across a full invocation, aborts dozens of tests".
   Tam suite koşusunu **ortada öldürme**; öldürdüysen artakalan bağlantılar temizlenmeden
   yeni tam koşu başlatma. Worktree'ye özel `TEST_DATABASE_URL` kullan.
2. **`app` fixture session-scoped** (`tests/conftest.py`). Test içinde route ekleyeceksen
   kendi `create_app()`'ini kur — yoksa probe route'ları birikir ve sonraki testler ilk
   eklenen route'a çarpar (bu tam olarak başıma geldi: beklenen 500 yerine 422).
3. **`ErrorResponse` OpenAPI'de yoktu.** Hata yanıtları endpoint'lerden değil exception
   handler'lardan çıktığı için FastAPI şemaya hiç koymuyordu; `openapi.json`'ı yenilemek
   diff üretmiyordu. `_publish_error_schema` bunu çözdü — path girdilerine dokunmadan.

## Sıradaki iş

Değişmedi: **product-owner imzası + R2 kapanışı**. Ayrıca hâlâ açık: **F-07 raw-id presentation
sweep kalıntısı** (empirik doğrulanmalı). K-serisi: K-01…K-07 landed.

**O-02'nin açtığı opsiyonel devam işi (bu slice'ta bilerek yapılmadı):** kalan ~110 hata sınıfı
taban sınıf kategorisini miras alıyor (`validation`/`authorization`/`not_found`/`conflict`).
Bunlar yanlış değil ama kaba. Sayfa taksonomisine göre incelterek (`lifecycle`,
`dependency_validation`, `data_time_validation`, `active_job`) ayrı bir sweep açılabilir.

## Paste-ready resume prompt

```
Entropia — devam. Session START protokolü: git fetch, git log --oneline origin/main -6,
gh pr list --state all ile NE MERGE OLDUĞUNU doğrula (handoff STALE-BY-DEFAULT).

Son durum: O-02 (hata zarfı recovery sözleşmesi) PR #400 ile landed, main 5ba6c0c.
Alembic head 0035_portfolio_rules (O-02'de migration yok). Oku: docs/O02_LANDED_KICKOFF.md,
docs/STAGE2_HANDOFF.md (son "landed" + "Next"), CLAUDE.md §Conventions "Hata zarfı".

Kalan blokaj: product-owner imzası — docs/implementation/v18_final_acceptance.md §4
(D-1…D-9). İmza olmadan entropia_v18_remediation_status.md'deki R2 RE-OPENING banner'ı
kalkmaz, hiçbir satır Complete olmaz. Ayrıca F-07 raw-id sweep kalıntısı empirik
doğrulanmalı.

Kod tarafına geçersen: yeni hata sınıfı eklerken ErrorCategory bildir (O02 kickoff
"Yeni hata sınıfı eklerken" bölümü) ve make openapi çalıştır. Tam integration suite'ini
koşarsan ORTADA ÖLDÜRME — artakalan Postgres bağlantıları sonraki koşuda düzinelerce
sahte hata üretir (conftest per-test drop/create + ACCESS EXCLUSIVE lock-wait).
```
