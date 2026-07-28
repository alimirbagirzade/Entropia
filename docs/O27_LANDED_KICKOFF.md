# O-27 landed — devam kickoff

> Bu dosya O-27 (AOS-03 legacy `item_kind` reddi) slice'ının kapanış handoff'udur.
> **En altta paste-ready resume prompt var** — temiz bir oturuma onu yapıştır.

## Nerede duruyoruz

- **PR [#450](https://github.com/alimirbagirzade/Entropia/pull/450)** —
  `feat/o27-invalid-item-kind-legacy-reject`, commit `9fc732a`.
  **Merge BEKLİYOR** (self-merge kapalı → kullanıcı merge eder).
- **Migration YOK.** Alembic head **`0039_backtest_run_cancellation`** sabit, `ENGINE_VERSION`
  sabit, **frontend dokunulmadı**.
- Tam kayıt: `docs/PROJECT_HISTORY.md` → "O-27 · AOS-03".
  Handoff girdisi: `docs/STAGE2_HANDOFF.md` → "O-27 — AOS-03: legacy `item_kind` etiketleri…".

## Slice'ın geride bıraktığı reuse anchor'ları (tam sembol adlarıyla)

| Sembol | Dosya | Ne işe yarar |
|---|---|---|
| `ensure_mainboard_item_kind(value, *, field=...)` | `backend/src/entropia/domain/mainboard/item_kind.py` | Client'tan gelen **her** kind string'inin tek kapısı. Yeni bir yüzey eklersen enum'u kendin çağırma — buradan geçir, yoksa AOS-03 o yüzeyde delinir. |
| `LEGACY_ITEM_KIND_ALIASES` | aynı dosya | `{signal_package → TRADING_SIGNAL, trade_log_package → TRADE_LOG}`. **Sadece reddetmek için** var; kastettiği kind'a çevirmek AOS-03'ün "hiçbir şey yaratılmaz" yarısını bozar. |
| `InvalidItemKindError` | `backend/src/entropia/shared/errors.py` | `INVALID_ITEM_KIND`, 422, `category=validation`, `retryable=false`, sınıfta pinli `suggested_action`/`remediation`. |
| `_coerce_item_kind(value, *, field=...)` | `application/commands/mainboard.py` | Guard'a delege eden ince sarmalayıcı. `field` zarfın `field_path`'ine ve `details[0].field`'ine düşer (`kind` / `object_kind` / `item_kind`). |
| `test_package_guard_still_faces_the_other_way` | `backend/tests/unit/test_mainboard_item_kind.py` | İki legacy sözlüğünün **kesişmediğini** pinler. Yeni bir legacy etiket eklerken bu testi oku — yanlış guard'a koymanı engeller. |
| `_DummySession` + `_override(app)` deseni | `backend/tests/contract/test_mainboard_invalid_item_kind_contract.py` | DB'ye dokunmadan reddedilen yolları contract seviyesinde sürmenin yolu. Yeni bir "hiçbir şey yaratılmadı" kanıtı yazacaksan bunu kopyala. |

## Dokunulmaması gerekenler (bu slice'ın sınırı)

- **`domain/package/kind.py::LEGACY_PACKAGE_TYPES` KALDIRILMAZ.** Ters yöne bakar
  (TS-01/TL-01: `trading_signal`/`trade_log`'u `PackageKind`'ın dışında tutar). İkisi farklı
  yön, ikisi de gerekli.
- **`MAINBOARD_ITEM_KIND_MISMATCH` iki koda çökertilmez.** `strategy` (external-only opener'da)
  ve bilinmeyen kind'lar hâlâ CR-01 kodunu döner — contract testi bunu aynı dosyada pinliyor.
- **Attach'ta hata sırası** değişmedi: workspace/root/revision çözümü kind doğrulamasından önce
  koşar. Erken doğrulama eklemek mevcut öncelik sözleşmesini değiştirir.
- Zarf alan adları (`code, message, details, request_id, correlation_id, category, retryable,
  suggested_action, remediation, scope_type, scope_id, field_path`) — O-02 adjudication'ı.

## Buradan mantıklı devam adayları (hiçbiri başlatılmadı)

1. **O-03 kalıntısı:** `KNOWN_UNRAISED` içindeki 5 ölü error sınıfı (`RoleContextStaleError`,
   `ValidationAlreadyRunning`, `ServiceUnavailableError`, `ArtifactNotAvailableError`,
   `HypothesisArtifactNotFoundError`) — ya gerçek bir raise yolu ya da silme.
2. **Doc 03 §11'in geniş okuması:** "item_kind must be exactly trading_signal or trade_log"
   satırı AOS sayfası bağlamında `strategy`'yi de `INVALID_ITEM_KIND` yapmayı okumaya açık.
   O-27 bunu **yapmadı** (kayıtlı yorum sınırı) — istenirse ayrı bir slice.
3. **`INVALID_ITEM_KIND`'ı OpenAPI'de belgelemek** — zarf `ErrorResponse` altında yayımlanıyor
   ama kodlar enumerate edilmiyor; enumerate etmek drift guard snapshot'ı yenilemeyi ister.
4. **F-07 §4.4** — 4 yüzey backend display-DTO bekliyor (`v18_visual_traceability.md §4.4`).
5. **PO imzası + R2 kapanışı** — proje düzeyindeki asıl blokaj (aşağıya bak).

## Ortam tuzağı (her oturumda geçerli)

Paralel worktree oturumları paylaşılan `entropia_test` DB'sini ezer (`conftest` her testte
`drop_all`/`create_all`). **`TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan:**

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_<slug>_test"
```

O-27'de bu işe yaradı: tam suite **tek koşuda 2538 passed / 43dk39sn** ile tamamlandı (önceki
slice'larda lokal tam suite tamamlanamıyordu). Koşuyu **ortada öldürme**, koşarken `uv sync`
çalıştırma, ve `pytest … | tail` **kullanma** — exit code `tail`'in olur, pytest'in değil.
Çıktıyı dosyaya yaz, `$?`'i ayrı oku.

---

## Paste-ready resume prompt

```
Entropia — O-27 (AOS-03 legacy item_kind reddi) landed, PR #450 merge bekliyor.
Session START protokolünü uygula: git fetch + git log --oneline origin/main -6 +
gh pr list --state all → #450'un merge olup olmadığını ÖNCE doğrula (handoff STALE-BY-DEFAULT).

Oku (otorite sırası): docs/O27_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md ("O-27 … landed" +
"Next") → docs/PROJECT_HISTORY.md "O-27 · AOS-03" (ayrıntı gerekirse, hedefli oku).

Durum: O-27 migration eklemez (main head 0039_backtest_run_cancellation), ENGINE_VERSION sabit,
frontend dokunulmadı. item_kind=signal_package / trade_log_package artık üç yüzeyde de
(chooser opener, POST /work-objects, attach) 422 INVALID_ITEM_KIND ile reddediliyor; tek kapı
domain/mainboard/item_kind.py::ensure_mainboard_item_kind. Alias'lar SADECE reddedilmek için
tanınır, kastettikleri kind'a asla çevrilmez.

Dokunma: domain/package/kind.py::LEGACY_PACKAGE_TYPES (ters yöne bakan TS-01/TL-01 guard'ı,
KALDIRMA); MAINBOARD_ITEM_KIND_MISMATCH (strategy + bilinmeyen kind hâlâ onu döner, contract'ta
pinli); attach'taki hata sırası; O-02 zarf alan adları.

Kayıtlı sapma: spec §8.3 "400" der, §11 taksonomisi type/schema validation der → 422 seçildi.
Kayıtlı yorum sınırı: doc 03 §11'in geniş okuması strategy'yi de INVALID_ITEM_KIND yapardı;
O-27 bunu yapmadı.

Proje düzeyindeki asıl blokaj değişmedi: product-owner imzası —
docs/implementation/v18_final_acceptance.md §4 (D-1…D-9). İmza olmadan R2 RE-OPENING banner'ı
kalkmaz. Açık: F-07 §4.4 (4 yüzey display-DTO), O-03 kalıntısı (5 ölü error sınıfı,
KNOWN_UNRAISED), Round-3 backlog (S5 a/b/c/d + S-L1…S-L6).

Backend verify: cd backend && uv run ruff check . && uv run ruff format --check . &&
uv run mypy src && uv run pytest --no-cov -q  (TEST_DATABASE_URL ile İZOLE DB kullan; çıktıyı
dosyaya yaz, tail'e pipe etme).
```
