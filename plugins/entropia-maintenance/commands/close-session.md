---
description: Entropia kapanış ritüeli — handoff, kickoff+resume prompt, PROJECT_HISTORY, memory checkpoint, codemap, PR
argument-hint: "<slice adı, ör. ADIM 31 — ItemParticipant>"
allowed-tools: Bash(git:*), Bash(gh:*), mcp__github__list_pull_requests, mcp__github__pull_request_read, mcp__github__actions_list, mcp__github__actions_get, mcp__github__get_job_logs, mcp__github__create_pull_request, Read, Edit, Write, Glob, Grep
---

Kapanan slice: **$ARGUMENTS**

## Durum

- Bu dalın commit'leri: !`git log --oneline origin/main..HEAD 2>/dev/null || git log --oneline -5`
- Değişen dosyalar: !`git status --porcelain`

## Görevin — ALTI çıktının HEPSİ (CLAUDE.md §Session CLOSING ile aynı)

Biri eksikse kapanış tamamlanmamıştır. Sırayı bozma.

### 1. Handoff — `docs/STAGE2_HANDOFF.md`
`## Stage <x> — <title> landed (PR #n)` girdisi ekle: migration, yeni tablolar,
test sayıları, review sonucu, **ertelenen kalemler**. `## Next: …` satırını
güncelle.

### 2. Kickoff + resume prompt — `docs/STAGE<next>_KICKOFF.md`
Nerede olduğumuz, son slice'ın **bıraktıkları (reuse anchor'ları — kesin sembol
adlarıyla)**, sonraki tasarım işaretçileri, REUSE listesi, çalışma yöntemi ve en
altta **paste-ready resume prompt bloğu** (temiz bir oturuma yapıştırılacak
birebir metin).

### 3. Tarihçe + özet — İKİSİ AYRI (context disiplini)
- `docs/PROJECT_HISTORY.md` → slice'ın **tam** kaydı (ne landed, migration, OCC
  biçimi, test sayıları, **honest boundary'ler**).
- `CLAUDE.md` §Current position → **SADECE 5–6 satır** (HEAD sha, alembic head,
  test sayıları, son dalga, Next). **Buraya slice anlatısı YAZMA** — CLAUDE.md
  her oturumda tamamen context'e yüklenir.

### 4. Memory checkpoint — **türetilir, elle yazılmaz** (ADIM 52)
Md. 3'teki `PROJECT_HISTORY.md` kaydını yazdıktan **sonra**:

```bash
node scripts/memory_index.mjs --sync --only <slice-slug>
```

`<slice-slug>` = başlığın slug'ı (`node scripts/memory_index.mjs --emit` ile gör).
Tek doğruluk kaynağı git'teki belgedir; `agentmemory` onun **aranabilir
indeksidir**. Store efemer bir container'da kaybolursa borç doğmaz —
`--sync` (argümansız) hepsini yeniden üretir; sunucu `.mcp.json` üzerinden
kendiliğinden kalkar. Ayrıntı + sınırlar:
`CLAUDE.md` §Hafıza. **`ecc` / `claude-mem` artık zorunlu değil** (yerelde
bağlıysa yazmak serbest).

### 5. Codemap tazeleme
Slice yeni endpoint / tablo / sayfa / job eklediyse `docs/CODEMAPS/` içindeki
ilgili haritayı güncelle (veya `ecc:update-codemaps`).

### 6. Commit → PR → merge bekle
- Branch: `docs/stage-<x>-landed`
- Commit: `<type>(stage-<x>): <subject>` — **AI attribution YOK**
- `gh pr create` → `gh pr checks <n> --watch`
  — **`gh` yoksa** (remote container: yok): `mcp__github__create_pull_request`
    (draft) + `mcp__github__pull_request_read`. PR'a abone ol:
    `subscribe_pr_activity`; CI olayları oturuma **kendiliğinden** düşer.
- **Self-merge bloklu → merge'ü kullanıcıdan iste**, kendin merge etme.

## Kapanmadan önce — iki tuzak

- **Docs kayıt silme kontrolü ZORUNLU** (üç kez oldu):
  `git show <sha> -- docs/ | grep '^-## '` → çıktı **boş** olmalı.
- **Numara çakışması:** iki slice adı çift kullanıldı. Yeni kayıt yazarken
  başlık eklerini **aynen** kullan — `ADIM 16 (sevk edilen)`,
  `ADIM 16 (ADR §12)`, `ADIM 21 (worker delivery)`. Eksiz "ADIM 16" tek anlamlı
  değildir.

## Dürüstlük kuralı

Koşturulmamış bir kapıyı "geçti" yazma. İşaretlenmemiş kestirme gizli borçtur:
kod içinde `# ponytail:` yorumu **ve** `PROJECT_HISTORY.md`'de *honest boundary*.

## Çıktı

Altı maddenin her biri için: **yapıldı / yapılmadı (neden)**. Sonda PR linki.
