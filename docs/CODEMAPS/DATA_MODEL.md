# DATA_MODEL — Postgres tabloları

Modeller: `backend/src/entropia/infrastructure/postgres/models/*.py` (30 dosya, **63 tablo**).
Alembic: `backend/alembic/versions/` — **head = `0035_portfolio_rules`** (35 migration).

## Kritik yapısal gerçek — DB-seviyesi FK neredeyse yok

Tüm repoda yalnızca **8 açık `ForeignKey(...)` bildirimi** var:

| Tablo | FK |
|---|---|
| `human_users` | → `principals.principal_id` (PK) |
| `agents` | → `principals.principal_id` (PK) |
| `human_credentials` | → `human_users.user_id` (PK) |
| `auth_sessions` | → `human_users.user_id` |
| `reauth_proofs` | → `human_users.user_id` |
| `approval_decision` | → `principals.principal_id` |
| `entity_revisions` | → `entity_registry.entity_id` |
| `market_validation_issue` | → `market_validation_run.run_id` |
| `research_validation_issue` | → `research_validation_run.run_id` |

Diğer tüm `*_id` kolonları **mantıksal bağdır** (ULID string, DB constraint yok).
Sonuç: insert sırası SQLAlchemy tarafından FK'den türetilemez — bu yüzden identity seed'inde
her FK-bağımlı child'dan önce `Principal` flush edilmek zorundadır (`apps/seed.py::seed_identities`).

## OCC ve soft-delete konvansiyonu

- **`row_version` (int)** → optimistic concurrency token'ı. Aşağıdaki tabloda ✔ olanlar taşır.
- **`deletion_state`** → mantıksal soft-delete bayrağı (registry/kök satırlarda).
- **`deleted_at`** → yalnızca `entity_registry`, `human_users`, `manual_documents`, `trash_entries`.
- Revision tabloları **değişmezdir**: ne `row_version` ne `deletion_state` taşır; yaşam döngüsü hep kök satırdadır.

---

## Omurga (root/revision spine)

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `entity_registry` | Evrensel kimlik + yaşam döngüsü + head pointer | `owner_principal_id`, `current_revision_id` | `deletion_state`, `deleted_at` | ✔ `row_version` |
| `entity_revisions` | Değişmez revision zinciri (tek gerçek DB FK'si) | **FK** `entity_id`, `parent_revision_id` | — | — |
| `app_metadata` | Uygulama meta anahtar/değer | — | — | — |

## Identity & Auth

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `principals` | Tüm aktörlerin (insan + ajan) ortak kimlik satırı | `principal_id` (PK) | — | — |
| `human_users` | İnsan kullanıcı + rol | **FK** → `principals` | `deletion_state`, `deleted_at` | — |
| `agents` | Sistem/ajan aktörleri | **FK** → `principals` | — | — |
| `human_credentials` | argon2id parola özeti | **FK** → `human_users` | — | — |
| `auth_sessions` | Opak Bearer oturum (yalnız SHA-256 özeti) | **FK** → `human_users` | — | — |
| `reauth_proofs` | Yıkıcı işlemler için re-auth kanıtı | **FK** → `human_users` | — | — |
| `approval_decision` | Onay kararı kaydı | **FK** → `principals`, `target_entity_id/_revision_id` | — | — |

## Audit, outbox, jobs

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `audit_events` | Değişmez denetim akışı (Admin Logs projeksiyonunun kaynağı) | `actor_principal_id`, `target_entity_id`, `correlation_id`, `causation_event_id` | — | — |
| `outbox_events` | Transactional outbox (domain mutasyonuyla aynı tx) | `resource_id`, `correlation_id` | — | — |
| `jobs` | Durable iş satırı (transport + retry backstop) | `actor_principal_id`, `correlation_id` | — | — |
| `idempotency_keys` | `Idempotency-Key` tekilleştirme | `actor_principal_id` | — | — |

## Mainboard (kompozisyon düzlemi)

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `mainboard_workspace` | Varsayılan çalışma alanı kökü | `entity_id` | — | ✔ |
| `work_object_root` | Work object kimliği (yaşam döngüsü registry'de) | `entity_id` | — | — |
| `work_object_revision` | Değişmez work object revizyonu | `entity_id`, `parent_revision_id`, `supersedes_revision_id` | — | — |
| `mainboard_working_item` | Kompozisyondaki pin'lenmiş item | `workspace_entity_id`, `work_object_root_id`, `pinned_revision_id` | — | ✔ |
| `mainboard_composition_snapshot` | Dondurulmuş kompozisyon + readiness bağı | `workspace_entity_id`, `readiness_report_id` | — | — |

## Strategy

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `strategy_root` | Strateji kimliği + yayınlanmış head | `current_revision_id`, `rationale_family_id` | — | ✔ `current_row_version` |
| `strategy_revision` | Değişmez strateji config revizyonu | `entity_id`, `parent_revision_id` | — | — |
| `strategy_revision_references` | Revizyonun pinlediği dış paket referansları | `strategy_revision_id`, `referenced_root_id`, `referenced_revision_id` | — | — |
| `strategy_editor_draft` | Mutable editör durumu | `strategy_root_id`, `last_saved_revision_id` | — | ✔ |

## Trading Signal / Trade Log (external work objects)

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `source_asset` | İçerik-adresli yüklenmiş kaynak dosya | `owner_principal_id`, `draft_id` | — | — |
| `normalized_signal_event_revision` | Normalleştirilmiş sinyal olayları | `source_asset_id`, `job_id`, `instrument_id`, `work_object_revision_id` | — | — |
| `canonical_trade_record_batch` | Kanonik trade kayıt partisi | `source_asset_id`, `job_id`, `instrument_id`, `work_object_revision_id` | — | — |

## Market Data

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `market_dataset_revision` | Market veri seti revizyonu (approve/deprecate hedefi) | `entity_id`, `parent/supersedes_revision_id`, `instrument_id` | — | — |
| `market_raw_asset` | Ham yükleme (object key + digest) | `entity_id`, `revision_id` | — | — |
| `market_processed_asset` | İşlenmiş Parquet (bar kaynağı, INF-12) | `raw_asset_id` | — | — |
| `market_schema_mapping` | Onaylanmış şema eşlemesi | `entity_id`, `revision_id` | — | — |
| `market_validation_run` / `market_validation_issue` | Doğrulama koşusu + bulguları | **FK** issue → run | — | — |
| `dataset_coverage_slice` | Kapsama aralıkları | `entity_id`, `revision_id` | — | — |

## Research Data

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `research_dataset_revision` | Research veri seti revizyonu | `base_revision_id`, `raw/native_asset_id`, `linked_market_dataset_revision_id` | — | — |
| `research_raw_asset` / `research_native_asset` | Ham + native varlıklar | `revision_id`, `raw_asset_id` | — | — |
| `research_field_definition` / `research_feature_definition` | Alan ve feature tanımları | `entity_id`, `revision_id` | — | — |
| `research_time_policy` | Available-time politikası (look-ahead koruması) | `entity_id`, `revision_id` | — | — |
| `research_market_link` | Market veri setine DR3 bağı | `market_dataset_revision_id` | — | — |
| `research_validation_run` / `research_validation_issue` | Doğrulama koşusu + bulguları | **FK** issue → run | — | — |

## Packages, ESP, Rationale, Instruments, Sharing

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `package_root` | Paket kimliği (türetme kökeni dahil) | `derived_from_revision_id`, `origin_package_id` | — | — |
| `package_revision` | Değişmez paket revizyonu (`dependency_snapshot` burada) | `entity_id`, `parent/supersedes_revision_id` | — | — |
| `package_request` | Create Package isteği; `row_version` = request_version | `rationale_family_id`, `current_scan_id`, `draft_revision_id`, `baseline_asset_id` | (registry'de) | ✔ (registry) |
| `dependency_scan` | Pre-Check tarama artefaktı | `request_entity_id`, `job_id` | — | — |
| `baseline_asset` | Yüklenmiş baseline dosyası | `request_entity_id`, `parse_job_id` | — | — |
| `package_validation_run` | CP validation koşusu | `request_entity_id`, `draft_revision_id`, `job_id` | — | — |
| `package_import_job` | Paket import işi (export'un tersi) | `origin_package_id`, `result_package_root_id`, `job_id` | — | — |
| `embedded_resolver_registry` | ESP resolver registry (`registry_version` = OCC kaynağı) | `package_entity_id`, `trusted_active_revision_id`, `replacement_revision_id` | — | ✔ (`registry_version`) |
| `embedded_resolver_contract` | Resolver imza sözleşmesi | `entity_id`, `revision_id` | — | — |
| `embedded_resolver_validation_run` | Resolver doğrulama koşusu | `entity_id`, `revision_id` | — | — |
| `rationale_family_root` / `_revision` | Rationale ailesi kökü + revizyonları | `entity_id`, `parent_revision_id` | (registry'de) | (registry'de) |
| `package_rationale_assignment` | Paket ↔ aile ataması | `target_root_id`, `rationale_family_id`, `..._revision_id` | — | — |
| `instrument_registry` / `instrument_alias` | Kanonik enstrüman + takma adları | `venue_id`, `instrument_id` | — | ✔ (`registry_version`)? |
| `resource_share` | Açık paket paylaşımı | `resource_id`, `grantee_principal_id`, `revoked_by_principal_id` | (revoke) | — |

## Backtest (RUN → Result → artifacts)

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `backtest_run` | RUN admission satırı | `composition_snapshot_id`, `manifest_id`, `ready_report_id`, `retry_of_run_id`, `job_id`, `result_id` | — | ✔ |
| `backtest_run_manifest` | Değişmez Run Manifest (pinlenmiş her şey) | `run_id`, `composition_snapshot_id` | — | — |
| `backtest_result` | Değişmez sonuç kökü | `run_id`, `manifest_id` | `deletion_state` | ✔ |
| `result_summary` | Headline özet (ör. `timeframe`) | `result_id` | — | — |
| `metric_value` | Kalıcı metrik satırları | `result_id` | — | — |
| `result_equity_point` / `trade_ledger_row` / `signal_event` / `diagnostic_artifact` | Ağır artifact'lar (keyset drill-down) | `result_id` | — | — |
| `result_manifest_snapshot` | Result'a bağlı manifest kopyası | `result_id` | — | — |
| `export_artifact` | Result'ın şema-versiyonlu türevi | `result_id` | — | — |
| `ready_check_report` / `readiness_issue` | Değişmez readiness raporu + bulguları | `composition_snapshot_id`, `report_id` | — | — |

## Portfolio / Allocation, Metric Profile

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `portfolio_allocation_plan` | Draft/plan kökü (sermaye, currency, compounding) | `workspace_entity_id`, `current_revision_id` | — | ✔ |
| `portfolio_allocation_entry` | Item başına tahsis satırı | `plan_id`, `composition_item_id` | — | ✔ |
| `portfolio_allocation_plan_revision` | Değişmez plan revizyonu | `plan_id`, `source_draft_row_version` | — | — |
| `metric_definition` | Metrik registry (sistem tanımlı) | — | — | — |
| `result_view_metric_profile_root` | Kişisel/sistem profil kökü | `owner_principal_id`, `current_revision_id` | — | ✔ |
| `result_view_metric_profile_revision` | Değişmez profil revizyonu | `profile_id`, `previous_revision_id` | — | — |

## Agent Lab & Tool Gateway

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `agent_runtime` | Runtime durumu (pause/resume/stop OCC token'ı buradan) | `agent_id`, `active_task_id`, `last_checkpoint_id` | — | ✔ |
| `agent_task` | Ajan görevi | `agent_id`, `context_manifest_id`, `parent_task_id` | — | — |
| `task_directive` | Kuyruğa alınan direktif | `author_principal_id`, `consumed_checkpoint_id` | — | — |
| `agent_checkpoint` | Safe-checkpoint | `task_id`, `context_manifest_id` | — | — |
| `lab_message` | Lab Assistant tartışma mesajı | `author_principal_id`, `task_id` | — | — |
| `hypothesis_artifact` | Hipotez artefaktı | `source_task_id`, `checkpoint_id` | `deletion_state` | ✔ |
| `artifact_link` | Artefakt ilişkileri | `source_artifact_id`, `target_id` | — | — |
| `agent_event` | Ajan olay akışı | `actor_principal_id`, `task_id`, `directive_id` | — | — |
| `agent_tool_call` | Governed gateway çağrı kaydı (yetkili gerçek) | `task_id`, `checkpoint_id`, `input_manifest_id` | — | — |

## Manual, Trash, Future Dev

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `manual_documents` | Manual doküman kimliği | `owner_principal_id`, `current_revision_id` | `deletion_state`, `deleted_at` | ✔ |
| `manual_document_revisions` | Değişmez doküman revizyonu | `document_id` | — | — |
| `manual_stream_entries` | Yayınlanmış stream girdisi (`expected_stream_version` kaynağı) | `document_id`, `visible_revision_id` | — | ✔ |
| `manual_content_blocks` | Kanonik güvenli-render blokları | `revision_id` | — | — |
| `manual_search_chunks` | Arama parçaları | `document_id`, `revision_id` | — | — |
| `manual_publication_events` | Yayın olay kaydı | `document_id`, `stream_entry_id` | — | — |
| `trash_entries` | Trash projeksiyonu (restore/purge OCC token'ı) | `entity_id`, `purge_job_id` | `deleted_at` | ✔ |
| `tombstones` | Purge sonrası mezar taşı | `entity_id` | — | — |
| `future_capability` | Capability registry (`registry_version` OCC) | `capability_id`, `changed_by_actor_id` | — | ✔ (`registry_version`) |
| `capability_activation_event` | Lifecycle geçiş geçmişi | `capability_id`, `actor_principal_id` | — | — |
| `view_dataset` | `view_dataset.query` çıktısı | `owner_principal_id` | `deletion_state` | ✔ |
| `analysis_artifact` | `analysis_artifact.create` çıktısı | `owner_principal_id` | `deletion_state` | ✔ |
| `experiment_proposal` / `execution_plan` | Future-Dev planlama satırları | `owner_principal_id` | — | ✔ |

---

## Doğrulanmamış noktalar (`?`)

- `instrument_registry` OCC kolonu: route `X-Registry-Version` header'ı okuyor (`routes/instrument.py:142`)
  ama model dosyasında `row_version`/`registry_version` kolonu grep'te **görülmedi** — token'ın hangi
  kolondan geldiği doğrulanmalı (`models/instrument.py:31` açılmalı).
- `embedded_resolver_registry` için de aynı: `registry_version` kolonu adı imzadan değil kullanımdan çıkarıldı.
- `package_request` docstring'i `row_version = request_version` diyor, ancak kolon registry satırında
  yaşıyor (`create_package.py:57` yorumu) — hangi tabloda fiziksel olarak durduğu doğrulanmalı.
- Kolon-seviyesi index/constraint detayları bu haritada YOK (yalnızca `trash_entries` keyset index'i
  ve `audit_events` trigram/log index'leri migration'larda mevcut).
