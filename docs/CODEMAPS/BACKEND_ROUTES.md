# BACKEND_ROUTES — HTTP yüzeyi

Tüm router'lar `apps/api/main.py:116-146` içinde `prefix=settings.api_base_path` ile mount edilir.
Varsayılan prefix: **`/api/v1`** (`config/settings.py:34`). Aşağıdaki path'ler prefix'siz yazılmıştır.

Sütunlar:
- **OCC** — imzada gözlenen eşzamanlılık token'ı. `yok` = imzada hiç yok.
- **Idem** — `Idempotency-Key` header'ı okunuyor mu (`✔`/`—`).
- **Rol kapısı** — route katmanındaki açık `require_*`. Boş = command/query katmanında.

---

## DUAL-TOKEN KURALI (O-12) — tek ve bağlayıcı

**16 mutating op** eşzamanlılık token'ını **iki yerden** kabul eder: gövde (`expected_*`,
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
| GET `/live` | `live` `health.py:31` | — | |
| GET `/ready` | `ready` `health.py:36` | — | |
| GET `` (meta) | `meta` `meta.py:22` | — | |
| GET `/metrics` | `metrics_endpoint` `metrics.py:98` | Prometheus text exposition | `require_metrics_scraper:40` (O-22 — Bearer `ENTROPIA_METRICS_TOKEN`; yok=401 `METRICS_SCRAPE_UNAUTHORIZED`, yanlış=403 `METRICS_SCRAPE_FORBIDDEN`; token yapılandırılmamışsa production'da fail-closed 403, local'de açık) |

| POST `/login` | `login` `auth.py:107` | `auth_commands.login` | (anonim; `AUTH_MODE=dev`'de insan login sunucu-reddi — #346/#347) |
| POST `/logout` | `logout` `auth.py:132` | `auth_commands.logout` | |
| GET `/bootstrap-status` | `bootstrap_status` `auth.py:148` | `auth_commands.bootstrap_status` (döner: `login_capable_admin_exists` — PROV-05) | (anonim) |
| POST `/reauth` | `reauth` `auth.py:164` | `auth_commands.reauthenticate` | `require_authenticated` |
| GET `/me` | `me` `identity.py:37` | ctx.actor | |
| POST `/users/{user_id}/role` | `set_user_role` `identity.py:49` | `commands.roles.change_user_role` — OCC **yok** (doğrulandı: legacy yüzey; OCC'li yol `PATCH /admin/users/{id}/role`), **Idem ✔** (O-13; replay `version`'ı ikinci kez artırmaz) | `require_admin` |

## admin_panel.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| GET `/admin/users` | `list_users:70` | `user_registry_query.list_registered_users` | yok | — | `require_admin_panel` |
| PATCH `/admin/users/{user_id}/role` | `assign_role:82` | `role_assignment_cmd.assign_user_role` | **DUAL** — body `expected_head_revision_id` (int, ge=1, ZORUNLU) + `If-Match`; eşitlik `reconcile_occ_tokens` ile. **O-12 öncesi çelişki 422 VALIDATION_ERROR'dı** (tüm dual uçlardan farklı şekil) → artık kanonik **409 `OCC_TOKEN_CONFLICT`** | ✔ | `require_admin_panel` |
| GET `/admin/system-actors` | `list_system_actors:105` | `user_registry_query.list_system_actors` | yok | — | `require_admin_panel` |
| GET `/admin/role-matrix` | `role_matrix:111` | `user_registry_query.get_role_matrix` | yok | — | `require_admin_panel` |
| GET `/admin/logs` | `list_logs:120` | `log_query.list_log_events` | yok | — | `require_admin_panel` |
| GET `/admin/log-resource-types` | `list_log_resource_types:157` | `log_query.list_resource_types` | yok | — | `require_admin_panel` |
| GET `/admin/logs/{event_id}` | `get_log:168` | `log_query.get_log_event` | yok | — | `require_admin_panel` |
| POST `/admin/data-queue/redeliver` | `redeliver_data_queue:177` | `data_queue_cmd.redeliver_data_queue_jobs` | yok | **✔** (O-13) | `require_admin_panel` |

| GET `/audit-events` `audit.py:16` | `audit_events` | `queries.audit_log.list_audit_events` | yok | — | `require_admin:21` |

## mainboard.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| GET `/mainboards/default` | `get_default_mainboard:71` | `mb_query.get_default_mainboard` | yok | — | |
| POST `/external-work-object-drafts/{kind}` | `start_external_work_object_draft:87` | (geçici opener) | yok | — (**bilerek**: O-13 listesindeydi ama **mutating DEĞİL** — `commands/mainboard.py:106` senkron saf fonksiyon, session'a dokunmaz, `{"draft_id": new_id(...), "unsaved": true}` döner; kalıcı satır yok → tekilleştirilecek yan etki yok) | |
| POST `/work-objects` | `create_work_object:95` | `mb_cmd.create_work_object` | yok | ✔ | |
| POST `/work-objects/{root_id}/revisions` | `create_work_object_revision:112` | `mb_cmd.create_work_object_revision` | **body `expected_head_revision_id` (str, opsiyonel)** | ✔ | |
| POST `/mainboards/{workspace_id}/items` | `attach_mainboard_item:131` | `mb_cmd.attach_mainboard_item` | yok | ✔ | |
| PATCH `/mainboard-items/{item_id}` | `patch_mainboard_item:150` | `mb_cmd.patch_mainboard_item` | **DUAL** — body `expected_row_version` (int) veya `If-Match`; en az biri ZORUNLU, çelişki → 409 | ✔ | |
| POST `/mainboards/{workspace_id}/snapshots` | `create_composition_snapshot:180` | `mb_cmd.create_composition_snapshot` | yok | ✔ | |
| DELETE `/work-objects/{root_id}` | `soft_delete_work_object:194` | `mb_cmd.soft_delete_work_object` | yok | ✔ | |

## strategy.py — OCC: **body `expected_draft_row_version` (int)**, `_resolve_expected_version:53` body > If-Match, sonuç ZORUNLU int

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| POST `/strategy-drafts` | `create_strategy_draft:69` | `strat_cmd.create_strategy_draft` / `derive_strategy_draft_from_package` | yok | ✔ | |
| PATCH `/strategy-drafts/{draft_id}` | `patch_strategy_draft:96` | `strat_cmd.patch_strategy_draft` | body `expected_draft_row_version` / If-Match | ✔ | |
| POST `/strategy-drafts/{draft_id}/validate` | `validate_strategy_draft:116` | `strat_cmd.validate_strategy_draft` | yok (pure) | — | |
| POST `/strategy-drafts/{draft_id}/save` | `save_strategy_revision:124` | `strat_cmd.save_strategy_revision` | body `expected_draft_row_version` / If-Match | ✔ | |
| POST `/strategy-drafts/{draft_id}/clear` | `clear_strategy_draft:142` | `strat_cmd.clear_strategy_draft` | body `expected_draft_row_version` / If-Match | ✔ | |
| GET `/strategy-drafts` | `list_strategy_drafts:165` | `strat_query.list_strategy_drafts` | yok | — | |
| GET `/strategy-drafts/{draft_id}` | `get_strategy_draft:172` | `strat_query.get_strategy_draft` | yok | — | |
| GET `/strategies/{root_id}` | `get_strategy:180` | `strat_query.get_strategy` | yok | — | |
| GET `/strategies/{root_id}/revisions` | `list_strategy_revisions:188` | `strat_query.list_strategy_revisions` | yok | — | |
| GET `/strategy-revisions/{revision_id}` | `get_strategy_revision:197` | `strat_query.get_strategy_revision` | yok | — | |

## trading_signal.py / trade_log.py (ikiz yüzeyler — aynı şekil)

| METHOD path (`{k}` = `trading-signals` \| `trade-logs`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/{k}/source-assets` | `upload_source_asset:62` | `*_cmd.upload_source_asset` | yok | ✔ |
| POST `/{k}/imports` (202) | `request_import:85` | `*_cmd.request_*_import` | yok | ✔ |
| GET `/{k}/imports/{job_id}` | `get_import_report:108` | `*_query.get_import_report` | yok | — |
| POST `/{k}` | `create_*:116` | `*_cmd.create_*_and_attach` | yok | ✔ |
| POST `/{k}/{root_id}/revisions` | `create_*_revision:133` | `*_cmd.create_*_revision` | **body `expected_head_revision_id` (str, `:53`)** | ✔ |
| POST `/{k}/{root_id}/export` | `export_*:150` | `*_cmd.export_*` | yok | ✔ |
| GET `/{k}/{root_id}` | `get_*:171` | `*_query.get_*` | yok | — |

## allocation.py — OCC: **body `expected_row_version` (int)**, `_resolve_expected:61` body > If-Match

| METHOD path (ön ek `/mainboard-compositions/{composition_id}`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/portfolio-allocation-draft` | `get_allocation_draft:68` | `alloc_query.get_allocation_draft` | yok | — |
| PUT `/portfolio-allocation-draft` | `put_allocation_draft:81` | `alloc_cmd.upsert_allocation_draft` | body `expected_row_version` / If-Match | ✔ |
| POST `/portfolio-allocation/validate` | `validate_allocation_draft:108` | `alloc_cmd.validate_allocation_draft` | yok | — |
| POST `/portfolio-allocation/sync` | `sync_from_mainboard:118` | `alloc_query.sync_preview` (**pure read**) | yok | — |
| POST `/portfolio-allocation/revisions` (201) | `create_allocation_revision:126` | `alloc_cmd.create_allocation_revision` | body `expected_row_version` / If-Match | ✔ |

## readiness.py — OCC: **body `expected_fingerprint` (str)**, `_resolve_expected:35` body > If-Match

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/mainboard-compositions/{composition_id}/readiness-checks` (201) | `run_readiness_check:49` | `readiness_cmd.run_readiness_check` | body `expected_fingerprint` | ✔ |
| GET `/mainboard-compositions/{composition_id}/readiness` | `get_current_readiness:67` | `readiness_query.get_current_readiness` | yok | — |
| GET `/readiness-reports/{report_id}` | `get_readiness_report:77` | `readiness_query.get_readiness_report` | yok | — |

## backtest.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/mainboard-compositions/{composition_id}/backtest-runs` (202) | `request_backtest_run:57` | `backtest_cmd.request_backtest_run` | **body `expected_fingerprint`** / If-Match (`_resolve_fingerprint:45` — sayısal If-Match reddedilir) | ✔ |
| GET `/backtest-runs/{run_id}` | `get_backtest_run:78` | `backtest_query.get_backtest_run` | yok | — |
| GET `/backtest-runs/{run_id}/events` | `list_backtest_run_events:86` | `backtest_query.list_backtest_run_events` | yok | — |
| POST `/backtest-runs/{run_id}/retries` (202) | `retry_backtest_run:106` | `backtest_cmd.retry_backtest_run` | yok | ✔ |
| POST `/backtest-runs/{run_id}/cancel` (202) | `cancel_backtest_run:133` | `backtest_cmd.cancel_backtest_run` | **DUAL** — body `expected_row_version` (int) + sayısal `If-Match`, `reconcile_occ_tokens` ile uzlaştırılır; çelişki → 409 `OCC_TOKEN_CONFLICT` | ✔ |
| GET `/backtest-results/{result_id}` | `get_backtest_result:153` | `backtest_query.get_backtest_result` | yok | — |
| DELETE `/backtest-results/{result_id}` | `soft_delete_backtest_result:161` | `backtest_cmd.soft_delete_backtest_result` | **body `expected_row_version` (int)** / If-Match `rv-N` (`:169-171`) | ✔ |

> **Run stage replay (O-05).** `GET /backtest-runs/{run_id}/events?last_sequence=&limit=`
> yalnız `sequence_no > last_sequence` olaylarını artan sırada döner (limit 1–500,
> varsayılan 200). `get_backtest_run` projeksiyonu `last_sequence` taşır — önce run'ı oku,
> sonra o sequence'tan devam et; arada kayıp olmaz. Aynı mantıksal olay sonsuza dek aynı
> `sequence_no`'yu tutar (`UNIQUE(run_id, sequence_no)`), tekrar teslim edilen olay bu
> anahtarla de-dupe edilir (doc 15 §7, §11).

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
| POST `/backtest-results/{result_id}/delete` | `soft_delete_backtest_result:66` | `backtest_cmd.soft_delete_backtest_result` | body `expected_row_version` (`:40`) / If-Match | ✔ |

> **Görünürlük (O-14, doc 16 §2).** Result okuma kapsamının kökü, sonucun üretildiği
> composition'dır (`mainboard_workspace` registry root'u) — `backtest_result`'ın kendi
> visibility kolonu yoktur. Tek kural `queries/result_access.py`'te: **sahip** +
> `resource_share` (`resource_type='mainboard_workspace'`, `revoked_at IS NULL`) ile
> **explicitly shared** + **Admin** hepsi; **Admin/Supervisor** ayrıca Agent research
> (Analysis Lab) kapsamı — başkasının sonucu **salt-okunur** (`can_edit` yazmayı zaten
> reddeder → `allowed_actions.soft_delete=false`). List yüklemi SQL'de (`has_more`/cursor
> yetkili kümeyi sayar); `GET /backtest-results/{id}`, `POST /backtest-results/compare`,
> `.../metrics` ve `.../artifacts/{type}` aynı kuralı satır bazında yeniden değerlendirir.
> **Dürüst sınır:** "published result" V1'de yok — composition'da `visibility_scope`
> kolonu yoktur; composition grant'i YAZAN bir komut yüzeyi de V1'de yok (yalnız okuma).

## metric_profile.py · result_export.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/metric-definitions` | `list_metric_definitions:39` | `metric_profile_query.list_metric_definitions` | yok | — |
| GET `/metric-profiles/resolved` | `get_resolved_metric_profile:49` | `..get_resolved_metric_profile` | yok | — |
| POST `/metric-profiles/{profile_id}/revisions` | `create_metric_profile_revision:56` | `metric_profile_cmd.create_metric_profile_revision` | **body `expected_profile_revision_id` (str, `:35`)** + If-Match okunuyor `:60` | ✔ |
| GET `/backtest-results/{result_id}/metrics` | `get_result_metrics:78` | `metric_profile_query.get_result_metrics` | yok | — |
| POST `/backtest-results/{result_id}/exports` (201) | `request_result_export:37` | `export_cmd.request_result_export` | yok | ✔ |
| GET `/backtest-results/{result_id}/artifacts/{artifact_type}` | `query_result_artifact:55` | `artifact_query.query_result_artifact` | yok | — |

## market_data.py — OCC: **`If-Match "rv-N"`** (`row_version_from_if_match`, body token YOK)

| METHOD path (ön ek `/market-datasets`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `` (201) | `create_dataset:73` | `md_cmd.create_market_dataset` | yok | **✔** (O-13; replay aynı root+revision'ı döner) |
| POST `/{id}/raw-uploads` (201) | `start_upload:96` | `md_cmd.start_market_raw_upload` | yok | ✔ |
| POST `/{id}/raw-uploads/finalize` | `finalize_upload:121` | `md_cmd.finalize_market_raw_upload` | yok | ✔ |
| POST `/{id}/analysis` (202) | `request_analysis:137` | `md_cmd.request_market_dataset_analysis` | yok | ✔ |
| POST `/{id}/schema-mapping` | `confirm_mapping:157` | `md_cmd.confirm_market_schema_mapping` | yok | **✔** (O-13; upsert zaten yakınsaktı, key ikinci audit'i engeller) |
| POST `/{id}/revisions` | `create_revision:178` | `md_cmd.create_market_dataset_revision` | If-Match `rv-N` (`:195`) | ✔ |
| POST `/{id}/approve` | `approve:201` | `md_cmd.approve_market_dataset_revision` | If-Match `rv-N` (`:214`) | ✔ |
| POST `/{id}/successor` | `create_successor:220` | `md_cmd.create_successor_revision` | yok | **✔** (O-13; fingerprint `payload`'dır — komutun kendisinin oynattığı head pointer DEĞİL, yoksa retry sonsuza dek 409'lardı) |
| POST `/{id}/deprecate` | `deprecate:243` | `md_cmd.deprecate_market_dataset_revision` | yok | **✔** (O-13) |
| DELETE `` `/{id}` (204) | `soft_delete:258` | `md_cmd.soft_delete_market_dataset` | If-Match `rv-N` (`:271`) | — (OCC korumalı + durum-idempotent) |
| GET `` | `list_datasets:277` | `md_query.list_market_dataset_revisions` | yok | — |
| GET `/{id}` | `get_detail:288` | `md_query.get_market_dataset_detail` | yok | — |
| GET `/{id}/approved-bundle` | `resolve_bundle:299` | `md_query.resolve_approved_market_data_bundle` | yok | — |

## research_data.py — router seviyesinde `Depends(_require_page_access)` (`:39,45`); OCC: **`If-Match "rv-N"`**

| METHOD path (ön ek `/research-datasets`) | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `` (201) | `create_dataset:122` | `rd_cmd.create_research_dataset` | yok | **✔** (O-13; replay aynı root+revision, ikinci immutable market-link yok) |
| POST `/{id}/upload-session` (201) | `create_upload_session:147` | `rd_cmd.create_upload_session` | yok | ✔ |
| POST `/{id}/upload-session/finalize` | `finalize_upload:172` | `rd_cmd.finalize_upload` | yok | ✔ |
| POST `/{id}/analysis` (202) | `request_analysis:188` | `rd_cmd.request_research_dataset_analysis` | yok | ✔ |
| POST `/{id}/revisions` | `create_revision:208` | `rd_cmd.create_research_dataset_revision` | If-Match `rv-N` (`:229`) | ✔ |
| POST `/{id}/time-policy` | `set_time_policy:235` | `rd_cmd.set_time_policy` | yok | **✔** (O-13) |
| POST `/{id}/field-definitions` (201) | `define_field:260` | `rd_cmd.define_field` | yok | **✔** (O-13; replay aynı definition, mükerrer satır yok) |
| POST `/{id}/feature-definitions` (201) | `define_feature:280` | `rd_cmd.define_feature` | yok | **✔** (O-13; replay aynı definition) |
| POST `/{id}/approve` | `approve:301` | `rd_cmd.approve_research_dataset_revision` | If-Match `rv-N` (`:314`) | ✔ |
| POST `/{id}/revoke` | `revoke:320` | `rd_cmd.revoke_research_dataset_approval` | If-Match `rv-N` (`:333`) | ✔ |
| DELETE `/{id}` (204) | `soft_delete:339` | `rd_cmd.soft_delete_research_dataset` | If-Match `rv-N` (`:352`) | — |
| GET `` | `list_datasets:358` | `rd_query.list_research_dataset_revisions` | yok | — |
| GET `/{id}` | `get_detail:369` | `rd_query.get_research_dataset_detail` | yok | — |
| POST `/bundles/agent` | `compile_agent_bundle:380` | `rd_jobs.compile_agent_data_bundle` (**pure read**) | yok | — |
| POST `/bundles/backtest-evidence` | `compile_evidence_bundle:393` | `rd_jobs.compile_backtest_evidence_bundle` (**pure read**) | yok | — |

## esp.py — OCC: **`X-Registry-Version` düz int header** (`_REGISTRY_VERSION_HEADER:30`)

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| POST `/embedded-system-packages` (201) | `create_esp:80` | `esp_cmd.create_esp_package` | yok | **✔** (O-13) | |
| GET `/embedded-system-packages` | `list_esp:103` | `esp_query.list_embedded_system_packages` | yok | — | |
| GET `/embedded-system-packages/{entity_id}` | `get_esp:120` | `esp_query.get_esp_detail` | yok | — | |
| POST `/embedded-system-packages/{entity_id}/validate` | `validate_esp:131` | `esp_cmd.run_resolver_validation` | yok | ✔ | |
| POST `/embedded-system-packages/{entity_id}/activate` | `activate_esp:150` | `esp_cmd.activate_resolver` | `X-Registry-Version` (`:154`) | ✔ | (command: Admin) |
| POST `/embedded-system-packages/{entity_id}/deprecate` | `deprecate_esp:170` | `esp_cmd.deprecate_resolver` | `X-Registry-Version` (`:174`) | ✔ | (command: Admin) |
| POST `/embedded-system-packages/resolve` | `resolve_dependency:189` | `esp_query.resolve_embedded_dependency` (**pure read**) | yok | — | `require_authenticated:196` |

## instrument.py — OCC: **`X-Registry-Version` düz int header** (`:29`)

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| POST `/instruments` (201) | `register_instrument:71` | `instrument_cmd.register_instrument` | yok | ✔ | |
| GET `/instruments` | `list_instruments:94` | `instrument_query.list_instruments` | yok | — | |
| GET `/instruments/{instrument_id}` | `get_instrument:109` | `instrument_query.get_instrument_detail` | yok | — | |
| POST `/instruments/{instrument_id}/aliases` (201) | `add_alias:122` | `instrument_cmd.add_instrument_alias` | yok | ✔ | |
| POST `/instruments/{instrument_id}/deprecate` | `deprecate_instrument:138` | `instrument_cmd.deprecate_instrument` | `X-Registry-Version` (`:142`) | ✔ | |
| POST `/instruments/resolve` | `resolve_scope:156` | `instrument_query.resolve_scope` | yok | — | `require_authenticated:161` |

## create_package.py — OCC: **`X-Request-Version` düz int header** (`_REQUEST_VERSION_HEADER:29`)

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| POST `/create-package/requests` (201) | `create_request:84` | `cp_cmd.create_package_request` | yok | ✔ |
| GET `/create-package/requests` | `list_requests:109` | `cp_query.list_package_requests` | yok | — |
| GET `/create-package/requests/{request_id}` | `get_request:120` | `cp_query.get_package_request` | yok | — |
| POST `../pre-check` | `run_pre_check:141` | `cp_cmd.run_precheck` → **admission + `default` aktör dispatch** | `X-Request-Version` | ✔ |
| POST `../generate-candidate` | `generate_candidate:159` | `cp_cmd.submit_candidate_generation` → **admission + `default` aktör dispatch** | `X-Request-Version` | ✔ |
| POST `../draft` | `create_draft:177` | `cp_cmd.create_draft_from_candidate` | **body `expected_candidate_hash` (`:60`)** | ✔ |
| POST `../validate` | `run_validation:194` | `cp_cmd.start_package_validation_run` → **admission + `default` aktör dispatch** | `X-Request-Version` | ✔ |
| POST `../request-revision` | `request_revision:193` | `cp_cmd.request_package_revision` | `X-Request-Version` | ✔ |
| POST `../baseline` (201) | `upload_baseline:209` | `cp_cmd.upload_baseline_asset` | `X-Request-Version` | ✔ |
| POST `../baseline-parse` | `parse_baseline:256` | `cp_cmd.start_baseline_parse` → **admission + `default` aktör dispatch** | `X-Request-Version` | ✔ |
| POST `../approve` | `approve_request:253` | `cp_cmd.approve_and_publish` | **body `expected_head_revision_id` (`:64`)** | ✔ |
| GET `/dependency-scans/{scan_id}` | `get_scan:271` | `cp_query.get_dependency_scan` | yok | — |
| GET `/validation-runs/{validation_run_id}` | `get_validation_run:279` | `cp_query.get_validation_run` | yok | — |
| GET `/baseline-assets/{baseline_asset_id}` | `get_baseline_asset:289` | `cp_query.get_baseline_asset` | yok | — |

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
| GET `/library` | `list_library:67` | `library_query.list_packages` | yok | — |
| GET `/library/{entity_id}` | `get_library_package:97` | `library_query.get_package_detail` | yok | — |
| POST `/library/{entity_id}/deprecate` | `deprecate_package:108` | `pkg_cmd.deprecate_package` | **yok** (doğrulandı: deprecate revision eklemez, head ile yarışamaz — kardeş `market_data` deprecate ile aynı) | **✔** (O-13; key olmadan ikinci çağrı `LIFECYCLE_BLOCKED`, key ile saklı yanıt replay olur) |
| DELETE `/library/{entity_id}` (204) | `soft_delete_package:125` | `pkg_cmd.soft_delete_package` | If-Match `rv-N` (`:140`) | — |
| POST `/library/{entity_id}/derive` (201) | `derive_package:146` | `pkg_cmd.derive_package` | yok (docstring `:154` açıkça "No OCC") | ✔ |
| POST `/library/{entity_id}/revisions` (201) | `create_package_revision:169` | `pkg_cmd.create_package_revision` | **body `expected_head_revision_id`** | ✔ |
| POST `/library/{entity_id}/request-approval` | `request_package_approval:194` | `pkg_cmd.request_package_approval` | **body `expected_head_revision_id`** | ✔ |
| POST `/library/{entity_id}/approve` | `approve_package:216` | `pkg_cmd.approve_and_publish_package` | **body `expected_head_revision_id`** | ✔ |
| POST `/library/{entity_id}/export` | `export_package:239` | `pkg_cmd.export_package` | yok | ✔ |
| POST `/library/{entity_id}/shares` (201) | `share_package` `sharing.py:35` | `sharing_cmd.share_package` | If-Match `rv-N` (`:47`) | ✔ |
| GET `/library/{entity_id}/shares` | `list_package_shares` `sharing.py:53` | `sharing_query.list_package_shares` | yok | — |
| DELETE `/library/{entity_id}/shares/{share_id}` | `revoke_package_share` `sharing.py:64` | `sharing_cmd.revoke_package_share` | If-Match `rv-N` (`:76`) | ✔ |
| GET `/library-shared-with-me` | `list_shared_with_me` `sharing.py:82` | `library_query.list_shared_with_me` | yok | — |
| POST `/package-imports` (202) | `submit_package_import` `package_import.py:31` | `import_cmd.submit_package_import` | yok | ✔ |
| GET `/package-imports` | `list_package_imports:50` | `import_query.list_import_reports` | yok | — |
| GET `/package-imports/{import_job_id}` | `get_package_import:57` | `import_query.get_import_report` | yok | — |

## rationale.py

| METHOD path | fonksiyon | çağırdığı | OCC | Idem |
|---|---|---|---|---|
| GET `/rationale-families` | `list_families:60` | `rationale_query.list_families` | yok | — |
| POST `/rationale-families` (201) | `create_family:72` | `rationale_cmd.create_family` | yok | ✔ |
| GET `/rationale-families/{entity_id}` | `get_family:89` | `rationale_query.get_family` | yok | — |
| POST `/rationale-families/{entity_id}/revisions` | `revise_family:100` | `rationale_cmd.revise_family` | **body `expected_head_revision_id`** (`:44`) — **O-12: atıl `If-Match` parametresi KALDIRILDI** (okunuyor ama hiç kullanılmıyordu; family ETag'i `rv-N` row_version, bu token revision id → farklı eksen, uzlaştırma sahte 409 üretirdi) | ✔ |
| DELETE `/rationale-families/{entity_id}` | `soft_delete_family:124` | `rationale_cmd.soft_delete_family` | If-Match `rv-N` (`:133`) | — |
| GET `/package-rationale-assignments` | `list_assignments:138` | `rationale_query.list_package_assignments` | yok | — |
| POST `/package-rationale-assignments:batch` | `batch_assign:149` | `rationale_cmd.batch_assign_rationale` | **body `expected_table_version` (str, `:56`)** + per-item `expected_head_revision_id` / `expected_family_current_revision_id` | ✔ |

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
| GET `/manual/stream` | `stream:71` | `queries.manual.get_manual_stream` | yok | — | |
| GET `/manual/search` | `search:80` | `queries.manual.search_manual` | yok | — | |
| POST `/admin/manual/documents` (201) | `create_document:90` | `commands.manual.*` | **body `expected_stream_version` (int, `:47`)** | ✔ | `require_manual_admin:95` |
| POST `/admin/manual/documents:upload` (201) | `upload_document:108` | `commands.manual.*` | **Form `expected_stream_version` (`:112`)** | ✔ | `require_manual_admin:121` |
| POST `/admin/manual/documents/{id}/revisions` (201) | `replace_revision:136` | `commands.manual.*` | **body `expected_head_revision_id` (str)**, body > If-Match (`_expected_revision:61`) | ✔ | `require_manual_admin:143` |
| DELETE `/admin/manual/documents/{id}` | `soft_delete_document:156` | `commands.manual.*` | **body `expected_stream_version` (opsiyonel gövde)** | ✔ | `require_manual_admin:162` |
| POST `/admin/manual/documents/{id}:restore` | `restore_document:175` | `commands.manual.*` | yok | ✔ | `require_trash_admin:180` |

## trash.py — OCC: **body `expected_head_revision_id` (int!)**, `_expected_version:53` body > If-Match

| METHOD path | fonksiyon | çağırdığı | OCC | Idem | Rol kapısı |
|---|---|---|---|---|---|
| DELETE `/entities/{entity_id}` (204) | `soft_delete:59` | `commands.deletion.soft_delete_entity` | **O-18: DUAL** — body `expected_row_version` (opsiyonel) / `If-Match` `rv-N`; kilit ALTINDA `check_row_version` (önceden **hiç** token yoktu → yarışan bir düzenleme sahibinin altından silinebiliyordu) | **✔** (O-13) | |
| GET `/trash-entries` | `get_trash_entries:71` | `queries.trash.list_trash_entries` | yok | — | `require_trash_admin:78` |
| GET `/trash-entries/{id}` | `get_trash_entry:124` | `queries.trash.get_trash_entry_detail` | yok | — | `require_trash_admin` |
| GET `/trash-entries/{id}/restore-preflight` | `restore_preflight:133` | `queries.trash.get_restore_preflight` | yok (salt-okuma) | — (salt-okuma) | `require_trash_admin` |
| POST `/trash-entries/{id}/restore` | `restore:149` | `commands.deletion.*` | body `expected_head_revision_id` (int) / If-Match; **O-17: body `resolution` (typed enum, opsiyonel)** | ✔ | `require_trash_admin` |
| POST `/trash-entries/{id}/purge` (202) | `purge:113` | `commands.deletion.*` | body `expected_head_revision_id` (int) / If-Match | ✔ | `require_trash_admin:120` |

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

Hepsi gerekçeli, hiçbiri açık kusur değil:

| Grup | Op'lar | Neden |
|---|---|---|
| Salt-okuma POST (8) | `allocation.validate/sync` · `strategy.validate_draft` · `results_history.compare` · `esp.resolve_dependency` · `instrument.resolve_scope` · `research_data.compile_agent_bundle/compile_evidence_bundle` | hiçbir satır yazmaz → tekilleştirilecek yan etki yok |
| Oturum işlemleri (3) | `auth.login/logout/reauth` | tekrarı yeni kaynak yaratmaz |
| OCC korumalı soft-delete (4) | `library.soft_delete_package` · `market_data.soft_delete` · `rationale.soft_delete_family` · `research_data.soft_delete` | `If-Match` OCC + durum-idempotent (tekrar = no-op) |
| Geçici opener (1) | `mainboard.start_external_work_object_draft` | senkron saf fonksiyon, kalıcı satır yazmaz |
