# ADIM 26 — Kickoff (ADIM 25 observability kapandıktan sonra)

> Bu belge **ADIM 25 (observability) — PR #622** kapanışında yazıldı.
> Alttaki **paste-ready resume prompt** bloğu temiz bir oturuma yapıştırılacak tohumdur.

---

## Neredeyiz

- **main HEAD `780dc92`** — `ops(observability): add alerts and operator runbooks (#622)`.
- **alembic head `0043_i08_registry_strategy_fks`** — ADIM 25'te migration YOK.
- **`ENGINE_VERSION` değişmedi** · `SHARED_ALLOCATION_STATUS = future_dev` (containment KAPALI).
- Backend **3912 passed / 1 xfailed / 0 failed**, coverage **%93.52** (kapı ≥90).
  Frontend **721 passed / 70 dosya**, **%84.92 line**.
- **xfail sayısı artık 1** (4 değil): `test_research_point_in_time_parity.py:583`, **GH #558**.
  #556 ×2 ve #557 düzeltildi ve normal assert ediyor — bu kapanışta `CLAUDE.md`'deki bayat
  "4 bilinçli xfail" iddiası **düzeltildi**.

---

## ADIM 25'in bıraktıkları — REUSE anchor'ları (kesin sembol adları)

Yeni bir metrik / alert / runbook işine girersen **bunları yeniden yazma, bunlardan geç:**

| Sembol | Dosya | Ne işe yarar |
|---|---|---|
| `_bounded_method` | `backend/src/entropia/apps/api/hardening.py:159` | Ham `request.method`'u bilinen kümeye sıkıştırır; **yeni bir label eklerken deseni budur** |
| `_KNOWN_METHODS` | `backend/src/entropia/apps/api/hardening.py:156` | 7 metot; dışındaki her şey `"other"` → kardinalite tavanı 8 |
| `record_worker_heartbeat` | `backend/src/entropia/application/jobs/heartbeat.py:50` | `app_metadata` upsert'i; **yeni bir liveness sinyali eklemenin yazılmış yolu** |
| `worker_heartbeat_age_seconds` | `backend/src/entropia/application/jobs/heartbeat.py` (okuma ucu `queries/job_gauges.py:73`) | Yaşı hesaplar; **kayıt yoksa `None` döner — 0.0 DEĞİL** |
| `JobGauges.worker_heartbeat_age_seconds` | `backend/src/entropia/application/queries/job_gauges.py:48` | Scrape-time gauge taşıyıcısı |
| `_render_operational_gauges` | `backend/src/entropia/apps/api/routes/metrics.py:63` | **Saf fonksiyon, I/O yok.** `None` → `# TYPE` basar, **örnek satırı basmaz** |
| `_emitted_metric_names` | `backend/tests/contract/test_alert_rules_contract.py:76` | Legal metrik-adı kümesini **expozisyon kodundan türetir** |
| `_referenced_metric_names` | `backend/tests/contract/test_alert_rules_contract.py:104` | Kural dosyasındaki metrik adlarını çıkarır → yeniden adlandırma aynı commit'te kırılır |

Ek anchor'lar: `SCRAPER_PROVIDED` (aynı contract dosyası — scrape'in sağladığı `up` gibi
adlar), `test_absent_is_always_joined_with_on_to_match_label_sets` (PromQL `and on()` regresyon
kapısı), `tests/unit/test_metrics_gauge_rendering.py` (eski gövde **ÖNEK** olarak pinli — altı
mevcut ailenin adı/label'ı/bayt sırası korunur).

**Belge anchor'ları:** `docs/runbooks/METRIC_ALERT_MATRIX.md` **§2** = var olan metrikler,
**§3** = neden latency/saturation SLO alert'i yok, **§4** = **kör nokta haritası** (backlog
değil, uyarı). `docs/runbooks/README.md` = alert → runbook indeksi.

---

## Sonraki tasarım işaretleri

### 1. Otorite sıradaki iş — **PR B: `ItemParticipant` adaptörü + worker call site**

Bu ADIM 25'ten **önce de** sıradaydı ve ADIM 25 motor yoluna dokunmadığı için **değişmedi**.

- `run_portfolio` hâlâ üretimde **çağrısız**. Kapatılacak yer: `jobs/backtest_engine.py:298`
  (item döngüsü) ve `:363` (`combine_item_runs`).
- Stepper indi (**PR #602**): `engine.py::_build_stepper` → `_ItemStepper{step(bar),
  finalize(), output(), open_position(), ledger, ctx}`. **Modül-private, `__all__`'da değil —
  üretimde çağıranı yok**; ona tüketici kazandıran şey PR B'dir.
- **Dürüst sınır (mekanik ikame DEĞİL):** `ItemParticipant.entry` **hazır** bir `ItemIntent`
  ister, ama `form_intent` entry'yi item'ın kendi `StrategyConfig` / `FillCosts`'u olmadan
  ölçemez; ayrıca stepper bir barı **bütün olarak** ilerletirken faz döngüsü aynı barı
  **fazlara bölünmüş** ister. Bu boşluk bir **tasarım** işidir.
- Kabul kapısı: **46 golden digest** (ADR §15 R-4). Ayrıntı:
  `docs/ADIM16_STEPPER_LANDED_KICKOFF.md`.

### 2. Observability devam ettirilecekse (opsiyonel, ADIM 25'in doğal uzantısı)

Sırayla en yüksek getirili kör noktalar (hepsi `METRIC_ALERT_MATRIX.md` §4'te kayıtlı):

1. **`promtool` kapısı** — bugün PromQL **anlamsal olarak doğrulanmıyor**; ölü `and absent()`
   kuralını bir kapı değil insan review'ı yakaladı. En ucuz gerçek kazanç budur.
2. **`prometheus.yml` repoya** — dört alert `job="entropia-api"` scrape adına dayanıyor ve bu
   adı hiçbir şey zorlamıyor.
3. **Backtest metrikleri** — `jobs/backtest_engine.py`'de **logger bile yok**; admission /
   readiness / duration / bars / artifact tamamen görünmez.
4. **`correlation_id` worker log context'ine** — kolon (`Job.correlation_id`) var, bağlayan yok.
5. **structlog redaction processor** — kural bugün elle, call-site bazında uygulanıyor.
6. Agent coordinator · SSE · object storage · backup age · DB pool utilization.

> **Kural:** yeni bir alert yazarken **mutlak latency/throughput hedefi UYDURMA.**
> `docs/performance/README.md:144` p95'i bilerek boş bıraktı. Eşik ya shipped config
> default'unun katı, ya yapısal (seri absent / süreç down), ya da histogram'ın kendi en büyük
> bucket'ı olmalı — ve `test_alert_rules_contract.py`'de `get_settings()`'e karşı pinlenmeli.

### 3. Kayıt borcu (küçük, ucuz)

**ADIM 23 (#610)** ve **ADIM 24 (#619)** main'e indi ama `PROJECT_HISTORY.md`'de kayıtları
**yok**; #620/#621/#614 de kayıtsız. Bir docs slice'ı bunu kapatabilir.

---

## Çalışma yöntemi (bu repoda işleyen döngü)

1. **Doğrula, güvenme.** `git fetch` → `git log --oneline origin/main -8` → `gh pr list`.
   Handoff/kickoff **stale-by-default**.
2. **Kod okumadan önce haritaya sor:** `docs/CODEMAPS/` → `codebase-memory-mcp`
   (`search_graph` / `get_code_snippet` / `trace_path`). Kör grep + tam dosya okuma pahalı.
3. **Tembel merdiven (ponytail):** gerekiyor mu → repoda var mı → stdlib → native → kurulu
   bağımlılık → tek satır. Override listesi (coverage kapısı, katman deseni, adjudicated
   alanlar) **pazarlıksız**: `.claude/skills/ponytail-entropia/SKILL.md`.
4. **Direct-author (Workflow YOK)** backend slice'ları için; önceki slice'ın desenini aynala.
5. **GateGuard:** YENİ dosyayı Bash heredoc ile yaz (`cat > f << 'PYEOF'`); mevcut dosyada
   EDIT/WRITE fact-force tetikler. Oturumun ilk Bash'i de bir kez fact gate tetikler.
6. **Yerel doğrulama:**
   `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
   — `addopts` `--cov-fail-under=90` taşır, **tam suite** koşusu CI kapısını da doğrular.
   **Alt küme koşarken `--no-cov` ekle** (tek dosya paketin tamamını ~%4 ölçer → sahte kırmızı).
   Frontend: `npm run coverage`; vitest'te **`--no-file-parallelism` ZORUNLU**.
7. **Test koşusu tuzakları:** çıktıyı **dosyaya yaz**, `$?`'i **ayrı** oku (`| tail` KULLANMA —
   exit code `tail`'in olur). Tam suite'i **tek pytest çağrısında** koş, ortada öldürme.
   Paralel worktree'ler için `TEST_DATABASE_URL` ile izole DB (**sürücü
   `postgresql+asyncpg://`**).
8. **Kapanış ritüeli** (CLAUDE.md §Session CLOSING): PROJECT_HISTORY (tam kayıt) +
   STAGE2_HANDOFF (landed + Next) + yeni KICKOFF + CLAUDE.md §Current position (**5–6 satır**)
   + iki bellek sistemi + codemap tazeleme + PR.
9. **DOCS REGRESYON KORUMASI:** branch'i **taze `origin/main`'den** aç; commit sonrası
   `git show HEAD -- docs/ | grep '^-## '` **BOŞ** olmalı. Hiçbir CI kapısı `docs/` okumaz;
   bayat base'li docs PR'ları geçmişte **üç kez** kayıt sildi (#590, #604).

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 26

ROL: Entropia V18 üzerinde çalışan kıdemli principal engineer.
Konuşma dili TÜRKÇE; teknik tanımlayıcılar İngilizce kalır.

OTURUM BAŞLANGICI (zorunlu, sırayla):
1. `git fetch --all --prune` · `git status --short` (temiz değilse DUR, stash/silme YOK)
2. `git log --oneline origin/main -8` · `gh pr list --state all --limit 10`
3. main HEAD'in `780dc92` (ADIM 25 / PR #622) veya daha yeni olduğunu doğrula.
   Handoff/kickoff/README iddialarını current truth SAYMA — hepsi stale-by-default.
4. Otorite sırasıyla oku: docs/ADIM26_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md
   ("... landed" + "Next") → docs/STAGE_BUILD_PLAN.md → ilgili docs/spec/NN_*.
5. Koda geçmeden ÖNCE dokunacağın alanın docs/CODEMAPS/ haritasını oku, sonra
   codebase-memory-mcp ile sembolleri bul (kör grep + tam dosya okuma YOK).

DOĞRULANMIŞ DURUM (yeniden keşfetme; doğrula ve kullan):
- main HEAD `780dc92` · alembic head `0043_i08_registry_strategy_fks` (ADIM 25'te migration YOK)
- `ENGINE_VERSION` değişmedi · `SHARED_ALLOCATION_STATUS = future_dev` (containment KAPALI)
- Backend 3912 passed / 1 xfailed / 0 failed · coverage %93.52 (kapı ≥90)
- Frontend 721 passed / 70 dosya · %84.92 line
- xfail sayısı 1'dir (4 DEĞİL): test_research_point_in_time_parity.py:583, GH #558

GÖREV — otorite sıradaki iş: PR B — `ItemParticipant` adaptörü + worker call site.
- `run_portfolio` üretimde ÇAĞRISIZ. Kapatılacak yer: jobs/backtest_engine.py:298 (item
  döngüsü) ve :363 (`combine_item_runs`).
- Stepper hazır (PR #602): engine.py::_build_stepper → _ItemStepper{step(bar), finalize(),
  output(), open_position(), ledger, ctx} — modül-private, üretimde çağıranı YOK.
- DÜRÜST SINIR: bu mekanik bir ikame DEĞİL. `ItemParticipant.entry` HAZIR bir `ItemIntent`
  ister ama `form_intent` entry'yi item'ın kendi StrategyConfig/FillCosts'u olmadan ölçemez;
  ayrıca stepper barı BÜTÜN olarak ilerletirken faz döngüsü aynı barı FAZLARA BÖLÜNMÜŞ ister.
  Bu boşluk bir TASARIM işidir — önce tasarımı yaz, sonra kodu.
- KABUL KAPISI: 46 golden digest sabit kalmalı (ADR §15 R-4). Başka hiçbir şey değil.
- Ayrıntı: docs/ADIM16_STEPPER_LANDED_KICKOFF.md

ALTERNATİF (kullanıcı observability'ye devam demek isterse): en yüksek getirili kör nokta
`promtool` kapısıdır — PromQL bugün anlamsal olarak doğrulanmıyor. Sonra prometheus.yml'i
repoya almak, sonra backtest metrikleri. Kural: MUTLAK LATENCY/THROUGHPUT HEDEFİ UYDURMA
(docs/performance/README.md:144 p95'i bilerek boş bıraktı); eşik ya shipped config
default'unun katı, ya yapısal, ya da histogram'ın kendi en büyük bucket'ı olmalı ve
test_alert_rules_contract.py'de get_settings()'e karşı pinlenmeli.

ÇALIŞMA BİÇİMİ:
- Tembel merdiven (ponytail): gerekiyor mu → repoda var mı → stdlib → native → kurulu
  bağımlılık → tek satır. Override listesi pazarlıksız.
- Direct-author (Workflow YOK); önceki slice'ın desenini aynala.
- GateGuard: YENİ dosyayı `cat > f << 'PYEOF'` ile yaz; mevcut dosyada EDIT fact-force tetikler.
- Yerel doğrulama: cd backend && uv run ruff check . && uv run ruff format --check . &&
  uv run mypy src && uv run pytest -q  (alt küme koşarken --no-cov EKLE)
  Çıktıyı DOSYAYA yaz, `$?`'i AYRI oku — `| tail` KULLANMA. Tam suite tek çağrıda, öldürme.
  Paralel worktree için TEST_DATABASE_URL (sürücü postgresql+asyncpg://).
- Yeni `create_*` varsa L1 FK insert-order kanıtı + alembic up/down/up + kolon paritesi.
- Kod-review CRITICAL/HIGH bulgularını DÜZELTMEDEN ÖNCE ampirik doğrula (çoğu yanlış çıkıyor).

KAPANIŞTA (CLAUDE.md §Session CLOSING — hepsi zorunlu): PROJECT_HISTORY tam kayıt +
STAGE2_HANDOFF landed/Next + yeni KICKOFF (paste-ready prompt ile) + CLAUDE.md §Current
position (SADECE 5–6 satır) + ecc graph & claude-mem checkpoint + codemap tazeleme +
commit/PR. Docs branch'ini TAZE origin/main'den aç; commit sonrası
`git show HEAD -- docs/ | grep '^-## '` çıktısı BOŞ olmalı. Self-merge bloklu — merge'i
kullanıcıdan iste.
```
