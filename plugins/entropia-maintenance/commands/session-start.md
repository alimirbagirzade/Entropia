---
description: Entropia oturum başlangıç protokolü — bayat belge doğrulaması + otorite sırasıyla okuma
allowed-tools: Bash(git fetch:*), Bash(git log:*), Bash(git status:*), Bash(gh pr list:*), Read, Glob, Grep
---

## Taze durum (bu blok komut çağrılırken koşturuldu)

- `git fetch`: !`git fetch --quiet 2>&1 || echo "fetch basarisiz (offline olabilir)"`
- origin/main son 6: !`git log --oneline origin/main -6 2>&1 || echo "origin/main yok"`
- Yerel HEAD: !`git log --oneline -3`
- Çalışma ağacı: !`git status --porcelain`
- PR'lar: !`gh pr list --state all --limit 8 2>&1 || echo "gh yok/yetkisiz"`

## Görevin

Yukarıdaki **gerçek** çıktıya bakarak oturumu başlat. Bu protokol
`CLAUDE.md` §Session START ile aynıdır; kısaltma.

1. **Doğrula — handoff/özet BAYAT VARSAYILIR.** Yukarıdaki `git log`/`gh pr list`
   çıktısıyla neyin gerçekten **landed/merged** olduğunu tespit et. Bir önceki
   oturumun özetine ya da yerel branch'e güvenme.
2. **Otorite sırasıyla oku** (hepsini değil, gerekeni):
   1. En yeni `docs/STAGE<next>_KICKOFF.md` / `docs/ADIM<n>_*_KICKOFF.md`
   2. `docs/STAGE2_HANDOFF.md` — "… landed" + "Next"
   3. `docs/STAGE_BUILD_PLAN.md` — stage tablosu + acceptance
   4. İlgili `docs/spec/NN_*` — spec'i **tam** çıkar
   5. `docs/generated/repository_facts.md` — **sayısal otorite** (alembic head,
      `ENGINE_VERSION`, `SHARED_ALLOCATION_STATUS`, test collection)
3. **Çelişki bulursan sustur değil, bildir.** `CLAUDE.md` §Current position elle
   yazılır ve HEAD sha'sı yapısal olarak bayattır; üretilmiş blokla çelişirse
   **üretilmiş blok kazanır**.
4. **Kod tarafına geçmeden** dokunacağın alanın `docs/CODEMAPS/` haritasını oku,
   sonra `codebase-memory-mcp` ile sembolleri bul. Kör grep + tam dosya okuma yok.
5. Ayrıntı gerekiyorsa `docs/PROJECT_HISTORY.md`'den **hedefli** oku.

## Çıktı

```
## Gerçekten nerede duruyoruz
<origin/main HEAD + son merge edilen PR'lar — kanıtla>

## Belge ile gerçek arasındaki fark
<varsa; yoksa "fark yok">

## Bu oturumun işi
<kickoff'un Next'i — tek cümle>

## İlk adım
<somut>
```

Şüphe varsa `entropia-regression-check` skill'ini oku (bayat belge tuzakları,
0-job'lı "yeşil" CI, çift kullanılmış ADIM numaraları).
