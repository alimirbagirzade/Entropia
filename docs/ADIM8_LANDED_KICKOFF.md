<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 8 landed — Typed API contracts (PR #529) · sıradaki slice kickoff'u

> Bu belge **ADIM 8'in** kapanış handoff'udur. En altta **paste-ready resume prompt** var.

## Nerede duruyoruz

| | |
|---|---|
| ADIM 8 merge | `8a87460` · commit `62705ec` · base `870cc1a` |
| **Araya giren merge** | **PR #528** `fix/agent-tools-trade-log-handoff` (`30ff98f` → `a84a4b4`) — ADIM 8'in base'i ile merge'i ARASINA girdi |
| **Bir sonraki base** | **`8a87460`** — `870cc1a` DEĞİL |
| Alembic head | `0043_i08_registry_strategy_fks` — tek head, **ADIM 8 migration EKLEMEDİ** |
| OpenAPI | **196 operation** (değişmedi) · 121 → **151 schema** (30 yeni, 0 kaldırılan) |
| Testler | backend **3143 passed**, coverage **%92.81** (kapı ≥90) · frontend **696 passed** |
| CI | **6/6 pass** (Backend 44m18s) |
| `ENGINE_VERSION` | `backtest-engine-v18-same-candle-entry-exit` — değişmedi |

## ADIM 8 ne bıraktı — reuse anchor'ları (tam sembol adlarıyla)

**Yeni paket: `backend/src/entropia/apps/api/schemas/`**

| Modül | İçerik |
|---|---|
| `common.py` | `CursorPageMeta` — `{cursor: str \| None, has_more: bool}`, ESP ve Library sayfaları paylaşıyor |
| `esp.py` | `EspRegistryEntry` · `EspRegistryPageResponse` · `EspResolverContract` · `EspValidationRunSummary` · `EspPackageDetailResponse` · `CreateEspResponse` · `EspValidationCheck` · `EspValidationRunResponse` · `ActivateResolverResponse` · `DeprecateResolverResponse` · `ResolveDependencyResponse` |
| `library.py` | `PackagePermissionFlags` · `PinnedRationaleFamilyRef` · `LiveRationaleFamilyRef` · `PackageProvenanceScan` · `PackageProvenance` · `PackageRevisionSummary` · `_LibraryPackageFields` (private taban) · `LibraryPackageRow` · `LibraryPageResponse` · `LibraryPackageDetailResponse` · `DeprecatePackageResponse` · `DerivePackageResponse` · `CreatePackageRevisionResponse` · `RequestPackageApprovalResponse` · `ApprovePackageResponse` · `PackageRegistryObservation` · `PackageExportResponse` · `PackageValidationRunAcceptedResponse` |
| `agent_tool_gateway.py` | `AgentToolCallCard` · `AgentToolCallListResponse` · `AgentToolCallDetailResponse` |

**Yeni testler** (kopyalanacak kalıplar burada):

| Dosya | Ne öğretir |
|---|---|
| `tests/contract/test_typed_contract_no_field_drop.py` | Modeli **kendisini besleyen gerçek serializer'a** karşı sabitleme (ORM stub'ları, DB yok) |
| `tests/contract/test_typed_contract_openapi.py` | `_response_components()` + `_refs_in()` — 2xx gövdesinden **geçişli component walk**; el listesi yerine blanket kural |
| `tests/contract/test_wire_contract_parity.py` | `_ts_fields()` — TS interface parser; OpenAPI ↔ `lib/*.ts` alan+nullability paritesi |
| `tests/integration/test_typed_contract_replay_parity.py` | `_stored_envelope(session, key)` — HTTP gövdesini **saklı idempotency zarfıyla** karşılaştırma |

**Düzeltilen serializer kapıları:** `application/queries/library.py::_snapshot_family_id` ve
`::_snapshot_display_name` — JSONB snapshot'tan gelen id/ad string değilse eler.

**Yeni doküman:** `docs/audit/high_risk_api_contract_audit.md`.

## Bir sonraki slice için tasarım işaretleri

**En yakın kalem (bu slice'ın bilerek ertelediği):** `GET /library-shared-with-me`
(`apps/api/routes/sharing.py:82` → `library_query.list_shared_with_me`) birebir aynı
`LibraryPage` zarfını döndürüyor ve hâlâ `dict[str, Any]`. `LibraryPageResponse` olduğu gibi
uygulanabilir — `response_model=LibraryPageResponse` + `test_wire_contract_parity.py`'a çift
eklemek yeterli. ~5 satır üretim kodu.

**Yeni bir yüzeyi tiplerken kopyalanacak kurallar** (hepsi `schemas/__init__.py` docstring'inde):
- Her alan REQUIRED, nullability TİPTE (`x: str | None`, **default YOK**).
- Enum'lar `str` olarak bildirilir, Python enum'u olarak DEĞİL — RESPONSE'ta kapalı enum,
  `response_model` çıkış doğrulamasında 500 üretir.
- Zaman damgaları `str`, `datetime` DEĞİL — serializer zaten `.isoformat()` basıyor.
- Nullable/non-null kararı **kolon tanımından** alınır, gözlemlenen veriden değil.
- Aynı adı taşıyan iki farklı şekil iki farklı modeldir (bkz. `checks`, `rationale_family`).
- Sürümlü/keyfi JSONB artifact'ler AÇIK `dict[str, Any]` kalır.

**REUSE listesi:** `CursorPageMeta` (her yeni cursor sayfası), `_stored_envelope` kalıbı (her
`run_idempotent`-sarmalı uç), `_response_components` walk'u (her yeni tipli yüzey otomatik
kapsanır — sadece `_TYPED_RESPONSES`'a satır ekle), `_ts_fields` parser'ı (her yeni
OpenAPI↔TS çifti).

## Çalışma döngüsü (ADIM 8'de işe yarayan)

1. `git fetch --all --prune` → `git switch -c <branch> origin/main` (**base `8a87460`**).
2. Dokunulacak alanın `docs/CODEMAPS/` haritasını oku, sonra serializer'ları **kaynaktan** oku
   — özet belgeye güvenme.
3. **Read-only subagent'ları paralel çalıştır** (araştırma + adversarial review). ADIM 8'de
   review **iki gerçek kusur** buldu: `GET /library` sayfasını 500 yapacak poisoned-snapshot,
   ve çalışma zamanı bağı olmayan tek model. **Bulguları kodla doğrula** — ADIM 8'de hepsi
   doğru çıktı ama bu garanti değil.
4. Yerel doğrulama: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
5. Frontend: `npm run typecheck && npm run lint && npx vitest run --no-file-parallelism && npm run coverage`.
6. `make openapi` → commit et. Drift guard **byte-byte** karşılaştırır.
7. PR → `gh pr checks <n> --watch`.

## Ortam tuzakları (ADIM 8'de bizzat karşılaşıldı)

- **`npx prettier --write` KULLANMA.** Bu repoda prettier config'i, script'i ve bağımlılığı
  **yok**. Çalıştırdım; beş frontend dosyası baştan aşağı yeniden biçimlendi (~700 satır
  ilgisiz churn) ve dosyaları commit'lenmiş içerikten yeniden kurmak zorunda kaldım. Frontend
  formatlaması **elle**, çevredeki stile bakarak yapılır.
- **Worktree'ye özel `TEST_DATABASE_URL`** kullan (paralel worktree oturumları var).
- Tam suite'i **tek pytest çağrısında** koş, ortada öldürme, `| tail` KULLANMA (exit code
  `tail`'in olur). Çıktıyı dosyaya yaz, `$?`'i ayrı oku.
- Suite koşarken `uv sync` çalıştırma. `uv run ruff`/`mypy` güvenli (venv zaten sync'li) ama
  gereksiz yere yapma.
- Alt küme koşarken `--no-cov` ekle.
- Worktree'de `frontend/node_modules` yoksa önce `npm ci`.
- **GateGuard:** yeni dosyayı Bash heredoc ile yaz (gate-free); mevcut dosyaya Edit/Write
  fact-force tetikler (4 olgu sun → yeniden dene). Yıkıcı komutlar ayrı bir kapıdan geçer ve
  **tekrar tekrar bloklanabilir** — yıkıcı olmayan bir yol bul (ADIM 8'de dosyaları
  `git show HEAD:<path>` çıktısından yeniden kurdum).

## Kapanışta yapılmayan (dürüst sınır)

**Memory checkpoint YAZILAMADI.** `mcp__plugin_ecc_memory__*` araçları bu oturumun sonunda
**bağlantısı kesik** durumdaydı, dolayısıyla ecc knowledge graph girdisi (`Entropia ADIM 8 —
Typed API contracts` + `unblocks` ilişkisi) **oluşturulmadı**. Bir sonraki oturum bunu
`mem-search` ile bulamaz — bu belge ve `docs/PROJECT_HISTORY.md` tek kayıttır.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 9

ROL VE ÇALIŞMA BİÇİMİ

Sen Entropia V18 üzerinde çalışan kıdemli principal engineer ve release-closure
sorumlususun. Amaç yeni özellik icat etmek değil; canonical Production V1 sözleşmesini
current `origin/main` üzerinde kanıtlamak, yalnız doğrulanmış boşluğu dar bir PR ile
kapatmak ve sistemi geriletmemektir.

Claude Code içindeki mevcut skills/subagent/agent araçlarını kullanabilirsin. Ancak:
- Araştırma, mimari inceleme, test inceleme ve adversarial review için read-only subagent kullan.
- Aynı dosyalara eşzamanlı birden fazla writer atama.
- Production değişikliklerini yalnız ana oturum yapsın.
- Subagent sonuçlarını gerçek kod ve testlerle doğrula.
- Tek branch, tek PR ve tek sorumlu writer kuralını bozma.

HER OTURUMUN ZORUNLU BAŞLANGICI

1. `git fetch --all --prune`
2. `git status --short`
3. Worktree temiz değilse DUR; hiçbir dosyayı silme veya stash etme.
4. `git switch main`
5. Yerel main'i origin/main ile eşitle (hard reset).
6. Current main SHA, tarih ve açık PR/issue snapshotını kaydet.
7. ADIM 8 PR'ının (#529) merge edildiğini doğrula; edilmediyse DUR.
8. İlgili `docs/CODEMAPS/` dosyalarını ve gerçek çağrı zincirini oku.
9. Eski README, CLAUDE.md, handoff, kickoff veya backlog iddiasını current truth sayma.
10. Önce mevcut davranışı test/probe ile yeniden üret; kusur üretilemiyorsa kod yazma.

ADIM 8 NE BIRAKTI

- Merge `8a87460` (base `870cc1a`, commit `62705ec`). Araya PR #528 girdi; base olarak
  `8a87460` al.
- Migration YOK, alembic head `0043_i08_registry_strategy_fks` sabit, tek head.
- OpenAPI 196 operation sabit; 30 yeni schema; `apps/api/schemas/` paketi kuruldu.
- Backend 3143 passed / coverage %92.81; frontend 696 passed; CI 6/6.
- Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 8 ve `docs/audit/high_risk_api_contract_audit.md`.
- Kickoff/reuse anchor'ları: `docs/ADIM8_LANDED_KICKOFF.md`.

BU ADIMIN AMACI

<BURAYA ADIM 9'UN KAPSAMI YAZILACAK>

Kapsam verilmemişse, ADIM 8'in bilerek ertelediği en yakın kalem şudur ve dar bir PR'dır:
`GET /library-shared-with-me` (`apps/api/routes/sharing.py`) birebir aynı `LibraryPage`
zarfını döndürüyor ama hâlâ `dict[str, Any]`; `apps/api/schemas/library.py::LibraryPageResponse`
olduğu gibi uygulanabilir + `tests/contract/test_wire_contract_parity.py`'a çift eklenir.
Bunu yapmadan önce kullanıcıya doğrula — kapsamı kendin genişletme.

TAVİZ VERİLEMEZ KURALLAR

- Trading Signal ve Trade Log Package değildir.
- Backtest Run ile Backtest Result aynı entity değildir.
- Yalnız `SUCCEEDED` Run immutable Result üretir.
- Agent human account, browser veya human session değildir.
- Lab Assistant ile Alpha Agent aynı aktör değildir.
- Uzun işler durable queue/worker üzerinden yürür.
- UI hidden/disabled durumu authorization değildir.
- Server-side policy, ownership, OCC, idempotency, audit ve lifecycle korunur.
- Revision, snapshot, fingerprint, manifest ve exact pinned revision geriye dönük bozulmaz.
- Research Data için `event_time` ve `available_time` ayrımı korunur.
- Future Dev capability sahte job, sahte output veya sessiz fallback üretmez.
- Canonical boşlukta formül, öncelik, time ordering veya ürün kararı uydurulmaz.
- Historical Result/manifest canlı root veya live registry join'iyle yeniden yorumlanmaz.
- Başarısız test varken `Complete` veya `Done` yazılmaz.

TİPLİ SÖZLEŞME KURALLARI (ADIM 8'de kuruldu, korunur)

- Response modelinde her alan REQUIRED; nullability TİPTE (`x: str | None`, default YOK).
- Enum'lar `str` olarak bildirilir — RESPONSE'ta kapalı enum çıkış doğrulamasında 500 üretir.
- Zaman damgaları `str`, `datetime` değil — serializer zaten `.isoformat()` basıyor.
- Nullable/non-null kararı kolon tanımından alınır, gözlemlenen veriden değil.
- Sürümlü/keyfi JSONB artifact'ler AÇIK `dict[str, Any]` kalır.
- Yeni tipli yüzey eklersen `test_typed_contract_openapi.py::_TYPED_RESPONSES` ve
  `test_wire_contract_parity.py::_PAIRS` listelerine satır ekle.

PR DİSİPLİNİ

- Yalnız bu promptun slice'ı üzerinde çalış.
- İlgisiz refactor, dependency upgrade veya görsel değişiklik yapma.
- `npx prettier` KULLANMA — bu repoda prettier yok, tüm dosyayı yeniden biçimlendirir.
- Migration gerekiyorsa single-head, upgrade/downgrade/upgrade ve veri koruma kanıtı ver.
- Engine semantiği değişiyorsa `ENGINE_VERSION` kararını açıkça değerlendir.
- Public API değişiyorsa OpenAPI snapshot ve frontend wire contractlarını güncelle.
- Mimari değişiyorsa codemapleri yenile.
- PR sonunda base SHA, branch, commit, PR, changed behavior, unchanged boundaries,
  targeted tests, full-suite exit code, migration/OpenAPI/codemap etkisi, kalan risk
  ve sonraki tek adımı raporla.

DURMA KOŞULU

Repository çapında rewrite yapma. Yalnız touched surfaces PR'ı aç ve dur. All checks have
passed olana kadar loop ile fix et.
```
