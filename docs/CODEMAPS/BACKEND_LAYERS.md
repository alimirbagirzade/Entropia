# BACKEND_LAYERS — modül haritası

Katmanlar: `domain/` (saf, I/O yok) → `application/{commands,queries,jobs}` → `infrastructure/` → `apps/{api,worker,scheduler}`.

> **Dosya sayıları (2026-07-29, ampirik):** `application/commands` **32** · `application/queries`
> **37** · `application/jobs` **14** · `domain/` **26 paket**. Aşağıdaki tablolar bu dosyaların
> **tamamını** adlandırır (`__init__.py` hariç). Bir modül eklendiğinde satırı da ekle — bu dosya
> türetilmiş bir haritadır, otomatik tazelenmez.

**Command konvansiyonu (her modülün docstring'inde tekrarlanan):** modül seviyesinde `async def`,
request bağımlılığından gelen **TEK transaction**, burada **asla commit yok**, şekil =
`policy check → pure domain state-machine → persist → audit + outbox (aynı tx)`.

---

## `application/commands/` — yazma yolu

| Dosya | Ne yapar | Ana tablolar |
|---|---|---|
| `agent_control.py` | Analysis Lab direktif kuyruğu + Admin runtime yaşam döngüsü (pause/resume/stop) | `agent_runtime`, `task_directive`, `agent_task` |
| `agent_coordinator.py` | Deterministik Coordinator iskeleti — safe-checkpoint makinesi | `agent_checkpoint`, `agent_task` |
| `agent_loop.py` | Sürekli Coordinator cycle (iskeletin gerçek döngü gövdesi) | `agent_task`, `agent_checkpoint`, `agent_event` |
| `agent_artifact.py` | Analysis Lab output soft-delete (owner Agent / Admin) — state flip + **Trash Entry** + audit/outbox tek tx (K-06) | `hypothesis_artifact`, `trash_entries` |
| `allocation_plan.py` | Portfolio / Equity Allocation draft upsert, validate, revision append. **Portfolio-level cross-item kuralları** (`max_total_exposure_percent`, `conflict_policy`) burada plan köküne yazılır ve revision `config` snapshot'ına taşınır — bu iki alan **doc 13 §8.2'de YOK**, tam kayıt: `docs/PROJECT_HISTORY.md` §B-1 | `portfolio_allocation_plan`, `..._entry`, `..._revision` |
| `auth.py` | Local auth: `sign_up` / `login` / `logout` / `reauthenticate` / first-Admin bootstrap | `human_credentials`, `auth_sessions`, `reauth_proofs`, `human_users` |
| `backtest_run.py` | RUN admission (sunucu tarafı preflight) + retry + Result soft-delete | `backtest_run`, `backtest_run_manifest`, `backtest_result` |
| `backtest_run_context.py` | K-04: manifest'in deref arkasındaki 3 alan grubu (strategy/package · external object · data/time) admission'da çözülür; worker `_unresolved_pins` ile fail-closed doğrular | okuma: `work_object_revision`, `package_revision`, `market_dataset_revision`, `dataset_coverage_slice`, `research_dataset_revision`, `normalized_signal_event_revision`, `canonical_trade_record_batch` |
| `capability.py` | Future Dev capability lifecycle transition + operasyonel çıktı POST'ları | `future_capability`, `capability_activation_event`, `view_dataset`, `analysis_artifact` |
| `create_package.py` | Create Package + Pre-Check mutasyonları (scan/candidate/draft/validate/approve). **Pre-Check · candidate · validation · baseline-parse = admission** (durable job + `default` aktör); compute `jobs/create_package.py`'de — F-01c ile tx-içi compute kalmadı | `package_request`, `dependency_scan`, `baseline_asset`, `package_validation_run`, `jobs` |
| `data_queue.py` | Operator recovery: takılı `data` kuyruğu job'larını yeniden dağıt (INF-03) | `jobs` |
| `deletion.py` | Soft-delete / restore / purge (owner-or-Admin; trash+tombstone+audit tek tx). Restore/purge `entity_type` ile dallanır: registry kökü · `backtest_result` · `manual_document` · `hypothesis_artifact`. **`_soft_delete_preflight` = tek blocker kapısı**, `entity_type` ile dallanır (`work_object` aktif run · `rationale_family` canlı atama · `package` deprecate-first ESP) ve **HEM** `soft_delete_entity` **HEM** `soft_delete_registry_root` tarafından çağrılır — `soft_delete_package` ikinciden geçtiği için kapıyı tek yere koymak yetmez | `trash_entries`, `tombstones`, `entity_registry`, `embedded_resolver_registry`, `backtest_result`, `manual_documents`, `hypothesis_artifact` |
| `entities.py` | Generic root/revision omurga create/save (ürünsüz referans desen) | `entity_registry`, `entity_revisions` |
| `esp.py` | ESP resolver create/validate/activate/deprecate | `embedded_resolver_registry`, `..._contract`, `..._validation_run` |
| `instrument.py` | Kanonik enstrüman registry: register / alias / deprecate | `instrument_registry`, `instrument_alias` |
| `lab_message.py` | Lab Assistant tartışma mesajı (kaydedilmiş bağlamdan cevap; runtime'ı kesmez) | `lab_message` |
| `mainboard.py` | Kompozisyon düzlemi: work object create/revision/attach/patch/snapshot/delete | `mainboard_workspace`, `work_object_root/_revision`, `mainboard_working_item`, `mainboard_composition_snapshot` |
| `manual.py` | User Manual: blok parse + root/revision/stream/search-chunk + publication event | `manual_documents`, `manual_document_revisions`, `manual_stream_entries`, `manual_content_blocks`, `manual_search_chunks` |
| `market_data.py` | Market Data ingest + revision lifecycle (D1–D8) | `market_dataset_revision`, `market_raw_asset`, `market_processed_asset`, `market_schema_mapping` |
| `metric_profile.py` | Arrange Metrics profil revision append — **PRESENTATION-ONLY** (Result'a dokunmaz) | `result_view_metric_profile_root/_revision` |
| `package_import.py` | Paket import (export'un tersi): manifest doğrula + durable import job aç. **G-02:** `export_schema_version` kapısı `_coerce_kind`'dan ÖNCE koşar — v1 (alan yok) ve v2 okunur, başkası fail-closed 422 | `package_import_job` |
| `package_lifecycle.py` | Library kök yaşam döngüsü: deprecate / soft-delete / derive / revision / approve / export. **`export_package` = schema v2 (G-02):** contract + evidence **EXPORT EDİLEN revision'ın kendi satırlarından** okunur (asla kökün head'inden), `created_at` hash'e girmez, canlı registry manifest'in dışında `registry_observation` olarak taşınır → arada bir şey değişmediyse yeniden export **birebir** aynı `manifest_hash`'i verir. **Dürüst sınır:** digest revision ömrü boyunca DONMUŞ değildir — revision'ın kendi `validation_state`/`approval_state`'i yerinde güncellenir ve yeniden validate yeni bir run satırı ekler (evidence snapshot en yeniyi izler, çünkü `revision.validation_state`'i yazan da odur); ikisi de test edilmiş **kasıtlı** davranıştır ve `validation_run_id` hangi kanıtın digest'i desteklediğini adlandırır. Pre-G-02 Idempotency-Key replay'i `_with_export_envelope_defaults` ile v1 etiketlenir, saklı manifest **verbatim** döner (O-30 kalıbı) | `package_root`, `package_revision`, `export_artifact`; **okuma:** `embedded_resolver_contract`, `embedded_resolver_validation_run`, `embedded_resolver_registry` |
| `rationale.py` | Rationale Families CRUD + paket atama batch (shared-editing istisnası) | `rationale_family_root/_revision`, `package_rationale_assignment` |
| `readiness_check.py` | Ready Check — sunucu tarafı değişmez-snapshot doğrulayıcı | `ready_check_report`, `readiness_issue` |
| `research_data.py` | Research Data ingest + field/feature/time-policy + approve/revoke (DR1–DR8) | `research_dataset_revision`, `research_raw/native_asset`, `research_*_definition`, `research_time_policy` |
| `result_export.py` | Bir değişmez Result'ın şema-versiyonlu türevini üret (V1 senkron) | `export_artifact` |
| `role_assignment.py` | Tek Management mutasyonu: bir human user'ın rolünü atomik değiştir | `human_users`, `principals` |
| `roles.py` | Human rol ataması (Admin-only) + last-admin koruması | `human_users` |
| `sharing.py` | Açık paket paylaşımı: grantee çöz → policy → grant/revoke | `resource_share` |
| `strategy_draft.py` | Strategy editor draft create/patch/validate/save/clear | `strategy_editor_draft`, `strategy_root`, `strategy_revision` |
| `trade_log.py` | Trade Log native work object create/revision/export (doc 05) | `work_object_root/_revision`, `canonical_trade_record_batch`, `source_asset` |
| `trading_signal.py` | Trading Signal native work object create/revision/export (doc 04) | `work_object_root/_revision`, `normalized_signal_event_revision`, `source_asset` |

## `application/queries/` — okuma yolu (read model / projeksiyon)

| Dosya | Ne yapar | Ana tablolar |
|---|---|---|
| `agent_tool_gateway.py` | Gateway tool-call geçmişi (task-scoped özet liste + tam detay) | `agent_tool_call` |
| `agent_workspace.py` | Analysis Lab projeksiyonları; Admin/Supervisor policy her çağrıda yeniden kontrol | `agent_runtime`, `agent_task`, `lab_message`, `hypothesis_artifact` |
| `allocation_currency.py` | Kompozisyon item'larının settlement currency'sini çöz (read-only yardımcı) | `instrument_registry` |
| `allocation_plan.py` | Allocation draft projeksiyonu + aday item picker + sync preview | `portfolio_allocation_*` |
| `audit_log.py` | Audit log cursor-sayfalı okuma (route'ta Admin-only) | `audit_events` |
| `backtest_run.py` | RUN durumu + Result detayı (yalnız `result_id` + değişmez artifact'lardan hidrasyon) | `backtest_run`, `backtest_result`, `result_summary` |
| `capability.py` | Capability registry listesi/detayı + Graphic View overview | `future_capability` |
| `create_package.py` | CP istekleri + scan artifact (owner veya Admin görürlüğü) | `package_request`, `dependency_scan` |
| `dependency_pins.py` | **Approve-time** pinlenmiş ESP resolver ref'lerinin yeniden doğrulaması (doc 06 §7). Pre-Check ref'leri pinler ama Pre-Check ile Approve **iki ayrı insan adımıdır**; arada `trusted_active` bir resolver deprecate olabilir → approve kapısı yeniden bakar | `embedded_resolver_registry`, `package_revision` |
| `package_dependency.py` | **Publish-time** bağımlılık grafı çözümü + döngü kapısı (doc 08 §10/§13/§14). `A -> B -> A` yaratan publish denemesi **SUNUCU** tarafından, döngü yolunu adlandıran bir teşhisle reddedilir — UI asla kapı değildir | `package_root`, `package_revision` |
| `panel_backtest_log.py` | Admin Panel backtest-log read model (doc 19, P-14) — `GET /admin/backtest-logs`'un PRIMARY görünümü: değişmez `backtest_result` üzerinde newest-first, cursor'lı "All User Backtest Logs" projeksiyonu. Admin "hangi kullanıcı hangi backtest'i koştu"yu **domain event çözmeden** okur. Net Profit / ROMAD / Trades kolonları `metric_value` satırlarından hidre edilir, `result_summary`'den DEĞİL | `backtest_result`, `metric_value`, `human_users`, `entity_registry` |
| `timezone_audit.py` | **K-01 geriye-dönük denetim, SALT-OKUMA:** sessiz-UTC varsayımı altında alınmış revizyonları bulur. K-01 öncesi parse yolu beyan edilen timezone'u yok sayıp her NAIVE damgayı UTC okuyordu → `custom`+UTC-dışı IANA veya identifier taşımayan `exchange` beyan eden revizyon **yanlış an**'da saklanıp yine de auto-verify oluyordu | `market_dataset_revision`, `research_dataset_revision` |
| `esp.py` | ESP registry listesi/detayı + resolve probe (rol-farkındalıklı). `resolve_embedded_dependency` **iki facet'i birden** okur: registry trust pointer'ı VE Package Root lifecycle'ı (`deletion_state`+`lifecycle_state`+`package_kind`) — doc 09 §11.2 bunları ayrı tutar, o yüzden "pointer hâlâ `trusted_active`" kökün yaşadığının kanıtı değildir. Soft-deleted/purge-pending/purged/deprecated kök YENİ iş için asla çözülmez (`RESOLVER_NOT_ACTIVE`); pinlenmiş historical revision bu yoldan hiç geçmez | `embedded_resolver_registry`, `embedded_resolver_contract`, `entity_registry`, `package_root`, `package_revision` |
| `funding.py` | Pinlenmiş Funding kaynağını available-time-güvenli takvime çöz (F-11) | `research_*`, `market_*` |
| `indicator_plan.py` | Pinlenmiş StrategyConfig → hesaplanabilir indicator plan (paket gövdesi çalıştırılmaz) | `package_revision` |
| `instrument.py` | Enstrüman registry okuma + `resolve_scope` | `instrument_registry`, `instrument_alias` |
| `job_gauges.py` | **I-05:** `/metrics` operasyonel gauge'ları — kuyruk derinliği (`queue`×`status`), outbox lag, en eski RUNNING lease yaşı. Route-seviyesindeki son ORM bypass'ıydı: `routes/metrics.py` ham `select(Job...)` kuruyordu. Sorgular artık burada, route yalnız Prometheus metnini render eder (`_render_operational_gauges`, saf fonksiyon). Değer-only projeksiyon (`JobGauges`) — ORM entity dışarı sızmaz | `jobs`, `outbox_events` |
| `library.py` | Paket katalog listesi/detayı (Guest'e katalog dönmez, 401) | `package_root`, `package_revision`, `resource_share` |
| `log_projection.py` | Admin Logs — `audit_events` üzerinde filtreli, newest-first, keyset projeksiyon | `audit_events` |
| `mainboard.py` | Varsayılan workspace projeksiyonu (Guest → 401, auto-create yok) | `mainboard_workspace`, `mainboard_working_item` |
| `manual.py` | Published manual projeksiyonu (tüm roller aynı okuma) + arama | `manual_stream_entries`, `manual_content_blocks`, `manual_search_chunks` |
| `market_bars.py` | Pinlenmiş market revision → işlenmiş bar (Parquet) kaynağı (INF-12) | `market_processed_asset` |
| `market_data.py` | Market Data listesi/detayı + approved bundle çözümü | `market_dataset_revision` |
| `market_ticks.py` | `market_bars`'ın intrabar/tick aynası (F-07i B) | `market_processed_asset` |
| `metric_profile.py` | Metrik registry + çözümlenmiş profil + Result metrik hidrasyonu | `metric_definition`, `result_view_metric_profile_*`, `metric_value` |
| `package_import.py` | Import raporu (owner-scoped; cross-owner → 404, varlık sızdırmaz) | `package_import_job` |
| `rationale.py` | Rationale registry + atama tablosu (Guest → 401) | `rationale_family_*`, `package_rationale_assignment` |
| `readiness_check.py` | Ready raporu; **güncellik saklanmaz** — fingerprint karşılaştırmasıyla hesaplanır | `ready_check_report`, `readiness_issue` |
| `research_data.py` | Research Data listesi/detayı (sayfa erişimi Admin/Supervisor/Agent) | `research_dataset_revision` |
| `result_access.py` | **Result görünürlüğünün TEK yeri (O-14):** composition (workspace) sahibi + `resource_share` grant'leri + Analysis Lab (Agent research) kapsamı. `visible_composition_stmt` = list SQL yüklemi, `ensure_can_view_composition` = detail/compare/metrics/artifacts yeniden-kontrolü | `entity_registry`, `mainboard_workspace`, `resource_share` |
| `result_artifacts.py` | Ağır result artifact drill-down (equity/ledger/signals/diagnostics), keyset | `result_equity_point`, `trade_ledger_row`, `signal_event`, `diagnostic_artifact` |
| `results_history.py` | Results History indeksi (değişmez `backtest_result` üzerinde; V18 dizisi değil). Görünürlük `result_access.py`'a delege — kendi + explicitly shared + (Admin/Supervisor için) Agent research kapsamı; filtre SQL'de, cursor yetkili kümeyi sayar | `backtest_result`, `result_summary` |
| `sharing.py` | Bir paketin ACTIVE grantee'leri + OCC için `row_version` | `resource_share` |
| `strategy.py` | Strategy okuma (Guest → 401, yabancı private strateji → 403) | `strategy_root`, `strategy_revision`, `strategy_editor_draft` |
| `trade_log.py` | Import raporu + trade log okuma | `work_object_*`, `canonical_trade_record_batch` |
| `trading_signal.py` | Import raporu + trading signal okuma | `work_object_*`, `normalized_signal_event_revision` |
| `trash.py` | Trash keyset projeksiyonu (her girişte `require_trash_admin` yeniden uygulanır) | `trash_entries`, `tombstones` |
| `user_registry.py` | Admin Panel: human user registry + System Actor kartı + rol matrisi | `human_users`, `agents`, `principals` |

## `application/jobs/` — durable worker gövdeleri

| Dosya | Kuyruk | Ne yapar |
|---|---|---|
| `agent_executor.py` | `agent-executor` | Alpha Agent task executor; `jobs` satırı transport + retry backstop |
| `agent_tools.py` | `agent` / `agent-high` | Tool Gateway — ajan, insanla **aynı** policy'li servis hattından iş yapar |
| `backtest_engine.py` | `backtest` | Engine worker gövdesi; `jobs` + `backtest_run` tek gerçek kaynağı |
| `create_package.py` | `default` | CP kind-dispatch worker: `precheck` · `candidate_generation` · `validation` · `baseline_parse` (F-01a/F-01b/F-01c); durable kanıt + state ilerlemesi + audit/outbox |
| `data_queue.py` | (yardımcı) | `data` kuyruğu job-kind taksonomisi + operator redelivery listesi |
| `maintenance.py` | (scheduler) | `recover_stale_jobs` (INF-09) + `redeliverable_queued_jobs` (INF-03) sweep'leri |
| `market_data.py` | `data` | Raw asset → Polars parse → şema map → normalize → validate → processed asset |
| `outbox_relay.py` | (scheduler + SSE) | Transactional outbox tüketici tarafı: `relay_unpublished` + `fetch_events_after` |
| `package_import.py` | `data` | Export'un tersi: manifest doğrula → yerel bağımlılıkları yeniden çöz. **G-02:** okunamayan `export_schema_version` = yapısal kusur → terminal `failed` (`unsupported_export_schema_version`, sınır kapısının defence-in-depth kopyası). v2 manifestin `resolver_contract_snapshot`'ı `diagnostics.origin_resolver_contract` olarak **`trusted: false`** damgasıyla yankılanır — `embedded_resolver_contract` veya `embedded_resolver_registry` satırı ASLA yaratılmaz; yabancı adapter dosyada adı geçtiği için yerel güven kazanmaz |
| `package_validation.py` | (`default` worker gövdesi) | CP validation: yedi zorunlu kontrol, gerçek DB gerçeklerinden; `create_package.py::run_validation_job` çağırır |
| `purge.py` | `maintenance` | Trash purge gövdesi; uygunluğu **worker yeniden kontrol eder** |
| `research_data.py` | `data` | Research analiz + agent/evidence bundle derleyicileri (content-addressed) |
| `trade_log.py` | `data` | Trade Log import: object storage → CSV/TXT parse → normalize/validate |
| `trading_signal.py` | `data` | Trading Signal import: aynı zincir + time-safe validation |

## `domain/` — saf katman (I/O yok)

| Paket | Modüller | Ne yapar |
|---|---|---|
| `admin_panel` | `log_taxonomy`, `role_matrix` | Log olay taksonomisi + kanonik rol-scope matrisi (doc 19) |
| `agent_lab` | `cursor`, `enums`, `state_machine`, `tool_gateway` | Analysis Lab durum makinesi + gateway sözleşmesi |
| `allocation` | `capability`, `config`, `enums`, `rules` | Run-scoped paylaşımlı sermaye havuzu tipleri + semantik kurallar. **CONTAINMENT (ADIM 3):** `capability.py` shared capital'in bu build'de **çalışmadığını** ilan eden TEK kaynak (`SHARED_ALLOCATION_STATUS = "future_dev"`); `rules.py::validate_allocation` enabled planı `SHARED_MODE_NOT_IN_BUILD` BLOCKER'ı ile açar → Portfolio sayfası + revision freeze + Ready Check (`ALLOCATION_SHARED_MODE_NOT_IN_BUILD`) + `commands/backtest_run.py` admission guard aynı verdict'i okur. Independent mod etkilenmez. Kaldırma şartları: `docs/decisions/2026-08-03_shared_portfolio_containment.md` §6. **Portfolio-level cross-item kuralları burada tanımlı ve doc 13 §8.2'de YOK:** `config.py:118-119` iki alan · `enums.py:37-53` `CrossItemConflictPolicy` (`NET` / `BLOCK_OPPOSITE` / `KEEP_SEPARATE`) · `rules.py:164-186` `MAX_TOTAL_EXPOSURE_INVALID` (BLOCKER) + `CONFLICT_POLICY_NET_V1` (WARNING). Tam kayıt: `docs/PROJECT_HISTORY.md` §B-1 |

| `capability` | `baseline`, `enums`, `lifecycle` | Future Dev capability registry durum makinesi + activation gate'leri |
| `create_package` | `candidate`, `generator`, `source_scan`, `language_detect`, `validation`, `state_machine`, `policy`, `baseline`, `value_objects`, `enums` | CP + Pre-Check; deterministik candidate manifest (`GENERATOR_VERSION`). **Pre-Check fail-closed (K-05):** `source_scan` (`SOURCE_SCANNER_VERSION=source-lexer-2.0`) tanınmayan-token oranı + kapanmamış string/blok yorum sayar → `PARSE_UNSUPPORTED`; `language_detect` (`LANGUAGE_DETECTOR_VERSION`) içerik dil sinyali → seçimle çelişki `SOURCE_LANGUAGE_MISMATCH`, rakip kanıt `REQUIRES_CLARIFICATION`. Üçü de FAILED scan + `precheck_failed`, asla PASSED |
| `deletion` | `state_machine` | Soft-delete/restore/purge geçiş kuralları |
| `esp` | `resolver`, `policy`, `state_machine`, `validation`, `enums` | ESP resolver imza/trust durum makinesi |
| `identity` | `actor`, `policy` | `require_admin` / `require_role` / `require_*_admin` — tüm yetki yardımcıları |
| `importing` | `column_mapping`, `source_file`, `timezone` | TS + TL sınırlayıcılı dosya importer'larının paylaşımlı yardımcıları. **`source_file`** = fail-closed dosya-tipi kapısı (K-07; doc 05 §5.2 + doc 04 §7 — filename yok/boş → RED, uzantı iddiası içerik sniff'i ile desteklenir). **`timezone`** = ortak kaynak-timezone kapısı (O-28): beyan edilen zaman dilimi GERÇEK bir IANA tanımlayıcısı olmalı (`zoneinfo` çözmeli) ve kayıtları üreten import ile çapraz kontrol edilir — iki kural ikizler drift edemesin diye **tek yerde** |
| `instrument` | `scope`, `policy`, `state_machine`, `enums` | Kanonik enstrüman kapsamı + registry durumu |
| `lifecycle` | `enums` | `Role`, `VisibilityScope` gibi çapraz enum'lar |
| `mainboard` | `composition`, `enums`, `item_kind` | Kompozisyon hash/fingerprint (yalnız re-export yüzeyi). **`item_kind`** = istemciden gelen item-kind koruması (doc 03 §11, AOS-03): chooser yalnız `trading_signal` / `trade_log` sunar; V18 legacy prototip etiketleri (`signal_package` / `trade_log_package`) 422 **`INVALID_ITEM_KIND`** verir ve **hiçbir** PackageKind genişlemesi/kök/revizyon yaratmaz |
| `manual` | `blocks`, `stream`, `baseline`, `enums` | Kanonik güvenli-render blokları + stream ayrımı |
| `market_data` | `schema_mapping`, `validation_rules`, `state_machine`, `policy`, `value_objects`, `enums` | Market Data domain yüzeyi (re-export) |
| `metric_profile` | `profile`, `registry`, `enums` | Result View Metric Profile |
| `package` | `catalog`, `kind`, `permissions`, `policy`, `enums`, `dependency_graph`, `export_contract` | Paylaşımlı paket yüzeyi: katalog facet'leri + izin bayrakları (S-L3 ile `can_request_validation` eklendi). **`dependency_graph`** = saf, yan etkisiz döngü dedektörü (doc 08 §9.1/§10/§13/§14): çağıran pinlenmiş kenarları DB'den materyalize eder, bu modül TEK soruyu cevaplar — graf `A -> B -> A` kapatıyor mu? — ve döngüdeki kökleri **adlandırır** (§14 çıplak ret'ten fazlasını ister). **`export_contract`** = export artifact'inin saf kurucu düzlemi (G-02, doc 09 §15 ESP-19): `EXPORT_SCHEMA_VERSION=2`, `EXPORTER_VERSION`, `build_resolver_contract_snapshot` / `build_validation_evidence_snapshot` / `build_registry_observation`, `resolve_import_schema_version` (v1+v2 okur, gerisi `None` → çağıran fail-closed), `describe_origin_resolver_contract` (yabancı iddianın `trusted: false` yankısı). Kanıt yoksa `legacy_incomplete_evidence` — **asla uydurma `passed`** |
| `rationale` | `colors`, `names`, `policy`, `enums` | Rationale Families |
| `readiness` | `validators`, `issues`, `enums` | Saf, deterministik readiness doğrulayıcıları |
| `research_data` | `time_policy`, `usage_scope`, `quality_rules`, `state_machine`, `policy`, `value_objects`, `enums` | Research Data domain yüzeyi |
| `revision` | `hashing`, `head` | Root/revision omurgası: içerik hash + head ilerletme. **`hashing` yalnızca re-export yüzeyi (I-04):** `canonical_json`/`content_hash` gerçekte `shared/hashing.py`'de yaşar, çünkü `shared` en alt katmandır ve `shared.idempotency` + `shared.manifest` aynı canonicalizer'a ihtiyaç duyar — `shared` → `domain` importu ters katman ihlaliydi. İkinci bir canonicalizer forklama; `tests/unit/test_layer_boundaries.py` bu yönü ve 0-döngü değişmezini kilitler |
| `sharing` | `policy`, `enums` | Açık kaynak paylaşımı. `ShareResourceType` değeri = paylaşılan kökün `entity_type`'ı: `package` (yönetilen grant yüzeyi) + `mainboard_workspace` (O-14 — Results History'nin okuduğu composition kapsamı; grant yazan komut yüzeyi V1'de yok) |
| `strategy` | `compiler`, `config`, `enums` | Strategy config tipleri + derleyici (blocking issue üretir) |
| `trade_log` | `compiler`, `config`, `records`, `enums` | Trade Log external work object (CR-01/TL-01) |
| `trading_signal` | `compiler`, `config`, `events`, `enums` | Trading Signal external work object |

