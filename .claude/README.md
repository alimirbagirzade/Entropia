# `.claude/`

Entropia'nın ajanları, invariant skill'leri ve hook'ları artık bir plugin'dir:
**[`plugins/entropia-maintenance/`](../plugins/entropia-maintenance/README.md)**

```bash
/plugin marketplace add .
/plugin install entropia-maintenance@entropia
```

**GÜNCEL DURUM: plugin kurulu olmasa da hiçbir şey kaybolmaz.** Kurulum hâlâ
gerçekleşmiyor ve aşağıdaki ölçüm hâlâ geçerli — değişen şey, plugin'in TÜM
içeriğinin kurulum istemeyen iki yoldan birine bağlanmış olması:

| İçerik | Nasıl ulaşılıyor | Tek kaynak |
|---|---|---|
| Ajanlar (`entropia-triage`, `entropia-scoped-fix`, `entropia-verifier`) | `.claude/agents/` **aynası** | plugin |
| Skill'ler (`entropia-canonical-rules`, `entropia-testing`, `entropia-regression-check`, `entropia-frontend-parity`) | `.claude/skills/` **aynası** | plugin |
| Slash command'lar (`/session-start`, `/verify`, `/merge-check`, `/close-session`) | `.claude/commands/` **aynası** | plugin |
| Beş hook'un **hepsi** | `settings.json`'daki **doğrudan kayıt** | plugin |

**"Kopya bırakılmadı" cümlesi ARTIK DOĞRU DEĞİL ve bu yüzden kaldırıldı.** Ajan ve
skill kopyaları `a5d9e4f` (2026-08-18) ile geri kondu; command kopyaları bu
değişiklikle eklendi. Ayna bir kopya olduğu için **sapabilir**, o yüzden eşitlik bir
CI kapısıdır: `scripts/agent-config-gate.mjs` ayrışan dosyayı **adıyla** kırmızıya
çevirir, `scripts/sync-agent-mirror.sh` eşitler. Plugin altında bir ajan/skill/command
düzenledikten sonra **sync betiğini koştur ve aynayı da commit et.**

**Command'lar neden İŞARETÇİ değil KOPYA — ölçüldü, tercih değil.**
`commands/session-start.md` taze git durumunu `` !`…` `` biçimiyle enjekte eder ve
harness bu genişletmeyi **yüklediği** dosyada yapar; *"plugin'deki kopyayı oku"* diyen
bir dosya hem o genişletmeyi hem `close-session`/`verify`'ın `$ARGUMENTS` ikamesini
kaybederdi. Davranışı koruyan şey kopyalama, kopyayı dürüst tutan şey kapıdır.

**`enabledPlugins` KURULUM DEĞİLDİR — ölçüldü (2026-08-13, bu remote container).**
`settings.json`'daki `extraKnownMarketplaces.entropia` + `enabledPlugins` yalnızca
adın **çözülebildiğini** ve kurulunca etkin sayılacağını söyler; kurulumun kendisi
bir **onay istemi** ister ve remote container etkileşimsizdir, istem yoktur. Ölçüm:
`/root/.claude/plugins/installed_plugins.json` = `{"version":2,"plugins":{}}` — **boş**.
Yani plugin **kurulu değil** — ve ajanları/skill'leri/komutları **plugin olarak**
yüklenmedi. (Yukarıdaki tablonun anlattığı gibi, içerikleri artık aynadan yükleniyor;
ölçümün kendisi değişmedi, sonucu değişti.)
Bu bir yapılandırma hatası DEĞİL: `scripts/agent-config-gate.mjs` adın marketplace'te
çözüldüğünü doğruluyor ve yeşil. ADIM 53'ün *"depoya güvenen her oturumda
önerilir/etkinleşir"* cümlesi remote'ta **yanlıştı**; yerelde önerilir, remote'ta
**hiç önerilmez**.

**Sonuç (ADIM 57): iki bloklayıcı guard kurulumdan bağımsız hale getirildi.**
`settings.json` artık plugin'in `hooks/guard-git.sh` ve `hooks/guard-generated.sh`
betiklerini `${CLAUDE_PROJECT_DIR}` üzerinden **doğrudan** kaydediyor. Dosyalar
kopyalanmadı — tek kaynak hâlâ plugin'in içinde; ikilenen şey yalnızca **kayıt**.
Plugin yerelde kuruluysa aynı guard iki kez koşar (ölçülen bedel ≈ 25 ms/çağrı,
gerekçe: `../plugins/entropia-maintenance/README.md` §Çift koşma).

**Genişletildi: kalan ÜÇ hook da aynı yolla kaydedildi.** ADIM 57 yalnız **bloklayan**
ikisini ikilemişti; gerekçesi *"öteki üçü hatırlatmadır, ikilenmeleri güvenlik
kazandırmaz, yalnız gürültü üretir"* idi. Karar sahibince geri alındı, çünkü
**erişilebilirlik de bir sonuçtur**: o üçü remote'ta hiç koşmadığı için `frontend/src`
altında vendor kural sınırı hiç hatırlatılmadı, migration / `lib/*.ts` / adjudicated
shared dosya uyarıları hiç çıkmadı, oturum brifi hiç görünmedi. Ayrıca eski
gerekçedeki *"hatırlatma"* nitelemesi `post-edit-lint.sh` için **yanlıştı**: onun ruff
dalı **exit 2** ile bloklar.

| Olay | Script | Bu değişiklikle eklendi |
|---|---|---|
| `PreToolUse` (Bash) | `guard-git.sh` | — (ADIM 57) |
| `PreToolUse` (Edit/Write/MultiEdit/NotebookEdit) | `guard-generated.sh` | — (ADIM 57) |
| `PreToolUse` (Edit/Write/MultiEdit/NotebookEdit) | `vendor-react-rules.sh` | ✔ |
| `PostToolUse` (Edit/Write/MultiEdit) | `post-edit-lint.sh` | ✔ |
| `SessionStart` (`startup`/`resume`/`clear`) | `session-brief.sh` | ✔ |

**Çift koşmanın bedeli bu üçü için ayrıca ÖLÇÜLMEDİ; şekli biliniyor:** plugin
**yerelde kuruluysa** vendor notu ve oturum brifi bağlama iki kez enjekte edilir, ruff
aynı dosyada iki kez koşar (temiz dosyada ~50 ms) ve kırmızıda iki özdeş stderr bloğu
çıkar. Yan etki yok — üçü de salt-okurdur ve idempotenttir. Alternatif (*"kuruluysa
atla"*) ADIM 57'de **fail-open** olduğu için reddedilmişti; o gerekçe burada da
geçerlidir. Üçünü birden susturmak için: `export ENTROPIA_HOOKS=off`.

Aynı zamanda `settings.json` **#651'den beri geçersiz JSON'du** ve ADIM 53'te
onarıldı: o aradaki her oturumda buradaki `docs-history-guard` ve
`ultrareview-advisor` hook'ları hiç koşmuyordu (`scripts/agent-config-gate.mjs`).

`skills/ponytail-entropia/` plugin'e **hiç alınmadı**: bu çalışmadan önce vardı ve
`CLAUDE.md` ona **yoluyla** atıf yapıyor, o yüzden yeri değişmedi. `pr-drive-to-green`
ve iki `vercel-*` skill'i de plugin'de yok — üçü de aynanın **dışındadır**: kapı yalnız
plugin'de tanımlı olanı arar, `.claude/` altındaki fazlalığa karışmaz.

## `skills/vercel-*` — vendor'lanan üçüncü taraf skill'ler

`vercel-labs/agent-skills` (MIT) reposundan `npx skills` CLI'ı ile alınan iki
skill burada durur, plugin'in içinde **değil**: sürümlerini kök dizindeki
`skills-lock.json` yönetir ve `npx skills update` bu yolu bekler. Plugin'e
taşınırlarsa güncelleme zinciri kopar.

| Skill | Bu projede geçerli kural aileleri |
|---|---|
| `vercel-composition-patterns` | `architecture-*`, `state-*`, `patterns-*` — `react19-*` ATLA (React 18.3) |
| `vercel-react-best-practices` | `rerender-*`, `rendering-*`, `js-*`, `advanced-*` — `async-*`/`bundle-*`/`server-*`/`client-swr-*` Next.js + RSC özel, GEÇERSİZ |

Bu ayrımı `frontend/src/**/*.ts(x)` yazılırken plugin'in
`hooks/vendor-react-rules.sh` PreToolUse hook'u hatırlatır. Sınırın kendisi
(presentation-only, ellenmeyenler) o hook'ta değil, `entropia-frontend-parity`
skill'indedir.

Her iki skill'in `AGENTS.md`'si silindi: `rules/*.md`'nin birebir birleştirilmiş
kopyasıydı (108KB + 32KB) ve iç içe `AGENTS.md` olarak bağlam şişirirdi. Bu
yüzden `skills-lock.json` hash'i dosya ağacıyla ayrışıktır; `npx skills update`
geri indirirse tekrar silin.
