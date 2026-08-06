# DATA_MODEL — Postgres tabloları

Modeller: `backend/src/entropia/infrastructure/postgres/models/*.py`.
Alembic: `backend/alembic/versions/` — **head = `0043_i08_registry_strategy_fks`**
(`0042_package_import_source_name` üzerine I-08 slice 1'de eklendi — **yeni tablo yok,
yalnız 3 FK constraint**).

> **Tablo / FK / migration SAYISI artık burada yazmıyor — üretiliyor:**
> [`docs/generated/repository_facts.md`](../generated/repository_facts.md)
> (`database.table_count`, `database.foreign_key_count`, `alembic.revision_count`;
> üretici `scripts/generate_repository_facts.py`, CI'da `--check` ile bloklayıcı).
> Buradaki elle sayım **bayatlamıştı**: bu satır **102 tablo** derken SQLAlchemy
> metadata'sı **104** veriyordu, `CODEMAPS/README.md` de 104 yazıyordu — aynı olgu
> iki haritada iki farklı sayıydı. (Aynı sayı daha önce de kaymıştı:
> `DOC_TRUTH_REPAIR_LANDED_KICKOFF.md` §"63 → 100 → 102".) Head satırı elle kalıyor
> ama artık **kapılı** — gerçek head'den saparsa CI kırmızıya döner.

> **`0042` YENİ TABLO GETİRMEDİ.** F-07 §4.4: `package_import_job` tablosuna
> nullable `source_package_name VARCHAR(255)` ekler — Library Import raporunun ham `import_job_id`
> yerine gösterdiği ad. `submit_package_import` bunu **submit anında** gönderilen export
> manifest'inin `name` alanından yakalar; `blocked`/`failed` biten bir import hiç paket üretmediği
> için sonradan join edilemezdi. **Backfill YOK** — eski satırlar `NULL` okur ve UI ham id'ye düşer.
>
> **`0040` DE YENİ TABLO GETİRMEDİ.**
> `0040_export_type_agent_pine` yalnız `export_artifact.export_type` kolonunu `VARCHAR(13)` →
> `VARCHAR(24)` genişletir (S-L2 / doc 15 §3.2: `pinescript_signal_marker` + `agent_dataset`
> üyeleri). Kolon **PG ENUM değildir** (`SAEnum(native_enum=False)`) ve SQLAlchemy 2.0
> varsayılanıyla CHECK constraint'i de yoktur; üyelik Python'da (`validate_strings=True`)
> zorlanır → enum'a bağlı **tek şema gerçeği uzunluktur**. Head'i ampirik doğrula:
> `ls backend/alembic/versions/*.py | wc -l` + `down_revision` grafiğinde tek yaprak kalması.

> **Sayı tazeleme (2026-07-29, ampirik).** Tablo sayısı uzun süre **63** yazıyordu — gerçek
> **102**. Yeniden üretmek için:
> `grep -rh __tablename__ backend/src/entropia/infrastructure/postgres/models/ | sed 's/.*= *//' | tr -d '"' | sort -u | wc -l`
> Aşağıdaki bölümler 102 tablonun **tamamını** adlandırır. Sayı bir slice'ta değişirse bu satırı
> da güncelle — bu dosya türetilmiş bir haritadır, otomatik tazelenmez.

## Kritik yapısal gerçek — FK var, ama insert sırası yine de türetilemiyor

> **DÜZELTME (2026-07-29, ampirik).** Bu bölüm önceden "tüm repoda yalnızca **8** açık
> `ForeignKey(...)` bildirimi var" diyordu — ve hemen altında 9 satır listeliyordu, yani kendi
> içinde de tutarsızdı. Gerçek: **140 `ForeignKey(...)` kolon bildirimi, 25 model dosyasında**
> (I-08 slice 1 öncesi 137; bu dalga +3 getirdi — `strategy.py` 9 → **11**, `registry.py` 1 → **2**).
> Doğrula: `grep -rh "ForeignKey(" backend/src/entropia/infrastructure/postgres/models/ | wc -l`
> Yoğunluk: **`strategy.py` 11** · `manual.py` 11 · `research_data.py` 11 · `agent_lab.py` 11 ·
> `create_package.py` 10 · `market_data.py` 10 · `backtest.py` 10 · `capability.py` 9 ·
> `mainboard.py` 8 · `esp.py` 5 · `allocation.py` 5.

### I-08 — cross-reference FK dalgası (slice 1 landed)

`0043_i08_registry_strategy_fks` üç "mantıksal bağ"ı DB'ye devretti:
`entity_registry.owner_principal_id` → `principals`, `strategy_root.current_revision_id` →
`strategy_revision`, `strategy_root.rationale_family_id` → `rationale_family_root`.
**ON DELETE = NO ACTION** (bilerek): `jobs/purge.py` V1'de hard-DELETE yapmaz (state-only,
revision'lar RETAINED), yani bir constraint'in karşılaşacağı gerçek olay bir **bug**'dır ve
bloklamak dürüst cevaptır; `SET NULL` canlı head pointer'ı sessizce silerdi. RESTRICT değil
NO ACTION, çünkü `strategy_root.entity_id` + `strategy_revision.entity_id` ikisi de
`entity_registry`'den CASCADE alır — registry seviyesindeki bir cascade tek statement'ta
ikisini de siler ve yalnız NO ACTION kontrolü statement sonuna erteleyebilir.

**FK ALAMAYAN iki kolon — polimorfik, ihmal değil (kalıcı muafiyet):**

| Kolon | Neden imkânsız |
|---|---|
| `entity_registry.current_revision_id` | Her domain kendi revision tablosuna yazar: `repositories/entities.py` → `entity_revisions`, `packages.py` → `package_revision`, `rationale.py` → `rationale_family_revision`, `market_data.py` → `market_dataset_revision`, `research_data.py` → `research_dataset_revision`. Ortak revision supertable'ı YOK → herhangi birine FK diğer tüm entity tiplerini reddederdi. |
| `package_rationale_assignment.target_revision_id` | `AssignmentTargetKind` iki hedef bildirir (`package_revision`, `working_item_revision`, doc 10 §9.1) → iki ayrı revision tablosu. (Buna karşılık **`target_root_id` FK ALIR**: her iki kind'ın kökü de `entity_registry`'ye asılı.) |

Ayrıca `tombstones.entity_id`, `trash_entries.entity_id` (silme SONRASI kasıtlı gevşek) ve
`audit_events.*` (audit kaydı hedefinden bağımsız yaşamalı) **kapsam dışıdır** — bunlara FK
eklemek, kaydın anlattığı nesne yok olduğunda kaydın kendisini imkânsız kılardı.

Kimlik/registry omurgasındaki **çekirdek** FK'ler (bu tablo tam liste DEĞİLDİR — yukarıdaki
grep otoritedir):

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

**Konvansiyon neden hâlâ geçerli:** FK'li kolonların yanında çok sayıda `*_id` kolonu **hâlâ
mantıksal bağdır** (ULID string, DB constraint yok) — özellikle cross-aggregate referanslar.
Bu yüzden insert sırası SQLAlchemy tarafından şemadan bütünüyle türetilemez ve identity seed'inde
her FK-bağımlı child'dan önce `Principal` flush edilmek zorundadır (`apps/seed.py::seed_identities`).
CLAUDE.md'deki **"her yeni `create_*` için L1 FK insert-order proof"** kuralının gerekçesi budur;
**kural değişmedi** — yalnız "FK neredeyse yok" gerekçesi yanlıştı.

## OCC ve soft-delete konvansiyonu

- **`row_version` (int)** → optimistic concurrency token'ı. Aşağıdaki tabloda ✔ olanlar taşır.
- **OCC token'ının adı `row_version` olmak ZORUNDA DEĞİL.** Token = "int, NOT NULL, default 1,
  mutasyonda +1, önkoşul uyuşmazlığında 409" davranışıdır; ad sayfanın kendi taksonomisinden gelir.
  Bugün üç ad ailesi var: `row_version` (çoğunluk), `registry_version` (`instrument_registry`,
  `embedded_resolver_registry`, `future_capability`) ve `version` (**yalnız `human_users`**).
  **Kolon adına bakıp "OCC yok" çıkarımı yapma** — OCC sütununa bak (aşağıda §I-07).
- **`deletion_state`** → mantıksal soft-delete bayrağı (registry/kök satırlarda).
- **`deleted_at`** → yalnızca `entity_registry`, `human_users`, `manual_documents`, `trash_entries`.
- Revision tabloları **değişmezdir**: ne `row_version` ne `deletion_state` taşır; yaşam döngüsü hep kök satırdadır.

---

## Omurga (root/revision spine)

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `entity_registry` | Evrensel kimlik + yaşam döngüsü + head pointer | **FK** `owner_principal_id` (I-08) · `current_revision_id` (polimorfik, FK YOK) | `deletion_state`, `deleted_at` | ✔ `row_version` |
| `entity_revisions` | Değişmez revision zinciri | **FK** `entity_id`, `parent_revision_id` | — | — |
| `app_metadata` | Uygulama meta anahtar/değer. **Tek yazarı (ADIM 25):** `application/jobs/heartbeat.py` → `key="worker.maintenance.last_heartbeat_at"`, `value=<ISO8601 UTC>`; `job_gauges.py` okur, `entropia_worker_heartbeat_age_seconds` olarak yayımlanır. PK conflict'te upsert — satır **birikmez**, migration gerekmedi | — | — | — |

## Identity & Auth

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `principals` | Tüm aktörlerin (insan + ajan) ortak kimlik satırı | `principal_id` (PK) | — | — |
| `human_users` | İnsan kullanıcı + rol | **FK** → `principals` | `deletion_state`, `deleted_at` (**yazılmıyor** — §I-07) | ✔ `version` (**`row_version` DEĞİL** — §I-07) |
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
| `strategy_root` | Strateji kimliği + yayınlanmış head | **FK** `current_revision_id`, `rationale_family_id` (ikisi de I-08) | — | ✔ `current_row_version` |
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
| `package_request` | Create Package isteği; `row_version` = request_version | `rationale_family_id`, `current_scan_id`, `draft_revision_id`, `baseline_asset_id`, `parent_revision_ref`, `prior_validation_run_ref` (+ `revision_attempt_no`) | (registry'de) | ✔ (registry) |
| `dependency_scan` | Pre-Check tarama artefaktı | `request_entity_id`, `job_id` | — | — |
| `baseline_asset` | Yüklenmiş baseline dosyası | `request_entity_id`, `parse_job_id` | — | — |
| `package_validation_run` | CP validation koşusu | `request_entity_id`, `draft_revision_id`, `job_id` | — | — |
| `package_revision_link` | Request Revision zinciri (append-only; attempt 1 = orijinal draft, ilk link `attempt_no=2`) | `request_entity_id`, `parent_revision_ref`, `parent_package_root_id`, `prior_validation_run_ref` | — | — |
| `package_import_job` | Paket import işi (export'un tersi). **`source_package_name`** (nullable, migration `0042`) = import edilen paketin submit anında manifest'ten pinlenen adı (F-07 §4.4) | `origin_package_id`, `result_package_root_id`, `job_id` | — | — |
| `embedded_resolver_registry` | ESP resolver registry (`registry_version` = OCC kaynağı) | `package_entity_id`, `trusted_active_revision_id`, `replacement_revision_id` | — | ✔ (`registry_version`) |
| `embedded_resolver_contract` | Resolver imza sözleşmesi | `entity_id`, `revision_id` | — | — |
| `embedded_resolver_validation_run` | Resolver doğrulama koşusu | `entity_id`, `revision_id` | — | — |
| `rationale_family_root` | Rationale ailesi kökü (`display_color` burada) | `entity_id` | (registry'de) | (registry'de) |
| `rationale_family_revision` | Ailenin değişmez revizyon snapshot'ı (asla UPDATE edilmez; `uq_rationale_family_revision_no`) | `entity_id`, `parent_revision_id`, `revision_no` | — | — |
| `package_rationale_assignment` | Paket ↔ aile ataması | `target_root_id`, `rationale_family_id`, `..._revision_id` | — | — |
| `instrument_registry` / `instrument_alias` | Kanonik enstrüman + takma adları | `venue_id`, `instrument_id` | — | ✔ **`registry_version`** (`models/instrument.py:55`, `Integer NOT NULL default=1` — doğrulandı) |
| `resource_share` | Açık paket paylaşımı | `resource_id`, `grantee_principal_id`, `revoked_by_principal_id` | (revoke) | — |

## Backtest (RUN → Result → artifacts)

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `backtest_run` | RUN admission satırı. **O-06:** `cancel_requested_at` / `cancel_requested_by_principal_id` (FK → `principals`) cancel **niyetini**, `cancellation_reason` doc 15 §16 terminal gerekçesini taşır — cancel bir state DEĞİL, state kümesi doc 15 §4'te sabittir | `composition_snapshot_id`, `manifest_id`, `ready_report_id`, `retry_of_run_id`, `job_id`, `result_id`, `cancel_requested_by_principal_id` | — | ✔ |
| `backtest_run_event` | **O-05** — kalıcı, run başına monoton `sequence_no` taşıyan stage olayları (`RUN_STARTED` / `RUN_STAGE_CHANGED` / terminal). Worker her stage'i ayrı commit eder → PROVISIONING/RUNNING dışarıdan görünür | `run_id` (FK → `backtest_run`, CASCADE), `UNIQUE(run_id, sequence_no)` | — | — |
| `backtest_run_manifest` | Değişmez Run Manifest (pinlenmiş her şey) | `run_id`, `composition_snapshot_id` | — | — |
| `backtest_result` | Değişmez sonuç kökü | `run_id`, `manifest_id` | `deletion_state` | ✔ |
| `result_summary` | Headline özet (ör. `timeframe`) | `result_id` | — | — |
| `metric_value` | Kalıcı metrik satırları | `result_id` | — | — |
| `result_equity_point` / `trade_ledger_row` / `signal_event` / `diagnostic_artifact` | Ağır artifact'lar (keyset drill-down) | `result_id` | — | — |
| `filtered_event` | **I-02** — filtre vetolarının AYRI artifact'ı (`filtered_no_entry`). `signal_event` ile aynı şekil, ama kendi `seq` dizisi: doc 15 §3.2 "View Signal Events" + "View Filtered Events" iki ayrı drill-down | `result_id` (FK → `backtest_result`, CASCADE), `UNIQUE(result_id, seq)` | — | — |
| `result_artifact_checksum` | **I-02** — (result, artifact tipi) başına içerik checksum'ı + `row_count` (doc 15 §7 "artifact checksum verification", §8.3). Beş artifact tipinin **hepsi** için yazılır | `result_id` (FK, CASCADE), `UNIQUE(result_id, artifact_type)` | — | — |
| `result_manifest_snapshot` | Result'a bağlı manifest kopyası | `result_id` | — | — |
| `export_artifact` | Result'ın şema-versiyonlu türevi. **`export_type` = non-native enum → düz `VARCHAR(24)`**, PG ENUM tipi de CHECK constraint'i de YOK; üyelik Python'da zorlanır (`domain/backtest/export.py::ExportType`). Migration `0040` bu kolonu 13 → 24'e genişletti (S-L2) | `result_id` | — | — |
| `ready_check_report` / `readiness_issue` | Değişmez readiness raporu + bulguları | `composition_snapshot_id`, `report_id` | — | — |

## Portfolio / Allocation, Metric Profile

| Tablo | Amacı | Ana bağlar | soft-del | OCC |
|---|---|---|---|---|
| `portfolio_allocation_plan` | Draft/plan kökü (sermaye, currency, compounding) **+ portfolio-level cross-item kuralları:** `max_total_exposure_percent` `NUMERIC(9,6)` NULL (NULL = cap yok) · `conflict_policy` `VARCHAR(14)`+CHECK NULL (NULL = `KEEP_SEPARATE`) — migration `0035_portfolio_rules` | `workspace_entity_id`, `current_revision_id` | — | ✔ |
| `portfolio_allocation_entry` | Item başına tahsis satırı | `plan_id`, `composition_item_id` | — | ✔ |
| `portfolio_allocation_plan_revision` | Değişmez plan revizyonu. **Cross-item kuralları için KOLON ALMAZ** — değerler `config` JSON snapshot'ında taşınır | `plan_id`, `source_draft_row_version` | — | — |
| `metric_definition` | Metrik registry (sistem tanımlı) | — | — | — |
| `result_view_metric_profile_root` | Kişisel/sistem profil kökü | `owner_principal_id`, `current_revision_id` | — | ✔ |
| `result_view_metric_profile_revision` | Değişmez profil revizyonu | `profile_id`, `previous_revision_id` | — | — |

> **`portfolio_allocation_plan`'ın yukarıdaki iki kolonu doc 13 §8.2 canonical payload'ında YOK**
> (kod spec'ten ileri). Alanların anlamı, blocker/warning davranışı, motor fail-closed kapıları ve
> hangi slice'ta geldiği: `docs/PROJECT_HISTORY.md` §"B-1 · doc 13 §8.2'nin kapsamadığı, kodda
> uygulanan portfolio-level cross-item kuralları". **Dikkat:** `max_total_exposure_percent` adı
> doc 02'de **per-strategy** limit olarak da geçer — ayrı düzlem, ayrı alan.

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
| `manual_publication_events` | Yayın olay kaydı (published/revised/soft_deleted/**purged**; `duplicate_override` + `duplicate_of_document_id` = doc 21 §10 açık override kararı) | `document_id`, `stream_entry_id` | — | — |
| `trash_entries` | Trash projeksiyonu (restore/purge OCC token'ı) | `entity_id`, `purge_job_id` | `deleted_at` | ✔ |
| `tombstones` | Purge sonrası mezar taşı | `entity_id` | — | — |
| `future_capability` | Capability registry (`registry_version` OCC) | `capability_id`, `changed_by_actor_id` | — | ✔ (`registry_version`) |
| `capability_activation_event` | Lifecycle geçiş geçmişi | `capability_id`, `actor_principal_id` | — | — |
| `view_dataset` | `view_dataset.query` çıktısı | `owner_principal_id` | `deletion_state` | ✔ |
| `analysis_artifact` | `analysis_artifact.create` çıktısı | `owner_principal_id` | `deletion_state` | ✔ |
| `experiment_proposal` / `execution_plan` | Future-Dev planlama satırları | `owner_principal_id` | — | ✔ |

---

## Doğrulanmamış noktalar (`?`) — **üçü de 2026-07-29'da ampirik kapandı**

- ~~`instrument_registry` OCC kolonu~~ → **çözüldü:** kolon var ve adı `registry_version`
  (`models/instrument.py:55`, `Integer NOT NULL default=1`). `X-Registry-Version` header'ı bu
  kolonu taşır — `row_version` **değil**.
- ~~`embedded_resolver_registry.registry_version`~~ → **çözüldü:** aynı biçim,
  `models/esp.py:90` (`Integer NOT NULL default=1`). Ad kullanımdan değil, kolon bildiriminden
  doğrulandı.
- ~~`package_request.row_version` fiziksel olarak nerede~~ → **çözüldü:** kök satırda **değil**,
  `entity_registry` satırında. `models/create_package.py:9` + `:57` docstring'i bunu açıkça
  söylüyor: "The registry row owns identity, owner, deletion and `row_version` (the
  request_version)". Yani `X-Request-Version` registry `row_version`'ının bir yazımıdır.

Hâlâ açık olan tek nokta:

- Kolon-seviyesi index/constraint detayları bu haritada YOK (yalnızca `trash_entries` keyset index'i
  ve `audit_events` trigram/log index'leri migration'larda mevcut).

---

## §I-07 — `human_users` OCC taşır; adı `version` (migration YOK, bilinçli)

**Şüphe neydi:** `human_users` soft-delete kolonları taşıyıp `row_version` taşımayan tek kök
tablo görünüyordu → "OCC'siz kök" sanıldı. **Ampirik olarak yanlış.**

- **OCC VAR.** `models/identity.py:40` → `version: Mapped[int]` (`Integer NOT NULL default=1`).
  Mutasyonda +1 (`commands/role_assignment.py:123`, `commands/roles.py:66`), uyuşmazlıkta 409
  `USER_ROLE_VERSION_CONFLICT` (`commands/role_assignment.py:94-95` →
  `shared/errors.py:215`). Doc 19 §9.3/§11 taksonomisi bu kodu **ismen** istiyor.
- **Dual-token da bağlı (O-12 uyumlu).** `routes/admin_panel.py:97-100`
  `PATCH /admin/users/{id}/role` gövdesindeki `expected_head_revision_id` ile `If-Match`
  başlığını `shared/concurrency.py::reconcile_occ_tokens` üzerinden geçirir — kural route'a
  kopyalanmamış.
- **Kilit + no-op + idempotency tam.** `session.refresh(user, with_for_update=True)`,
  aynı rol → `changed=false` (**version bump YOK, audit YOK**), gövde `run_idempotent` içinde.

**Neden `row_version` kolonu EKLENMEDİ (karar):**

1. **İki token = O-12'nin tam olarak yasakladığı şey.** `version` zaten OCC token'ı; yanına
   `row_version` koymak aynı satırda iki bağımsız önkoşul yaratırdı — CLAUDE.md §O-12'nin
   "tek değerin iki yazımı, iki bağımsız önkoşul DEĞİL" kuralının ihlali.
2. **Yeniden adlandırma kırıcı bir sözleşme değişikliği.** `version` **tel üstünde**:
   `commands/role_assignment.py:47` + `queries/user_registry.py:32` + `routes/identity.py:69`
   projeksiyonlarında yayımlanıyor ve `frontend/src/lib/adminPanel.ts:27,72` bunu tüketiyor.
3. **Farklı ad zaten bu repoda konvansiyon.** `registry_version` üç tabloda aynı işi yapıyor ve
   yukarıda ("Doğrulanmamış noktalar") ampirik olarak kapatılmış durumda. Ad, sayfanın kendi
   hata taksonomisinden gelir; davranış tektir.

**Ayrı ve dürüst sınır — soft-delete kolonları BEYAN EDİLMİŞ ama HİÇ YAZILMIYOR.**
`human_users.deletion_state` / `deleted_at` / `deleted_by` / `delete_reason` kolonları var, ama
onlara **yazan tek bir komut yok**; yalnızca okuma kapısı olarak kullanılıyorlar
(`application/identity.py:30`, `commands/auth.py:364`, `:509`). `human_user`, K-06'nın
`domain/trash/page.py::TRASH_OBJECT_LOCATIONS` kataloğunda **yok** — yani kullanıcı silme diye
bir özellik yok, kolonlar da ileriye dönük şema. Bu tutarlı: katalogda olmayan tip için trash
entry yazma yükümlülüğü de yok. **Kullanıcı soft-delete'i eklenirse** K-06 gereği aynı anda
katalog + `commands/deletion.py` + `jobs/purge.py` + `queries/trash.py` dalları eklenmeli.

Doğrula: `uv run pytest tests/integration/test_panel_management_logs.py -k "assign_role" -q --no-cov`
→ `test_assign_role_version_conflict` bayat `version` ile `UserRoleVersionConflictError` bekler.
(I-07 görevinin önerdiği `-k "user_role_occ"` seçicisi **hiçbir teste uymuyor** — gerçek seçici budur.)
