<!-- doc-status: current -->

# P2 — Backend lint / type / test / coverage

**Slice:** ADIM 29 / P2 (V18 RC verification)
**Tarih:** 2026-08-07
**Base commit:** `1f4b88b` — `docs(a08): reconcile the record with #514 being closed unaudited (#631)`
**Worktree branch:** `claude/entropia-v18-backend-checks-e25aca`

> **Dal adı notu:** brief `release/v18-rc-verification` dalını adlandırıyordu; bu worktree farklı
> bir dal adı taşıyor. Ama **base commit aynı** (`1f4b88b`) ve çalışma ağacı temiz
> (`git status --short` boş çıktı), yani ölçüm hedeflenen kodu ölçüyor.

## SONUÇ — DÖRT KAPI DA YEŞİL

| Kapı | Komut | Exit | Sonuç |
|---|---|---:|---|
| Lint | `uv run ruff check .` | **0** | ✅ `All checks passed!` |
| Format | `uv run ruff format --check .` | **0** | ✅ `786 files already formatted` |
| Type | `uv run mypy src` | **0** | ✅ `Success: no issues found in 396 source files` |
| Test + coverage | `uv run pytest` | **0** | ✅ aşağıya bak |

### pytest

```
3966 passed, 1 xfailed, 11 warnings in 1289.32s (0:21:29)
TOTAL                                       27113   1756   93.5%
Required test coverage of 90% reached. Total coverage: 93.52%
```

| Metrik | Değer |
|---|---|
| passed | **3966** |
| failed | **0** |
| error | **0** |
| xfailed | **1** |
| warnings | 11 |
| süre | 21 dk 29 sn |
| coverage | **%93,52** |
| coverage kapısı (`--cov-fail-under=90`) | ✅ **GEÇTİ** |
| exit code | **0** |

`failed`/`error` sıfırı iddia değil, ölçüm: log'da `^FAILED`/`^ERROR` ile başlayan satır sayısı
**0**, ve `= FAILURES =` / `= ERRORS =` bölümü hiç yok.

**Karşılaştırma (ADIM 25 / PR #622, 2026-08-06):** 3912 passed / 1 xfailed, coverage %93,52.
Bu koşu **+54 test**, coverage aynı yüzdede. Gerileme yok.

## xfail(strict) — sayı 1, kopyalanmadı, iki yoldan doğrulandı

**Runtime:** pytest özet satırı `1 xfailed` diyor.
**Statik:** `backend/tests/` üzerinde `grep -rn "pytest.mark.xfail"` → **tam 1 eşleşme**.

Tek xfail:

| Alan | Değer |
|---|---|
| Konum | `tests/integration/test_research_point_in_time_parity.py:583` |
| Marker | `@pytest.mark.xfail(strict=True, …)` |
| Issue | **GH #558** |
| Test | `test_both_bundles_pin_the_available_time_policy` |
| Gerekçe | İki bundle üyesi de available-time policy'yi taşımıyor; doc 12 §9.1 Agent Data Bundle'ın "exact revision IDs, usage scope and time policy" pinlemesini gerektiriyor, §9.2 `available_time_policies[]`'i BacktestEvidenceBundle alanı olarak listeliyor. Run manifest bunu pinliyor → iki execution-evidence yüzeyi çelişiyor. |
| Sınıf | **ÜRÜN kararı**, bug değil |

Dinamik xfail **yok**: `pytest.xfail(` yok, `add_marker` yok, `pyproject.toml`'da `xfail_strict` yok.
Test dosyasının kendi yorumu (satır 522–531) eski üç xfail'in (#556 ×2, #557) **düzeltilip** normal
assert'e döndüğünü kaydediyor — gateway artık `rd_jobs.admit_bundle_member` kapısından geçiyor.

> Bazı belgelerin **"4 xfail"** iddiası **BAYATTIR**. Doğru sayı **1**'dir; bu koşu
> `CLAUDE.md` §Testler'in halihazırdaki "Bilinçli `xfail(strict)` sayısı 1'dir" ifadesini
> runtime'da doğrular.

## Ortam

- `uv sync --all-extras --frozen` (exit 0).
  **Tuzak, kayda geçiyor:** `ruff` / `mypy` / `pytest` `[project.optional-dependencies].dev`
  **extra**'sında; düz `uv sync --frozen` onları kurmaz ve `uv run ruff` `Failed to spawn: ruff`
  ile patlar. CI de `--all-extras` kullanıyor (`.github/workflows/ci.yml:58`). Bu bir repo
  kusuru değil, çağrı biçimi kuralı.
- İzole test DB: `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_v18rc_test`
  — sürücü `postgresql+asyncpg://`, ad bu worktree'ye özel. Koşudan önce üzerinde **0 backend**
  olduğu doğrulandı (önceki iptal edilen denemeden kalıntı kilit/transaction yok).
- **Tek** `pytest` çağrısı, tam suite, ortada öldürülmedi.
  `| tail` **KULLANILMADI** — exit code ayrı dosyaya (`echo $? > pytest.exit`) yazılıp ayrı okundu.
  Suite koşarken başka `uv` komutu çalıştırılmadı.

## İlk denemenin başarısızlığı (kayıt — kod kusuru DEĞİL)

İlk koşu **1 sa 44 dk'da yalnız %34**'e ulaşıp iptal edildi. Sebep suite veya veritabanı değil,
**host bellek tükenmesi / swap thrashing** idi:

```
vm.swapusage: total = 9216.00M  used = 8661.88M  free = 554.12M
Pages free: 3907 × 16KB ≈ 61 MB boş RAM
load averages: 29.92 27.48 23.09
```

Veritabanı tarafı temizdi — `db.py` docstring'inin uyardığı şema-yeniden-kurma kilit beklemesi
**gerçekleşmedi**: `entropia_v18rc_test` üzerinde tek backend vardı, durumu `idle in transaction`
+ `wait_event = ClientRead` (yani Postgres boşta, **Python istemcisini** bekliyor), ve hiçbir DB'de
`wait_event_type = 'Lock'` olan backend yoktu (**0**).

Makine boşaldıktan sonra (load 15dk ortalaması 29,9 → 4,82) aynı suite **21 dk 29 sn**'de bitti.

> **Ders:** bu suite'in tam koşusu ~21 dakikadır. Saatlerce sürüyorsa sorun testlerde değil,
> host'ta — `sysctl vm.swapusage` ve `uptime` bak, `pg_stat_activity`'de `wait_event_type='Lock'`
> say. Paralel worktree oturumlarını suite koşarken açık bırakma.

## Log dosyaları

Oturum scratchpad'i (kalıcı değil):
`…/scratchpad/p2logs/{uv_sync,ruff_check,ruff_format,mypy,pytest}.log` + `pytest.exit`

## AÇIK İŞ

Yok. P2 kapsamındaki dört kontrol de tamamlandı ve geçti.
