# BACKEND_LAYERS — modül haritası

Katmanlar: `domain/` (saf, I/O yok) → `application/{commands,queries,jobs}` → `infrastructure/` → `apps/{api,worker,scheduler}`.

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
| `allocation_plan.py` | Portfolio / Equity Allocation draft upsert, validate, revision append | `portfolio_allocation_plan`, `..._entry`, `..._revision` |
| `auth.py` | Local auth: `sign_up` / `login` / `logout` / `reauthenticate` / first-Admin bootstrap | `human_credentials`, `auth_sessions`, `reauth_proofs`, `human_users` |
| `backtest_run.py` | RUN admission (sunucu tarafı preflight) + retry + Result soft-delete | `backtest_run`, `backtest_run_manifest`, `backtest_result` |
| `capability.py` | Future Dev capability lifecycle transition + operasyonel çıktı POST'ları | `future_capability`, `capability_activation_event`, `view_dataset`, `analysis_artifact` |
| `create_package.py` | Create Package + Pre-Check mutasyonları (scan/candidate/draft/validate/approve) | `package_request`, `dependency_scan`, `baseline_asset`, `package_validation_run` |
| `data_queue.py` | Operator recovery: takılı `data` kuyruğu job'larını yeniden dağıt (INF-03) | `jobs` |
| `deletion.py` | Soft-delete / restore / purge (owner-or-Admin; trash+tombstone+audit tek tx) | `trash_entries`, `tombstones`, `entity_registry` |
| `entities.py` | Generic root/revision omurga create/save (ürünsüz referans desen) | `entity_registry`, `entity_revisions` |
| `esp.py` | ESP resolver create/validate/activate/deprecate | `embedded_resolver_registry`, `..._contract`, `..._validation_run` |
| `instrument.py` | Kanonik enstrüman registry: register / alias / deprecate | `instrument_registry`, `instrument_alias` |
| `lab_message.py` | Lab Assistant tartışma mesajı (kaydedilmiş bağlamdan cevap; runtime'ı kesmez) | `lab_message` |
| `mainboard.py` | Kompozisyon düzlemi: work object create/revision/attach/patch/snapshot/delete | `mainboard_workspace`, `work_object_root/_revision`, `mainboard_working_item`, `mainboard_composition_snapshot` |
| `manual.py` | User Manual: blok parse + root/revision/stream/search-chunk + publication event | `manual_documents`, `manual_document_revisions`, `manual_stream_entries`, `manual_content_blocks`, `manual_search_chunks` |
| `market_data.py` | Market Data ingest + revision lifecycle (D1–D8) | `market_dataset_revision`, `market_raw_asset`, `market_processed_asset`, `market_schema_mapping` |
| `metric_profile.py` | Arrange Metrics profil revision append — **PRESENTATION-ONLY** (Result'a dokunmaz) | `result_view_metric_profile_root/_revision` |
| `package_import.py` | Paket import (export'un tersi): manifest doğrula + durable import job aç | `package_import_job` |
| `package_lifecycle.py` | Library kök yaşam döngüsü: deprecate / soft-delete / derive / revision / approve / export | `package_root`, `package_revision`, `export_artifact` |
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
| `esp.py` | ESP registry listesi/detayı + resolve probe (rol-farkındalıklı) | `embedded_resolver_registry` |
| `funding.py` | Pinlenmiş Funding kaynağını available-time-güvenli takvime çöz (F-11) | `research_*`, `market_*` |
| `indicator_plan.py` | Pinlenmiş StrategyConfig → hesaplanabilir indicator plan (paket gövdesi çalıştırılmaz) | `package_revision` |
| `instrument.py` | Enstrüman registry okuma + `resolve_scope` | `instrument_registry`, `instrument_alias` |
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
| `result_artifacts.py` | Ağır result artifact drill-down (equity/ledger/signals/diagnostics), keyset | `result_equity_point`, `trade_ledger_row`, `signal_event`, `diagnostic_artifact` |
| `results_history.py` | Results History indeksi (değişmez `backtest_result` üzerinde; V18 dizisi değil) | `backtest_result`, `result_summary` |
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
| `data_queue.py` | (yardımcı) | `data` kuyruğu job-kind taksonomisi + operator redelivery listesi |
| `maintenance.py` | (scheduler) | `recover_stale_jobs` (INF-09) + `redeliverable_queued_jobs` (INF-03) sweep'leri |
| `market_data.py` | `data` | Raw asset → Polars parse → şema map → normalize → validate → processed asset |
| `outbox_relay.py` | (scheduler + SSE) | Transactional outbox tüketici tarafı: `relay_unpublished` + `fetch_events_after` |
| `package_import.py` | `data` | Export'un tersi: manifest doğrula → yerel bağımlılıkları yeniden çöz |
| `package_validation.py` | (senkron/worker) | CP validation: yedi zorunlu kontrol, gerçek DB gerçeklerinden |
| `purge.py` | `maintenance` | Trash purge gövdesi; uygunluğu **worker yeniden kontrol eder** |
| `research_data.py` | `data` | Research analiz + agent/evidence bundle derleyicileri (content-addressed) |
| `trade_log.py` | `data` | Trade Log import: object storage → CSV/TXT parse → normalize/validate |
| `trading_signal.py` | `data` | Trading Signal import: aynı zincir + time-safe validation |

## `domain/` — saf katman (I/O yok)

| Paket | Modüller | Ne yapar |
|---|---|---|
| `admin_panel` | `log_taxonomy`, `role_matrix` | Log olay taksonomisi + kanonik rol-scope matrisi (doc 19) |
| `agent_lab` | `cursor`, `enums`, `state_machine`, `tool_gateway` | Analysis Lab durum makinesi + gateway sözleşmesi |
| `allocation` | `config`, `enums`, `rules` | Run-scoped paylaşımlı sermaye havuzu tipleri + semantik kurallar |
| `backtest` | `engine`, `indicators`, `manifest`, `metrics`, `artifacts`, `export`, `funding`, `history`, `enums` | Bar-replay engine, artımlı TA compute, değişmez Run Manifest, kanonik metrikler |
| `capability` | `baseline`, `enums`, `lifecycle` | Future Dev capability registry durum makinesi + activation gate'leri |
| `create_package` | `candidate`, `generator`, `source_scan`, `validation`, `state_machine`, `policy`, `baseline`, `value_objects`, `enums` | CP + Pre-Check; deterministik candidate manifest (`GENERATOR_VERSION`) |
| `deletion` | `state_machine` | Soft-delete/restore/purge geçiş kuralları |
| `esp` | `resolver`, `policy`, `state_machine`, `validation`, `enums` | ESP resolver imza/trust durum makinesi |
| `identity` | `actor`, `policy` | `require_admin` / `require_role` / `require_*_admin` — tüm yetki yardımcıları |
| `importing` | `column_mapping` | TS + TL sınırlayıcılı dosya importer'larının paylaşımlı yardımcıları |
| `instrument` | `scope`, `policy`, `state_machine`, `enums` | Kanonik enstrüman kapsamı + registry durumu |
| `lifecycle` | `enums` | `Role`, `VisibilityScope` gibi çapraz enum'lar |
| `mainboard` | `composition`, `enums` | Kompozisyon hash/fingerprint (yalnız re-export yüzeyi) |
| `manual` | `blocks`, `stream`, `baseline`, `enums` | Kanonik güvenli-render blokları + stream ayrımı |
| `market_data` | `schema_mapping`, `validation_rules`, `state_machine`, `policy`, `value_objects`, `enums` | Market Data domain yüzeyi (re-export) |
| `metric_profile` | `profile`, `registry`, `enums` | Result View Metric Profile |
| `package` | `catalog`, `kind`, `permissions`, `policy`, `enums` | Paylaşımlı paket yüzeyi: katalog facet'leri + on izin bayrağı |
| `rationale` | `colors`, `names`, `policy`, `enums` | Rationale Families |
| `readiness` | `validators`, `issues`, `enums` | Saf, deterministik readiness doğrulayıcıları |
| `research_data` | `time_policy`, `usage_scope`, `quality_rules`, `state_machine`, `policy`, `value_objects`, `enums` | Research Data domain yüzeyi |
| `revision` | `hashing`, `head` | Root/revision omurgası: içerik hash + head ilerletme |
| `sharing` | `policy`, `enums` | Açık kaynak paylaşımı |
| `strategy` | `compiler`, `config`, `enums` | Strategy config tipleri + derleyici (blocking issue üretir) |
| `trade_log` | `compiler`, `config`, `records`, `enums` | Trade Log external work object (CR-01/TL-01) |
| `trading_signal` | `compiler`, `config`, `events`, `enums` | Trading Signal external work object |
| `trash` | `page` | Trash sayfa sözleşmesi (doc 20) |
