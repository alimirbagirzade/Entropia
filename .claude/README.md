# `.claude/`

Entropia'nın ajanları, invariant skill'leri ve hook'ları artık bir plugin'dir:
**[`plugins/entropia-maintenance/`](../plugins/entropia-maintenance/README.md)**

```bash
/plugin marketplace add .
/plugin install entropia-maintenance@entropia
```

Kurulmadan ajanlar (`entropia-triage`, `entropia-scoped-fix`, `entropia-verifier`),
skill'ler (`entropia-canonical-rules`, `entropia-testing`,
`entropia-regression-check`, `entropia-frontend-parity`) ve plugin'in **öteki**
hook'ları **aktif olmaz**. Kopya bırakılmadı — aynı isim iki kez yüklenmesin diye.
İki **bloklayıcı** guard bu kuralın bilinçli istisnasıdır, aşağıya bak.

**`enabledPlugins` KURULUM DEĞİLDİR — ölçüldü (2026-08-13, bu remote container).**
`settings.json`'daki `extraKnownMarketplaces.entropia` + `enabledPlugins` yalnızca
adın **çözülebildiğini** ve kurulunca etkin sayılacağını söyler; kurulumun kendisi
bir **onay istemi** ister ve remote container etkileşimsizdir, istem yoktur. Ölçüm:
`/root/.claude/plugins/installed_plugins.json` = `{"version":2,"plugins":{}}` — **boş**.
Yani plugin **kurulu değil** ve ajanları/skill'leri/komutları bu oturumda **yüklenmedi**.
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

Aynı zamanda `settings.json` **#651'den beri geçersiz JSON'du** ve ADIM 53'te
onarıldı: o aradaki her oturumda buradaki `docs-history-guard` ve
`ultrareview-advisor` hook'ları hiç koşmuyordu (`scripts/agent-config-gate.mjs`).

Burada kalan tek şey `skills/ponytail-entropia/`: bu çalışmadan önce vardı ve
`CLAUDE.md` ona **yoluyla** atıf yapıyor, o yüzden yeri değişmedi.

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
