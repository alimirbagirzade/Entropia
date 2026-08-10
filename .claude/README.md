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

Burada kalan tek şey `skills/ponytail-entropia/`: bu çalışmadan önce vardı ve
`CLAUDE.md` ona **yoluyla** atıf yapıyor, o yüzden yeri değişmedi.
