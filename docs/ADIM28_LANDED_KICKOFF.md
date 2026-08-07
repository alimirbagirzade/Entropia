<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı). Devralan kickoff:
> `docs/ADIM29_LANDED_KICKOFF.md`.

# ADIM 28 kapanış devri — A-08 için iskele kuruldu, denetim hâlâ yapılmadı

## Nerede duruyoruz

`main` HEAD **`20e942b`** — "a11y(a08): prepare the human screen-reader acceptance run
(#628)", **MERGED**. Ebeveyni `81336e1` (#629, js-yaml advisory freeze — bu dalganın
unblocker'ı). Öncesi: `610ed20` (#627, ADIM 27 docs), `0e67e9d` (#626, doc-truth kapısı).

Bu slice **ürün koduna dokunmadı**: migration yok, yeni tablo yok, yeni endpoint yok,
yeni sayfa yok, yeni job yok, OpenAPI değişmedi, codemap değişmedi, `.github/workflows/`
hiç dokunulmadı. Alembic head `0043_i08_registry_strategy_fks` sabit; `ENGINE_VERSION`
sabit; `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).

Getirdiği şey bir **iskele**: A-08 insan ekran-okuyucu denetiminin koşulabilmesi için
gereken ortam, defter, bulgu kanalı ve makine-önkoşulları. **Denetimin kendisi YAPILMADI**
ve buradaki hiçbir çıktı denetim olarak kaydedilemez.

## ADIM 28 ne bıraktı — REUSE çapaları (tam sembol adlarıyla)

| Çapa | Ne yapar / neye bağlı |
|---|---|
| `scripts/a11y-audit-stack.sh` | `up \| validate \| status \| down`; izole Compose projesi `entropia-a11y-audit` (`down` başka projeyi reddeder) |
| `scripts/a11y-audit-stack.sh::cmd_validate` | beş adım / **9 kontrol**: `/health/ready` + web, `/meta.auth_mode=session`, Admin + `/me.is_admin`, üç seed fixture'ı satır üretiyor mu, 23 rota servis ediliyor mu |
| `scripts/a11y-audit-stack.sh::cmd_up` · `cmd_down` · `cmd_status` | teardown **EXIT trap DEĞİL**, açık alt komut (tüketici oturum ortasındaki insan) |
| `A11Y_HOST` (env, varsayılan `127.0.0.1`) | tek ayar düğmesi; `0.0.0.0` **hard error** (bind adresi ≠ tarayıcının açacağı adres), LAN'a açarken uyarı basar |
| `.env.a11y-audit` (`ENTROPIA_ENV_FILE`) | hermetik, **git-ignored** ortam; portlar çakışmaz |
| `AUDIT_ROUTES` (script içi dizi) | 23 denetim rotası — kontrat testi bunu `TARGET_PAGES` ile karşılaştırır |
| `docs/audit/a11y_screen_reader_audit_results.md` | çalışma defteri: §0 oturum başlığı, §1 23 rota × 2, §2 10 akış × 2, §3 **16 kolon** + kolon sözleşmesi, §4 retest, §5 çıkış kriterleri, §6 **K-1..K-6** |
| `.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml` | her kolon için alan + **ZORUNLU "duydum" beyanı** + retest checkbox'ları |
| label `accessibility` · `a11y-screen-reader` | bu dalgada repoda AÇILDI; şablon ikisini de basar |
| `frontend/e2e/specs/20-a11y-prechecks.spec.ts` | `@a11y` etiketli → `npm run a11y` (`--grep @a11y`) **otomatik alır**; BLOCKING yapısal + ADVISORY gözlem ayrımı |
| `a11y-report/precheck-results.json` | precheck raporu; **`.gitignore`'da**, CI artifact olarak yüklenir; her kayıt `screen_reader_verified: false` |
| `backend/tests/contract/test_a11y_audit_prep_contract.py` | **21 test**; rota↔`TARGET_PAGES`, akış↔checklist, script seed bayrakları + rota listesi ↔ ikisi, defter sayaçları ↔ kendi hücreleri |
| `frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES` | rota matrisinin **tek kaynağı** — defter satırları buradan üretildi, elle yazılmadı |
| `frontend/e2e/utils/pageTruth.ts:15` | `/user-manual`'ın `<h1>` yerine `<h2 class="page-title">` kullanması **zaten kayıtlı** sapma |
| `scripts/npm-audit-gate.mjs` (freeze listesi) | #629'un eklediği `GHSA-5p4m-2wfm-xmqj` kaydı — gerekçe + **iki bitiş koşulu** |

## Yeni bir a11y işi yaparken uyulacak kural

1. **A-08'i tamamlanmış gösterme.** Defter boş, §5'in dördü de ☐. `check_assertions`'ın
   `A08_COMPLETE` invariant'ı bunu zaten kırmızıya çevirir — ama kapı bir tripwire'dır,
   kural insanındır.
2. **K-2..K-6 birer ürün kararıdır.** Advisory'yi bloklayıcıya çevirmek o kararı ihmalle
   vermek olur. Erişim sayıları bayatlar — düzeltmeden önce precheck'i yeniden koş.
3. Denetim ortamını `scripts/a11y-audit-stack.sh up && … validate` ile kur; `validate`
   kırmızıysa **denetmen zamanı ayırtma**.
4. Bir bulgu ancak **duyulduğunda** bulgudur. Issue şablonunun beyanı boş geçilemez.
5. Yeni belge yazarken **tek `doc-status: current`** kuralı geçerli; sayı yazma,
   `docs/generated/repository_facts.md`'ye referans ver. Artefaktı bayatlattıysan:
   `cd backend && uv run python ../scripts/generate_repository_facts.py --root ..`

## İskelenin KORUMADIĞI şeyler (bilerek)

* **Denetimin kendisi.** Bu slice bir ortam ve bir defter üretti; hiçbir şey *duymadı*.
* `validate` §5 rota kontrolü **shell'in servis edildiğini** kanıtlar, sayfanın kendi
  sorgusunun başarısını **değil** — onu `frontend/e2e/specs/17-page-coverage.spec.ts` iddia eder.
* Precheck **yapısal** ölçer: bir yapının *yararlı biçimde duyurulduğunu* hiçbir DOM probu
  söyleyemez. Raporun kendi damgası: `screen_reader_verified: false`.
* **K-6 (focus indicator)** computed-style ile **karara bağlanamaz**; UA varsayılan halkası
  boyanıyor olabilir. Bu, otomasyonun ilkece çözemeyeceği sınıftır.

## Açık sınırlar (yumuşatılmadı)

* **A-08 YAPILMADI.** Bulgu defterinde tek satır yok; dört çıkış kriteri de ☐
  (`0 / 2` kombinasyon, `0 / 46` rota, `0 / 20` akış). **Boş şablon kanıt değildir.**
* **GitHub #514 kanıtsız KAPATILDI** — 2026-08-07T03:52Z, `state_reason: completed`, her iki
  dalga commit'inden de önce. Kapalı issue ile boş defter arasındaki ayrışma **sürüyor**;
  belgelerin bunu nasıl anlatacağı **ayrı bir slice**. Burada yalnızca not düşüldü.
* **K-2..K-6 ölçüldü, düzeltilmedi:** skip link yok 23/23 · `contentinfo` yok 23/23 ·
  `h1 → h3` atlaması 21/23 · `/user-manual`'da `<h1>` yok · focus indicator görünmüyor.
  (Precheck koşusu: 23 rota, **0 blocking failure, 85 advisory gözlem**.)
* **D-10 sürüyor:** 45 aksan-mavisi düğüm; **WCAG 2.2 AA 1.4.3 karşılanmıyor**. AA iddiası yok.
* **İki ÖNCEDEN VAR OLAN kararsızlık:** `14-keyboard-flow` 4 koşudan 1'inde autofocus
  yarışında düştü; `13-a11y-scan` ilk denemede **gerçek** bir ratchet ihlali verdi
  (`arrange-metrics`: `color-contrast` 4 düğüm vs baseline 2), retry'da 2 ölçtü. O sayfayı
  yeşil tutan şu an `playwright.config.ts:22` → `retries: process.env.CI ? 1 : 0`.
* **Alertmanager YOK** — ADIM 25/26 alert kuralları ateşliyor ama **kimseye ulaşmıyor**.
* **`PROJECT_HISTORY.md`'de ADIM 23 ve ADIM 24 hâlâ KAYITSIZ.**
* **Documentation-truth kapısı silmeyi görmez.** Docs PR'ı merge etmeden önce elle:
  `git show <sha> -- docs/ | grep '^-## '` (bu repoda üç kez kayıt silindi — #590, #604).
* **Memory checkpoint YAZILAMADI (ritüelin 4. maddesi), ADIM 27 ile aynı sebep:** ne ecc
  knowledge graph MCP'si (`create_entities` / `create_relations`) ne de `claude-mem` bu
  oturumda bağlıydı. Bu slice bellekten aranamaz — kaynağı `docs/PROJECT_HISTORY.md`
  §ADIM 28 ve bu belgedir. Bağlandığında geriye dönük yazılabilir: entity
  `Entropia ADIM 28 — A-08 audit preparation`, ilişki `unblocks` → PR B.

## Sıradaki TEK adım

**PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**
`run_portfolio` üretimde hâlâ **çağrısız**; `:363` `combine_item_runs`;
`SHARED_ALLOCATION_STATUS` = `future_dev`. ADIM 20 matrisindeki A1/A3/A5 dışında hiçbir
satır bu boşluk kapanmadan kapanamaz. Stepper indi (#602); kalan borç **adaptör + call site**.
Tasarım işaretleri: `docs/ADIM16_STEPPER_LANDED_KICKOFF.md`, `docs/ADIM26_KICKOFF.md`.

**A-08 ayrı eksendir ve PR B'yi bloklamaz** — insan denetimi bir insan takvimi ister.

**Yarım-cent yuvarlama** 2026-08-06'da KARARA BAĞLANDI ama **UYGULANMADI**:
`initial_sleeve_capital` yeniden quantize edilmez, dondurulmuş `derived_amounts`'tan
**kopyalanır**; iki yuvarlama sabiti de değişmez. Ayrıntı: `STAGE2_HANDOFF.md` §Yarım-cent.

## Çalışma yöntemi (değişmedi)

Direct-author, Workflow yok. Önceki slice'ın desenini aynala. Yerel doğrulama:

```
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
```

Alt küme koşarken `--no-cov` ekle. Frontend karşılığı `npm run coverage`
(vitest'te `--no-file-parallelism` zorunlu). Paralel worktree oturumlarında
`TEST_DATABASE_URL` ile izole DB kullan (sürücü `postgresql+asyncpg://`).
Tam suite'i **tek pytest çağrısında** koş, `| tail` KULLANMA (exit code `tail`'in olur).

---

## Paste-ready resume prompt

```
ENTROPIA V18 — PR B: ItemParticipant adaptörü + engine call site

ROL
Sen Entropia V18 üzerinde çalışan kıdemli principal engineer'sın. Konuşma dili
Türkçe, teknik tanımlayıcılar İngilizce.

ZORUNLU BAŞLANGIÇ
1. git fetch --all --prune && git status --short  → temiz değilse DUR
2. git log --oneline origin/main -6 ; gh pr list --state all --limit 5
3. Oku: docs/ADIM28_LANDED_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md
   §Next → docs/ADIM16_STEPPER_LANDED_KICKOFF.md → docs/CODEMAPS/JOBS_AND_EVENTS.md
4. SAYISAL OTORİTE: docs/generated/repository_facts.md (üretilmiş, CI'da kapılı).
   CLAUDE.md §Current position'daki HEAD sha'sı yapısal olarak bayattır.
5. Kod okumadan önce codebase-memory-mcp (search_graph / trace_path /
   get_code_snippet) — kör grep + tam dosya okuma yok.

İŞ
PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.
`run_portfolio` üretimde çağrısız; `:363` `combine_item_runs`;
`SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI). ADIM 20
matrisindeki A1/A3/A5 dışında hiçbir satır bu boşluk kapanmadan kapanamaz.
Stepper #602'de indi; kalan borç adaptör + call site.

KURALLAR
- Direct-author (Workflow YOK); önceki slice'ın desenini aynala: module-level
  async command, one-tx no-commit, `run_idempotent`,
  `session.refresh(with_for_update=True)`, `_audit_and_outbox`.
- Tembel merdiven (ponytail-entropia): gerekiyor mu → codebase'de var mı →
  stdlib → kurulu bağımlılık. Coverage kapısı ve katman deseni pazarlıksız.
- Yerel doğrulama: cd backend && uv run ruff check . && uv run ruff format
  --check . && uv run mypy src && uv run pytest -q  (kapı %90)
  + yeni her `create_*` için L1 FK insert-order kanıtı + alembic up/down/up.
- Kod-review CRITICAL/HIGH bulgularını DÜZELTMEDEN ÖNCE empirik doğrula.
- GateGuard: YENİ dosyayı Bash heredoc ile yaz; mevcut dosyada Edit fact-force
  tetikler (4 olgu sun, tekrar dene).
- Yeni belge yazarken: tek `doc-status: current` kuralı geçerli; sayı yazma,
  docs/generated/repository_facts.md'ye referans ver.
- A-08 YAPILMADI ve #514 kanıtsız kapatıldı — hiçbir belgeye A-08 için
  `Complete`/`PASS` YAZMA. Başarısız test varken de `Complete` yazma.

KAPANIŞTA
CLAUDE.md §Session CLOSING ritüelinin 6 maddesi + kapanış PR'ında:
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  git diff origin/main -- docs/ | grep '^-## '   → BOŞ olmalı
```
