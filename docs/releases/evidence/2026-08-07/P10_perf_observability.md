<!-- doc-status: historical -->
> **EVIDENCE RECORD — 2026-08-10.** Bu belge o gün, `7926490` ağacı üzerinde koşulan
> performans bütçesi ve gözlemlenebilirlik doğrulamasının kaydıdır. Sayılar koşuldukları
> anın değerleridir; güncel sayısal otorite `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı). Dosya adı P10'un ait olduğu ADIM 29 kanıt
> dizinini (`2026-08-07`) korur; koşu tarihi 2026-08-10'dur.

# ADIM 29 / P10 — Performans bütçeleri ve gözlemlenebilirlik

**Verdict: PARTIAL — 5 PASS + 1 KAPANMAMIŞ GÖZLEMLENEBİLİRLİK BOŞLUĞU + 2 kayıt bulgusu.**

| # | Başlık | Sonuç |
|---|---|---|
| 1 | `performance.yml` → `load-smoke` adımları yerelde | **PASS** — 17/17 senaryo, `err=0`, SSE bağlandı, exit 0 |
| 2 | Query bütçeleri (N+1 kapısı) çalışıyor mu | **PASS (kapı olarak)** — 8 test yeşil, bütçe aşımı yok |
| 2b | Kod tabanında N+1 var mı | **VAR — iki tanesi bilerek kayıtlı, ama izleme issue'ları KAPALI** → §3.3 (Bulgu **P10-B1**) |
| 3 | Sayfalama sınırları uygulanıyor mu | **PASS (runtime)** — her `limit` 100'de kelepçeli; 9 uçta sınır **şemada yayımlanmıyor** (Bulgu **P10-B2**) |
| 4 | `scripts/alert-rules-gate.sh` (promtool) | **PASS** — `check config` + `check rules` + `test rules`, 11 kural, exit 0 |
| 5 | Her alarmın runbook linki var mı | **PASS** — 11/11 alarm, dosya **var** ve alarmı **adıyla anıyor** |
| 6 | Alertmanager | **YOK — kapanmamış boşluk.** Kurallar ateşliyor, kimseye ulaşmıyor → §5 |

**Bu koşu salt-okumadır.** Hiçbir kaynak dosya, workflow, alarm kuralı veya runbook
değiştirilmedi; yalnız bu belge ve yanındaki ham log/JSON dosyaları eklendi. Hiçbir GitHub
issue açılmadı/kapatılmadı — §3.3'teki issue-durum çelişkisinin çözümü **insan işidir**.

## Ağaç ve ortam

| | |
|---|---|
| HEAD | `7926490` — `git fetch` sonrası `origin/main` ile **birebir aynı** |
| Branch | `claude/perf-budgets-observability-e91c92` (worktree) |
| Working tree | temiz (yalnız bu dizindeki yeni kanıt dosyaları untracked) |
| Python | 3.12.13 (CPython) · pytest 9.1.1 · pytest-asyncio (`Mode.AUTO`) |
| PostgreSQL | 16.14 (Homebrew), `localhost:5432` |
| İzole DB'ler | `entropia_p10_test` (bütçe testleri) · `entropia_p10_load` (load smoke, `alembic upgrade head` ile taze kuruldu) |
| Alembic head | `0043_i08_registry_strategy_fks` — migration koşusunda doğrulandı |
| Docker | CLI 29.4.0 / **daemon 29.4.0 AYAKTA** (OrbStack bu oturumda başlatıldı) — P8'in `daemon cevapsız` engeli **bu koşuda yok** |
| Runner class | `local-darwin-arm64-dev-laptop` — **CI baseline'ı ile karşılaştırılamaz** (`docs/performance/README.md` §2) |

> **Alt-küme koşusu → `--no-cov`.** Üç pytest çağrısının üçü de `--no-cov` taşıdı; kapı
> (`--cov-fail-under=90`) yalnız tam suite koşusunda anlamlıdır. **Bu belge coverage
> iddiası taşımaz** — o P1'in işidir.

Ham kanıt dosyaları (aynı dizin):

| Dosya | İçerik |
|---|---|
| `p10_query_budgets_and_alert_contract.txt` | 66 passed / exit 0 (8 bütçe + 58 alarm sözleşmesi) |
| `p10_loadgen_smoke.txt` · `p10_loadgen_smoke.json` | load smoke konsol çıktısı + tam rapor |
| `p10_loadgen_unit.txt` | `test_loadgen.py` 32 passed / exit 0 |
| `p10_alert_rules_gate.txt` | promtool üç geçiş, exit 0 |
| `p10_n_plus_one_probe.txt` | N+1 kaynak kanıtı + issue durumları |
| `p10_pagination_bounds.txt` | limit parametreleri ve kelepçe yerleri |

---

## 1. `performance.yml` — hangi adım nerede koşulabilir

Workflow iki iş taşıyor ve **ikisi aynı şeyi ölçmüyor**:

| Job | Tetikleyici | Yerelde koşuldu mu |
|---|---|---|
| `load-smoke` | push + PR (**bloklayıcı**) | **EVET** — adım adım aynalandı (§2) |
| `load-full` | nightly 04:23 UTC + manual | **HAYIR** — tam Compose yığını + golden seed ister; bu koşunun kapsamı dışı |
| `nightly-failure-notice` | yalnız cron başarısızlığında | koşulmadı (tetiklenmedi) |

DB round-trip bütçeleri **bu workflow'da değil**; sıradan integration testi olarak
`ci.yml`'in pytest adımında koşuyor. Bu ayrım bilinçli ve `docs/performance/README.md`
§1'de gerekçeli: *round-trip sayıları deterministik, milisaniyeler değil.*

**CI gerçekten koşuyor.** P4'ün "hiçbir CI workflow'u koşmuyor" bulgusunun aksine
`Performance` workflow'u son 8 koşuda **8/8 success** (en son main push `31350909899`,
1m17s; gecelik `31296683657`, 2m38s). `ci.yml`'deki `Alert rules — promtool` job'ı da
son iki main koşusunda **success**.

## 2. Load smoke — 17/17 senaryo, sıfır hata

CI job'ının adımları yerelde birebir aynalandı: taze DB → `alembic upgrade head` →
`AUTH_MODE=session` ile uvicorn → bootstrap admin signup (HTTP 201, rol `admin`) →
`loadgen.py --profile smoke --concurrency 4 --repeats 5 --sse-seconds 5`.

**Redis kasten ölü porta bağlandı** (`redis://127.0.0.1:59999/0`) — CI job'ının
yorumundaki iddiayı sınamak için: *hiçbir okuma senaryosu iş kuyruğa atmıyor veya artefakt
çekmiyor.* İddia **doğrulandı**: 17 senaryonun tamamı ve SSE probu Redis olmadan cevap verdi.

```
  meta                 n=5  err=0   p50=3.559ms   p95=4.715ms
  mainboard            n=5  err=0   p50=13.402ms  p95=32.5ms
  library              n=5  err=0   p50=11.524ms  p95=41.284ms
  library_shared       n=5  err=0   p50=9.395ms   p95=35.465ms
  results_history      n=5  err=0   p50=9.288ms   p95=38.411ms
  strategy_drafts      n=5  err=0   p50=7.005ms   p95=10.343ms
  market_datasets      n=5  err=0   p50=7.166ms   p95=13.161ms
  research_datasets    n=5  err=0   p50=9.429ms   p95=14.623ms
  instruments          n=5  err=0   p50=8.296ms   p95=16.732ms
  capabilities         n=5  err=0   p50=9.177ms   p95=22.803ms
  agent_tasks          n=5  err=0   p50=7.709ms   p95=20.674ms
  agent_overview       n=5  err=0   p50=11.264ms  p95=25.523ms
  hypotheses           n=5  err=0   p50=12.866ms  p95=17.547ms
  lab_messages         n=5  err=0   p50=6.974ms   p95=19.639ms
  audit_events         n=5  err=0   p50=7.42ms    p95=23.818ms
  admin_logs           n=5  err=0   p50=6.838ms   p95=47.838ms
  trash_entries        n=5  err=0   p50=9.036ms   p95=24.235ms
loadgen: OK      (exit 0)
```

SSE: `connects=1, reconnects=0, transport_disconnects=0, events_received=0` —
0 event **beklenen**: hiçbir iş üretilmedi ve outbox relay'i sürecek scheduler yok.

Sürücünün kendi mantığı da yeşil: `test_loadgen.py` **32 passed / exit 0** — bu test
her senaryonun `docs/openapi.json`'da hâlâ çözüldüğünü de pinliyor.

> **Bu milisaniyeler bir bütçe değildir.** `runner_class = local-darwin-arm64-dev-laptop`;
> `README.md` §2 bu sınıfı CI baseline'ı ile **karşılaştırılamaz** ilan ediyor. Buradaki
> tek sert kapı **`err=0`**, ve o karşılandı. Raporun `not_measured` alanı da kendi
> sınırlarını sayıyor: `api_rss_and_cpu`, `backtest_run_admission`,
> `ready_check_admission`, `worker_throughput`.

## 3. Query bütçeleri — kapı çalışıyor, iki N+1 hâlâ canlı

### 3.1 Kapı yeşil

`tests/integration/test_query_budgets.py` → **8 passed**, hiçbir bütçe aşılmadı.
`tests/contract/test_alert_rules_contract.py` ile birlikte **66 passed / exit 0**.

Kapının üç ayrı iddiası var ve üçü de koşuldu: `queries_small` tavanı, `queries_large`
tavanı ve **eğim** (`per_item`) — sonuncusu asıl N+1 kapısıdır: `per_item 0` kayıtlı bir
yüzey satır başına okumaya başlarsa, küçük-n toplamı değişmese bile kırmızıya döner.

### 3.2 Sıfır-eğimli (N+1 içermeyen) dört yüzey

| Yüzey | n=1 → n=11 | `per_item` |
|---|---|---|
| `library.list_packages` | 3 → 3 | 0 |
| `results_history.list_backtest_results` | 6 → 6 | 0 |
| `agent_workspace.list_tasks` | 1 → 1 | 0 |
| `audit_log.list_audit_events` | 1 → 1 | 0 |

### 3.3 Bulgu P10-B1 — iki N+1 canlı, izleme issue'ları KAPALI

`docs/performance/query_budgets.json` iki satırı **"OPEN N+1, recorded not blessed"**
olarak taşıyor ve her ikisi de bir GitHub issue'suna işaret ediyor:

| Yüzey | n=1 → n=11 | `per_item` | Kayıtlı issue |
|---|---|---|---|
| `readiness_check.market_data_leg` | 2 → **12** | **1** | #617 |
| `dependency_pins.ensure_pinned_resolvers_active` | 2 → **22** | **2** | #618 |

**Empirik doğrulama (çıkarım değil):**

1. Test `-s` ile koşuldu. Bütçenin **altına** düşen bir yüzey
   `[query-budget] … came in under budget` satırı bastırır. Çıktıda bu satır
   **0 kez** geçiyor → ölçülen sayılar bütçeye **eşit**, yani düşmemişler.
2. Kaynak hâlâ döngü içinde per-item await taşıyor:
   * `commands/readiness_check.py:401-406` → `for item in items:` … `await market_repo.get_dataset_root(...)`
   * `queries/dependency_pins.py:114-115` → `for ref in pinned_resolver_refs(...)` → `_pin_defect`,
     içinde **iki** await (`esp_repo.get_registry_by_key:80`, `pkg_repo.get_revision:91`).

**Çelişki:** her iki issue de `CLOSED / COMPLETED`.
#617 açılış 2026-08-06 06:47 → kapanış aynı gün 08:55; #618 açılış 2026-08-06 06:47 →
kapanış 2026-08-07 03:53. Kapatan: repo sahibi. Yorum yok.

Yani kod düzeltilmemiş, bütçe dosyası hâlâ "OPEN N+1" diyor, **izleme kapalı**. Bu
**#514 (a11y) ile aynı şekildeki** bir ayrışmadır: *iş açık, izleme kapalı.* Bu belge onu
**çözmüyor, KAYDEDİYOR** — issue yeniden açmak insan kararıdır ve bir agent bunu yapamaz.

Etkisi ölçülmüş ve sınırlı: `readiness_check` bir kullanıcının **beklediği sayfada**
composition'daki Strategy sayısı kadar round-trip ekliyor (asıl kanayan yer);
`dependency_pins` ise admin eylemi ve pin sayısı paketin bildirdiği çağrılarla sınırlı.
Bütçe kapısı **regresyonu** durduruyor — mevcut N+1'i onaylamıyor, dondurup görünür tutuyor.

## 4. Sayfalama sınırları

**Uygulanıyor — runtime'da istisnasız.** Ama iki katmanda, ve bu ayrım şemaya sızıyor.

* **19 route parametresi** sınırı FastAPI katmanında ilan ediyor:
  `limit: int = Query(default=20, ge=1, le=100)`. Ortak sabitler
  `shared/pagination.py`: `DEFAULT_LIMIT=20`, `MAX_LIMIT=100`.
* **9 route parametresi** (`agent_lab` ×4, `admin_panel` ×3, `capability` ×2) `le=`
  taşımıyor: `limit: int | None = Query(default=None)`. **Bunlar sınırsız değil** —
  hepsi sorgu katmanında kelepçeleniyor:
  * `domain/agent_lab/cursor.py::clamp_limit` → `min(limit, MAX_PAGE_LIMIT=100)`, `None → 20`
    (çağıranlar: `agent_workspace` ×3, `capability` ×2, `user_registry`, `trash`,
    `manual` ×2, `agent_tool_gateway`)
  * `queries/log_projection.py::_clamp_limit` → `MAX_LOG_LIMIT=100`
  * `queries/panel_backtest_log.py::_clamp_limit` → `MAX_BACKTEST_LOG_LIMIT=100`

Sayfalı uçların 24'ü **keyset cursor** kullanıyor (`cursor` + `has_more`), offset değil —
derin sayfalamada tarama patlaması yok. `limit` taşıyıp `cursor` taşımayan **dört** uç var
ve dördü de bilinçli sınırlı listedir, sınırsız değil:

| Uç | Sınır | Not |
|---|---|---|
| `backtest.py::list_backtest_run_events` | `le=500` | cursor yerine `last_sequence` (sıra numarası) ile ilerliyor |
| `strategy.py::list_strategy_revisions` | `le=500` | tek root'un revizyon listesi; **tavan 100 değil 500** |
| `rationale.py::suggest_families` | route `le=100`, sorguda `SUGGEST_MAX_LIMIT=25` | daha sıkı olan kelepçe kazanıyor |
| `agent_lab.py::list_task_tool_calls` | `clamp_limit` → 100 | route'ta `le=` yok (aşağıdaki 9'dan biri) |

### Bulgu P10-B2 — sınır çalışıyor ama sözleşmede yayımlanmıyor

Bu 9 uç için `docs/openapi.json` hiçbir üst sınır bildirmiyor:

```
/api/v1/admin/logs  -> limit: {"anyOf":[{"type":"integer"},{"type":"null"}]}
/api/v1/admin/users -> limit: {"anyOf":[{"type":"integer"},{"type":"null"}]}
```

Sonuç: `limit=100000` gönderen bir istemci **reddedilmez, sessizce 100'e indirilir**.
Kaynak tüketimi açısından güvenli (kelepçe fail-safe), sözleşme açısından yanıltıcı —
`le=100` taşıyan 19 uç 422 verirken bu 9 uç 200 verir. **Kusur değil, tutarsızlık;**
düzeltmesi `le=MAX_LIMIT` eklemek ve tek satırlık, ama bu salt-okuma koşusunun kapsamı dışı.

## 5. Alarm kuralları — geçerli, değerlendirilmiş, **ve kimseye ulaşmıyor**

### 5.1 promtool kapısı: PASS

`scripts/alert-rules-gate.sh` digest-pinli `prom/prometheus@sha256:63805ebb…` (v3.5.0)
ile üç geçiş koştu, **exit 0**:

```
==> promtool (v3.5.0) check config   → SUCCESS: 1 rule files found; config valid
==> promtool check rules             → SUCCESS: 11 rules found
==> promtool test rules              → SUCCESS
==> alert rules OK
```

Üçüncü geçiş kritik olan: kurallar **sentetik serilere karşı değerlendiriliyor**
(`ops/alerts/entropia.rules.test.yml`), yani ADIM 25'te sevk edilen
`up{...} == 1 and absent(...)` biçimindeki **hiç ateşleyemeyen** kural bugün bu kapıda
kırmızı verir. Metin düzeyindeki sözleşme testi de yeşil: **58 passed**, ki bu
`test_every_alert_has_an_evaluated_firing_case` ve
`test_every_job_matcher_names_a_declared_scrape_job`'ı içeriyor.

### 5.2 Runbook kapsaması: 11/11

Sözleşme testi runbook dosyasının **var olduğunu** pinliyor
(`test_every_alert_points_at_a_runbook_that_exists`). Bu koşu bir adım öteye gitti ve
runbook'un alarmı **adıyla andığını** da doğruladı:

| Alarm | severity | `runbook` | Alarmı adıyla anan runbook(lar) |
|---|---|---|---|
| `EntropiaApiDown` | **page** | `api.md` | api, postgres, migration, README, MATRIX |
| `EntropiaApiServerErrors` | **page** | `api.md` | api, object-storage, README, MATRIX |
| `EntropiaMetricsDatabaseProbeFailing` | **page** | `postgres.md` | postgres, README, MATRIX |
| `EntropiaWorkerHeartbeatStale` | **page** | `worker-down.md` | worker-down, outbox-lag, redis, README, MATRIX |
| `EntropiaWorkerHeartbeatNeverRecorded` | **page** | `worker-down.md` | worker-down, README, MATRIX |
| `EntropiaJobLeaseStuck` | **page** | `stale-jobs.md` | stale-jobs, backtest, README, MATRIX |
| `EntropiaOutboxLagSevere` | **page** | `outbox-lag.md` | outbox-lag, README, MATRIX |
| `EntropiaApiRequestsExceedLargestBucket` | ticket | `api.md` | api, postgres, README, MATRIX |
| `EntropiaQueueNeverDrains` | ticket | `stale-jobs.md` | stale-jobs, worker-down, backtest, redis, agent-coordinator, README, MATRIX |
| `EntropiaJobsFailingTerminally` | ticket | `stale-jobs.md` | stale-jobs, README, MATRIX |
| `EntropiaOutboxLagGrowing` | ticket | `outbox-lag.md` | outbox-lag, worker-down, README, MATRIX |

**7 page + 4 ticket = 11.** Boşta kalan alarm yok; ölü link yok. Her kural ayrıca
`derivation` taşıyor ve eşiği shipped bir config default'unun katı olarak gerekçelendiriyor
(`SCHEDULER_TICK_SECONDS=30`, `JOB_STALE_AFTER_SECONDS=600`,
`JOB_REDELIVER_GRACE_SECONDS=600`, histogram'ın en büyük kovası `5.0`) — çünkü Entropia'nın
**adjudicated bir latency/throughput hedefi yok** ve hiçbir kuralın uydurma yetkisi yok.

### 5.3 DÜRÜST SINIR — **Alertmanager YOK**

Bu, bu koşunun en önemli çıktısıdır ve bir test başarısızlığı değildir — **hiçbir otomatik
kapı bunun için kırmızıya dönemez**, tam da bu yüzden burada açıkça yazılmalıdır.

**Olgu:** repo hiçbir Alertmanager sevk etmiyor. `ops/prometheus/prometheus.yml` içinde
**`alerting:` bloğu bilerek yok** (dosya başlığı bunu kendi kelimeleriyle söylüyor);
`docker-compose.yml`'de Prometheus servisi de yok. Repo genelinde bir receiver, bir routing
ağacı, bir silence yapılandırması, bir on-call entegrasyonu bulunmuyor.

**Sonuç zinciri — nerede kopuyor:**

```
metrik üretimi  →  scrape config  →  kural değerlendirme  →  ateşleme  →  BİLDİRİM  →  insan
   ✅ 7 aile        ✅ entropia-api    ✅ promtool PASS       ✅ 11/11      ❌ YOK      ❌ ulaşmıyor
```

`severity: page` ve `severity: ticket` **hiçbir şeyin okumadığı etiketlerdir.** Gece 03:00'te
`EntropiaApiDown` ateşler, Prometheus UI'da `alertstate="firing"` görünür ve **hiç kimsenin
telefonu çalmaz.** Yedi *page* seviyeli alarm — ürünün kullanılamaz olduğunu, Postgres'in
erişilemez olduğunu, async düzlemin hiç kurulmamış olduğunu söyleyen alarmlar — bu boşluğun
arkasında duruyor.

**"`alerts` job'ı yeşil" bunu KAPATMAZ.** O job'ın kanıtladığı tek şey kuralların
*doğru* olduğudur: PromQL geçerli, metrik adları gerçek, eşikler gerekçeli, sentetik seride
ateşliyorlar. **Doğru bir kuralın kime gittiğini o job hiç sormaz.** Yeşil bir
`Alert rules — promtool` rozetini "alarm sistemi çalışıyor" diye okumak, bu ADIM 29
dalgasının tekrar tekrar yakaladığı hatanın aynısıdır: *kapının ölçtüğü şeyi, ölçmediği şey
sanmak.*

**Ek olarak doğrulanmamış iki nokta** (`METRIC_ALERT_MATRIX.md` §4'ün kendi kaydı):
kurallar **gerçek production serilerine** karşı hiç değerlendirilmedi (var olan ama hiç
doldurulmayan bir metrik burada sağlıklı görünür), ve **sevk edilen Prometheus'un gerçekten
bu dosyadan yapılandırıldığını** kanıtlayan bir kapı yok.

**Kapsam durumu — dürüst okuma.** Bu boşluk *keşfedilmedi*; repo onu iki yerde kendi
ilan ediyor (`ops/prometheus/prometheus.yml` başlığı ve
`docs/runbooks/METRIC_ALERT_MATRIX.md` §4) ve "bu slice'ın kapsamı dışı" diyor. Ama
**"kapsam dışı" ile "imzalı kalıcı sapma" aynı şey değildir.** D-10 biçiminde bir kayıt —
adı verilmiş imzalayan + ISO tarih + kapsam — **yoktur**. Dolayısıyla bu, bilinen,
belgelenmiş, **imzasız** bir üretim boşluğudur ve RC imzasında insanın önüne çıkması gerekir.

---

## 6. Verdict ve Alertmanager'ın verdict'e etkisi — karara bağlandı

**P10 = PARTIAL.** Ölçülen altı başlığın beşi PASS; altıncısı bir kapı değil, bir boşluk.

Alertmanager yokluğunun verdict'e etkisi **iki ayrı eksende** karara bağlanmıştır:

1. **Kapı ekseninde — verdict'i düşürmez.** P10'un koştuğu her kapı ölçtüğünü iddia
   ettiği şeyi ölçtü ve geçti. `alert-rules-gate.sh`'in işi bildirim değil, kural
   geçerliliğidir; bildirim yokluğu o kapının başarısızlığı sayılamaz. Bu yüzden P10
   **BLOCKED değildir** — P5/P6/P9'daki gibi "ölçüm yapılamadı" durumu yoktur; her ölçüm
   yapıldı.

2. **RC (ürün işletilebilirliği) ekseninde — kapatıcıdır ve kapatılmamıştır.**
   Gözlemlenebilirlik zinciri *bildirim* adımında kopuyor. Bir V18 Release Candidate'ın
   "izleniyor" sayılabilmesi için ateşleyen bir alarmın bir insana ulaşması gerekir; bugün
   ulaşmıyor. Bu nedenle **RC imza belgesi P10'u `Complete`/`PASS` olarak GÖSTEREMEZ**;
   gösterebileceği en fazla şey: *"performans bütçeleri ve alarm kuralları doğrulandı;
   alarm BİLDİRİMİ yok."*

**Kapanış için iki yol vardır ve ikisi de insan işidir** — bir agent hiçbirini yapamaz:

* **(A)** Alertmanager'ı ayağa kaldırmak (receiver + routing + silence + on-call), ve
  sevk edilen Prometheus'un gerçekten `ops/prometheus/prometheus.yml`'den yapılandığını
  kanıtlayan bir kapı eklemek;
* **(B)** D-10 biçiminde **imzalı kalıcı sapma** kaydı yazmak — adı verilmiş imzalayan +
  ISO tarih + kapsam — ve "V1 üretimi bildirimsiz alarm ile sevk edilir" kararını açıkça
  üstlenmek.

Bunlardan biri yapılana kadar §5.3 **açık sınırdır** ve her RC özetinde bu haliyle
tekrarlanmalıdır.

## 7. Bu koşunun kapsamadıkları

* `load-full` (gecelik Compose baseline'ı) koşulmadı — tam yığın + golden seed gerektirir.
* Latency **ratio gate** hâlâ bağlanmamış durumda (`_ratio_gate` yazılmış ve unit-test'li,
  ama devrede değil); `README.md` §6 aktivasyon için beş gecelik baseline istiyor.
* Frontend bundle bütçesi / Core Web Vitals bu belgenin konusu değil (P3/P11).
* Alarm kuralları **gerçek** üretim serilerine karşı değerlendirilmedi (§5.3).
* `docs/performance/baseline_local_2026-08-06.json` ile karşılaştırma yapılmadı —
  runner class farklı, `README.md` §2 gereği karşılaştırma geçersiz olurdu.
