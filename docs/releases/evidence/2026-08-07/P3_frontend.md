<!-- doc-status: historical -->
> **EVIDENCE SNAPSHOT — bu belge bir koşunun kaydıdır, güncel gerçek iddiası DEĞİLDİR.**
> Aşağıdaki sayılar 2026-08-07 tarihli tek bir yerel koşuya aittir; sonraki commit'lerle
> bayatlar. Otorite CI'dır (`gh run list --branch main --limit 1`).

# ADIM 29 / P3 — frontend lint · typecheck · test · build

**Sonuç: 5/5 YEŞİL.** Beş komutun tamamı `exit 0` döndü; hiçbir eşik düşürülmedi,
hiçbir test atlanmadı/quarantine edilmedi.

## Koşum ortamı

| Alan | Değer |
|---|---|
| Tarih (UTC) | 2026-08-07T14:29Z |
| Worktree | `.claude/worktrees/frontend-lint-typecheck-test-build-021385` |
| Branch | `claude/frontend-lint-typecheck-test-build-021385` |
| HEAD | `1f4b88b7370dd73929d068175885c05f65fd3b9a` (`1f4b88b`) |
| Platform | darwin 25.5.0 (arm64) |
| Node / npm | v24.15.0 / 11.12.1 |
| TypeScript / ESLint / Vitest / Vite | 5.9.3 / 9.39.5 / 4.1.10 / 8.2.0 |
| Çalışma dizini | `frontend/` |

`frontend/node_modules` worktree'de **yoktu** → önce `npm ci` koşuldu (CLAUDE.md'deki not:
ilk koşudaki `ERR_MODULE_NOT_FOUND` test hatası değildir; burada hiç oluşmadı).

## Exit code'lar (her biri ayrı koşu, ayrı log, `$?` ayrı okundu)

| # | Komut | Exit | Süre |
|---|---|---|---|
| 1 | `npm ci` | **0** | ~13 s |
| 2 | `npm run lint` | **0** | <5 s |
| 3 | `npm run typecheck` | **0** | <5 s |
| 4 | `npm run coverage -- --no-file-parallelism` | **0** | 475.33 s |
| 5 | `npm run build` | **0** | 1.52 s (vite) |

## 1) `npm ci`

```
added 243 packages, and audited 244 packages in 13s
3 high severity vulnerabilities
```

Kurulum temiz. **Dürüst not:** `npm audit` 3 HIGH bildiriyor (0 critical / 0 moderate / 0 low).
Bu, P3 kapsamının dışıdır ve **kapı değildir** — bu koşuda hiçbir komutu kırmadı:

- `js-yaml` — *Quadratic CPU consumption in `!!omap` resolution*, CVE-2026-59870 fix'i 3.x/4.x'e
  backport EDİLMEDİ. Bu advisory **bilerek dondurulmuş** durumda (PR #629, `security(deps)`).
- `react-router` + `react-router-dom` — *RSC Mode CSRF Bypass Allows Action Execution Before
  400 Response*. **Değerlendirilmedi** (bu slice'ın işi değil); Entropia RSC modunu kullanmıyor
  ama bunu bu koşuda **doğrulamadım** — açık bir izleme kalemidir.

## 2) `npm run lint` → `eslint .`

Çıktı boş, exit 0. Sıfır error, sıfır warning.

## 3) `npm run typecheck` → `tsc -b --noEmit`

Çıktı boş, exit 0. Sıfır tip hatası.

## 4) `npm run coverage` → `vitest run --coverage --no-file-parallelism`

`--no-file-parallelism` CLAUDE.md gereği **zorunlu** olarak eklendi (script'in kendisinde yok;
`npm run coverage -- --no-file-parallelism` ile geçildi).

```
 Test Files  70 passed (70)
      Tests  721 passed (721)
   Duration  475.33s (transform 12.45s, setup 31.81s, import 27.42s,
                      tests 241.15s, environment 122.36s)
```

**0 failed · 0 skipped · 0 todo · 0 unhandled error.**

### Coverage — ölçülen vs. kapı (`frontend/vite.config.ts` → `test.coverage.thresholds`)

| Metrik | Ölçülen | Kapı | Pay |
|---|---|---|---|
| **Lines** | **84.92 %** (4914/5786) | 83 | +1.92 |
| Statements | 82.62 % (5247/6350) | 80 | +2.62 |
| Functions | 75.27 % (1976/2625) | 73 | +2.27 |
| Branches | 72.84 % (4810/6603) | 70 | +2.84 |

Dördü de kapının üstünde → koşu yeşil. **Hiçbir eşik bu slice'ta değiştirilmedi.**
Sayılar ADIM 25 / PR #622'de kaydedilen değerlerle **birebir aynı** (721 passed / 70 dosya /
%84.92 line) → bu dalgada frontend regresyonu yok.

## 5) `npm run build` → `tsc -b && vite build`

```
vite v8.2.0 building client environment for production...
✓ 176 modules transformed.
dist/index.html                   0.51 kB │ gzip:   0.31 kB
dist/assets/index-XKVdEXBv.css   56.40 kB │ gzip:  10.01 kB
dist/assets/index-Bzm0BPr8.js   964.37 kB │ gzip: 242.36 kB
✓ built in 1.52s
```

Build başarılı. İki **uyarı** (hata değil, exit 0):

1. **Chunk boyutu** — `index-*.js` 964.37 kB (gzip 242.36 kB), Vite'ın 500 kB eşiğinin üstünde.
   Uygulama tek chunk halinde bundle'lanıyor; route-level `dynamic import()` ile code-splitting
   yapılmamış. Bu **bilinen ve kabul edilmiş** bir durum, bu slice'ta değiştirilmedi.
2. **Vite config uyarısı** — `vite.config.ts:18` içindeki `__dirname`, gelecekte varsayılan
   olacak `configLoader: 'native'` tarafından desteklenmiyor; `import.meta.dirname`'e geçilmesi
   öneriliyor. Bugün kırmıyor, gelecekteki bir Vite major'ında kıracak.

## Değişiklik kaydı

Bu koşu **hiçbir kaynak dosyayı değiştirmedi** — `git status` temiz (`node_modules/` ve `dist/`
gitignored). Salt doğrulama koşusudur; üretilen tek kalıcı çıktı bu belgedir.
