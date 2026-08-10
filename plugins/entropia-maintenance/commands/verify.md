---
description: Yerel kapıları koştur (ruff, mypy, pytest+coverage, frontend, drift guard'ları) ve dürüst rapor ver
argument-hint: "[backend|frontend|all]  (varsayılan: all)"
---

Kapsam: **$ARGUMENTS** (boşsa `all`).

`entropia-verifier` ajanını çalıştır ve bu kapsamı ona ver. Ajan yoksa aynı
disiplini kendin uygula — `entropia-testing` skill'i tam metindir.

## Koşulacak kapılar

**backend**
```
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
cd backend && uv run pytest -q > /tmp/entropia-pytest.out 2>&1; echo "exit=$?"; tail -25 /tmp/entropia-pytest.out
cd backend && uv run python -m entropia.apps.api.openapi_export --check
cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```

**frontend**
```
cd frontend && npm run lint && npm run typecheck && npm run coverage && npm run build
```

## Pazarlıksız kurallar

- **`| tail` KULLANMA** — exit code `tail`'in olur. Çıktıyı dosyaya yaz, `$?`'i
  **ayrı** oku (yukarıdaki kalıp).
- **Alt küme koşarken `--no-cov` ekle** — tek dosyalık koşu paketin tamamını ~%4
  ölçer, kapı sahte kırmızı verir.
- Tam suite **tek pytest çağrısında** koşar, ortada öldürülmez; suite koşarken
  `uv sync` / paralel `uv run` yok.
- Paralel worktree varsa `TEST_DATABASE_URL` ile izole DB
  (**sürücü `postgresql+asyncpg://`**).
- vitest için **`--no-file-parallelism` zorunlu**; `node_modules` yoksa önce
  `npm ci` (`ERR_MODULE_NOT_FOUND` test hatası değildir).
- **Eşik düşürmek yasak.** `--cov-fail-under=90` ve `frontend/vite.config.ts`
  eşikleri **kapıdır** — düşen sayıyı indirme, eksik testi yaz.
- Yeni migration varsa: L1 FK insert-order proof + alembic `<n>` up/down/up
  (`LC_ALL=en_US.UTF-8`, önce `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`)
  + migration↔model kolon paritesi.

## Rapor biçimi

| Kapı | Komut | Sonuç |
|---|---|---|

Kırmızı olanların **gerçek çıktısını** göster. Koşturmadığın kapıya
"KOŞTURULMADI — <neden>" yaz. Sayıları çıktıdan al; hatırladığını ya da belgede
yazanı raporlama. Sonda tek cümlelik karar: **GREEN** veya **BLOCKED**.
