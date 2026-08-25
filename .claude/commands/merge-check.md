---
description: Merge öncesi regresyon kapısı — docs kayıt silme, üretilmiş dosya drift'i, 0-job'lı sahte yeşil CI
argument-hint: "<PR numarası veya commit sha>"
allowed-tools: Bash(git:*), Bash(gh:*), mcp__github__list_pull_requests, mcp__github__pull_request_read, mcp__github__actions_list, mcp__github__actions_get, mcp__github__get_job_logs, Read, Grep
---

Hedef: **$1**

## Toplanan durum

- Taze base: !`git fetch --quiet 2>&1; git log --oneline origin/main -5`
- Yerel HEAD: !`git log --oneline -1`

## Görevin — beş kapı, hepsi elle koşulur

CI bu kapıların **hiçbirini** tam kapsamaz. Sırayla koştur ve her birine
PASS/FAIL yaz.

### 1. Docs kayıt silme (ÜÇ KEZ oldu — #590: 211 satır, #604: 194 satır)

**Hiçbir CI kapısı `docs/` okumaz.**

```bash
git show $1 -- docs/ | grep '^-## ' || echo "kayit silinmemis"
```

PR numarası verildiyse önce sha'ya çevir (`gh pr view $1 --json headRefOid`; `gh`
yoksa `mcp__github__pull_request_read`) ya da diff'i doğrudan al (`gh pr diff $1 --
docs/`; `gh` yoksa aynı aracın diff/files kipi). Çıktı **boş değilse merge ETME** —
base bayat, kayıt geri konmalı.

### 2. Base tazeliği

Branch `origin/main`'in gerisindeyse docs PR'ı regresyon riski taşır. Rebase iste.

### 3. Üretilmiş dosya drift'i

```bash
cd backend && uv run python -m entropia.apps.api.openapi_export --check
cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```

Kırmızıysa **dosyayı elle düzeltme** — üreticiyi koştur (`make openapi`).

### 4. CI gerçekten koştu mu (0-job tuzağı)

`ci.yml` concurrency kusuru yüzünden main'de kuyruğa giren koşu bir öncekini
iptal etti; `e8d1d48` (#633) ve `bc59dae` (#634) **0 job ile cancelled** —
CI'ları hiç koşmadı.

```bash
gh pr checks $1
gh run list --limit 5
gh run view <id>     # job sayısı 0 ise "yeşil" DEĞİLDİR
```

> **`gh` HER ORTAMDA YOK — ölçüldü (2026-08-25, remote container: `command -v gh` boş).**
> Aşağıdaki `gh` komutları **yerel** oturumun yoludur. `gh` yoksa aynı bilgiyi GitHub
> MCP araçlarından al (bunlar `.claude/settings.json` `permissions.allow`'da salt-okur
> olarak zaten kayıtlı): PR listesi `mcp__github__list_pull_requests` · PR ayrıntısı,
> diff'i ve check'leri `mcp__github__pull_request_read` · koşu listesi
> `mcp__github__actions_list` · koşu ayrıntısı `mcp__github__actions_get` · job log'u
> `mcp__github__get_job_logs` · PR açma `mcp__github__create_pull_request`.
> **Kanıt sorusu değişmez, aracı değişir.**
> Burada 0-job tuzağını gören alan `mcp__github__actions_get` çıktısındaki **job
> sayısıdır**; `conclusion: success` tek başına kanıt değildir.

### 5. "Landed / closed" iddialarının kanıtı

PR açıklaması veya değişen belgeler bir işi `Complete` / `PASS` / `Done`
gösteriyorsa **kanıt iste**. Bu repoda kanıtsız kapatma geçmişi var (A-08
denetimi yapılmadı, defter boş, #514 iki kez kanıtsız kapatıldı). Kapatma
yetkisi **insandadır** — agent kapatamaz.

## Çıktı

```
| Kapı | Sonuç | Kanıt |
|---|---|---|
| 1 docs kayıt silme | PASS/FAIL | <komut çıktısı> |
| 2 base tazeliği | | |
| 3 drift guard | | |
| 4 CI gerçekten koştu | | |
| 5 iddia kanıtı | | |

## Karar
MERGE EDİLEBİLİR / BLOKE — <tek cümle gerekçe>
```

Ayrıntı: `entropia-regression-check` skill'i.
