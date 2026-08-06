<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 27 kapanış devri — belgeler artık ağaca karşı kapılı

## Nerede duruyoruz

`main` HEAD **`0e67e9d`** — "ci(docs): prevent repository fact drift (#626)", **MERGED**.
Öncesi: `7a9be2d` (#625, ADIM 26 docs), `c859f1c` (#624, promtool gate). Üçü de merged.

Bu slice **ürün koduna dokunmadı**: migration yok, yeni tablo yok, yeni endpoint yok,
yeni sayfa yok, yeni job yok. Alembic head `0043_i08_registry_strategy_fks` sabit;
`ENGINE_VERSION` sabit; `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).

Getirdiği tek şey bir **kapı**: belgelerin ileri sürdüğü olgular artık çalışma ağacından
üretiliyor ve CI'da karşılaştırılıyor. Sayısal otorite bundan sonra elle yazılan hiçbir
paragraf değil, **`docs/generated/repository_facts.md`**'dir.

## ADIM 27 ne bıraktı — REUSE çapaları (tam sembol adlarıyla)

**Üretici: `scripts/generate_repository_facts.py`** (873 satır, tek dosya, bağımlılıksız).

| Sembol | Ne yapar |
|---|---|
| `collect_facts(root)` | on olgu ailesini tek sözlükte toplar; alt toplayıcıları çağırır |
| `collect_alembic` · `collect_database` · `collect_http_api` | head + revision sayısı · tablo/FK · path/operation |
| `collect_frontend_routes` · `collect_engine_and_capabilities` | router path + nav item · `ENGINE_VERSION`, capability matrisi |
| `collect_tests` · `collect_acceptance` · `collect_visual_and_deviations` | **collection** sayıları · kriter/clause · PNG/baseline/sapma |
| `render_markdown` · `render_json` · `render_readme_block` · `splice_readme` | üç artefaktın tek kaynaktan üretimi |
| `check_artifacts` | `docs/generated/repository_facts.{json,md}` + README bloğu bayat mı |
| `check_classification` | `doc-status` işareti var mı · **tam olarak bir** `current` · history/audit asla `current` |
| `check_assertions` | güncel belgede ağacın yalanladığı head / `ENGINE_VERSION` / `SHARED_ALLOCATION_STATUS` |
| `CLASSIFIED_GLOBS` · `ALWAYS_HISTORICAL_GLOBS` | hangi belge sınıflandırılmak zorunda · hangisi asla `current` olamaz |
| `HISTORICAL_BANNER` · `CURRENT_BANNER` | banner metinleri — **yeni belge yazarken buradan birebir kopyala** |
| `PRESENT_TENSE_GLOBS` · `INVARIANT_GLOBS` | şimdiki zaman okunan yüzeyler · invariant taramasının kapsamı |
| `INVARIANT_RULES` | beş yasak eşitleme: `A08_COMPLETE` · `WCAG_CONFORMANCE` · `RUN_IS_RESULT` · `SIGNAL_IS_PACKAGE` · `FUTURE_DEV_ACTIVE` |
| `NEGATION_RE` · `HISTORICAL_HEDGE_RE` | iddiayı **reddeden** ve kendini **geçmiş** olarak çerçeveleyen satırları muaf tutar |

**Kapı: `.github/workflows/ci.yml` → backend job → adım
`Documentation truth gate (generated repository facts)`**, OpenAPI drift guard'ından
SONRA (route olguları o adımın ürettiği şemadan okunur). Komut:

```
cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```

**Testler: `backend/tests/contract/test_repository_facts_guard.py`** — 28 case
(16 `def test_`, geri kalanı parametrize genişlemesi).

**Sınıflandırılmış belgeler:** 77 belge `doc-status` işareti aldı — 76 `historical`,
**1 `current`** (bu slice'tan önce `docs/ADIM26_LANDED_KICKOFF.md`, bu kapanışla **bu
dosya**). #626'daki 77 dokunuşun tamamı saf eklemeydi (76×+6/−0, 1×+4/−0, sıfır silme).

## Yeni belge yazarken uyulacak kural (kapı bunu zorlar)

1. Yeni kickoff `CURRENT_BANNER` ile **başlar**; bir öncekini **aynı commit'te**
   `HISTORICAL_BANNER`'a çevir. İki `current` = kırmızı CI.
2. Sayı yazma, **referans ver**: `docs/generated/repository_facts.md`. Elle yazılan
   sayı bayatlar — bu repoda tam olarak böyle oldu (102 vs 104 tablo, "4 xfail" vs 1).
3. Head / `ENGINE_VERSION` / `SHARED_ALLOCATION_STATUS` yazacaksan ağacın değerini yaz,
   ya da satırı `HISTORICAL_HEDGE_RE`'nin tanıdığı bir ifadeyle geçmişe çerçevele.
4. Artefaktı bayatlattıysan yeniden üret:
   `cd backend && uv run python ../scripts/generate_repository_facts.py --root ..`

## Kapının KORUMADIĞI şeyler (bilerek — tripwire, kanıt değil)

* **Commit sha, timestamp, GitHub durumu** (açık PR/issue, workflow run) kapsam dışı:
  bunlar sunucunun özelliği, ağacın değil. `CLAUDE.md`'nin "PR #624 AÇIK" yalanını kapı
  **yakalayamadı**, elle düzeltildi.
* **Test PASS sayısı** kapsam dışı. Her test sayısı bir *collection* sayısıdır ve adı
  bunu söyler. Pass sayısını yalnızca tam bir CI koşusu bildirir.
* **İki olgu hâlâ elle sayılı:** audit `event_kind` 126 literal, frontend 31 sayfa /
  40 `lib/*.ts`. Kapı bunlara dokunmaz.
* `INVARIANT_RULES` **regex tabanlıdır** — aynı yalanı farklı cümleyle yazan metni kaçırır.
* Üretici `entropia`'yı import eder → yalnız backend venv'inde koşar. Salt-docs
  katkıcısı artefaktı yeniden üretemez.

## Açık sınırlar (yumuşatılmadı)

* **Alertmanager YOK.** ADIM 25/26 alert kuralları doğru ateşliyor ama **kimseye
  ulaşmıyor**; `severity: page` hiçbir alıcının okumadığı bir etiket.
* **`PROJECT_HISTORY.md`'de ADIM 23 ve ADIM 24 hâlâ KAYITSIZ** (dürüst not, kapatılmadı).
* Ekran okuyucu (NVDA/VoiceOver) denetimi **YAPILMADI** — GitHub #514 açık; kapatma
  yetkisi insandadır.
* **D-10 imzalı kalıcı kontrast sapması:** WCAG 2.2 AA 1.4.3 karşılanmıyor.
* Docs regresyonu bu repoda **üç kez** oldu (#590, #604). Hiçbir CI kapısı `docs/`
  içeriğini *silinmeye* karşı okumaz — `check_classification` yalnız sınıflandırmayı
  görür. Docs PR'ı merge etmeden önce hâlâ elle:
  `git show <sha> -- docs/ | grep '^-## '`
* **ADIM 27 kapanışında memory checkpoint YAZILAMADI — ritüelin 4. maddesi eksiktir.**
  Ne ecc knowledge graph MCP'si (`create_entities` / `create_relations`) ne de `claude-mem`
  bu oturumda bağlıydı; bağlı olan tek bellek sunucusu `codebase-memory-mcp` (kod grafiği),
  ve o bir slice checkpoint'i tutmaz. Sonraki oturum bu slice'ı bellekten **bulamayacak** —
  kaynak `docs/PROJECT_HISTORY.md` §ADIM 27 ve bu belgedir. İki sunucu bağlandığında
  geriye dönük yazılabilir: entity `Entropia ADIM 27 — documentation-truth CI`, ilişki
  `unblocks` → PR B.

## Sıradaki TEK adım

**PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**
`run_portfolio` üretimde hâlâ **çağrısız**; `:363` `combine_item_runs`;
`SHARED_ALLOCATION_STATUS` = `future_dev`. ADIM 20 matrisindeki A1/A3/A5 dışında hiçbir
satır bu boşluk kapanmadan kapanamaz. Stepper indi (#602); kalan borç **adaptör + call site**.
Tasarım işaretleri: `docs/ADIM16_STEPPER_LANDED_KICKOFF.md`, `docs/ADIM26_KICKOFF.md`.

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
3. Oku: docs/ADIM27_LANDED_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md
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
  --check . && uv run mypy src && uv run pytest -q  (kapı %90, ölçülen ~%93.5)
  + yeni her `create_*` için L1 FK insert-order kanıtı + alembic up/down/up.
- Kod-review CRITICAL/HIGH bulgularını DÜZELTMEDEN ÖNCE empirik doğrula.
- GateGuard: YENİ dosyayı Bash heredoc ile yaz; mevcut dosyada Edit fact-force
  tetikler (4 olgu sun, tekrar dene).
- Yeni belge yazarken: tek `doc-status: current` kuralı geçerli; sayı yazma,
  docs/generated/repository_facts.md'ye referans ver.
- Başarısız test varken hiçbir belgeye `Complete` YAZMA. Sen merge etmezsin.

KAPANIŞTA
CLAUDE.md §Session CLOSING ritüelinin 6 maddesi + kapanış PR'ında:
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  git diff origin/main -- docs/ | grep '^-## '   → BOŞ olmalı
```
