<!-- doc-status: historical -->
> **EVIDENCE RECORD — 2026-08-07.** Bu belge o gün, o ağaç üzerinde koşulan worker
> dayanıklılığı ve no-lookahead kanıtının kaydıdır. Sayılar koşuldukları anın
> değerleridir; güncel otorite `docs/generated/repository_facts.md` (üretilmiş, CI'da
> `--check` ile kapılı).

# ADIM 29 / P8 — Worker dayanıklılığı ve lookahead güvenliği

**Verdict: PARTIAL — 2 PASS + 1 BLOCKED.**

| # | Başlık | Sonuç |
|---|---|---|
| 1a | At-least-once delivery guard (süreç içi kaos: commit-öncesi crash, eşzamanlı ikinci teslim, redelivery) | **PASS** — 49 passed, exit 0 |
| 1b | Konteyner düzeyi kaos — `scripts/worker-restart-smoke.sh` (SIGKILL + restart) | **BLOCKED** — Docker daemon ölü, her çağrı `exit=124` |
| 1c | Uzun işler durable queue/worker üzerinden mi yürüyor | **PASS** — 12 aktör / 7 kuyruk envanteri + registry invariant testleri yeşil |
| 2 | Research Data `event_time` vs `available_time` ayrımı, no-lookahead | **PASS** — 75 passed / 1 bilinen xfail, exit 0 |
| 3 | `test_research_point_in_time_parity.py:583` = ürün kararı, bug değil; oracle'da xfail sıfır | **PASS — ama izleme kaydı çelişkili** (§4.3) |

**Bu koşu salt-okumadır.** Hiçbir kaynak dosya değiştirilmedi; yalnız bu belge ve yanındaki
ham log dosyaları eklendi. Hiçbir GitHub issue açılmadı/kapatılmadı (§4.3'teki bulgunun
çözümü **insan işidir**).

## Ağaç ve ortam

| | |
|---|---|
| HEAD | `2cf7283` (`origin/main` ile aynı, `git fetch` sonrası doğrulandı) |
| Branch | `claude/worker-durability-lookahead-5a2ed0` (worktree) |
| Working tree | temiz (koşu boyunca yalnız bu dizindeki yeni kanıt dosyaları untracked) |
| Python | 3.12.13 (CPython) |
| pytest | 9.1.1 · pytest-asyncio 1.4.0 (`Mode.AUTO`) |
| PostgreSQL | 16.14 (Homebrew), `localhost:5432` |
| İzole DB | `entropia_p8_test` (bu koşu için; paralel worktree oturumlarıyla paylaşılmıyor) |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://entropia:***@localhost:5432/entropia_p8_test` |
| Docker | CLI 29.4.0 (orbstack) **var**, daemon **cevapsız** — §2.2 |

> **Alt-küme koşusu → `--no-cov`.** Üç pytest çağrısının üçü de `--no-cov` taşıdı; kapı
> (`--cov-fail-under=90`) yalnız tam suite koşusunda anlamlıdır, alt kümede sahte kırmızı
> verir. **Bu belge coverage iddiası taşımaz** — o P1'in işidir. Determinizm için
> `-p no:randomly` eklendi.

---

## 1. Durable iş modeli — neyin kanıtlanması gerekiyordu

Sistemin sözleşmesi tek cümle: **broker mesajı yalnız transport'tur, `jobs` satırı tek
gerçek kaynaktır** (`infrastructure/queues/enqueue.py`, `infrastructure/queues/broker.py`).
Bundan iki bağımsız at-least-once kaynağı doğar ve ikisi de
`application/jobs/delivery.py` docstring'inde adlandırılmıştır:

* **broker sınırı** — commit eden ama ack'ten önce ölen worker aynı mesajı yeniden alır;
* **lease sınırı** — scheduler'ın `redeliverable_queued_jobs` sweep'i `JOB_REDELIVER_GRACE_SECONDS`
  (varsayılan 600 s) geçmiş her `QUEUED` satırı yeniden dağıtır; mid-flight `RUNNING`
  geçişini commit etmemiş bir gövde tüm koşusu boyunca `QUEUED` kaldığı için sweep
  **canlı** bir işi ikinci bir worker'a verebilir.

Kanıtlanması gereken şey bu yüzden "mesaj kaybolmuyor" değil, **"aynı mesaj iki kez
işlenirse ikinci domain etkisi doğmuyor"**dur.

---

## 2. Worker kaos / redelivery

### 2.1 Süreç içi kaos — PASS

```
uv run pytest --no-cov -p no:randomly -v \
  tests/unit/test_worker_delivery_guard.py tests/unit/test_scheduler_redelivery.py \
  tests/unit/test_worker_queue_registry.py tests/unit/test_worker_plane_deployment.py \
  tests/unit/test_scheduler_loop_lifetime.py \
  tests/integration/test_worker_delivery_recovery.py \
  tests/integration/test_data_queue_redelivery.py \
  tests/integration/test_worker_actor_event_loop.py
```

**49 passed in 262.53 s, exit 0.** Ham log: `p8_worker_delivery.txt`.

| Dosya | Test |
|---|---|
| `unit/test_worker_delivery_guard.py` | 8 |
| `unit/test_scheduler_redelivery.py` | 8 |
| `unit/test_worker_queue_registry.py` | 5 |
| `unit/test_worker_plane_deployment.py` | 4 |
| `unit/test_scheduler_loop_lifetime.py` | 8 |
| `integration/test_worker_delivery_recovery.py` | 11 |
| `integration/test_data_queue_redelivery.py` | 3 |
| `integration/test_worker_actor_event_loop.py` | 2 |

Kullanıcının sorduğu iki soruyu **doğrudan** cevaplayan testler (hepsi gerçek DB'ye karşı):

| Soru | Test | Ne kanıtlıyor |
|---|---|---|
| Çift işlem? | `test_signal_import_redelivered_after_commit_writes_one_revision` | commit sonrası redelivery **ikinci** normalized revision yazmıyor |
| Çift işlem? | `test_trade_log_import_redelivered_after_commit_writes_one_batch` | ikinci canonical batch yok |
| Çift işlem? | `test_market_analysis_redelivered_after_commit_writes_one_validation_run` | ikinci market validation run yok |
| Çift işlem? | `test_research_analysis_redelivered_after_commit_writes_one_validation_run` | ikinci research validation run yok |
| Çift işlem? | `test_package_import_redelivered_after_commit_imports_one_package` | ikinci package root yok |
| Çift işlem? | `test_purge_redelivery_never_purges_twice` | terminal purge idempotent |
| Eşzamanlılık | `test_a_live_delivery_locks_the_job_row_against_a_second_worker` | `FOR UPDATE` ikinci teslimi **bekletiyor** (hemen dönüp "in flight"i "already done" sanmıyor) |
| Eşzamanlılık | `test_a_second_worker_replays_once_the_first_delivery_commits` | bekleyen ikinci teslim yeniden hesaplamıyor, kaydı **replay** ediyor |
| **İş kaybı?** | `test_a_crash_before_commit_leaves_nothing_and_the_retry_writes_once` | commit-öncesi crash **hiçbir yarım artefakt bırakmıyor**, retry tam olarak bir kez yazıyor |
| İş kaybı? | `test_object_writes_are_content_addressed_so_a_retry_orphans_nothing` | retry object store'da yetim bırakmıyor |
| İş kaybı? | `test_an_expected_business_failure_is_recorded_and_never_retried` | beklenen iş hatası kalıcı FAILED, sonsuz retry değil |
| Kayıp mesaj | `test_unmapped_queue_is_skipped_but_not_silently` · `test_unroutable_backlog_is_counted_in_full_and_sampled_in_the_log` | yönlendirilemeyen sweep adayı **sessizce** düşmüyor (`scheduler.redeliver_unroutable`) |
| Plane kaybı | `test_every_durable_queue_has_a_worker_service` · `test_no_worker_service_consumes_a_queue_no_actor_serves` | tüketicisiz durable kuyruk (ADIM 21'de `agent-executor`'ın başına gelen) CI'da kırmızı |
| Loop ömrü | `test_concurrent_data_actor_bodies_never_cross_event_loops` · `test_every_worker_thread_commits_through_one_loop` | `run_sync` dikişi; `asyncio.run` regresyonu `data` kuyruğunda kurtarılamaz kayıp demekti |

**Guard'ın mekaniği** (`application/jobs/delivery.py::claim_job_for_delivery`): durable satırı
`with_for_update=True` ile kilitler, terminal ise `terminal_replay_ref(job)` döner ve gövde
**hiçbir şey yazmaz**. Guard'ı çağıran beş gövde — `trading_signal.py:51`, `trade_log.py:52`,
`market_data.py:243`, `research_data.py:271`, `package_import.py:158` — tam olarak `data`
kuyruğunun beş aktörüdür. Kalan durable gövdeler (`backtest_engine`, `agent_executor`,
`create_package`, `purge`, `agent_tools`) aynı iki soruyu **kendi domain satır kilidi** üzerinden
cevaplar (`session.refresh(..., with_for_update=True)` + terminal erken dönüş) ve bu yüzden
helper'ı çağırmaz — bu bilinçli bir tasarım, boşluk değil.

### 2.2 Konteyner düzeyi kaos — **BLOCKED**

`scripts/worker-restart-smoke.sh` **koşulamadı**. Script'in ilk satırdaki ön koşulu "ALREADY-RUNNING
stack"tir; Docker daemon cevap vermiyor. Ham kanıt: `p8_docker_probe.txt`.

| Komut | Çıktı | Exit |
|---|---|---|
| `command -v docker` | `/usr/local/bin/docker` | 0 |
| `docker version --format '{{.Server.Version}}'` (30 s) | *(boş)* | **124** |
| `docker info --format '{{.MemTotal}} bytes / {{.NCPU}} cpu'` (30 s) | `0 bytes / 0 cpu` | **124** |
| `docker ps -a` (30 s) | *(boş)* | **124** |
| `docker compose ps` (60 s) | *(boş)* | **124** |

Client 29.4.0 (context `orbstack`) kurulu, **server tarafı yanıt vermiyor** — `MemTotal=0`
daemon'ın hiç servis etmediğinin işareti. Bu, P5'in (`P5_docker_auth.md` §3, Docker VM
3.89 GiB) kaydettiği host kaynak tükenmesiyle **aynı kök nedendir**; P5'in 2, 3 ve 4 numaralı
kalemleri de bu yüzden BLOCKED.

**Dolayısıyla kanıtlanmayan iddia, açıkça:** "worker konteynerini SIGKILL'leyip geri
getirmek append-only tabloların hiçbirini büyütmez ve scheduler sweep'i hiçbir şey
uydurmaz." Bu, §2.1'in kanıtladığı süreç-içi özelliğin **konteyner düzeyindeki karşılığıdır**
ve teoride ondan çıkar, ama P8 kapsamında **ölçülmedi**. Kapatmak için Docker daemon'ı
sağlıklı bir hostta ayağa kaldırıp `make up` sonrası script'i koşmak gerekir — tercihen
mid-flight bir `data` işi kuyrukta iken (script'in kendi başlığı bunu şart koşuyor; boş
stack'te yalnız daha zayıf "temiz restart" özelliğini kanıtlıyor).

### 2.3 Uzun işler durable queue üzerinden mi yürüyor — PASS

**Envanter (kod okuması).** `jobs` satırı yazan 10 admission yüzeyi
(`enqueue_job(` çağrı yerleri) ve commit sonrası dispatch eden 12 route/plane
(`send_job(` çağrı yerleri) sayıldı. Uzun süren beş iş ailesinin tamamı durable:

| Aile | Admission | Aktör / kuyruk | HTTP |
|---|---|---|---|
| Trading Signal import | `commands/trading_signal.py:227` | `run_trading_signal_import` / `data` | 202 |
| Trade Log import | `commands/trade_log.py:231` | `run_trade_log_import` / `data` | 202 |
| Market Data analysis | `commands/market_data.py:349` | `run_market_data_analysis` / `data` | 202 |
| Research Data analysis | `commands/research_data.py:372` | `run_research_data_analysis` / `data` | 202 |
| Package import | `commands/package_import.py:107` | `run_package_import` / `data` | 202 |
| Backtest run / retry / cancel | `commands/backtest_run.py:624` | `run_backtest_engine` / `backtest` | 202 |
| Trash purge | `commands/deletion.py:751` | `run_trash_purge` / `maintenance` | 202 |
| Create-Package (precheck / candidate / validation) | `commands/create_package.py:1362` | `run_create_package_job` / `default` | 200 (§5-B2) |
| Agent tool | `jobs/agent_tools.py:1481` | `run_agent_tool` / `agent`, `run_agent_tool_high` / `agent-high` | — |
| Agent loop / executor | `commands/agent_loop.py:160` | `run_agent_executor` / `agent-executor` | — |

**Hiçbir uzun iş request thread'inde satır içi koşmuyor:** her yüzey önce `enqueue_job`
(commit yok) → çağıranın transaction'ı commit → `send_job` (commit sonrası) sırasını izliyor.
Sıra bu yüzden önemli: aktör yalnız **commit edilmiş** bir `jobs` satırı görür.

**Invariant testleri bunu koruyor** (`unit/test_worker_queue_registry.py`, §2.1'de yeşil):

* `test_every_single_actor_queue_is_registered_for_auto_redelivery` — tek durable aktörlü her
  kuyruk `ACTOR_BY_QUEUE`'da; aksi halde kayıp mesaj işi sonsuza dek `QUEUED` bırakırdı.
* `test_no_multi_actor_queue_is_auto_redelivered` — çok-aktörlü tek kuyruk `data`'dır ve
  **bilerek** otomatik sweep dışındadır (durable satır hangi aktöre gideceğini söyleyemez);
  yerine operator eylemi `POST /admin/data-queue/redeliver` vardır.
* `test_the_registered_actor_is_the_one_that_actually_serves_the_queue` — bayat kayıt, sessizce
  hiç koşmayan bir redelivery demekti.
* `test_every_data_job_kind_routes_to_an_actor` — `DATA_JOB_KINDS` (5) ↔ `DATA_ACTOR_BY_KIND`
  tam örtüşüyor; discriminator taşımayan eski satır `skipped_unknown_kind`, asla tahmin yok.

**Dürüst sınır:** bu bir **statik** kanıttır (kod + invariant testleri). Gerçek bir Redis
restart'ının kuyruğu boşaltıp sweep'in işi geri getirdiğini uçtan uca gösteren ölçüm §2.2 ile
birlikte BLOCKED'dır.

---

## 3. Research Data — `event_time` vs `available_time`, no-lookahead

```
uv run pytest --no-cov -p no:randomly -rxXs -v \
  tests/unit/test_research_time_policy.py tests/unit/test_research_point_in_time.py \
  tests/integration/test_research_available_time_enforcement.py \
  tests/integration/test_research_point_in_time_parity.py \
  tests/integration/test_readiness_research_data.py \
  tests/integration/test_ingest_timezone_normalization.py \
  tests/integration/test_backtest_manifest_pinning.py
```

**75 passed, 1 xfailed in 986.88 s (16:26), exit 0.** Ham log: `p8_research_lookahead.txt`.

| Dosya | Test |
|---|---|
| `unit/test_research_time_policy.py` | 9 |
| `unit/test_research_point_in_time.py` | 27 |
| `integration/test_research_available_time_enforcement.py` | 6 |
| `integration/test_research_point_in_time_parity.py` | 16 passed + **1 xfailed** |
| `integration/test_readiness_research_data.py` | 6 |
| `integration/test_ingest_timezone_normalization.py` | 8 |
| `integration/test_backtest_manifest_pinning.py` | 3 |

### 3.1 Ayrım korunuyor mu — evet, ve tek bir kapıdan geçiyor

Kanonik kural `domain/research_data/time_policy.py`'de saf predikat olarak duruyor:
**`event_time != available_time`; `available_at >= event_at` ZORUNLU.**

| Fonksiyon | Rol |
|---|---|
| `available_time_is_consistent(event_at, available_at)` | anti-lookahead: değer olaydan önce mevcut olamaz |
| `resolve_available_at(...)` | dört politikadan (`same_as_event_time` / `fixed_delay` / `provider_publish_timestamp` / `custom_documented_rule`) türetir; sonuç `event_at`'ten önceyse `TimePolicyInvalid` |
| `time_policy_is_valid(...)` | `fixed_delay` pozitif+sınırlı (`MAX_AVAILABLE_DELAY = 31 gün`) delay ister; diğer her kural `delay=None` ister — bayat delay motora sızamaz |
| **`is_eligible_for_decision(...)`** | **K-02: motorun research feed'ine eriştiği TEK kapı** — `has_instrument_mapping and available_at <= decision_time` |
| `ensure_time_policy_mutable(...)` | onaylanmış revizyonun politikası **donuk**; yeniden zamanlama 409 `LIFECYCLE_BLOCKED` |
| `time_policy_is_frozen(None) → True` | fail-closed: durum okunamıyorsa donuk sayılır |

`domain/backtest/engine.py` her aday funding kaydı için `is_eligible_for_decision`'ı bir kez
çağırır; yani bir research değeri karar noktasına **kapı dışı bir karşılaştırmayla** ulaşamaz.

### 3.2 Kanonik matris — hangi iddia nerede kanıtlandı

`docs/audit/research_point_in_time_matrix.md` T-1..T-11 satırlarının bu koşudaki karşılığı:

| # | İddia | Test | Sonuç |
|---|---|---|---|
| T-1 | Event time asla usable time'ın vekili değil (10:15 olay + 2 dk delay 10:15'te **uygun değil**) | `test_a_fixed_delay_source_is_ineligible_at_its_own_event_time` | PASS |
| T-2 | `available_at == decision_time` **dahildir** (`<=`) | `test_a_record_available_exactly_at_the_decision_time_is_eligible` | PASS |
| T-3 | `t + 1 mikrosaniye` hariç; ±1 µs iki yönde de çeviriyor | `test_one_microsecond_after_the_decision_time_is_not_eligible`, `test_the_microsecond_boundary_is_the_only_difference_either_side` | PASS |
| T-4 | Aynı `available_at`'i paylaşan iki kayıt ikisi de, **tam bir kez** ateşliyor | `test_two_records_sharing_one_available_at_both_fire_exactly_once` | PASS |
| T-5 | Geç gelen kayıt daha erken bir karar anı için **asla** ateşlemiyor | `test_a_late_arriving_record_never_fires_for_an_earlier_decision_time` | PASS |
| T-6 | Onaylı revizyonun politikası yerinde yeniden yazılamıyor | `test_an_approved_revision_cannot_be_retimed_in_place`, `test_the_canonical_recovery_is_a_new_revision_that_leaves_v1_intact` | PASS |
| **T-7** | **Bundle, derlendiği zaman politikasını pinliyor** | `test_both_bundles_pin_the_available_time_policy` | **XFAIL (#558)** — §4 |
| T-8 | UTC-dışı bildirilmiş zon funding schedule'a ulaşıyor; çözülemeyen zon altındaki naive satır **UTC sanılmak yerine düşüyor** | `test_a_naive_new_york_event_time_lands_on_the_true_utc_instant`, `test_a_naive_row_under_an_unresolvable_zone_drops_instead_of_assuming_utc` | PASS |
| T-9 | DST fold / gap davranışı karakterize (canon sessiz) | `test_an_ambiguous_dst_fold_string_resolves_to_the_first_occurrence`, `test_a_nonexistent_dst_gap_string_is_accepted_not_rejected` | PASS (#559 açık ürün kararı) |
| T-10 | İki ayrı implementasyon (ingest normalizer ↔ funding reader) her DST vakasında **aynı** cevabı veriyor | `test_the_ingest_normalizer_and_the_funding_reader_agree_on_every_dst_case` | PASS |
| T-11 | Çözülmüş available time asla event time'dan önce olamaz | `test_a_resolved_available_time_can_never_precede_its_event_time` | PASS |

Fail-closed davranışın uçtan uca (gerçek DB) karşılığı da yeşil:
`test_undefined_available_time_policy_fails_closed`,
`test_incoherent_policy_and_delay_fails_closed`,
`test_incoherent_instrument_mapping_fails_closed`,
`test_lookahead_fixture_changes_the_result_available_time_not_event_time` — sonuncusu tam
olarak kullanıcının sorduğu ayrımı ölçüyor: lookahead fixture'ı **available time**'ı değiştiriyor,
**event time**'ı değil, ve sonuç buna göre kayıyor.

---

## 4. `test_research_point_in_time_parity.py:583` — xfail(strict) / #558

### 4.1 Marker gerçekten strict ve gerçekten kırmızı

`tests/integration/test_research_point_in_time_parity.py:583` üzerindeki
`@pytest.mark.xfail(strict=True, reason="GH #558 — ...")`, `:591`'deki
`test_both_bundles_pin_the_available_time_policy`'yi işaretliyor.

Koşu çıktısı (`p8_research_lookahead.txt`):

```
XFAIL tests/integration/test_research_point_in_time_parity.py::test_both_bundles_pin_the_available_time_policy
================== 75 passed, 1 xfailed in 986.88s (0:16:26) ===================
```

`strict=True` olduğu için **XPASS bir başarısızlık olurdu**; `XFAIL` raporlanması testin
gerçekten düştüğünü, yani kusurun **hâlâ kodda** olduğunu kanıtlar.

**Repo genelinde bilinçli xfail sayısı = 1.** Üretilmiş, CI'da `--check` ile kapılı
`docs/generated/repository_facts.md`: *"Backend `xfail` markers | 1 (1 strict)"*. Bağımsız
teyit — `grep -rn "xfail" backend/tests/` yalnız üç isabet veriyor ve ikisi (`:14`, `:523`)
docstring/yorum metnidir; tek gerçek marker `:583`'tür. **CLAUDE.md'nin "eskiden 4 yazıyordu —
bayat" uyarısı doğrudur.**

### 4.2 "Ürün kararı, bug değil" — DOĞRU, ama tam olarak şu anlamda

| Kanıt | İçerik |
|---|---|
| GitHub etiketi | `product-decision` — *"Urun karari gerekiyor; agent karar veremez, kod yazilamaz"* |
| Issue başlığı | *"**product decision**: neither research bundle pins the available-time policy that doc 12 §9.1/§9.2 names, though the Run manifest does"* |
| Audit matrisi | `research_point_in_time_matrix.md` T-7 → **DISCREPANCY**, §D-4 |
| Issue gövdesindeki "Decision needed" | (1) alanlar üye alt-sözlüğüne mi girsin yoksa §9.2'nin literal `available_time_policies[]` dizisi mi olsun; (2) `bundle_hash` şekli iki yolda da değişiyor — kırıcı mı; (3) §9.2'nin diğer dört alanı V1'e girsin mi |

**Bu bir çalışma-zamanı hatası değildir.** Bundle yanlış bir şey hesaplamıyor;
`compile_backtest_evidence_bundle` zaman politikasını **doğruluyor** (`_ensure_time_policy_valid`)
ama **kaydetmiyor**. Sonuç: `bundle_hash` politika değişimine karşı **değişmez**, yani bir bundle
kendi içeriğinden hangi kural altında derlendiğini ispatlayamıyor. Run manifest
(`commands/backtest_run_context.py`) dokuz alanı birden pinliyor → iki execution-evidence
yüzeyi çelişiyor.

**Ama "sadece bir tercih" de değildir:** karşılanmayan bir **canon şartıdır** (doc 12 §9.1 "usage
scope **and time policy**"; §9.2 `available_time_policies[]`). Ürün kararı olan şey **kusurun
varlığı değil, çözümün ŞEKLİ**dir. Dürüst formülasyon: *bug değil, karşılanmamış spec şartı;
remedy'nin şekli ürün kararına bağlı.*

**No-lookahead güvenliği bundan etkilenmiyor.** ADIM 13'ün D-1 düzeltmesi
(`ensure_time_policy_mutable`) **ulaşılabilir drift'i** kapattı: onaylı bir revizyon yerinde
yeniden zamanlanamıyor (T-6 yeşil), dolayısıyla bitmiş bir Run'ın kanıtı sonradan başka bir
kural altında yeniden yorumlanamıyor. #558'in kapsadığı şey yalnız **eksik pin** — bundle'ın
kendi kendini attest edememesi.

### 4.3 **BULGU — izleme kaydı kod ile çelişiyor (#514 ile aynı desen)**

`gh issue view 558`:

| Alan | Değer |
|---|---|
| state | **CLOSED** |
| stateReason | **COMPLETED** |
| closedAt | **2026-08-07T03:53:57Z** |
| kapatan | `alimirbagirzade` |
| yorum sayısı | **0** |
| etiket | `product-decision` (hâlâ) |

Yani: **issue "COMPLETED" olarak kapalı, ama kaydedilmiş hiçbir karar yok ve strict xfail
bugün hâlâ düşüyor.** Aynı dakika içinde toplu kapatma yapılmış:

| # | Tür | closedAt | Durum |
|---|---|---|---|
| #559 | product decision (DST fold/gap) | `03:53:36Z` | COMPLETED — karar **kaydı yok**, davranış karakterize ama canon hâlâ sessiz |
| #557 | fix (Feature-Input-Only gate) | `03:53:49Z` | **meşru** — düzeltildi, marker kaldırıldı, `test_..._resolves_the_feature_definition_server_side` bugün PASS |
| **#558** | product decision (bundle time-policy pin) | `03:53:57Z` | COMPLETED — **kusur duruyor, xfail düşüyor** |
| #556 | fix (soft-deleted/deprecated pin) | `03:54:10Z` | kod tarafı düzeltildi; ama `unified_portfolio_oracle_acceptance.md` A17'ye göre **market yarısı açık** |

Bu, `CLAUDE.md`'nin #514 (ekran okuyucu denetimi) için tarif ettiği ayrışmanın **aynısıdır**:
kapalı izleme kaydı ↔ açık iş. **Hiçbir belge #558'i `Complete`/`PASS`/`Done` gösteremez**;
`test_both_bundles_pin_the_available_time_policy` kırmızı kaldığı sürece A17 çıkış kriteri
("tests green **unweakened**") de karşılanmamıştır.

**Çözüm yolları — ikisi de insan işi, agent yapamaz:**
(A) issue'nun insan eliyle **yeniden açılması**; veya
(B) imzalı kalıcı sapma kaydı (D-10 biçimi: adı verilmiş imzalayan + ISO tarih + kapsam) —
**imzalayan verilmediği için böyle bir kayıt YOK.**
Bu koşuda hiçbir issue açılmadı/kapatılmadı.

### 4.4 Oracle paketinde xfail — SIFIR, teyitli

```
uv run pytest --no-cov -p no:randomly tests/unit/oracles/ -rxX
111 passed in 2.55s          # exit 0
```

Ham log: `p8_oracle_xfail.txt`. İki bağımsız kanıt:

1. `grep -rn "xfail\|@pytest.mark.skip" backend/tests/unit/oracles/` → **hiç isabet yok** (10 test
   modülü + `harness.py` + `portfolio_harness.py`).
2. `-rxX` bayrağıyla koşu **hiçbir** XFAIL/XPASS satırı basmadı; 111'in 111'i `passed`.

---

## 5. Yan bulgular (P8 kapsamında ölçüldü, düzeltilmedi)

| # | Bulgu | Şiddet |
|---|---|---|
| **B1** | `jobs/agent_tools.py::pending_data_job_dispatch` (~`:1381`) docstring'i replay'de `None` dönmeyi *"the import job body has no terminal-state guard, so re-sending it would run the parse a second time"* diye gerekçelendiriyor. **Bu gerekçe ADIM 21'den beri bayat:** iki agent-admitted kind'ın (`trade_log_import`, `trading_signal_import`) gövdeleri artık `claim_job_for_delivery` çağırıyor (`trade_log.py:52`, `trading_signal.py:51`). **Davranış doğru ve değişmemeli** (replay yeni iş admit etmedi, dispatch edilecek bir şey yok) — bayat olan yalnız gerekçe. | düşük, salt-doküman |
| **B2** | Create-Package'ın durable admission uçları (`../pre-check`, `../generate-candidate`, `../validate`) `jobs` satırı yazıp aktör dispatch ediyor ama HTTP **200** dönüyor; diğer dokuz durable admission ucu **202** dönüyor. **Adjudicate EDİLMEDİ** — doc 06'nın kendi §-taksonomisi otoritedir ve bu koşuda okunmadı; sözleşme kusuru olarak değil, **tutarsızlık gözlemi** olarak kaydediliyor. | düşük, açık soru |
| **B3** | `docs/CODEMAPS/JOBS_AND_EVENTS.md` aktör tablosundaki satır numaraları ~24 satır kaymış (ör. `run_market_data_analysis` `:45` yazıyor, gerçek `:69`; yalnız `system_heartbeat :39` tutuyor). Kuyruk/aktör eşlemesinin **kendisi doğru**. Codemap türetilmiş dosyadır → `ecc:update-codemaps`. | düşük, salt-doküman |

Üçü de bu koşuda **düzeltilmedi** (P8 salt-okuma doğrulamadır).

---

## 6. Ham kanıt dosyaları

| Dosya | İçerik |
|---|---|
| `p8_worker_delivery.txt` | 49 passed / exit 0 — delivery guard, redelivery, scheduler sweep, plane deployment, event loop |
| `p8_research_lookahead.txt` | 75 passed + 1 xfailed / exit 0 — time policy, point-in-time, available-time enforcement, parity, readiness, timezone, manifest pinning |
| `p8_oracle_xfail.txt` | 111 passed / exit 0 + `tests/unit/oracles/` içinde xfail/skip marker grep'i (boş) |
| `p8_docker_probe.txt` | Docker daemon cevapsızlığının komut-komut kanıtı (§2.2 BLOCKED) |

## 7. Kapatılması gereken açık kalemler

1. **P8-1b** — `scripts/worker-restart-smoke.sh` sağlıklı bir Docker host'unda, mid-flight bir
   `data` işi kuyruktayken koşulmalı. (P5'in 2/3/4 kalemleriyle **aynı** engelde.)
2. **#558** — izleme kaydı ile kod çelişiyor (§4.3). Yeniden açma veya imzalı sapma: **insan kararı.**
3. **#559** — aynı desen; DST fold/gap için canon hâlâ sessiz, issue COMPLETED kapalı.
4. **A17 çıkış kriteri** — "tests green **unweakened**" strict xfail durdukça karşılanmıyor;
   ayrıca #556'nın market yarısı `unified_portfolio_oracle_acceptance.md`'ye göre açık.
