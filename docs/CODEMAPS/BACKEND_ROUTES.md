# BACKEND_ROUTES — HTTP yüzeyi

Tüm router'lar `apps/api/main.py:116-146` içinde `prefix=settings.api_base_path` ile mount edilir
(30 route router + `sse_router`). Varsayılan prefix: **`/api/v1`** (`config/settings.py:34`).
Aşağıdaki path'ler prefix'siz yazılmıştır.

> **Endpoint sayısı (2026-07-29, ampirik): 196.** Kaynak taramasındaki `@router.<method>` sayısı
> (`apps/api/routes/*.py` + `apps/api/sse.py`) `docs/openapi.json` içindeki operation sayısıyla
> **birebir eşleşiyor** — yayımlanmayan route yok. Yeniden üretmek için:
> `python3 -c "import json;d=json.load(open('docs/openapi.json'));print(sum(1 for p in d['paths'].values() for m in p if m in ('get','post','put','patch','delete')))"`
> Bu haritanın satırları **gruplanmıştır**, bu yüzden satır sayısı 196 değildir — sayı kapısı
> openapi'dir. Tam path literali içermeyen **51** operation'ın tamamı şu beş gruplamadan gelir
> (2026-07-29'da tek tek eşlendi, **kapsanmayan endpoint YOK**):
>
> | Gruplama | Nasıl yazılır | Operation |
> |---|---|---|
> | `create_package.py` | `../pre-check` kısaltması (ortak `/create-package/requests/{request_id}` ön eki) | 8 |
> | `allocation.py` | ön ek bölüm başlığında: `/mainboard-compositions/{composition_id}` | 5 |
> | `market_data.py` | ön ek başlıkta `/market-datasets`, satırlar `/{id}` | 11 |
> | `research_data.py` | ön ek başlıkta `/research-datasets`, satırlar `/{id}` | 13 |
> | ikiz TS/TL yüzeyi | tek tablo, `/{k}` = `trading-signals` \| `trade-logs` | 14 |

Sütunlar:
- **OCC** — imzada gözlenen eşzamanlılık token'ı. `yok` = imzada hiç yok.
- **Idem** — `Idempotency-Key` header'ı okunuyor mu (`✔`/`—`).
- **Rol kapısı** — route katmanındaki açık `require_*`. Boş = command/query katmanında.

---

## DUAL-TOKEN KURALI (O-12) — tek ve bağlayıcı

**17 mutating op** eşzamanlılık token'ını **iki yerden** kabul eder: gövde (`expected_*`,
domain kimliği) ve `If-Match` header'ı (aynı kimliğin HTTP taşıması). Üç spec de aynı şeyi
söyler — doc 15 §11, doc 20 §14 ("`If-Match`/ETag only as transport support … **Do not treat
them as interchangeable fields**"), doc 21 §7 ("The HTTP ETag transports concurrency
information; it is not the domain revision identity"). Yani bunlar **tek bir değerin iki
yazımıdır**, iki bağımsız önkoşul değil.

> **Kural:** ikisi de verilmişse ve **ÇELİŞİYORSA → 409 `OCC_TOKEN_CONFLICT`.**
> Biri verilmişse o kazanır. İkisi de verilmemişse `None` (op kendi zorunluluğunu belirler).
> Anlaşıyorlarsa gövde değeri geçer (tarihsel öncelik korunur → tek-token çağıranlar etkilenmez).

Kural **tek yerde** yaşar: `shared/concurrency.py::reconcile_occ_tokens`. Her dual-token route
oradan geçer; kural route'a kopyalanmaz, bu yüzden drift edemez. Hata sınıfı
`shared/errors.py::OccTokenConflictError` — `category=concurrency_or_preflight`,
**`retryable=false`** (aynı çelişkiyi körlemesine tekrar göndermek hep aynı hatayı verir;
çağıran isteği düzeltmeli), `suggested_action="resend_with_a_single_occ_token"`; `details`
hem `body_value` hem `if_match_value`'yu yankılar.

> **Sayı düzeltmesi (2026-07-29).** Bu paragraf uzun süre "16 mutating op" diyor, hemen altındaki
> liste ise **17** sayıyordu — kendi içinde tutarsızdı. `trash.soft_delete` O-18'de dual olunca 16 →
> 17 oldu; başlık satırı güncellenmemişti. Ampirik doğrulama (op sayısı, yardımcı fonksiyon sayısı
> DEĞİL — `_resolve_expected`/`_expected_version` gibi tek yardımcı birden çok op'a hizmet eder):
> `grep -rn reconcile_occ_tokens backend/src/entropia/apps/api/routes/` → 12 çağrı yeri,
> yardımcıları çağıran route'lara açıldığında **17 op**.

**Dual-token 17 op:** `admin_panel.assign_role` · `mainboard.patch_mainboard_item` ·
`strategy.patch/save/clear` (3) · `allocation.put_draft/create_revision` (2) ·
`readiness.run_readiness_check` · `backtest.request_backtest_run/soft_delete_result` (2) ·
**`backtest.cancel_backtest_run` (O-06'da eklendi)** ·
`results_history.soft_delete_backtest_result` · `manual.replace_revision` ·
`metric_profile.create_metric_profile_revision` · `trash.restore/purge` (2) ·
`trash.soft_delete` (O-18'de dual oldu).

**Bilerek dışarıda:** `rationale.revise_family` — burada `If-Match` **atıl** bir parametreydi
(okunuyor ama hiç kullanılmıyordu) ve uzlaştırılamaz: family ETag'i `rv-N` **row_version**,
komutun token'ı ise `expected_head_revision_id` (**revision id**) — farklı eksenler, kıyas
sahte 409 üretirdi. Hiçbir şey yapmayan bir header'ı reklam etmek bu slice'ın kapattığı
kusurun ta kendisi olduğu için parametre **kaldırıldı** (aynı ailenin soft-delete'i `If-Match
rv-N` kullanmaya devam ediyor).

**If-Match-only 14 op** (gövde token'ı yok → çelişki imkânsız): `agent_lab` pause/resume/stop ·
`library.soft_delete_package` · `market_data` create_revision/approve/soft_delete ·
`rationale.soft_delete_family` · `research_data` create_revision/approve/revoke/soft_delete ·
`sharing.share/revoke`.

---

## health · meta · metrics · sse · auth · identity — hiçbirinde OCC yok

> **O-13:** `POST /signup` ve `POST /users/{user_id}/role` artık `Idempotency-Key` okur
> (aşağıda işaretli). Kalan uçlar okumaz: `login`/`logout`/`reauth` oturum işlemleridir
> (tekrarları yeni kaynak yaratmaz), diğerleri salt-okumadır.

| METHOD path | fonksiyon | çağırdığı | Rol kapısı |
|---|---|---|---|
| GET `/health/live` | `live` `health.py:31` | — | |
| GET `/health/ready` | `ready` `health.py:36` | — | |
| GET `/meta` | `meta` `meta.py:32` | — | |
| GET `/metrics` | `metrics_endpoint` `metrics.py:104` | Prometheus text exposition | `require_metrics_scraper:42` (O-22 — Bearer `ENTROPIA_METRICS_TOKEN`; yok=401 `METRICS_SCRAPE_UNAUTHORIZED`, yanlış=403 `METRICS_SCRAPE_FORBIDDEN`; token yapılandırılmamışsa production'da fail-closed 403, local'de açık) |
| GET `/events` | `events` `sse.py:293` | **SSE stream** — `EventSourceResponse(_event_source)`; outbox→SSE fan-out'un HTTP ucu. `Last-Event-ID` header'ı replay cursor'ıdır (O-21). OCC/Idem kavramsal olarak yok | `_authenticated_subscriber:270` → `require_authenticated` (AUTH-11; anonim abonelik kapalı, handshake DB'ye dokunmadan reddedilir) |

> **Prob hatası artık sessiz değil (I-13, #467).** `/health/ready` ve `/metrics`'i besleyen dört
> bağımlılık probu (object storage `infrastructure/s3/client.py`, redis
> `infrastructure/redis/client.py`, postgres `infrastructure/postgres/health.py`, `/metrics`
> operasyonel gauge'ları) her istisnayı çıplak `except Exception` ile yutuyordu; kırmızı bir Ready
> Check `"redis": "down"` diyor ama operatör bunun reddedilen bağlantı mı, timeout mı, yanlış
> kimlik bilgisi mi olduğunu **öğrenemiyordu**. **Davranış bilerek değişmedi** — prob yine `False`
> döner, scrape yine yorum satırına düşer; tek fark yutmanın artık `<component>.probe_failed`
> WARNING'i ile ilan edilmesi. Uyarı **yalnız istisna SINIF ADINI** taşır, asla `str(exc)`'i:
> redis/asyncpg hataları parolayı taşıyan bağlantı URL'sini, botocore mesajları endpoint + imzalı
> istek materyalini alıntılar.

| POST `/auth/signup` (201) | `sign_up` `auth.py:84` | `auth_commands.sign_up` (+ ilk-Admin bootstrap) — **Idem ✔** (O-13) | (anonim) |
| POST `/auth/login` | `login` `auth.py:109` | `auth_commands.login` | (anonim; `AUTH_MODE=dev`'de insan login sunucu-reddi — #346/#347) |
| POST `/auth/logout` | `logout` `auth.py:134` | `auth_commands.logout` | |
| GET `/auth/bootstrap-status` | `bootstrap_status` `auth.py:150` | `auth_commands.bootstrap_status` (döner: `login_capable_admin_exists` — PROV-05) | (anonim) |
| POST `/auth/reauth` | `reauth` `auth.py:166` | `auth_commands.reauthenticate` | `require_authenticated` |
| GET `/me` | `me` `identity.py:37` | ctx.actor | |
| POST `/users/{user_id}/role` | `set_user_role` `identity.py:49` | `commands.roles.change_user_role` — OCC **yok** (doğrulandı: legacy yüzey; OCC'li yol `PATCH /admin/users/{id}/role`), **Idem ✔** (O-13; replay `version`'ı ikinci kez artırmaz) | `require_admin` |

## admin_panel.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| GET `/admin/users` | `list_users:73` | `user_registry_query.list_registered_users` | yok | — | `require_admin_panel` |
| PATCH `/admin/users/{user_id}/role` | `assign_role:85` | `role_assignment_cmd.assign_user_role` | **DUAL** — body `expected_head_revision_id` (int, ge=1, ZORUNLU) + `If-Match`; eşitlik `reconcile_occ_tokens` ile (`:97`). **O-12 öncesi çelişki 422 VALIDATION_ERROR'dı** (tüm dual uçlardan farklı şekil) → artık kanonik **409 `OCC_TOKEN_CONFLICT`** | ✔ | `require_admin_panel` |
| GET `/admin/system-actors` | `list_system_actors:117` | `user_registry_query.list_system_actors` | yok | — | `require_admin_panel` |
| GET `/admin/role-matrix` | `role_matrix:123` | `user_registry_query.get_role_matrix` | yok | — | `require_admin_panel` |
| GET `/admin/backtest-logs` | `list_backtest_logs:132` | `backtest_log_query.list_admin_backtest_log` (`queries/panel_backtest_log.py`) — **P-14 PRIMARY görünüm:** cross-user "All User Backtest Logs" tablosu (User · Date · Backtest · Net Profit · ROMAD · Trades). Cursor + limit; audit-event projeksiyonu (`/admin/logs`) **ikincil teknik görünüm** olarak kalır | yok | — | `require_admin_panel` |
| GET `/admin/logs` | `list_logs:148` | `log_query.list_log_events` | yok | — | `require_admin_panel` |
| GET `/admin/log-resource-types` | `list_log_resource_types:185` | `log_query.list_resource_types` | yok | — | `require_admin_panel` |
| GET `/admin/logs/{event_id}` | `get_log:196` | `log_query.get_log_event` | yok | — | `require_admin_panel` |
| POST `/admin/data-queue/redeliver` | `redeliver_data_queue:205` | `data_queue_cmd.redeliver_data_queue_jobs` | yok | **✔** (O-13) | `require_admin_panel` |

> **Son-Admin koruması, iki ayrı kod (audit-doc19, #464).** Panel rol yüzeyi (`PATCH
> /admin/users/{user_id}/role` → `commands/role_assignment.py:119`) **`LAST_ADMIN_PROTECTION`**
> yayar (`shared/errors.py::LastAdminProtectionError`, doc 19 §7.1/§9.3/§11/§14); legacy
> `POST /users/{user_id}/role` yolu ise Master Module 3 taksonomisiyle `LAST_ADMIN_PROTECTED`
> der. **Aynı kusur, iki sayfa taksonomisi** — K-07 upload kapısıyla aynı adjudication şekli.
> `LastAdminProtectionError` alt sınıftır, bu yüzden umursamayan çağıran hâlâ tek tip yakalar
> (`except LastAdminProtectedError`). `retryable=false` (aynı demotion başka Admin doğana dek hep
> başarısız).

| GET `/audit-events` `audit.py:16` | `audit_events` | `queries.audit_log.list_audit_events` | yok | — | `require_admin:21` |

## mainboard.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| GET `/mainboards/default` | `get_default_mainboard:75` | `mb_query.get_default_mainboard` | yok | — | |
| POST `/external-work-object-drafts/{kind}` | `start_external_work_object_draft:91` | (geçici opener) | yok | — (**bilerek**: O-13 listesindeydi ama **mutating DEĞİL** — senkron saf fonksiyon, session'a dokunmaz, `{"draft_id": new_id(...), "unsaved": true}` döner; kalıcı satır yok → tekilleştirilecek yan etki yok) | |
| POST `/work-objects` (201) | `create_work_object:99` | `mb_cmd.create_work_object` | yok | ✔ | |
| POST `/work-objects/{root_id}/revisions` (201) | `create_work_object_revision:116` | `mb_cmd.create_work_object_revision` | **body `expected_head_revision_id` (str, opsiyonel)** | ✔ | |
| POST `/mainboards/{workspace_id}/items` (201) | `attach_mainboard_item:135` | `mb_cmd.attach_mainboard_item` | yok | ✔ | |
| PATCH `/mainboard-items/{item_id}` | `patch_mainboard_item:154` | `mb_cmd.patch_mainboard_item` | **DUAL** — body `expected_row_version` (int) veya `If-Match` (`:163`); en az biri ZORUNLU, çelişki → 409 | ✔ | |
| POST `/mainboards/{workspace_id}/snapshots` (201) | `create_composition_snapshot:188` | `mb_cmd.create_composition_snapshot` | yok | ✔ | |
| DELETE `/work-objects/{root_id}` | `soft_delete_work_object:202` | `mb_cmd.soft_delete_work_object` | yok | ✔ | |

> **Legacy `item_kind` etiketleri spec adıyla reddedilir (O-27, #450).**
> `domain/mainboard/item_kind.py:43` — eski bir `item_kind` etiketi 422 **`INVALID_ITEM_KIND`**
> verir ve **hiçbir** PackageKind genişlemesi, kök veya revizyon yaratmaz. AOS-03: ne genel
> `VALIDATION_ERROR` ne de CR-01 mismatch kodu doğru cevaptı — kusurun kendi adı var.

## strategy.py — OCC: **body `expected_draft_row_version` (int)**, `_resolve_expected_version:57` (DUAL, `reconcile_occ_tokens:60`), sonuç ZORUNLU int

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| POST `/strategy-drafts` (201) | `create_strategy_draft:79` | `strat_cmd.create_strategy_draft` / `derive_strategy_draft_from_package` | yok | ✔ | |
| POST `/strategies/{root_id}/rationale-family` | `set_strategy_rationale_family:106` | `strat_cmd.set_strategy_rationale_family` — **R2-07:** NULL bir rationale family'yi **tek seferlik** set eder | **yok** (bilerek: `NULL→set` geçişinin kendisi kapıdır; zaten set edilmişse 409 — ayrı bir OCC token'ı yeni bir yarış penceresi açmazdı) | ✔ | |
| PATCH `/strategy-drafts/{draft_id}` | `patch_strategy_draft:124` | `strat_cmd.patch_strategy_draft` | body `expected_draft_row_version` / If-Match | ✔ | |
| POST `/strategy-drafts/{draft_id}/validate` | `validate_strategy_draft:144` | `strat_cmd.validate_strategy_draft` | yok (pure) | — | |
| POST `/strategy-drafts/{draft_id}/save` (201) | `save_strategy_revision:152` | `strat_cmd.save_strategy_revision` | body `expected_draft_row_version` / If-Match | ✔ | |
| POST `/strategy-drafts/{draft_id}/clear` | `clear_strategy_draft:170` | `strat_cmd.clear_strategy_draft` | body `expected_draft_row_version` / If-Match | ✔ | |
| GET `/strategy-drafts` | `list_strategy_drafts:193` | `strat_query.list_strategy_drafts` | yok | — | |
| GET `/strategy-drafts/{draft_id}` | `get_strategy_draft:200` | `strat_query.get_strategy_draft` | yok | — | |
| GET `/strategies/{root_id}` | `get_strategy:208` | `strat_query.get_strategy` | yok | — | |
| GET `/strategies/{root_id}/revisions` | `list_strategy_revisions:216` | `strat_query.list_strategy_revisions` | yok | — | |
| GET `/strategy-revisions/{revision_id}` | `get_strategy_revision:225` | `strat_query.get_strategy_revision` | yok | — | |

## trading_signal.py / trade_log.py (ikiz yüzeyler — aynı şekil)

| METHOD path (`{k}` = `trading-signals` \| `trade-logs`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/{k}/source-assets` | `upload_source_asset:62` | `*_cmd.upload_source_asset` | yok | ✔ |
| POST `/{k}/imports` (202) | `request_import:85` | `*_cmd.request_*_import` | yok | ✔ |
| GET `/{k}/imports/{job_id}` | `get_import_report:108` | `*_query.get_import_report` | yok | — |
| POST `/{k}` | `create_*:116` | `*_cmd.create_*_and_attach` | yok | ✔ |
| POST `/{k}/{root_id}/revisions` | `create_*_revision:133` | `*_cmd.create_*_revision` | **body `expected_head_revision_id` (str, `:53`)** | ✔ |
| POST `/{k}/{root_id}/export` (201) | `export_*:150` | `*_cmd.export_*` | yok | ✔ |
| GET `/{k}/{root_id}` | `get_*:171` | `*_query.get_*` | yok | — |

> **Yükleme dosya-tipi kapısı (K-07).** İki yüzey de ortak
> `domain/importing/source_file.py::assert_supported_source_file`'ı çağırır: filename yok/boş →
> **RED** (asla "atla"). Kod sayfa taksonomisine göre ayrışır: Trade Log →
> `UNSUPPORTED_SOURCE_FILE_TYPE`, Trading Signal → `FILE_TYPE_NOT_ALLOWED`.
>
> **Bildirilen zaman dilimi çapraz kontrol edilir (O-28, #449).** Trade Log import'unda beyan edilen
> kaynak time zone'u, kayıtları üreten import ile **karşılaştırılır** (`domain/importing/timezone.py`)
> — beyan artık sorgusuz kabul edilmiyor.
>
> **Trading Signal OHLCV fallback'i onaylı Market Data'ya bağlı (K-08, #443/#8a7a707).** Form
> onaylı bir Market Data revizyonunu bind edebilir; fallback **onaysız** veriye düşemez.

## allocation.py — OCC: **body `expected_row_version` (int)**, `_resolve_expected:65` (DUAL, çelişki → 409)

| METHOD path (ön ek `/mainboard-compositions/{composition_id}`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/portfolio-allocation-draft` | `get_allocation_draft:74` | `alloc_query.get_allocation_draft` | yok | — |
| PUT `/portfolio-allocation-draft` | `put_allocation_draft:87` | `alloc_cmd.upsert_allocation_draft` | body `expected_row_version` / If-Match | ✔ |
| POST `/portfolio-allocation/validate` | `validate_allocation_draft:114` | `alloc_cmd.validate_allocation_draft` | yok | — |
| POST `/portfolio-allocation/sync` | `sync_from_mainboard:124` | `alloc_query.sync_preview` (**pure read**) | yok | — |
| POST `/portfolio-allocation/revisions` (201) | `create_allocation_revision:132` | `alloc_cmd.create_allocation_revision` | body `expected_row_version` / If-Match | ✔ |

> **Çakışma gövdesi (I15B-SL1, #457).** Allocation 409'u artık **çıplak bir hata değil**: zarfın
> `details`'i `current_draft` (sunucunun gördüğü güncel draft) + `changed_paths` (hangi alanların
> ayrıştığı) taşır, böylece istemci körlemesine refetch etmeden neyin değiştiğini gösterebilir.

## readiness.py — OCC: **body `expected_fingerprint` (str)**, `_resolve_expected:47` (DUAL, çelişki → 409); `_header_fingerprint:35` sayısal If-Match'i reddeder

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/mainboard-compositions/{composition_id}/readiness-checks` (201) | `run_readiness_check:56` | `readiness_cmd.run_readiness_check` | body `expected_fingerprint` / If-Match | ✔ |
| GET `/mainboard-compositions/{composition_id}/readiness` | `get_current_readiness:74` | `readiness_query.get_current_readiness` | yok | — |
| GET `/readiness-reports/{report_id}` | `get_readiness_report:84` | `readiness_query.get_readiness_report` | yok | — |

## backtest.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/mainboard-compositions/{composition_id}/backtest-runs` (202) | `request_backtest_run:71` | `backtest_cmd.request_backtest_run` | **body `expected_fingerprint`** / If-Match (`_resolve_fingerprint:62` — sayısal If-Match `_header_fingerprint:52`'de reddedilir) | ✔ |
| GET `/backtest-runs/{run_id}` | `get_backtest_run:92` | `backtest_query.get_backtest_run` | yok | — |
| GET `/backtest-runs/{run_id}/events` | `list_backtest_run_events:100` | `backtest_query.list_backtest_run_events` | yok | — |
| POST `/backtest-runs/{run_id}/retries` (202) | `retry_backtest_run:120` | `backtest_cmd.retry_backtest_run` | yok | ✔ |
| POST `/backtest-runs/{run_id}/cancel` (202) | `cancel_backtest_run:133` | `backtest_cmd.cancel_backtest_run` | **DUAL** — body `expected_row_version` (int) + sayısal `If-Match`, `reconcile_occ_tokens:149` ile uzlaştırılır; çelişki → 409 `OCC_TOKEN_CONFLICT` | ✔ |
| GET `/backtest-results/{result_id}` | `get_backtest_result:164` | `backtest_query.get_backtest_result` | yok | — |
| DELETE `/backtest-results/{result_id}` | `soft_delete_backtest_result:172` | `backtest_cmd.soft_delete_backtest_result` | **DUAL** — body `expected_row_version` (int) / If-Match `rv-N` (`reconcile_occ_tokens:182`) | ✔ |

> **Run stage replay (O-05).** `GET /backtest-runs/{run_id}/events?last_sequence=&limit=`
> yalnız `sequence_no > last_sequence` olaylarını artan sırada döner (limit 1–500,
> varsayılan 200). `get_backtest_run` projeksiyonu `last_sequence` taşır — önce run'ı oku,
> sonra o sequence'tan devam et; arada kayıp olmaz. Aynı mantıksal olay sonsuza dek aynı
> `sequence_no`'yu tutar (`UNIQUE(run_id, sequence_no)`), tekrar teslim edilen olay bu
> anahtarla de-dupe edilir (doc 15 §7, §11).

> **Manifest artık warning SATIRLARINI taşır (S-L4, #456, doc 14 RC-03).**
> `commands/backtest_run.py:864 _manifest_warning_rows` — Run Manifest önceden yalnız
> `warning_count` taşıyordu; sayı "uyarı var mıydı?" sorusunu cevaplar, "hangisi?" sorusunu değil.
> RC-03 uyarının "raporda **VE** sonraki manifest'te" saklanmasını ister, bu yüzden satırların
> kendisi (`"warnings"`, `:553`) pinlenir. **Sonuç:** uyarı taşıyan koşuların manifest hash'i
> değişir — taşımayanlarınki değişmez.

> **Cancel (O-06).** `POST /backtest-runs/{run_id}/cancel` owner/Admin (`ensure_can_edit`,
> run'ın `requested_by_principal_id`'si üzerinden) — 403 yabancı aktöre, 409
> `RUN_NOT_CANCELLABLE` terminal run'a, 409 stale `expected_row_version`'a. **İki yol,
> satır kilidi altında ayrılır:** QUEUED run burada terminal `cancelled` olur (worker'ın
> at-least-once terminal guard'ı teslimatı no-op'a çevirir); PROVISIONING/RUNNING run'da
> yalnız **niyet** yazılır (`cancel_requested_at`) ve worker onu kendi O-05 stage
> sınırında sonlandırır → yanıt `cancellation: "requested"`, `delivery_policy:
> "cancellation_safe_boundary"`. **Hiçbir durumda BacktestResult yaratılmaz** (CR-03,
> doc 15 §16) — dolayısıyla Results History'ye de girmez.

## results_history.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/backtest-results` | `list_backtest_results:44` | `history_query.list_backtest_results` | yok | — |
| POST `/backtest-results/compare` | `compare_backtest_results:56` | `history_query.compare_backtest_results` (**pure read**) | yok | — |
| POST `/backtest-results/{result_id}/delete` | `soft_delete_backtest_result:66` | `backtest_cmd.soft_delete_backtest_result` | **DUAL** — body `expected_row_version` / If-Match (`reconcile_occ_tokens:76`) | ✔ |

> **Görünürlük (O-14, doc 16 §2).** Result okuma kapsamının kökü, sonucun üretildiği
> composition'dır (`mainboard_workspace` registry root'u) — `backtest_result`'ın kendi
> visibility kolonu yoktur. Tek kural `queries/result_access.py`'te: **sahip** +
> `resource_share` (`resource_type='mainboard_workspace'`, `revoked_at IS NULL`) ile
> **explicitly shared** + **Admin** hepsi; **Admin/Supervisor** ayrıca Agent research
> (Analysis Lab) kapsamı — başkasının sonucu **salt-okunur** (`can_edit` yazmayı zaten
> reddeder → `allowed_actions.soft_delete=false`). List yüklemi SQL'de (`has_more`/cursor
> yetkili kümeyi sayar); `GET /backtest-results/{id}`, `POST /backtest-results/compare`,
> `.../metrics`, `.../artifacts/{type}` ve `POST .../exports` aynı kuralı satır bazında yeniden
> değerlendirir (export doc 15 §2'de view ile **aynı satırda** derecelendirilir; RUN kabulü değil —
> `commands/backtest_run.py` kendi `private` kapısını korur).
> **Dürüst sınır:** "published result" V1'de yok — composition'da `visibility_scope`
> kolonu yoktur; composition grant'i YAZAN bir komut yüzeyi de V1'de yok (yalnız okuma).

## metric_profile.py · result_export.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/metric-definitions` | `list_metric_definitions:40` | `metric_profile_query.list_metric_definitions` | yok | — |
| GET `/metric-profiles/resolved` | `get_resolved_metric_profile:50` | `..get_resolved_metric_profile` | yok | — |
| POST `/metric-profiles/{profile_id}/revisions` | `create_metric_profile_revision:57` | `metric_profile_cmd.create_metric_profile_revision` | **DUAL** — body `expected_profile_revision_id` (str) / If-Match (`reconcile_occ_tokens:67`) | ✔ |
| GET `/backtest-results/{result_id}/metrics` | `get_result_metrics:82` | `metric_profile_query.get_result_metrics` | yok | — |
| POST `/backtest-results/{result_id}/exports` (201) | `request_result_export:37` | `export_cmd.request_result_export` | yok | ✔ |
| GET `/backtest-results/{result_id}/artifacts/{artifact_type}` | `query_result_artifact:55` | `artifact_query.query_result_artifact` | yok | — |

> **`{artifact_type}` (I-02):** `equity_curve` · `trade_ledger` · `signal_events` · **`filtered_events`** · `diagnostics` (+ alias'lar: `equity`, `ledger`/`trades`, `signals`/`events`, `filtered`/`no_entry`). Bilinmeyen değer 422 `ARTIFACT_TYPE_INVALID` — sessiz fallback YOK. `filtered_events` `signal_events`'in alt kümesi DEĞİL, kendi tablosu (`filtered_event`) ve kendi `seq` dizisi olan ayrı artifact'tır (doc 15 §3.2, §16). Yanıt zarfı `items` + `next_cursor` yanında `row_count` / `checksum` / `checksum_schema_version` taşır (doc 15 §7); I-02 öncesi materialize edilmiş Result'larda bu üçü `null`.

> **İki eksik export tipi eklendi (S-L2, #460, doc 15 §3.2).** `domain/backtest/export.py:42-43` —
> `ExportType` artık `pinescript_signal_marker` ve `agent_dataset` üyelerini de taşıyor (Data Export
> tablosunun Research Data / Agent Data satırları). Migration **`0040_export_type_agent_pine`**:
> `export_artifact.export_type` **PG ENUM değil**, `SAEnum(native_enum=False)` → düz `VARCHAR(n)`
> ve SQLAlchemy 2.0 varsayılanıyla CHECK constraint'i de yok; üyelik Python'da zorlanır. Bu yüzden
> enum'a bağlı **tek şema gerçeği uzunluktur**: kolon `signal_events` (13) için boyutlandırılmıştı,
> `pinescript_signal_marker` 24 karakter → **24'e genişletildi**. Veri değişimi yok (in-place
> katalog güncellemesi); downgrade 13'e daraltır ve uzun bir değer varsa **gürültülüce başarısız
> olur** — sessiz kırpma yerine doğru sonuç.

## market_data.py — OCC: **`If-Match "rv-N"`** (`row_version_from_if_match`, body token YOK)

| METHOD path (ön ek `/market-datasets`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `` (201) | `create_dataset:73` | `md_cmd.create_market_dataset` | yok | **✔** (O-13; replay aynı root+revision'ı döner) |
| POST `/{id}/raw-uploads` (201) | `start_upload:98` | `md_cmd.start_market_raw_upload` | yok | ✔ |
| POST `/{id}/raw-uploads/finalize` | `finalize_upload:123` | `md_cmd.finalize_market_raw_upload` | yok | ✔ |
| POST `/{id}/analysis` (202) | `request_analysis:139` | `md_cmd.request_market_dataset_analysis` | yok | ✔ |
| POST `/{id}/schema-mapping` | `confirm_mapping:159` | `md_cmd.confirm_market_schema_mapping` | yok | **✔** (O-13; upsert zaten yakınsaktı, key ikinci audit'i engeller) |
| POST `/{id}/revisions` | `create_revision:182` | `md_cmd.create_market_dataset_revision` | If-Match `rv-N` (`:199`) | ✔ |
| POST `/{id}/approve` | `approve:205` | `md_cmd.approve_market_dataset_revision` | If-Match `rv-N` (`:218`) | ✔ |
| POST `/{id}/successor` | `create_successor:224` | `md_cmd.create_successor_revision` | yok | **✔** (O-13; fingerprint `payload`'dır — komutun kendisinin oynattığı head pointer DEĞİL, yoksa retry sonsuza dek 409'lardı) |
| POST `/{id}/deprecate` | `deprecate:249` | `md_cmd.deprecate_market_dataset_revision` | yok | **✔** (O-13) |
| DELETE `` `/{id}` (204) | `soft_delete:266` | `md_cmd.soft_delete_market_dataset` | If-Match `rv-N` (`:279`) | — (OCC korumalı + durum-idempotent) |
| GET `` | `list_datasets:285` | `md_query.list_market_dataset_revisions` | yok | — |
| GET `/{id}` | `get_detail:296` | `md_query.get_market_dataset_detail` | yok | — |
| GET `/{id}/approved-bundle` | `resolve_bundle:307` | `md_query.resolve_approved_market_data_bundle` | yok | — |

> **Cadence'siz tipler de kapsama üretir (O-29, #448).** `domain/market_data/validation_rules.py:288`
> — coverage segment'leri artık **HER** veri tipi için üretilir. Cadence bildiren OHLCV cadence
> bucket'larıyla (`_build_coverage:397`), bildirmeyen tipler günlük bucket'larla
> (`_build_daily_coverage`) bölünür; `CADENCE_GAP` **yalnız** cadence yolunda doğar. Yani
> `dataset_coverage_slice` boşluğu artık "cadence yok" diye sessizce atlanmıyor.

## research_data.py — router seviyesinde `Depends(_require_page_access)` (`:39,45`); OCC: **`If-Match "rv-N"`**

| METHOD path (ön ek `/research-datasets`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `` (201) | `create_dataset:122` | `rd_cmd.create_research_dataset` | yok | **✔** (O-13; replay aynı root+revision, ikinci immutable market-link yok) |
| POST `/{id}/upload-session` (201) | `create_upload_session:149` | `rd_cmd.create_upload_session` | yok | ✔ |
| POST `/{id}/upload-session/finalize` | `finalize_upload:174` | `rd_cmd.finalize_upload` | yok | ✔ |
| POST `/{id}/analysis` (202) | `request_analysis:190` | `rd_cmd.request_research_dataset_analysis` | yok | ✔ |
| POST `/{id}/revisions` | `create_revision:210` | `rd_cmd.create_research_dataset_revision` | If-Match `rv-N` (`:231`) | ✔ |
| POST `/{id}/time-policy` | `set_time_policy:237` | `rd_cmd.set_time_policy` | yok | **✔** (O-13) |
| POST `/{id}/field-definitions` (201) | `define_field:264` | `rd_cmd.define_field` | yok | **✔** (O-13; replay aynı definition, mükerrer satır yok) |
| POST `/{id}/feature-definitions` (201) | `define_feature:291` | `rd_cmd.define_feature` | yok | **✔** (O-13; replay aynı definition) |
| POST `/{id}/approve` | `approve:314` | `rd_cmd.approve_research_dataset_revision` | If-Match `rv-N` (`:327`) | ✔ |
| POST `/{id}/revoke` | `revoke:333` | `rd_cmd.revoke_research_dataset_approval` | If-Match `rv-N` (`:346`) | ✔ |
| DELETE `/{id}` (204) | `soft_delete:352` | `rd_cmd.soft_delete_research_dataset` | If-Match `rv-N` (`:365`) | — |
| GET `` | `list_datasets:371` | `rd_query.list_research_dataset_revisions` | yok | — |
| GET `/{id}` | `get_detail:382` | `rd_query.get_research_dataset_detail` | yok | — |
| POST `/bundles/agent` | `compile_agent_bundle:393` | `rd_jobs.compile_agent_data_bundle` (**pure read**) | yok | — |
| POST `/bundles/backtest-evidence` | `compile_evidence_bundle:406` | `rd_jobs.compile_backtest_evidence_bundle` (**pure read**) | yok | — |

## esp.py — OCC: **`X-Registry-Version` düz int header** (`_REGISTRY_VERSION_HEADER:30`)

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| POST `/embedded-system-packages` (201) | `create_esp:80` | `esp_cmd.create_esp_package` | yok | **✔** (O-13) | |
| GET `/embedded-system-packages` | `list_esp:105` | `esp_query.list_embedded_system_packages` | yok | — | |
| GET `/embedded-system-packages/{entity_id}` | `get_esp:122` | `esp_query.get_esp_detail` | yok | — | |
| POST `/embedded-system-packages/{entity_id}/validate` | `validate_esp:133` | `esp_cmd.run_resolver_validation` | yok | ✔ | |
| POST `/embedded-system-packages/{entity_id}/activate` | `activate_esp:152` | `esp_cmd.activate_resolver` | `X-Registry-Version` (`_registry_version:33`) | ✔ | (command: Admin) |
| POST `/embedded-system-packages/{entity_id}/deprecate` | `deprecate_esp:172` | `esp_cmd.deprecate_resolver` | `X-Registry-Version` | ✔ | (command: Admin) |
| POST `/embedded-system-packages/resolve` | `resolve_dependency:191` | `esp_query.resolve_embedded_dependency` (**pure read**) | yok | — | `require_authenticated:198` |

## instrument.py — OCC: **`X-Registry-Version` düz int header** (`_registry_version:32`)

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| POST `/instruments` (201) | `register_instrument:71` | `instrument_cmd.register_instrument` | yok | ✔ | |
| GET `/instruments` | `list_instruments:94` | `instrument_query.list_instruments` | yok | — | |
| GET `/instruments/{instrument_id}` | `get_instrument:109` | `instrument_query.get_instrument_detail` | yok | — | |
| POST `/instruments/{instrument_id}/aliases` (201) | `add_alias:122` | `instrument_cmd.add_instrument_alias` | yok | ✔ | |
| POST `/instruments/{instrument_id}/deprecate` | `deprecate_instrument:138` | `instrument_cmd.deprecate_instrument` | `X-Registry-Version` | ✔ | |
| POST `/instruments/resolve` | `resolve_scope:156` | `instrument_query.resolve_scope` | yok | — | `require_authenticated:161` |

## create_package.py — OCC: **`X-Request-Version` düz int header** (`_request_version:33`)

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/create-package/requests` (201) | `create_request:85` | `cp_cmd.create_package_request` | yok | ✔ |
| GET `/create-package/requests` | `list_requests:110` | `cp_query.list_package_requests` | yok | — |
| GET `/create-package/requests/{request_id}` | `get_request:121` | `cp_query.get_package_request` | yok | — |
| POST `../pre-check` | `run_pre_check:142` | `cp_cmd.run_precheck` → **admission + `default` aktör dispatch** (`_dispatch_create_package_job:128`) | `X-Request-Version` | ✔ |
| POST `../generate-candidate` | `generate_candidate:160` | `cp_cmd.submit_candidate_generation` → **admission + `default` aktör dispatch** | `X-Request-Version` | ✔ |
| POST `../draft` | `create_draft:178` | `cp_cmd.create_draft_from_candidate` | **body `expected_candidate_hash`** | ✔ |
| POST `../validate` | `run_validation:195` | `cp_cmd.start_package_validation_run` → **admission + `default` aktör dispatch** | `X-Request-Version` | ✔ |
| POST `../request-revision` | `request_revision:213` | `cp_cmd.request_package_revision` | `X-Request-Version` | ✔ |
| POST `../baseline` (201) | `upload_baseline:229` | `cp_cmd.upload_baseline_asset` | `X-Request-Version` | ✔ |
| POST `../baseline-parse` | `parse_baseline:257` | `cp_cmd.start_baseline_parse` → **admission + `default` aktör dispatch** | `X-Request-Version` | ✔ |
| POST `../approve` | `approve_request:278` | `cp_cmd.approve_and_publish` | **body `expected_head_revision_id`** | ✔ |
| GET `/dependency-scans/{scan_id}` | `get_scan:296` | `cp_query.get_dependency_scan` | yok | — |
| GET `/validation-runs/{validation_run_id}` | `get_validation_run:304` | `cp_query.get_validation_run` | yok | — |
| GET `/baseline-assets/{baseline_asset_id}` | `get_baseline_asset:314` | `cp_query.get_baseline_asset` | yok | — |

> **Async düzlem (F-01a + F-01b + F-01c).** Pre-Check / generate-candidate / validate /
> baseline-parse artık **admission**'dır: durable QUEUED `jobs` satırı yazılır,
> `_dispatch_create_package_job:128` tx commit'inden sonra `default` kuyruğundaki tek aktörü
> tetikler ve yanıt anında döner (`checking` / `candidate_generating` / `validation_running` /
> `parsing` — asla var olmayan bir sonuç). Gerçek sonuç worker'dan `resource.changed` outbox'ı
> ile projeksiyona iner. Gate'ler admission'da kalır (PC-13 → `PRECHECK_BLOCKED/STALE`, draft
> yokluğu → `CANDIDATE_NOT_READY`, head baseline yokluğu → `BASELINE_ASSET_NOT_FOUND`, eksik
> metadata → `BASELINE_METADATA_INVALID`, `X-Request-Version` → 409). `PARSE_FAILED` artık
> HTTP hatası değil, worker'ın yazdığı durable `failed` attempt'tir.
> Ayrıntı: `JOBS_AND_EVENTS.md` §`default` kuyruğu.

## library.py · sharing.py · package_import.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/library` | `list_library:72` | `library_query.list_packages` | yok | — |
| GET `/library/{entity_id}` | `get_library_package:106` | `library_query.get_package_detail` | yok | — |
| POST `/library/{entity_id}/deprecate` | `deprecate_package:117` | `pkg_cmd.deprecate_package` | **yok** (doğrulandı: deprecate revision eklemez, head ile yarışamaz — kardeş `market_data` deprecate ile aynı) | **✔** (O-13; key olmadan ikinci çağrı `LIFECYCLE_BLOCKED`, key ile saklı yanıt replay olur) |
| DELETE `/library/{entity_id}` (204) | `soft_delete_package:136` | `pkg_cmd.soft_delete_package` | If-Match `rv-N` (`:151`) | — |
| POST `/library/{entity_id}/derive` (201) | `derive_package:157` | `pkg_cmd.derive_package` | yok (docstring açıkça "No OCC") | ✔ |
| POST `/library/{entity_id}/revisions` (201) | `create_package_revision:180` | `pkg_cmd.create_package_revision` | **body `expected_head_revision_id`** | ✔ |
| **POST `/library/{entity_id}/validation-runs` (201)** | `request_package_validation:205` | `pkg_cmd.request_package_validation` — **S-L3 (#461):** doc 08 §7 "Request validation"; CreatePackage düzlemindeki koşuyu **sarar** (yedi kontrol, değişmez kanıt satırı, durable job ve durum makinesi aynen kalır) | **body `expected_head_revision_id`** + head-match kuralı (`request-approval` ile birebir aynı) | ✔ |
| POST `/library/{entity_id}/request-approval` | `request_package_approval:230` | `pkg_cmd.request_package_approval` | **body `expected_head_revision_id`** | ✔ |
| POST `/library/{entity_id}/approve` | `approve_package:252` | `pkg_cmd.approve_and_publish_package` | **body `expected_head_revision_id`** | ✔ |
| POST `/library/{entity_id}/export` | `export_package:275` | `pkg_cmd.export_package` | yok | ✔ |
| POST `/library/{entity_id}/shares` (201) | `share_package` `sharing.py:35` | `sharing_cmd.share_package` | If-Match `rv-N` (`:47`) | ✔ |
| GET `/library/{entity_id}/shares` | `list_package_shares` `sharing.py:53` | `sharing_query.list_package_shares` | yok | — |
| DELETE `/library/{entity_id}/shares/{share_id}` | `revoke_package_share` `sharing.py:64` | `sharing_cmd.revoke_package_share` | If-Match `rv-N` (`:76`) | ✔ |
| GET `/library-shared-with-me` | `list_shared_with_me` `sharing.py:82` | `library_query.list_shared_with_me` | yok | — |
| POST `/package-imports` (202) | `submit_package_import` `package_import.py:31` | `import_cmd.submit_package_import` | yok | ✔ |
| GET `/package-imports` | `list_package_imports:50` | `import_query.list_import_reports` | yok | — |
| GET `/package-imports/{import_job_id}` | `get_package_import:57` | `import_query.get_import_report` | yok | — |

> **`validation-runs` 409/422 taksonomisi (S-L3).** Bayat head → 409 `PACKAGE_REVISION_CONFLICT`;
> hâlihazırda uçan bir koşu → 409 `VALIDATION_ALREADY_RUNNING`; doğrulanabilir draft'ı olmayan
> paket → 422 `VALIDATION_PIPELINE_UNAVAILABLE`. Katalog projeksiyonundaki
> `permissions.can_request_validation` bayrağı **yalnız** kökü gerçekten bir Create Package draft'ı
> destekliyorsa `true` olur — projeksiyon yapılamayacak bir eylemi asla reklam etmez (doc 08 §4.3).
> **Dürüst sınır:** bu uç V1'de yalnız backend'de; `frontend/src/lib/library.ts` bayrağı tipliyor
> ama çağıran bir hook henüz yok.

## rationale.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/rationale-families` | `list_families:60` | `rationale_query.list_families` | yok | — |
| POST `/rationale-families` (201) | `create_family:72` | `rationale_cmd.create_family` | yok | ✔ |
| **GET `/rationale-families:suggest`** | `suggest_families:92` | `rationale_query.suggest_families` — **S-L5 (#459):** salt-okuma Family önerisi (master ref Module 6 §11). Sorgu `q` (boş varsayılan) + `limit` (`SUGGEST_DEFAULT_LIMIT`, 1–100) | **yok** (mutasyon yok → uzlaşılacak bir şey yok) | — |
| GET `/rationale-families/{entity_id}` | `get_family:104` | `rationale_query.get_family` (yanıtta `ETag` = `rv-N`) | yok | — |
| POST `/rationale-families/{entity_id}/revisions` | `revise_family:115` | `rationale_cmd.revise_family` | **body `expected_head_revision_id`** — **O-12: atıl `If-Match` parametresi KALDIRILDI** (okunuyor ama hiç kullanılmıyordu; family ETag'i `rv-N` row_version, bu token revision id → farklı eksen, uzlaştırma sahte 409 üretirdi) | ✔ |
| DELETE `/rationale-families/{entity_id}` | `soft_delete_family:142` | `rationale_cmd.soft_delete_family` | If-Match `rv-N` (`:151`) | — |
| GET `/package-rationale-assignments` | `list_assignments:156` | `rationale_query.list_package_assignments` | yok | — |
| POST `/package-rationale-assignments:batch` | `batch_assign:167` | `rationale_cmd.batch_assign_rationale` | **body `expected_table_version` (str)** + per-item `expected_head_revision_id` / `expected_family_current_revision_id` | ✔ |

> **`:suggest` neden `/{entity_id}`'den ÖNCE bildirilir (`rationale.py:88-91`).** FastAPI route'ları
> **bildirim sırasına** göre eşler; `:suggest` sonra gelseydi `entity_id` olarak bağlanır ve var
> olmayan bir family'de 404 verirdi. Öneri **çıkarımdır, asla sessiz yazma değildir** (doc §9.3):
> bir chip'e tıklamak yalnız mevcut seçiciyi doldurur, Family yaratmaz — uygulama ayrı, audit'li
> bir komut olarak kalır.

## agent_lab.py — OCC: **`If-Match` → int row_version** (`_parse_if_match:58`)

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| GET `/agent-workspace/overview` | `get_overview:80` | `agent_workspace_query.get_overview` | yok | — | |
| GET `/agent-tasks` | `list_tasks:85` | `..list_tasks` | yok | — | |
| GET `/agent-tasks/{task_id}` | `get_task:97` | `..get_task` | yok | — | |
| GET `/agent-tasks/{task_id}/tool-calls` | `list_task_tool_calls:102` | `tool_gateway_query.list_task_tool_calls` | yok | — | |
| GET `/agent-tool-calls/{tool_call_id}` | `get_tool_call:113` | `tool_gateway_query.get_tool_call` | yok | — | |
| GET `/lab/messages` | `list_lab_messages:120` | `..list_lab_messages` | yok | — | |
| GET `/hypotheses` | `list_hypotheses:132` | `..list_hypotheses` | yok | — | |
| POST `/lab/messages` | `send_lab_message:147` | `lab_message_cmd.record_discussion_message` | yok | ✔ | |
| POST `/agent-directives` (202) | `queue_directive:162` | `agent_control_cmd.create_directive` | yok | ✔ | |
| POST `/agent-runtime/pause` (202) | `pause_runtime:179` | `agent_control_cmd.pause_runtime` | If-Match → `expected_row_version` | ✔ | |
| POST `/agent-runtime/resume` (202) | `resume_runtime:194` | `agent_control_cmd.resume_runtime` | If-Match → `expected_row_version` | ✔ | |
| POST `/agent-runs/{run_id}/stop` (202) | `stop_run:209` | `agent_control_cmd.stop_run` | If-Match → `expected_row_version` | ✔ | |
| GET `/agent-events/stream` | `agent_events_stream:237` | heartbeat SSE | yok | — | `require_role(_LAB_ROLES):241` |

## manual.py — iki farklı OCC token'ı

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| GET `/manual/stream` | `stream:73` | `queries.manual.get_manual_stream` | yok | — | |
| GET `/manual/search` | `search:82` | `queries.manual.search_manual` | yok | — | |
| POST `/admin/manual/documents` (201) | `create_document:92` | `commands.manual.*` | **body `expected_stream_version` (int)** | ✔ | `require_manual_admin:97` |
| POST `/admin/manual/documents:upload` (201) | `upload_document:110` | `commands.manual.*` | **Form `expected_stream_version`** | ✔ | `require_manual_admin:123` |
| POST `/admin/manual/documents/{id}/revisions` (201) | `replace_revision:138` | `commands.manual.*` | **DUAL** — body `expected_head_revision_id` (str) / If-Match (`_expected_revision:62`) | ✔ | `require_manual_admin:145` |
| DELETE `/admin/manual/documents/{id}` | `soft_delete_document:158` | `commands.manual.*` | **body `expected_stream_version` (opsiyonel gövde)** | ✔ | `require_manual_admin:164` |
| POST `/admin/manual/documents/{id}:restore` | `restore_document:177` | `commands.manual.*` | yok | ✔ | `require_trash_admin:182` |

> **Bayat arama çıpası kurtarılır (O-16, #444).** `GET /manual/search` sonucundaki bir çıpa artık
> revizyon değişmişse **hiçbir yere atlamaz** yerine kurtarılır — kullanıcı sessiz bir 404 yerine
> en yakın geçerli konuma iner.
>
> **Upload pipeline'ının kendi hata kodu (S-L6, #455).** `:upload` boru hattı bir aşamada çökerse
> yanıt `UPLOAD_JOB_FAILED` taşır (`shared/errors.py:2071`, doc 21 §10) — yani "yeniden dene",
> "dokümanını düzelt" **değil** (`commands/manual.py:109-116`). Önceden altyapı hatası kullanıcı
> hatası gibi raporlanıyordu.

## trash.py — OCC: **body `expected_*` (int) DUAL**, `_expected_version:91` → `reconcile_occ_tokens:99`

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| DELETE `/entities/{entity_id}` (204) | `soft_delete:103` | `commands.deletion.soft_delete_entity` | **O-18: DUAL** — body `expected_row_version` (opsiyonel) / `If-Match` `rv-N`; kilit ALTINDA `check_row_version` (önceden **hiç** token yoktu → yarışan bir düzenleme sahibinin altından silinebiliyordu) | **✔** (O-13) | |
| GET `/trash-entries` | `get_trash_entries:133` | `queries.trash.list_trash_entries` | yok | — | `require_trash_admin:140` |
| GET `/trash-entries/{id}` | `get_trash_entry:147` | `queries.trash.get_trash_entry_detail` | yok | — | `require_trash_admin:151` |
| GET `/trash-entries/{id}/restore-preflight` | `restore_preflight:156` | `queries.trash.get_restore_preflight` | yok (salt-okuma) | — (salt-okuma) | `require_trash_admin:167` |
| POST `/trash-entries/{id}/restore` | `restore:172` | `commands.deletion.*` | **DUAL** body `expected_head_revision_id` (int) / If-Match; **O-17: body `resolution` (typed enum, opsiyonel)** | ✔ | `require_trash_admin:179` |
| POST `/trash-entries/{id}/purge` (202) | `purge:192` | `commands.deletion.*` | **DUAL** body `expected_head_revision_id` (int) / If-Match | ✔ | `require_trash_admin:199` |

> **Detay snapshot'ı redakte + boyut sınırlı (I-09, #462, doc 20 §12).** `GET /trash-entries/{id}`
> nesnenin silinme anındaki snapshot'ını gösterir; bu snapshot artık **redaksiyondan** geçer ve
> **boyutu sınırlanır** (`domain/trash/redaction.py`) — Trash detayı sınırsız bir veri ihraç yüzeyi
> değildir.

> **Purge 202 gövdesi = iki ad, tek değer (O-30, #451).** `commands/deletion.py::request_purge`
> gövdesi hem `deletion_state` hem `root_lifecycle_state` anahtarını **`"purge_pending"`**
> değeriyle döndürür — doc 20 §4/§7 ADI, §9.2 DEĞERİ verir; ikisi asla ayrışmaz. Gövde
> `routes/trash.py::PurgeAcceptedResponse` ile **şemada yayımlanır** (bare `dict` dönüşü drift
> guard'ı yeşil tutarken sözleşmeyi görünmez bırakıyordu). O-30 ÖNCESİ yazılmış Idempotency-Key
> kayıtları bu alanı taşımaz → replay'de `deletion_state`'ten **kopyalanarak** backfill edilir
> (`response_ref` JSON kolonu mutate EDİLMEZ). Tam gerekçe: `CLAUDE.md` §O-30.

## capability.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| GET `/capabilities` | `capabilities_index:75` | `queries.capability.*` | yok | — | |
| GET `/capabilities/{key}` | `capability_detail:82` | `queries.capability.*` | yok | — | |
| POST `/capabilities/{key}/lifecycle-transitions` | `lifecycle_transition:90` | `commands.capability.*` | **body `expected_registry_version` (int, ZORUNLU `:55`)** | ✔ | `require_capability_admin:96` |
| GET `/capabilities/{key}/lifecycle-transitions` | `lifecycle_transitions_index:110` | `queries.capability.*` | yok | — | |
| GET `/future-dev/graphic-view/overview` | `graphic_view_overview:121` | `queries.capability.*` | yok | — | |
| POST `/view-datasets/query` (201) | `view_dataset_query:128` | `commands.capability.*` | yok | ✔ | (capability gate, command) |
| POST `/analysis-artifacts` (201) | `analysis_artifact_create:146` | `commands.capability.*` | yok | ✔ | (capability gate, command) |
| GET `/view-datasets` | `view_datasets_index:169` | `queries.capability.*` | yok | — | |
| GET `/view-datasets/{id}` | `view_dataset_detail:178` | `queries.capability.*` | yok | — | |
| GET `/analysis-artifacts` | `analysis_artifacts_index:186` | `queries.capability.*` | yok | — | |
| GET `/analysis-artifacts/{id}` | `analysis_artifact_detail:202` | `queries.capability.*` | yok | — | |

---

## Doğrulanmamış noktalar (`?`) — **O-12/O-13'te üçü de kapandı**

- ~~`identity.py:48` POST `/users/{user_id}/role`~~ → **çözüldü:** OCC **yok** (legacy yüzey;
  OCC'li yol `PATCH /admin/users/{id}/role`), `Idempotency-Key` **eklendi**.
- ~~`library.py:108` POST `/library/{entity_id}/deprecate`~~ → **çözüldü:** OCC **yok**
  (deprecate revision eklemez), `Idempotency-Key` **eklendi**.
- ~~`trash.py:59` DELETE `/entities/{entity_id}`~~ → **çözüldü:** O-18 ile OCC
  (`expected_row_version`, kilit altında) + `Idempotency-Key` **eklendi**.

## Idempotency-Key OKUMAYAN mutating op'lar — bilerek (O-13 sonrası 16)

> **2026-07-29 tazeleme.** Bu dalganın iki yeni mutating ucu (`library.request_package_validation`,
> `strategy.set_strategy_rationale_family`) **`Idempotency-Key` OKUR** → liste **16'da kaldı**.
> Yeni `rationale.suggest_families` bir GET'tir, mutating op sayılmaz.

Hepsi gerekçeli, hiçbiri açık kusur değil:

| Grup | Op'lar | Neden |
|---|---|---|
| Salt-okuma POST (8) | `allocation.validate/sync` · `strategy.validate_draft` · `results_history.compare` · `esp.resolve_dependency` · `instrument.resolve_scope` · `research_data.compile_agent_bundle/compile_evidence_bundle` | hiçbir satır yazmaz → tekilleştirilecek yan etki yok |
| Oturum işlemleri (3) | `auth.login/logout/reauth` | tekrarı yeni kaynak yaratmaz |
| OCC korumalı soft-delete (4) | `library.soft_delete_package` · `market_data.soft_delete` · `rationale.soft_delete_family` · `research_data.soft_delete` | `If-Match` OCC + durum-idempotent (tekrar = no-op) |
| Geçici opener (1) | `mainboard.start_external_work_object_draft` | senkron saf fonksiyon, kalıcı satır yazmaz |
