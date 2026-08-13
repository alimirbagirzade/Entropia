# entropia-maintenance

Entropia'ya özgü Claude Code plugin'i: **ajanlar** (kim çalışır), **skill'ler**
(hangi kuralı bilir), **hook'lar** (neyi otomatik uygular).

## Kurulum (bu depodan)

```bash
/plugin marketplace add .
/plugin install entropia-maintenance@entropia
```

`/plugin marketplace add` deponun kökündeki `.claude-plugin/marketplace.json`
dosyasını okur. Kurulum sonrası ajanlar, skill'ler ve hook'lar otomatik yüklenir;
oturumu yeniden başlat.

**Kurulmazsa hiçbiri aktif olmaz.** Bu bilinçli: aynı ajan/skill'i hem `.claude/`
hem plugin üzerinden yüklemek çift kayıt üretirdi, o yüzden `.claude/` altında
kopya bırakılmadı.

## İçerik

```
entropia-maintenance/
├── .claude-plugin/plugin.json
├── agents/     entropia-triage · entropia-scoped-fix · entropia-verifier
├── commands/   session-start · verify · merge-check · close-session
├── skills/     entropia-canonical-rules · entropia-testing
│               entropia-regression-check · entropia-frontend-parity
└── hooks/      hooks.json + guard-generated.sh · guard-git.sh
                 post-edit-lint.sh · session-brief.sh
```

### Ajanlar

| Ajan | Ne yapar | Ne YAPMAZ |
|---|---|---|
| `entropia-triage` | Codemap → `codebase-memory-mcp` → hedefli Read sırasıyla teşhis; riske giren invariant'ları adıyla listeler; kapsam önerir | Kod yazmaz |
| `entropia-scoped-fix` | Verilen kapsamı katman desenine ve adjudicated kurallara uyarak uygular; testi birlikte yazar | Kapsamı genişletmez, istenmeden commit/PR açmaz |
| `entropia-verifier` | Kapıları doğru komutlarla koşar, exit code'u ayrı okur, dürüst rapor verir | Eşik düşürmez, sayı uydurmaz |

Tipik zincir: **triage → scoped-fix → verifier**.

### Skill'ler

Açıklamalarıyla eşleşen işte kendiliğinden yüklenir; `/<skill-adı>` ile elle de
çağrılabilir.

| Skill | Tetikleyici |
|---|---|
| `entropia-canonical-rules` | endpoint / komut / hata sınıfı / soft-delete / upload / mutating op; "bunu sadeleştirebilir miyim" |
| `entropia-testing` | test yazma, coverage düşmesi, migration, commit/PR öncesi |
| `entropia-regression-check` | docs değişikliği, PR merge, "landed mi", oturum başı |
| `entropia-frontend-parity` | sayfa/stil/etiket değişikliği, mockup hizalama, kırılan frontend testi |

### Slash command'lar

Plugin komutları `/entropia-maintenance:<ad>` biçiminde çağrılır. Dördü birlikte
oturum yaşam döngüsünü kapsar: **session-start → verify → merge-check → close-session**.

| Komut | Ne yapar |
|---|---|
| `/entropia-maintenance:session-start` | `git fetch` + `origin/main` + `gh pr list` çıktısını **koşturarak** enjekte eder, sonra otorite sırasıyla (kickoff → handoff → build plan → spec → repository_facts) okutur. Belge ile gerçek arasındaki farkı raporlar. |
| `/entropia-maintenance:verify [backend\|frontend\|all]` | Yerel kapıları doğru komutlarla koşturur; `\| tail` yasağı, `--no-cov` alt-küme kuralı, `TEST_DATABASE_URL` izolasyonu ve "eşik düşürme yasak" kuralı komutun içinde yazılı. |
| `/entropia-maintenance:merge-check <PR\|sha>` | Merge öncesi beş kapı: docs kayıt silme (`git show … \| grep '^-## '`), base tazeliği, drift guard'ları, **0-job'lı sahte yeşil CI**, "landed/closed" iddialarının kanıtı. |
| `/entropia-maintenance:close-session <slice>` | `CLAUDE.md` kapanış ritüelinin altı çıktısı: handoff · kickoff+resume prompt · PROJECT_HISTORY (tam) + CLAUDE.md (5–6 satır) · memory checkpoint (**iki sistem**) · codemap · commit→PR→merge bekle. |

`session-start` ve `merge-check` frontmatter'ında `allowed-tools` ile sınırlıdır
(`git`, `gh`, okuma araçları) ve `!` ile **komut çağrılırken** taze git durumunu
enjekte eder — modelin hatırladığı duruma değil, gerçek çıktıya bakar.

### Hook'lar

| Olay | Script | Davranış |
|---|---|---|
| `PreToolUse` (Edit/Write/MultiEdit/NotebookEdit) | `guard-generated.sh` | `docs/openapi.json`, `docs/generated/*` elle düzenlemesini **engeller** (exit 2) ve üreticiyi söyler |
| `PostToolUse` (Edit/Write/MultiEdit) | `post-edit-lint.sh` | Değişen **tek** backend `.py` üzerinde ruff check + format → kırmızıysa exit 2. Migration / `lib/*.ts` / `app/nav.ts` / adjudicated shared dosyaları / `PROJECT_HISTORY.md` için bağlam hatırlatması (bloklamaz) |
| `PreToolUse` (Bash) | `guard-git.sh` | Üç otomatik kapı: **docs kayıt silen commit** (`git diff --cached -- docs/ \| grep '^-## '` boş değilse **engeller**), **self-merge** (`gh pr merge` engellenir — merge yetkisi insandadır), **main'e force push** |
| `SessionStart` | `session-brief.sh` | "Belgeler bayat varsayılır" + doğrulama komutları + skill/ajan listesi |

Kapat: `export ENTROPIA_HOOKS=off` (üç script de sessizce çıkar).

## Otomatik devreye girme

Elle çağırman gereken tek şey slash command'lar; geri kalan kendiliğinden çalışır.

| Katman | Nasıl tetiklenir |
|---|---|
| **Skill'ler** | Açıklamalarıyla eşleşen işte model tarafından kendiliğinden yüklenir |
| **Hook'lar** | Olay bazlı; kullanıcı ya da model müdahalesi gerekmez |
| **Ajanlar** | Açıklamalarında **PROAKTİF** yönergesi var — bug/kırmızı CI → `entropia-triage`, kapsam hazır → `entropia-scoped-fix`, kod değişti/commit öncesi → `entropia-verifier`; kullanıcının adıyla istemesi gerekmez |
| **Komutlar** | Elle (`/entropia-maintenance:…`). `merge-check` ayrıca `guard-git.sh` tarafından `gh pr merge` denendiğinde **otomatik hatırlatılır** |

`guard-git.sh`, üç kez yaşanan docs regresyonunu (#590, #604) commit anında
yakalar: hiçbir CI kapısı `docs/` okumadığı için bu tek otomatik savunmadır.

## Tasarım sınırları (bilerek)

- **Hook'ların yan etkisi yoktur.** `post-edit-lint.sh` ruff'u yalnız **hazır**
  bir binary'den koşar (`backend/.venv/bin/ruff` ya da PATH). `uv run ruff`
  **bilerek kullanılmaz**: deps'i kurulmamış bir worktree'de `.venv` yaratıp
  paket kurar. ruff yoksa **sessizce geçer**. Ölçülen maliyet: temiz dosyada ~50 ms.
- **Tam suite hook'ta koşmaz.** Kapılar `entropia-verifier` ajanındadır.
- **Yol çözümü:** hook komutları `${CLAUDE_PLUGIN_ROOT}` ile plugin köküne,
  script'lerin içi `CLAUDE_PROJECT_DIR` (yoksa `git rev-parse --show-toplevel`)
  ile **repo** köküne bakar. İkisi ayrı; plugin depo dışına kurulsa da çalışır.
- **`ponytail-entropia` plugin'e alınmadı.** O skill bu çalışmadan önce vardı ve
  `CLAUDE.md` ona `.claude/skills/ponytail-entropia/SKILL.md` **yoluyla** atıf
  yapıyor; taşımak o atfı kırardı ve plugin kurulmamış bir çekoutta merdiveni
  yok ederdi. Ajanlar ona **adıyla** atıf yapar, yükleme yeri değişmedi.
- **MCP kısmen eklendi (2026-08-12).** Eski gerekçe — `codebase-memory-mcp`
  makineye özel mutlak bir yolla tanımlıydı, repoya koymak o yolu herkese
  dayatırdı — ve konulan koşul: *"taşınabilir bir çalıştırma biçimi belirlenirse
  eklenebilir."* **Koşul karşılandı:** paket npm'de yayımlanmış ve çıplak çağrısı
  MCP'yi stdio'da başlatıyor (`npx -y codebase-memory-mcp@0.10.2`; initialize
  handshake'i bu argümanlarla doğrulandı). Sürüm **sabitlenmiştir** — `@latest`
  yazmak, deponun action'ları SHA'ya pinleyen tedarik-zinciri duruşuyla çelişirdi.
  `--ui=false` bilinçlidir: sunucunun HTTP graph görselleştirmesi bir port dinler,
  CI/remote'ta istemiyoruz.
  **Dosya plugin köküne değil DEPO KÖKÜNE kondu** (bu maddenin önerdiği yer plugin
  köküydü): asıl ihtiyaç remote container'da doğuyor, orası depoyu klonluyor ama
  plugin'i kurmuyor — plugin kökündeki bir dosya o oturuma hiç ulaşmazdı.
- **`claude-mem` ve `ecc` bu yolla EKLENEMEZ — ölçüldü, tahmin değil.**
  `claude-mem` bir MCP stdio sunucusu değil, **kurulum aracı**: `npx claude-mem
  install` bir plugin + Bun tabanlı worker servisi (ya da Docker pg+redis'li server
  runtime) kurar ve IDE'nin MCP config'ini **kendisi** enjekte eder; `.mcp.json`'a
  yazılırsa sunucu değil installer çağrılmış olur. `ecc` ise npm'de yok — araç
  öneki `mcp__plugin_ecc_memory__*` (bkz. `docs/ADIM8_LANDED_KICKOFF.md`), yani
  marketplace'ten kurulan bir **plugin**. İkisi de kapanış ritüeli md. 4'ün
  dayandığı sunuculardır → **memory checkpoint borcu bu değişiklikle KAPANMADI.**

## Sürüm

`0.3.0` — otomatik git guard'ı + proaktif ajan tetikleme.
(`0.2.0` — slash command'lar · `0.1.0` — ilk paketleme.) Sürüm iki yerde tutulur ve **birlikte** güncellenir:
`.claude-plugin/plugin.json` ve deponun kökündeki `.claude-plugin/marketplace.json`.
