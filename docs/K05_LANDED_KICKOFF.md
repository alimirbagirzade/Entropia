<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# K-05 landed — devam kickoff'u (V18-R3 fail-closed sweep)

> Bu doc bir **slice kapanış handoff'u**dur. Otoritesi: `docs/STAGE2_HANDOFF.md` §Next >
> `docs/STAGE_R3_KICKOFF.md` > bu doc. Aşağıdaki her değer **STALE-BY-DEFAULT** —
> `git fetch && git log --oneline origin/main -6 && gh pr list --state all` ile doğrula.

## Nerede duruyoruz

- `main` HEAD: **`604f8b4`** (PR #388, K-07). K-05 = PR **#387** / `e2b75cc`.
- alembic head: **`0035_portfolio_rules`** — K-05'te migration YOK.
- `SOURCE_SCANNER_VERSION` = **`source-lexer-2.0`** (K-05'te bump edildi).
- `LANGUAGE_DETECTOR_VERSION` = **`language-detector-1.0`** (yeni).
- `ENGINE_VERSION` = `backtest-engine-v18-capability-matrix` (F-05'ten, K-05 dokunmadı).

## K-05 ne bıraktı — REUSE anchor'ları (tam sembol adlarıyla)

| Sembol | Dosya | Ne işe yarar |
|---|---|---|
| `SourceScanResult.is_parse_unsupported` / `.unsupported_reason` / `.as_evidence()` | `domain/create_package/source_scan.py` | Lexer'ın kendi güven muhasebesi; `PARSE_UNSUPPORTED` kararının tek kaynağı |
| `UNTERMINATED_STRING` · `UNTERMINATED_BLOCK_COMMENT` · `UNRECOGNIZED_TOKEN_RATIO` | aynı dosya | Yapısal `unsupported_reason` sabitleri (scan evidence'ında kalıcı) |
| `detect_source_language()` · `score_language_markers()` · `LanguageSignal` | `domain/create_package/language_detect.py` (YENİ) | İçerik dil sinyali; `has_verdict` = "aktif kanıt var mı" |
| `ResolutionReason.RESOLVER_NOT_ACTIVE` · `_INACTIVE_TRUST_STATES` | `domain/esp/resolver.py` | `deprecated`/`unavailable` ayrımı (`candidate` bilerek ayrı) |
| `ParseUnsupported` · `RequiresClarification` · `ResolverNotActive` | `shared/errors.py` | Kanonik kodlar (422/422/409) |
| `_fail_closed(code, message, evidence)` · `_language_verdict(...)` | `application/jobs/create_package.py` | Determinist Pre-Check reddi üretme kalıbı — **yeni fail-closed sınıf eklerken bunu kopyala** |
| `PrecheckComputation.unsupported_calls` / `.error_detail` | aynı dosya | `dependency_scans`'e yazılan kanıt alanları |

**Kalıp (yeni bir fail-closed sınıfı eklerken):** kodu `shared/errors.py`'ye ekle → `compute_precheck`
içinde DESCRIPTION erken dönüşünden **sonra**, resolver çözümlemesinden **önce** bir kapı olarak
`_fail_closed(...)` döndür → sınıf `_RESOLVE_ERRORS` benzeri bir tuple'a giriyorsa
**`jobs/package_validation.py`'deki tuple'ı da güncelle** (K-05'te bu unutulmuş olsaydı validation
worker çökerdi; `run_validation_job`'ın `except Exception` yolu bunu maskeliyor).

## Sıradaki iş

**Blokaj değişmedi:** `docs/STAGE2_HANDOFF.md` §Next — **product-owner imzası**
(`docs/implementation/v18_final_acceptance.md` §4, D-1…D-9). İmza olmadan R2 RE-OPENING banner'ı
kalkmaz. Yanında hâlâ açık: **F-07 raw-id presentation sweep kalıntısı** — P-11/12/16 landed olduğu
için gerçekten kalıntı olup olmadığı **empirik doğrulanmalı** (K-05 kapsamadı).

## Bilinen tuzaklar (K-05'te bedeli ödendi)

1. **Paralel worktree'ler aynı `entropia_test` DB'sini paylaşıyor.** `tests/integration/db.py`
   varsayılanı her worktree'de aynı adı türetiyor → başka bir oturumun `drop_all`'u testlerini
   `RationaleFamilyNotActive` gibi **sahte** hatalarla düşürür. İzole koş:
   `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_<slug>_test`
2. **Postgres `text` kolonu NUL byte kabul etmiyor.** Integration fixture'ında `\x00` kullanma;
   gerçekçi bozuk-kodlama için U+FFFD replacement karakteri kullan (unit testte NUL sorun değil).
3. **`run_validation_job`'ın `except Exception` yolu teşhis maskeliyor** — aynı `FAILED` /
   `REVISION_REQUIRED` sonucunu ürettiği için test yeşil kalır. Validation testleri `checks` içeriğini
   assert etmeli, sadece status'ü değil.

---

## Paste-ready resume prompt

```
Entropia — devam. Session START protokolü: git fetch && git log --oneline origin/main -6 &&
gh pr list --state all ile gerçekten neyin merge olduğunu doğrula (handoff STALE-BY-DEFAULT).
Oku (otorite sırası): docs/K05_LANDED_KICKOFF.md, docs/STAGE2_HANDOFF.md §Next,
docs/STAGE_R3_KICKOFF.md, sonra dokunacağın alanın docs/CODEMAPS/ haritası.

Son durum: V18-R3 fail-closed sweep sürüyor. K-05 (PR #387) Pre-Check'in dört zorunlu hata
sınıfını getirdi — PARSE_UNSUPPORTED, SOURCE_LANGUAGE_MISMATCH, REQUIRES_CLARIFICATION,
RESOLVER_NOT_ACTIVE; hepsi FAILED scan + PRECHECK_FAILED, asla PASSED. K-07 (PR #388) upload
dosya-tipi kapısını fail-closed yaptı. main HEAD 604f8b4, alembic head 0035_portfolio_rules.

Sıradaki: (1) F-07 raw-id presentation sweep kalıntısının GERÇEKTEN kalıp kalmadığını ampirik
doğrula (P-11/12/16 landed) — varsa kapat; (2) product-owner imzası bekleyen R2 kapanışı
(docs/implementation/v18_final_acceptance.md §4, D-1…D-9) — imza gelmeden banner kaldırma.

Kurallar: direct-author (Workflow yok), backend verify =
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src &&
uv run pytest --no-cov -q — ama TEST_DATABASE_URL'i worktree'ye özel ver (paralel oturumlar
aynı entropia_test DB'sini paylaşıp sahte failure üretiyor). Ayrı branch + ayrı PR, NO AI
attribution, self-merge bloklu (merge'ü kullanıcı yapar).
```
