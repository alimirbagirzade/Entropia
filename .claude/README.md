# `.claude/`

Entropia'nın ajanları, invariant skill'leri ve hook'ları artık bir plugin'dir:
**[`plugins/entropia-maintenance/`](../plugins/entropia-maintenance/README.md)**

```bash
/plugin marketplace add .
/plugin install entropia-maintenance@entropia
```

Kurulmadan ajanlar (`entropia-triage`, `entropia-scoped-fix`, `entropia-verifier`),
skill'ler (`entropia-canonical-rules`, `entropia-testing`,
`entropia-regression-check`, `entropia-frontend-parity`) ve hook'lar **aktif olmaz**.
Kopya bırakılmadı — aynı isim iki kez yüklenmesin diye.

**ADIM 52:** artık elle kurmak gerekmiyor — `settings.json` `extraKnownMarketplaces` +
`enabledPlugins` ile depoya güvenen oturumda önerilir. Aynı slice `settings.json`'ı
**onarmıştı**: dosya #651'den beri geçersiz JSON'du, yani buradaki `docs-history-guard`
ve `ultrareview-advisor` hook'ları hiç koşmuyordu (`scripts/agent-config-gate.mjs`).

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
