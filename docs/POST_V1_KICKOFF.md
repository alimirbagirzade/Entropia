# Post-V1 — Kickoff / Resume

> **Amaç:** V1 kapandı (Stage 0–8 COMPLETE). Bu doküman post-V1 durumunu, aday iş listesini
> ve temiz oturumda yapıştırılacak resume prompt'u içerir.

## Durum (2026-07-10, TIER 2 frontend — Strategy Details sayfası; PR #117 MERGED)

**FRONTEND-ONLY (3 yeni + 1 edit, +1501 satır)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK,
alembic head `0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/strategy` placeholder'ı gerçek
sayfa oldu — `routes/strategy.py`'nin TAM yüzeyi (9/9 endpoint, Stage 3b doc 02 §7–§9) bağlandı:
editor draft workflow (create root+draft / full-payload PATCH / pure validate / save immutable
revision / clear) + root header + revision history + immutable revision deep-link. Workspace
grubunun en büyük sayfası landed. Frontend 189 → **197** (+8 vitest). main = `fcbbfb6`
(Merge #117), feat `8e5e068`. CI yeşil; self-review 0 CRITICAL/HIGH.

**AMPİRİK route haritası (imzalar OKUNDU):** PATCH/save/clear OCC'si **BODY-form
`expected_draft_row_version` INT** (body If-Match'e galip; ZORUNLU — yoksa 422; draft row_version
**0'dan** başlar — 0 geçerli token; stale → 409 `STRATEGY_DRAFT_CONFLICT` verbatim) + deneme
başına taze Idempotency-Key; **validate body/header OKUMAZ** (saf compiler pass, audit satırı YOK
→ Idem YOK, invalidation YOK); create OCC'siz (head yok) — `display_name` command-REQUIRED
(route'ta optional); save aynı tx'te bağlı Mainboard item'larını yeni mirror revision'a re-pin
eder (composition_hash oynar → önceki Ready raporu STALE) →
`["strategy"]+["mainboard"]+["readiness"]+["audit"]` invalidate; bloklu save 422
`error.details`'te compiler issue listesi (`{field,code,message}` — verbatim render). `draft_id`
bağımsız `stratdraft` ULID — **root→draft lookup endpoint'i YOK** → draft handle URL'de
(`?draft=`); `/strategies/{root}/revisions` **BARE LIST** (envelope yok).

**Reuse anchor'ları:** `lib/strategy.ts` (yeni) — `StrategyDraft`/`StrategyDetail`/
`StrategyRevisionRow`/`StrategyReference`/`StrategyRevisionDetail` + Create/Patch/Validate/Save/
Clear result tipleri (`SaveRevisionResult.ready_state="STALE"` sabiti) + `STRATEGY_LIFECYCLE_LABELS/
_TONES` + `VALIDATION_STATUS_TONES`; `["strategy"]` hook'ları (özel SSE YOK → `resource.changed`):
`useStrategyDraft`/`useStrategy`/`useStrategyRevisions` (bare list)/`useStrategyRevision`
(immutable, 5m staleTime) + 5 mutasyon. `pages/StrategyDetails.tsx` (yeni) — URL modları
`?draft=`/`?strategy=`/`?revision=`; `PayloadEditor` `key={row_version}` remount-reseed (asla
merge); mutation state PARENT `DraftWorkbench`'te; bozuk JSON client'ta kalır ("Not sent"); Clear
iki adımlı onay; `AttachedStrategiesCard` (default Mainboard `item_kind==="strategy"` keşfi).
`App.tsx` REAL_PATHS 20→21; `nav.ts` 24 sabit. `test/strategy.test.tsx` +8 (apiStub SIRALI —
draft-aksiyon fragmanları create prefix'inden ÖNCE; `/revisions` root GET'ten ÖNCE).

**Dürüst sınır:** strateji LIST endpoint'i YOK — keşif default Mainboard'a bağlı item'lardan; hiç
attach edilmemiş strateji yalnız create anındaki `?draft=` URL'iyle erişilir; Mainboard ATTACH
Stage-3a operasyonu (bu yüzeyde değil); payload editörü ham JSON (semantik otorite yalnız server
compiler'ı — issue'lar verbatim).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan **3 placeholder sayfa — hepsi
Workspace**, hepsinin V1 backend yüzeyi landed: `trading_signal.py` + `trade_log.py` (6+6
endpoint, neredeyse simetrik ikizler — source-asset → 202 import → create → revisions → read; tek
slice'ta ikisi mantıklı) / outsource-signal; VEYA ESP registry MUTASYON slice'ı (`esp.py`
create/activate/deprecate — Admin-only, `X-Registry-Version` OCC; `library.py` 2/2 zaten bağlı).
TIER 3 deferred: retention auto-purge, data-queue redelivery, SSE streaming e2e, tool-call status
shadowing.

---

## Durum (2026-07-10, TIER 2 frontend — User Manual sayfası; PR #115 MERGED)

**FRONTEND-ONLY (3 yeni + 2 edit, +1295 satır)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK,
alembic head `0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/user-manual` placeholder'ı gerçek
sayfa oldu — `routes/manual.py`'nin TAM yüzeyi (7/7 endpoint, Stage 7a doc 21) bağlandı: all-role
Published reader stream + server-side search + Admin publish/upload/replace/soft-delete/restore.
**Docs nav grubu KAPANDI** (Future Dev #82 + User Manual #115). Frontend 181 → **189** (+8 vitest).
main = `6a4ba3b` (Merge #115), feat `54fd4db`. CI yeşil; self-review 0 CRITICAL/HIGH.

**AMPİRİK route haritası (imzalar OKUNDU):** create/upload/delete OCC'si **BODY-form
`expected_stream_version` INT** (server'da optional — client HER ZAMAN render edilen snapshot ile
korur, UM-13/UM-15; stale → 409 `MANUAL_STREAM_CONFLICT` verbatim); revisions OCC'si **BODY-form
`expected_head_revision_id` STR** (route body'yi If-Match'e tercih eder; stale → 409
`MANUAL_REVISION_CONFLICT`); **DELETE opsiyonel BODY taşır** (reason + expected_stream_version) +
Idem → `api.del` body/header almadığından `apiRequest` doğrudan; `:restore` **`require_trash_admin`**
(manual admin DEĞİL), body YOK, dönüş = Trash-core `RestoreResult` (tip `lib/trash.ts`'ten REUSE);
`get_manual_section` ROUTE EDİLMEMİŞ (doc 21 §12 Agent Tool Gateway). Tüm mutasyonlar
`["manual"]`+`["audit"]` (+delete/restore'da `["trash"]`) invalidate; deneme başına taze
Idempotency-Key.

**Reuse anchor'ları:** `lib/manual.ts` (yeni) — `ManualBlock`/`ManualSection`/`ManualStreamPage`/
`ManualSearchResult` (heading_path STRING, liste değil!)/`PublishResult`/`ReviseResult`/
`DeleteResult` + `ACCEPTED_UPLOAD_EXTENSIONS` hydration aynası; `["manual"]` hook'ları (özel SSE
YOK → `resource.changed`): `useManualStream(cursor)`/`useManualSearch(q,cursor)` (boş sorgu fetch
etmez, doc 21 §14) + 5 mutasyon. `pages/UserManual.tsx` (yeni) — `BlockView` kanonik blok renderer
(heading/paragraph/lists/code/callout/divider — yalnız TEXT node, bilinmeyen tip fail-closed null);
baseline aksiyonları server-truth `is_baseline`'dan gizli (UM-10, Trash `restore_eligible` deseni);
delete sonucu PARENT'ta (`lastDelete` — section refetch'te kaybolmaz, Portfolio dersi); composers
client-role-gate'siz (doc 21 §2). `App.tsx` REAL_PATHS 19→20; `nav.ts` 24 sabit.
`test/userManual.test.tsx` +8 (apiStub SIRALI — `:upload`/`:restore`/`/revisions` fragmanları create
prefix'inden ÖNCE: create path'i hepsinin substring'i).

**Dürüst sınır:** revision replacement doc 21 §7'de "V18 UI not exposed" — 7/7 için açık Admin bakım
affordance'ı (PR #95 gated-POST emsali; server uçtan uca gate'ler); upload UTF-8 METİN taşır
(route sözleşmesi `content: str` — ham bayt geçmez; PDF/DOCX V1 değil); manual'ın özel SSE event'i
yok; Trash purge ayrı re-auth slice'ı.

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan **4 placeholder sayfa — hepsi
Workspace**, hepsinin V1 backend yüzeyi landed: `strategy.py` Strategy Details (9 endpoint — draft
create/patch/validate/save/clear + strateji/revizyon okumaları; en kapsamlı aday) /
`trading_signal.py` + `trade_log.py` (6+6 endpoint, neredeyse simetrik ikizler — source-asset →
202 import → create → revisions → read; tek slice'ta ikisi mantıklı) / outsource-signal; VEYA ESP
registry MUTASYON slice'ı (`esp.py` create/activate/deprecate — Admin-only, `X-Registry-Version`
OCC; `library.py` 2/2 zaten bağlı). TIER 3 deferred: retention auto-purge, data-queue redelivery,
SSE streaming e2e, tool-call status shadowing.

---

## Durum (2026-07-10, TIER 2 frontend — Portfolio / Equity Allocation sayfası; PR #113 MERGED)

**FRONTEND-ONLY (4 dosya, +1477 satır)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic
head `0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/portfolio` placeholder'ı gerçek sayfa oldu —
`routes/allocation.py`'nin TAM yüzeyi (5/5 endpoint, doc 13 Stage 4a) bağlandı: Ready Check'in
okuduğu allocation draft'ının editörü. **Backtest nav grubu KAPANDI** (RUN/History #72 + Arrange
Metrics #74 + Ready Check #111 + Portfolio #113). Frontend 174 → **181** (+7 vitest). main =
`3210ede` (Merge #113), feat `f3e9550`. CI yeşil; self-review 0 CRITICAL/HIGH.

**AMPİRİK route haritası (imzalar OKUNDU):** GET draft'ın body `row_version`'ı canlı OCC token
(0 = plan yok = geçerli creation token); PUT draft + POST revisions OCC'yi **BODY-form
`expected_row_version`** taşır (route `_resolve_expected` body'yi If-Match'e tercih eder) + deneme
başına taze `Idempotency-Key`; `validate` hiç body/header OKUMAZ (her koşuda yeni immutable
`validation_report_id` + audit satırı); `sync` POST ama **PURE READ** merge preview (query katmanı —
Idem YOK, invalidation YOK; removal yalnız açık Save PUT ile, §14#9). `item_type` PUT'ta gönderilmez
(server türetir, §8.2); stale → 409 `ALLOCATION_DRAFT_CONFLICT` verbatim. Draft PUT dönüşü
`readiness_invalidated: true` → `["allocation"]+["readiness"]+["mainboard"]+["audit"]` invalidate;
revision → `["allocation"]+["audit"]`; validate → yalnız `["audit"]`.

**Reuse anchor'ları:** `lib/allocation.ts` (yeni) — wire tipleri `AllocationDraftResponse`/
`SaveDraftResult`/`AllocationValidationReport`/`SyncPreview`/`RevisionResult`/`DerivedAmounts`/
`AllocationIssue` + `ALLOCATION_CURRENCIES`(4)/`COMPOUNDING_MODES`(2)/`ALLOCATION_STATE_LABELS`+
`_TONES` (UPPERCASE, doc-14 lowercase readiness'ten AYRI); `["allocation"]` hook'ları (özel SSE YOK):
`useAllocationDraft`/`useSaveAllocationDraft`/`useValidateAllocation`/`useSyncPreview`/
`useCreateAllocationRevision`. `pages/Portfolio.tsx` (yeni) — `DraftEditor` `key={row_version}`
remount-reseed (asla merge yok); mutation state PARENT'ta (remount'u atlatır); issues + derived
VERBATIM (istemci kapital matematiği hesaplamaz); `severityTone` `lib/readiness`'ten reuse. `App.tsx`
REAL_PATHS 18→19; `nav.ts` 24 sabit. `test/portfolio.test.tsx` +7 (apiStub SIRALI; OCC 0-token +
item_type-yok body asserti; pure-read sync header asserti).

**Dürüst sınır:** sayfa yalnız default Mainboard composition'ını okur; Validate SAVED draft'ı
doğrular (yerel edit'leri değil); sync preview'ın "Apply" düğmesi yok (birleştirme editörde yapılıp
Save ile uygulanır — §14#9); allocation'ın özel SSE event'i yok (`resource.changed`).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan **5 placeholder sayfa** (hepsinin
V1 backend yüzeyi landed): (1) Workspace — `strategy.py` Strategy Details / `trading_signal.py` /
`trade_log.py` / outsource-signal; (2) Docs — `manual.py` User Manual (muhtemelen en küçük slice);
VEYA ESP/Library registry MUTASYON slice'ları (Admin-only, `X-Registry-Version` OCC — Rationale
shared-editing / marketData `postWithOcc` deseni TABAN). TIER 3 deferred: retention auto-purge,
data-queue redelivery, SSE streaming e2e, tool-call status shadowing.

---

## Durum (2026-07-10, TIER 2 frontend — Backtest Ready Check sayfası; PR #111 MERGED)

**FRONTEND-ONLY (4 dosya, +748 satır)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic
head `0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/backtest/ready-check` placeholder'ı gerçek
sayfa oldu — `routes/readiness.py` (doc 14 §4/§7/§9) bağlandı: Backtest grubunun strateji→RUN kapısı
(RUN/History zaten #72'de bağlı). Frontend 168 → **174** (+6 vitest). main = `946b6cf` (Merge #111),
feat `6232486`. CI 3/3 yeşil; self-review 1 bug buldu + düzeltti (aşağıda).

**AMPİRİK route bulgusu (imza OKUNDU):** OCC token `"rv-N"` DEĞİL — composition **FINGERPRINT**.
`POST /mainboard-compositions/{id}/readiness-checks` `expected_fingerprint`'i **BODY-form** taşır
(If-Match değil; route `_resolve_expected` body'yi öncelikler) + deneme başına taze
`Idempotency-Key`; 409 `CompositionStale` = RC-09 verbatim. Success `["readiness"]` +
`["mainboard"]` İKİSİNİ de invalidate eder (default-Mainboard `ready_summary` hareket eder).

**Reuse anchor'ları:** `lib/readiness.ts` (yeni) — wire tipleri `ReadinessIssue`/`ReadinessSummary`/
`ReadinessReport`/`CurrentReadiness`/`RunCheckResult`; `enums.py` aynaları `READINESS_STATE_LABELS`/
`READINESS_STATE_TONES` + `NOT_CHECKED_STATE` + `readinessStateLabel`/`readinessStateTone`/
`severityTone`; `["readiness"]` hook'ları (özel SSE YOK → `resource.changed`):
`useCurrentReadiness(compositionId)` / `useReadinessReport(reportId)` / `useRunReadinessCheck`.
`pages/ReadyCheck.tsx` (yeni) — iki mod: `?report=<id>` immutable deep-link + default workbench
(`useDefaultMainboard` composition → current readiness → guard toggle'lı run); stale ("re-run") vs
superseded ("a newer report exists") ayrımı SERVER `state`'inden (`state === "stale"`), asla
yeniden türetilmez. **SELF-REVIEW BUG:** stale bayrağı `stored_state !== state` idi → superseded'a
yanlış "re-run" gösterirdi → `state === "stale"`'e düzeltildi + regression testi. `App.tsx`
REAL_PATHS 17→18; `nav.ts` 24 sabit. `test/readyCheck.test.tsx` +6 (apiStub SIRALI; zincirleme
yükleme için `findBy*` — senkron `getBy*` erken çalışıyordu).

**Dürüst sınır:** RUN admission (`POST /backtest-runs`) RUN sayfasında kalır (doc 14 §9.3 scope);
readiness'in özel SSE event'i yok; sayfa yalnız default Mainboard composition'ını okur (RUN sayfası
deseni; Stage 3 gerçek Mainboard sayfası app-level'a taşıyabilir).

**SIRADAKİ İŞ — KULLANICI TEYİT ETTİ (2026-07-10):** `allocation.py` **Portfolio/Equity Allocation**
(`/portfolio`) slice'ı — Ready Check'in okuduğu allocation draft'ının editörü, Backtest grubunu
kapatır. Route imzalarını ÖNCE OKU (OCC/Idem her endpoint'te olmayabilir — PR #105/#111 dersi).
Sonrası: kalan **5 placeholder** — Workspace (`strategy.py` / `trading_signal.py` / `trade_log.py` /
outsource-signal), Docs (`manual.py` User Manual) — + ESP/Library registry MUTASYON slice'ları
(Admin-only, `X-Registry-Version` OCC). TIER 3 deferred: retention auto-purge, data-queue
redelivery, SSE streaming e2e, tool-call status shadowing.

---

## Durum (2026-07-10, TIER 2 frontend — Research Data lifecycle aksiyonları; PR #109 MERGED)

**FRONTEND-ONLY (2 yeni + 3 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. PR #107'nin read+ingest dürüst sınırı kapandı:
`routes/research_data.py`'nin bağlanmayan 8 lifecycle endpoint'i bağlandı → Research Data sayfası
**14/14 endpoint** (Packages & Data grubu TAM). Frontend 157 → **168** (+11 vitest). main = `32d07e4`
(Merge #109), feat `2e488dc`. CI 3/3 yeşil; self-review 0 CRITICAL/HIGH.

**AMPİRİK route haritası (imzalar OKUNDU — PR #105 dersi):** revise/approve/revoke → `postWithOcc`
(If-Match `"rv-N"` + taze Idempotency-Key); time-policy/field-def/feature-def → header YOK;
bundles/agent + bundles/backtest-evidence → PURE READ compile probe (durable row/audit/Idem/
invalidation YOK — ESP resolve-probe deseni). approve/revoke Admin-only (`ensure_can_approve`/
`ensure_can_revoke` → `APPROVAL_REQUIRES_ADMIN` 403 verbatim). Validation: `fixed_delay`→delay
zorunlu/diğerleri null; `custom` timezone→IANA zorunlu/diğerleri null; `other_custom`→custom_category
zorunlu. approve ayrıca DR3 (`DEPENDENCY_BLOCKED`) + DR4 (`TIME_POLICY_INVALID`) yeniden kontrol.

**Reuse anchor'ları:** `lib/researchData.ts` (genişletildi) — 8 hook + taksonomi aynaları
(`EVENT_TIME_SEMANTICS`/`AVAILABLE_TIME_POLICIES`/`FIXED_DELAY_POLICY`/`RESEARCH_TIMEZONE_MODES`/
`CUSTOM_TIMEZONE_MODE`) + `postWithOcc` (marketData birebir kopyası); `useCreateRevision` (OCC, body
`entity_id`/`row_version` YOK) / `useSetTimePolicy` / `useDefineField` / `useDefineFeature` /
`useApproveRevision` / `useRevokeApproval` (invalidate `["research-data"]`+`["audit"]`) /
`useCompileAgentBundle` / `useCompileEvidenceBundle` (invalidation YOK). `components/ResearchLifecycle.tsx`
(yeni, 713 satır) — 6 composer DetailCard'da (`key={detail.data.entity_id}`): ReviseComposer /
TimePolicyComposer / FieldDefinitionComposer (`FIELD_INPUTS` map) / FeatureDefinitionComposer /
ApprovalComposer (revision picker) / BundleComposer (+`BundleResultView`). `pages/ResearchData.tsx` =
import+render+yorum tazeleme. `test/researchDataLifecycle.test.tsx` +11 (apiStub SIRALI — 8 aksiyon
route'u liste prefix'inden ÖNCE). `test/researchData.test.tsx` 2 assertion `within(identityTable)`
scope'landı (lifecycle `<option>`'ları event-time semantics + "rv 4" metnini paylaşıyor). App/nav
UNCHANGED (REAL_PATHS 17, nav 24).

**Dürüst sınır:** ham baytlar sayfadan geçmez; `["jobs"]` liste yüzeyi kalıcı yok; bundle'lar pure read
(kalıcı read yüzeyi yok — command return + `bundle_hash`); özel research-data SSE yok
(`resource.changed`). **routes/research_data.py TAM bağlı (14/14) — Packages & Data grubu kapandı.**

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan **7 placeholder sayfa** (hepsinin
V1 backend yüzeyi landed): (1) Workspace — `strategy.py` Strategy Details / `trading_signal.py` /
`trade_log.py` / outsource-signal; (2) Backtest — `allocation.py` Portfolio / `readiness.py` Ready
Check (RUN/History zaten bağlı); (3) Docs — `manual.py` User Manual; + ESP/Library registry MUTASYON
slice'ları (Admin-only, `X-Registry-Version` OCC — Rationale shared-editing / marketData `postWithOcc`
deseni TABAN). TIER 3 deferred: retention auto-purge, data-queue redelivery, SSE streaming e2e,
tool-call status shadowing.

---

## Durum (2026-07-09, TIER 2 frontend — Research Data sayfası; PR #107 MERGED)

**FRONTEND-ONLY (2 yeni + 1 edit + 1 test)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK,
alembic head `0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/research-data` gerçek sayfa oldu —
`routes/research_data.py` (doc 12) OKUMA yüzeyi (role-aware registry list + head detail) + sahip
INGEST zinciri (create dataset [DR3 market-link] / upload-session start+finalize / durable 202
analysis) bağlandı — 14 endpoint'in 6'sı. **Packages & Data grubunun SON gerçek sayfası.** Market
Data sayfası (#103) deseninin birebir paraleli: read+ingest önce, revision lifecycle ertelendi.
Frontend 146 → **157** (+11 vitest). main = `38988a2` (Merge #107), feat `5049f4e`. CI yeşil;
self-review 0 CRITICAL/HIGH.

**AMPİRİK bulgu (route/command okundu):** create + upload-session `Idempotency-Key` OKUMUYOR →
gönderilmedi; finalize + analysis okuyor → deneme başına taze key. Her endpoint Admin/Supervisor/
Agent gate'li (`ensure_can_access_page` — User/Guest 403 verbatim); create ayrıca DR3 (ACTIVE+
APPROVED linked market revision yoksa 409 `DEPENDENCY_BLOCKED`). `research_data.router` `market_data`
ile aynı `prefix=base` → `/api/v1/research-datasets`.

**Reuse anchor'ları:** `lib/researchData.ts` — wire tipleri `_revision_dict`/`get_research_dataset_detail`
+ command dict aynası; `RESEARCH_CATEGORIES`(8; `other_custom`→`custom_category` ZORUNLU, diğerleri
null)/`USAGE_SCOPES`(3)/`RESEARCH_REVISION_STATES`(7; verified≠approved, approval_revoked) aynaları +
`researchStateTone`/`OTHER_CUSTOM_CATEGORY`; `["research-data"]` hook'ları (özel SSE YOK →
`resource.changed`): `useResearchDatasets` keyset + `useResearchDataset` (dönen `row_version` = ertelenen
lifecycle OCC token'ı). `useCreateDataset` Idempotency-Key YOK; `useStartUpload` no-idem;
`useFinalizeUpload`/`useRequestAnalysis` taze key. `pages/ResearchData.tsx` = `CreateDatasetCard` (DR3
`market_entity_id` required + category/usage_scope + `other_custom`→custom_category) + `RegistryCard`
(keyset) + `DetailCard` (meaning/timing/usage tablo + history + Step 1/2 ingest). `App.tsx` REAL_PATHS
16→17; `nav.ts` 24 sabit. `test/researchData.test.tsx` +11 (apiStub SIRALI).

**Dürüst sınır:** revision lifecycle (append DRAFT/successor revision, `set_time_policy`,
`define_field`/`define_feature`, Admin `approve`/`revoke`, agent/backtest evidence bundles — 8
endpoint) doğal follow-up'a ertelendi (detay `row_version` If-Match OCC token'ı hazır); ham baytlar
sayfadan geçmez; `["jobs"]` liste yüzeyi kalıcı yok.

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** (a) **Research Data lifecycle follow-up**
(revise/successor/time-policy/field+feature defs/Admin approve+revoke/evidence bundles — Market Data
#105 deseni + `market_data.postWithOcc` If-Match `"rv-N"`+Idem helper TABAN) — doğal sıradaki; VEYA
kalan **7 placeholder sayfa** (hepsinin V1 backend yüzeyi landed): Workspace (`strategy.py` Strategy
Details / `trading_signal.py` / `trade_log.py` / outsource-signal), Backtest (`allocation.py` Portfolio
/ `readiness.py` Ready Check), Docs (`manual.py` User Manual); + ESP/Library registry MUTASYON
slice'ları (Admin-only, `X-Registry-Version` OCC — Rationale shared-editing deseni TABAN). TIER 3
deferred: retention auto-purge, data-queue redelivery, SSE streaming e2e, tool-call status shadowing.

---

## Durum (2026-07-09, TIER 2 frontend — Market Data lifecycle aksiyonları; PR #105 MERGED)

**FRONTEND-ONLY (3 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. Market Data sayfası (PR #103) DÜRÜST SINIRI kapandı:
`routes/market_data.py`'nin bağlanmayan 4 lifecycle endpoint'i bağlandı — 10/10 endpoint artık
frontend'te. Frontend 140 → **146** (+6 vitest). main = `db7b585` (Merge #105), feat `d2a9ada`. CI
3/3 yeşil; self-review 0 CRITICAL/HIGH.

**AMPİRİK BULGU (route okuyarak — handoff/kickoff özeti YANLIŞTI):** successor + deprecate rotaları
`If-Match`/`Idempotency-Key` OKUMUYOR (imzalarında header yok); yalnız revisions + approve İKİSİNİ de
taşır. approve + deprecate Admin-only (`ensure_can_approve`). Route'u okumadan yazsaydım successor/
deprecate'e gereksiz OCC header koyacaktım.

| Endpoint | If-Match `"rv-N"` | Idem-Key | Admin | Transition |
|---|---|---|---|---|
| `POST /{id}/revisions` | ✓ | ✓ | — | append DRAFT (timezone REQUIRED) |
| `POST /{id}/successor` | — | — | — | superseding successor |
| `POST /{id}/approve` | ✓ | ✓ | ✓ | VERIFIED → APPROVED |
| `POST /{id}/deprecate` | — | — | ✓ | APPROVED → DEPRECATED |

**Reuse anchor'ları (kesin semboller):**
- **`lib/marketData.ts` (genişletildi):** `useCreateRevision`/`useCreateSuccessor`/
  `useApproveRevision`/`useDeprecateRevision` — `["market-data"]` altında (özel SSE YOK →
  `resource.changed`; her biri `["market-data"]`+`["audit"]` invalidate). `postWithOcc(path,
  rowVersion, body)` helper (`If-Match \`"rv-${rowVersion}"\`` + taze `Idempotency-Key`) —
  `lib/rationale.ts::useSoftDeleteFamily` deseninin birebir kopyası. `TIMEZONE_MODES`
  (exchange/utc/custom) aynası + wire tipleri `CreateRevisionResult`/`SuccessorResult`/
  `ApprovalResult`/`RevisionBody`. `RevisionBody`'de `timezone_mode` HER İKİ create-path için de
  gönderilir (successor route'u Pydantic-required kılar ama command yok sayar). row_version detay
  `useMarketDataset`'ten; her mutation sonrası invalidate → detay refetch → taze OCC token.
- **`pages/MarketData.tsx`:** `DetailCard`'a `LifecycleSection` — `RevisionComposer` (append
  revision [OCC] / create successor [OCC yok]; custom-mode IANA input; lokal JSON payload
  parse-block, `CreateDatasetCard` deseni) + `ApprovalComposer` (Admin approve/deprecate; revision
  picker `detail.revision_id` head'e default; `revisionOptionLabel`). Butonlar asla role-ön-gate'li
  değil — 403 (non-Admin) / 409 (stale token / illegal transition) kanonik zarf verbatim.
- **Testler:** `test/marketData.test.tsx` +6 (append revision If-Match `"rv-4"`+Idem-Key+default
  body / successor İKİ header YOK / approve OCC+Idem+seçilen revision+null note / deprecate header
  YOK / Admin-only denial `APPROVAL_REQUIRES_ADMIN` verbatim / custom-mode IANA gönderimi). apiStub
  SIRALI — 4 aksiyon route'u `POST /market-datasets` create prefix'inden ÖNCE. Mevcut `/rv 4/`
  ready-check kırıldı (composer "If-Match rv N" çakıştı) → composer metni "rv-N" yapıldı (ETag
  formatı zaten `"rv-N"`; boşluklu `/rv 4/` artık eşleşmez).

**Dürüst sınır:** ESP/Library registry MUTASYON slice'ları ayrı (Admin-only, `X-Registry-Version`
OCC). Revision picker mount'ta head'i okur; oturum-içi head kayması `["market-data"]` invalidation
refetch'i ile kapanır. `["jobs"]` liste yüzeyi YOK (kalıcı). Ham baytlar hâlâ sayfadan geçmez.

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan **8 placeholder sayfa** —
HEPSİNİN V1 backend yüzeyi landed: Packages & Data (`research_data.py` Research Data — grubu
kapatır), Workspace (`strategy.py` Strategy Details / `trading_signal.py` / `trade_log.py` /
outsource-signal), Backtest (`allocation.py` Portfolio / `readiness.py` Ready Check — RUN/History
zaten bağlı), Docs (`manual.py` User Manual); + ESP + Library registry MUTASYON slice'ları
(Admin-only, `X-Registry-Version` OCC — Rationale shared-editing OCC deseni TABAN). TIER 3 deferred:
retention auto-purge, data-queue redelivery, SSE streaming e2e, tool-call status shadowing.

---

## Durum (2026-07-09, TIER 2 frontend — Market Data sayfası; PR #103 MERGED)

**FRONTEND-ONLY (3 yeni + 1 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/market-data` gerçek sayfa oldu —
`routes/market_data.py` doc 11 OKUMA yüzeyi (registry list + head detail + approved-bundle resolve)
**+ sahip INGEST zinciri** (create dataset / raw-upload start+finalize / durable 202 analysis job /
schema mapping) bağlandı — 10 endpoint'in 8'i. Kalan placeholder'ların DÖRDÜNCÜSÜ indi — **8 kaldı**.
Frontend 128 → **140** (+12 vitest). main = `c09051a` (Merge #103), feat `0ca0468`. CI yeşil;
self-review + yerel döngü (0 CRITICAL/HIGH; 1 MEDIUM — bundle-probe tekrar-deneme — commit
öncesi düzeltildi).

**Reuse anchor'ları (kesin semboller):**
- **YENİ `frontend/src/lib/marketData.ts`:** wire tipleri `application/queries/market_data.py`
  `_revision_dict`/`get_market_dataset_detail`/`resolve_approved_market_data_bundle` +
  `application/commands/market_data.py` return dict'leri birebir aynası (`MarketDatasetRow`/
  `MarketDatasetDetail`/`ApprovedBundle` + `CreateDatasetResult`/`StartUploadResult`/
  `FinalizeUploadResult`/`AnalysisAccepted`/`SchemaMappingResult`). Taksonomi hidrasyon aynaları
  `MARKET_DATA_TYPES` (ohlcv/tick_trades/spread_execution) + `MARKET_REVISION_STATES` (8 state;
  `verified` ≠ `approved`) — sunucu her değeri yeniden doğrular (CR-04). Hook'lar `["market-data"]`
  altında (özel SSE event YOK — `resource.changed` süpürür): `useMarketDatasets` (keyset registry,
  placeholderData) + `useMarketDataset` (enabled-gated detay; dönen `row_version` ertelenen
  lifecycle aksiyonlarının OCC token'ı) + `useApprovedBundle` (İSTEĞE-BAĞLI salt-okuma probe —
  enabled-gated GET, retry:false; 404 verbatim → tüketici asla "latest"e bağlanmaz; tekrar tıklama
  refetch). Mutasyonlar `["market-data"]`+`["audit"]` invalidate: `useCreateDataset`
  (**Idempotency-Key YOK — create rotası okumuyor, birebir ayna**), `useStartUpload` (immutable
  evidence satırı: yalnız object_key+digest+size metadata), `useFinalizeUpload`/`useRequestAnalysis`
  (deneme başına taze `Idempotency-Key`; analysis 202 admission `{job_id, queue, status}` verbatim),
  `useConfirmMapping` (boş confirmed mapping GÖNDERİLMEZ → sunucu auto-confirm;
  `MAPPING_REVIEW_REQUIRED` 422 verbatim, D7). `parseMappingLines` ("canonical: source" satırı;
  boş source → null) + `linesToList` + `revisionStateTone`.
- **YENİ `pages/MarketData.tsx`:** `CreateDatasetCard` (kanonik üç tipten select; opsiyonel payload
  JSON OBJESİ — parse hatası lokal bloklanır [transport shaping], domain doğrulama sunucuda; create
  detayını otomatik açar), `RegistryCard` (revision-state badge + validation verbatim; cursor-stack
  Pager), `DetailCard` (kimlik/hash/revision history + Step 1/2 ingest akışı `UploadComposer`→
  `AnalysisAction`→`MappingComposer` + `BundleProbe`). Butonlar asla role-ön-gate'li değil —
  sunucunun owner/Admin draft gate'i (`ensure_can_edit_draft`) kanonik zarf ile verbatim yanıtlar.
- **`App.tsx`:** `/market-data` REAL_PATHS (15 → 16) + gerçek Route; **`nav.ts` DEĞİŞMEDİ** (24).
- **Testler:** YENİ `test/marketData.test.tsx` (+12: 1 `parseMappingLines` unit + 11 component;
  apiStub SIRALI — finalize `/raw-uploads`'tan, aksiyon/detay/bundle fragment'ları
  `/market-datasets` liste prefix'inden ÖNCE; "Binance 15m OHLCV" ready-check, badge assert'leri
  `within` ile registry tablosuna scope'lu).

**Dürüst sınır:** revision lifecycle aksiyonları (create revision / successor, Admin approve /
deprecate — If-Match `"rv-N"` OCC + `Idempotency-Key`) DOĞAL SONRAKİ slice (CP #91→#93 deseni;
detay `row_version` token'ı hazır); ham BAYTLAR bu sayfadan geçmez (bu yüzeyde byte-upload
endpoint'i yok — D5/D6 evidence satırı object key + digest pinler); analysis job id bilgilendirme
amaçlı (`["jobs"]` liste yüzeyi yok — kalıcı), ilerleme revision state'e düşer.

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** (1) **Market Data lifecycle
aksiyonları follow-up** — revise/successor + Admin approve/deprecate (If-Match `"rv-N"` OCC +
Idempotency-Key; PR #103 sınırını kapatır, CP #91→#93 deseni) — doğal sıradaki; (2) kalan 8
placeholder sayfa — HEPSİNİN V1 backend yüzeyi landed: Packages & Data (`research_data.py`
Research Data — grubu kapatır), Workspace (`strategy.py` Strategy Details / `trading_signal.py` /
`trade_log.py` / outsource-signal), Backtest (`allocation.py` Portfolio / `readiness.py` Ready
Check), Docs (`manual.py` User Manual); (3) ESP + Library registry MUTASYON slice'ları
(Admin-only, `X-Registry-Version` OCC — Rationale'deki shared-editing OCC deseni TABAN). TIER 3
deferred: retention auto-purge, data-queue redelivery, SSE streaming e2e, tool-call status
shadowing.

## Durum (2026-07-09, TIER 2 frontend — Rationale Families sayfası; PR #101 MERGED)

**FRONTEND-ONLY (3 yeni + 1 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/rationale-families` gerçek sayfa oldu —
`routes/rationale.py` TAM yüzeyi (doc 10 §7/§8) bağlandı: paylaşılan taksonomi düzlemi, İKİ tablo.
Önceki salt-okuma dilimlerinin AKSİNE bu TAM CRUD + editör dilimi — çünkü backend **shared-editing**
(Guest hariç herkes düzenler; `ensure_can_manage_families`/`ensure_can_edit_assignments`, Admin-only
DEĞİL) ve salt-okuma `useRationaleFamilies` seçici zaten vardı (salt-okuma tekrarı düşük değerdi).
Kalan placeholder'ların ÜÇÜNCÜSÜ indi — **9 kaldı**. Frontend 121 → **128** (+7 vitest).
main = `7372478` (Merge #101), feat `20ccacc`. CI 3/3 yeşil; self-review + yerel döngü (0 CRITICAL/HIGH).

**Reuse anchor'ları (kesin semboller):**
- **YENİ `frontend/src/lib/rationale.ts`:** wire tipleri `application/queries/rationale.py`
  `_family_dict`/`_assignment_row` + `application/commands/rationale.py` return dict'leri birebir
  aynası (`RationaleFamilyCard`/`RationaleAssignmentRow` + `CreateFamilyResult`/`ReviseFamilyResult`/
  `SoftDeleteFamilyResult`/`BatchAssignResult`). Hook'lar `resource.changed` süpüren prefix'ler
  altında (özel rationale SSE event YOK): `useFamilies` (aktif registry projeksiyonu, keyset cursor,
  placeholderData) + `useAssignments` (`meta.table_version` = batch OCC token'ı). 4 mutasyon
  `lib/trash.ts`/`lib/adminPanel.ts` aynası: `useCreateFamily` (taze `Idempotency-Key`, **OCC token
  YOK** — create'in head'i yok), `useReviseFamily` (OCC `expected_head_revision_id` = ailenin current
  head'i, command'ın token'ı doc 10 §5 + `Idempotency-Key`), `useSoftDeleteFamily` (OCC `row_version`
  → **`"rv-N"` If-Match ETag**, `shared/concurrency.py row_version_from_if_match`), `useBatchAssign`
  (`expected_table_version` echo; sunucu-tarafı all-or-nothing + `Idempotency-Key`). Aile
  mutasyonları `["rationale-families"]`+`["rationale-assignments"]`+`["audit"]` invalidate eder;
  batch aynı seti. `assignmentStateTone` doc 10 §9.2 projeksiyonunu eşler (assigned→ok /
  unassigned→neutral / assigned_to_deleted_family→down).
- **YENİ `pages/RationaleFamilies.tsx`:** `FamilyRegistryCard` — tek editör create eder ya da bir
  satırın Edit'i onu beslerse revise eder (`key` ile remount → mod değişince yeniden beslenir;
  subfamilies/compatible-outputs satır-başına textarea → trim'li liste); iki-adım onaylı Delete;
  sunucu zarfı her hatada verbatim (`RATIONALE_FAMILY_CONFLICT`/`RATIONALE_FAMILY_IN_USE`/
  `NAME_CONFLICT`/`NAME_RESERVED`). `AssignmentTableCard` — satır-başına aile `select`'i (ilk aktif-
  aile sayfasından hidre); staged reatamalar server-truth'a karşı diff'lenir (yalnız değişen satırlar
  batch'e girer); Save değişen her satır için bir `AssignmentChange` kurar (`current_package_revision_id`
  head OCC + seçilen ailenin `current_revision_id`'si pinlenir); non-blocking `OUTPUT_TYPE_NOT_LISTED`
  uyarıları verbatim; soft-deleted pinli aile synthetic `select` option olarak görünür (değer
  option'ların dışına asla düşmez).
- **`App.tsx`:** `/rationale-families` REAL_PATHS (14 → 15) + gerçek Route; **`nav.ts` DEĞİŞMEDİ**
  (24 — item zaten placeholder olarak vardı).
- **Testler:** YENİ `test/rationaleFamilies.test.tsx` (+7; apiStub SIRALI — revise/delete/batch
  aksiyon fragment'ları liste prefix'lerinden ÖNCE; "Momentum" ready-check DEĞİL — registry satırı +
  assignment hücresi + HER select option'da geçer → "trend" (fam_1 benzersiz subfamily) kullanıldı,
  aile-adı assert'leri `within` ile registry tablosuna scope'lu).

**Dürüst sınır:** assignment `select` yalnız İLK aktif-aile sayfasını okur (doc 10 §7 UI kapsam —
>20 aile option setini kısaltır); soft-deleted aileler Admin-only Trash yüzeyinde (restore/purge
burada dispatch edilmez); özel rationale SSE event YOK (`resource.changed` süpürür).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan 9 placeholder sayfa — HEPSİNİN V1
backend yüzeyi landed: Packages & Data (`market_data.py` Market Data / `research_data.py` Research
Data), Workspace (`strategy.py` Strategy Details / `trading_signal.py` / `trade_log.py` /
outsource-signal), Backtest (`allocation.py` Portfolio / `readiness.py` Ready Check), Docs
(`manual.py` User Manual). TIER 3 deferred: retention auto-purge, data-queue redelivery, SSE
streaming e2e, tool-call status shadowing. Trash purge (destructive + re-auth) AYRI slice; ESP +
Library registry MUTASYONLARI (create/activate/deprecate, Admin-only, `X-Registry-Version` OCC)
AYRI mutasyon slice'ları — OCC token'ları detaylarda hazır.

## Durum (2026-07-09, TIER 2 frontend — Embedded System Packages sayfası; PR #99 MERGED)

**FRONTEND-ONLY (3 yeni + 1 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. Kalan placeholder'ların İKİNCİSİ indi:
`/packages/embedded` gerçek sayfa oldu — `routes/esp.py` doc 09 OKUMA yüzeyi bağlandı (role-aware
resolver-registry listesi + detay + Pre-Check-parity resolve probe). Frontend 113 → **121**
(+8 vitest). main = `fa2003f` (Merge #99), feat `5bf633a`. CI 3/3 yeşil; self-review + yerel
döngü (0 CRITICAL/HIGH).

**Reuse anchor'ları (kesin semboller):**
- **YENİ `frontend/src/lib/esp.ts`:** wire tipleri `application/queries/esp.py` birebir aynası —
  `EspRegistryRow` (`_registry_dict`) / `EspPackageDetail` (`get_esp_detail`) / `EspContract`
  (`_contract_dict`) / `ResolveResult` (`resolve_embedded_dependency`); taksonomi hidrasyon
  aynaları `RESOLVER_TRUST_STATES` (candidate/trusted_active/deprecated/unavailable) +
  `RUNTIME_ADAPTERS` (pine_v5/python) — sunucu her değeri yeniden doğrular; L4
  `ESP_PERFORMANCE_FIELDS` (net_profit/backtest_ready/oos_passed — doğası gereği N/A, doc 09
  §14, asla uydurma değer). Hook'lar `["esp"]` altında (özel SSE event yok — `resource.changed`
  süpürür): `useEspRegistry` (trust_state facet'i — boş facet ASLA gönderilmez; canonical_key
  keyset cursor; placeholderData) + `useEspPackage` (enabled-gated, `encodeURIComponent`) +
  `useResolveProbe` — doc 09 §4.3 probe SALT-OKUMA (hiçbir şey yaratmaz, audit satırı yazmaz)
  → POST'ta **Idempotency-Key YOK, invalidation YOK** (POST yalnız transport — PR #80 compare
  deseni). `parseSignatureParams` (satır-başına "name:type" → sıralı `{name?, type}`) +
  `trustTone`.
- **YENİ `pages/Embedded.tsx`:** registry tablosu (canonical_key / trust badge / adapter /
  registry_version / trusted revision) + trust facet + cursor-stack `Pager`; detay kartı
  (contract signature + warm-up/timing/repaint verbatim, registry snapshot — OCC-hazır
  `registry_version`, lifecycle/validation/approval badge'leri, **L4 N/A label'ları verbatim**);
  Resolve Probe kartı — sıralı param TİPLERİ kimliktir (isimler görüntü); başarı EXACT pinned
  revision (P4/L5 — asla latest); typed hatalar (`RESOLVER_NOT_RESOLVED` 404 /
  `RESOLVER_SIGNATURE_MISMATCH` 422 / `RESOLVER_ADAPTER_INCOMPATIBLE` 409) verbatim
  (doc 09 §9.1–§9.3).
- **`App.tsx`:** `/packages/embedded` REAL_PATHS (13 → 14) + gerçek Route; **`nav.ts` DEĞİŞMEDİ**
  (24).
- **Testler:** YENİ `test/embedded.test.tsx` (+8: 1 `parseSignatureParams` unit + 7 component;
  apiStub SIRALI — resolve POST + detay GET fragment'ları `/embedded-system-packages` liste
  prefix'inden ÖNCE; trust assert'leri tabloya scope'lu).

**Dürüst sınır:** okuma dilimi — registry MUTASYONLARI (create / activate / deprecate —
Admin-only sunucu-tarafı, `X-Registry-Version` OCC header + Idempotency-Key) bu sayfadan
dispatch edilmez (sonraki slice'lar; detaydaki `row_version`/`registry_version` OCC token'ları
hazır); ESP performansı doğası gereği `not_applicable` kalır (doc 09 §14, L4).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan 10 placeholder sayfa —
HEPSİNİN V1 backend yüzeyi landed: Packages & Data (`rationale.py` Rationale Families — doğal
sıradaki: paylaşılan `useRationaleFamilies` hook'u zaten var / `market_data.py` /
`research_data.py`), Workspace (`strategy.py` Strategy Details / `trading_signal.py` /
`trade_log.py` / outsource-signal), Backtest (`allocation.py` Portfolio / `readiness.py` Ready
Check), Docs (`manual.py` User Manual). TIER 3 deferred: retention auto-purge, data-queue
redelivery, SSE streaming e2e, tool-call status shadowing. Trash purge (destructive + re-auth)
AYRI slice.

## Durum (2026-07-09, TIER 2 frontend — Package Library katalog sayfası; PR #97 MERGED)

**FRONTEND-ONLY (3 yeni + 1 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. Kalan 12 placeholder'ın İLKİ indi:
`/packages/library` gerçek sayfa oldu — `routes/library.py` TAM okuma yüzeyi (iki GET) frontend'e
bağlandı. Frontend 105 → **113** (+8 vitest). main = `af7c66b` (Merge #97), feat `53394fe`.
CI 3/3 yeşil; self-review + yerel döngü (0 CRITICAL/HIGH).

**Reuse anchor'ları (kesin semboller):**
- **YENİ `frontend/src/lib/library.ts`:** wire tipleri `application/queries/library.py` birebir
  aynası — `LibraryPackageRow`/`LibraryPage`/`LibraryPackageDetail` (canlı rationale-family
  çözümü `{id, name, pinned_name, family_active}`, Stage-2e `provenance` + immutable scan
  özeti, `revisions` geçmişi, 10-flag `PackagePermissions` backend dataclass sırasında +
  `PERMISSION_FLAGS`/`PERFORMANCE_FIELDS` render-sırası aynaları); facet taksonomi hidrasyon
  aynaları (`CATALOG_PACKAGE_KINDS`/`CATALOG_LIFECYCLE_STATES`/`PACKAGE_VALIDATION_STATES`/
  `APPROVAL_STATES`/`VISIBILITY_SCOPES` + `UNASSIGNED_FAMILY` sentineli) — sunucu her filtreyi
  yeniden doğrular (`CatalogFilterInvalid` 422 verbatim); hook'lar `["library"]` altında (özel
  SSE event yok — `resource.changed` süpürür): `useLibraryPackages` (kind facet'i `type` route
  ALIAS'ı ile gider; boş facet ASLA gönderilmez; keyset cursor; placeholderData) +
  `useLibraryPackage` (enabled-gated, `encodeURIComponent`); SALT-OKUNUR — mutation/OCC token
  YOK; `validationTone`/`approvalTone`/`lifecycleTone` sunum yardımcıları.
- **YENİ `pages/Library.tsx`:** 5 taksonomi select'i + paylaşılan `useRationaleFamilies` ile
  hidre edilen family select (`unassigned` sentineli dahil) + serbest-metin `q`; ortogonal
  lifecycle/validation/approval badge'li katalog tablosu (doc 08 §13 — V18 Status tek kolona
  ASLA katlanmaz); cursor-stack `Pager`; detay kartı: 10 permission flag'i METİN olarak (asla
  yalnız renk), **L4 performance availability label'ları verbatim (asla uydurma sıfır)**,
  contract/dependency-snapshot/validation-summary JSON, provenance + scan özeti, revizyon
  geçmişi; Guest → 401 zarfı verbatim (doc 08 §2 — UI görünürlüğü asla yetkilendirme değildir).
- **`App.tsx`:** `/packages/library` REAL_PATHS (12 → 13) + gerçek Route; **`nav.ts` DEĞİŞMEDİ**
  (24 — nav item placeholder olarak zaten vardı).
- **Testler:** YENİ `test/library.test.tsx` (+8; apiStub SIRALI — detay fragment'i `/library`
  liste prefix'inden ÖNCE; facet assert'leri tabloya scope'lu — select option'ları aynı
  değerleri listeler).

**Dürüst sınır:** salt-okunur katalog dilimi — paket AKSİYONLARI (revise / request-validation /
approve-publish / deprecate / soft-delete / export) sunucu-hesaplı permission flag'leriyle
AÇIKLANIR ama bu sayfadan dispatch edilmez (sonraki slice'lar; detay ETag/`row_version` OCC
token'ları için hazır); performance metrikleri run bağlanana dek sunucu sözleşmesiyle
`not_applicable` (doc 08 §3.2, L4).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan 11 placeholder sayfa —
HEPSİNİN V1 backend yüzeyi landed: Packages & Data (`esp.py` Embedded — Library deseninin
doğal devamı / `rationale.py` Rationale Families / `market_data.py` / `research_data.py`),
Workspace (`strategy.py` Strategy Details / `trading_signal.py` / `trade_log.py` /
outsource-signal), Backtest (`allocation.py` Portfolio / `readiness.py` Ready Check), Docs
(`manual.py` User Manual). TIER 3 deferred: retention auto-purge, data-queue redelivery, SSE
streaming e2e, tool-call status shadowing. Trash purge (destructive + re-auth) AYRI slice.

## Durum (2026-07-09, TIER 2 frontend — gated capability operasyonel POST'ları; PR #95 MERGED)

**FRONTEND-ONLY (4 edit, yeni dosya yok)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK,
alembic head `0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. PR #82'nin dürüst sınırı kapandı:
iki gated operasyonel POST (`POST /view-datasets/query` + `POST /analysis-artifacts`) frontend'e
bağlandı — `routes/capability.py` TAM yüzeyi artık tüketiliyor, capability'de bağlanmamış
endpoint KALMADI. Frontend 98 → **105** (+7 vitest). main = `5225629` (Merge #95), feat
`652dfde`. CI 3/3 yeşil; self-review + yerel döngü (0 CRITICAL/HIGH).

**Reuse anchor'ları (kesin semboller):**
- **`frontend/src/lib/capability.ts` (YERİNDE GENİŞLETİLDİ):** `ANALYSIS_ARTIFACT_CAPABILITY` —
  `commands/capability.py` aynası (doc 22 §10.3–§10.6; yalnız hidrasyon — sunucu gate'i her
  dispatch'te `artifact_type`'tan yeniden türetir) + `ANALYSIS_ARTIFACT_TYPES` (sunucunun sorted
  `allowed` sırası); wire tipleri `ViewDatasetResult`/`AnalysisArtifactResult` komut dönüşlerinin
  birebir aynası; `useQueryViewDataset`/`useCreateAnalysisArtifact` — **her denemede taze
  `Idempotency-Key`, OCC token YOK** (create'in yarışacağı head yok); boş opsiyonel alanlar
  gövdeye HİÇ girmez; başarı yalnız `["audit"]` invalidate eder (iki entity'nin de READ yüzeyi
  yok — sonuç komut dönüşü + audit izinde yaşar).
- **`pages/FutureDev.tsx`:** `ViewDatasetComposer` Graphic View kartının içinde (source manifest
  refs satır-başına + schema version + opsiyonel series/marker refs; `parseRefLines` CreatePackage
  declared-keys deseninin aynası) + YENİ `AnalysisArtifactsCard` (tip seçici + salt-görüntü gating
  capability aynası + input refs + method version + opsiyonel output ref). Composer'lar ASLA
  client-tarafı ön-gate'lenmez (UI görünürlüğü asla yetkilendirme değildir, doc 22 §3): sunucu her
  dispatch'te Limited/Active'i yeniden kontrol eder, `CAPABILITY_NOT_ACTIVE` verbatim render
  edilir (CR-09/FD-02) — sahte iş/ilerleme yok.
- **Testler:** +5 `futureDev.test.tsx` (body + Idempotency-Key + boş-opsiyonel omit / submit
  gating / CAPABILITY_NOT_ACTIVE verbatim + retry'da FARKLI taze key / gating görüntü scoping /
  artifact POST + created id) + 2 `capabilityLib.test.ts` ayna birimi. **`App.tsx`/`nav.ts`
  DEĞİŞMEDİ** (REAL_PATHS 12 — `/future-dev` zaten gerçekti).

**Dürüst sınır:** `range_spec` composer girdisi yok (V1'de tüketen renderer yok — wire tipi
taşır); üretilen view dataset / analysis artifact'ların LİSTE/READ yüzeyi YOK (backend
projeksiyonu gelene dek kalıcı — audit satırları Panel → Logs'ta görünür); capability'nin özel
SSE event'i yok (`resource.changed` süpürür).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):** kalan 12 placeholder sayfa —
HEPSİNİN V1 backend yüzeyi landed: Packages & Data (`library.py` Package Library — doğal ilk
aday / `esp.py` Embedded / `rationale.py` Rationale Families / `market_data.py` /
`research_data.py`), Workspace (`strategy.py` Strategy Details / `trading_signal.py` /
`trade_log.py` / outsource-signal), Backtest (`allocation.py` Portfolio / `readiness.py` Ready
Check), Docs (`manual.py` User Manual). TIER 3 deferred: retention auto-purge, data-queue
redelivery, SSE streaming e2e, tool-call status shadowing. Trash purge (destructive + re-auth)
AYRI slice.

## Durum (2026-07-08, TIER 2 frontend — CP request aksiyonları + Pre-Check sayfası; PR #93 MERGED)

**FRONTEND-ONLY (2 yeni + 4 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. PR #91'in dürüst sınırı kapandı: request detayı
lifecycle AKSİYONLARINI aldı (doc 06 §7, doc 07 §8) ve `/packages/pre-check` placeholder'ı gerçek
sayfa oldu (doc 07). Frontend 89 → **98** (+9 vitest). main = `5b59884` (Merge #93), feat
`e8f8982`. CI 3/3 yeşil; review self-review + yerel döngü (0 CRITICAL/HIGH).

**Reuse anchor'ları (kesin semboller):**
- **`frontend/src/lib/createPackage.ts` (YERİNDE GENİŞLETİLDİ, yeni lib dosyası yok):** aksiyon
  wire tipleri komut dönüşlerinin aynası (`PrecheckActionResult`/`CandidateActionResult`/
  `DraftActionResult`/`ApproveActionResult`) + `DependencyScanDetail`
  (`queries::get_dependency_scan`) + `ResolvedRef`/`MissingCall` (`_resolve_declared`);
  `useRunPrecheck`/`useGenerateCandidate` — request `row_version` **`X-Request-Version` OCC
  header** + her denemede **taze `Idempotency-Key`** (private `postWithRequestVersion` —
  agentLab `postWithIfMatch` aynası); `useCreateDraft` — **`expected_candidate_hash` BODY
  token** (kabul edilen generate sonucundan; CANDIDATE'la yarışır, request head'le değil);
  `useApproveRequest` — **`expected_head_revision_id` = draft head** + opsiyonel not,
  **Admin-only SUNUCU-tarafı (CR-02)** — UI rol-gate'lemez, 403 verbatim. Tüm aksiyonlar
  `["package-requests"]` + `["audit"]` invalidate; `useDependencyScan` immutable artifact
  (5m staleTime, `["package-requests"]` prefix'i altında); `scanStatusTone` + `asRecordArray`.
- **`pages/CreatePackage.tsx`:** detay kartında `RequestActions` barı — gating YALNIZ sunucu
  ipuçları (`can_generate_candidate`, `candidate_ready`, draft varlığı); kabul edilen candidate
  hash kart state'inde draft token'ı olarak yaşar; sonuç/red satırları verbatim.
- **YENİ `pages/PreCheck.tsx`** (`/packages/pre-check`): own-requests picker (keyset `Pager`) →
  scan çalıştır (`Checking dependencies…`) → §7.1 dependency result satırları (metinli
  **Resolved/Missing**, asla yalnız renk; tüm değerler text node) → §7.2 kanonik durum satırları
  + stale uyarısı → immutable scan artifact viewer (`GET /dependency-scans/{scan_id}`).
- **`App.tsx`:** `/packages/pre-check` REAL_PATHS (11→12) + Route; **`nav.ts` DEĞİŞMEDİ** (24).
- **Testler:** +4 `createPackage.test.tsx` (OCC header + taze key / sunucu-hint gating / draft
  hash token / approve head token + Admin reddi verbatim) + YENİ `test/preCheck.test.tsx` (+5) —
  apiStub SIRALI (aksiyon POST + detay GET fragment'ları `/create-package/requests` liste
  prefix'inden ÖNCE).

**Dürüst sınır:** `compatible_rationale_family_ids`/`linked_indicator` composer alanları hâlâ
ertelenmiş; draft staleness token'ı yalnız Generate'i çalıştıran kartta yaşar (projeksiyon
`candidate_hash` taşımaz — reload sonrası yalnız sunucu state kontrolü korur); approve
sunucu-tarafı yalnız `draft_created`/`eligible_for_approval` kenarlarını hedefler; CP'nin özel
SSE event'i yok (`resource.changed` süpürür); `["jobs"]` backend liste yüzeyi YOK (kalıcı).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):**
- **Capability aktivasyonları** (EN DOĞAL SONRAKİ) — Future Dev slotlarını placeholder'dan çıkar
  (`graphic_view` ilk aday; `routes/capability.py` + `lib/capability.ts` hazır — PR #82; gated
  operasyonel POST'lar `/view-datasets/query` + `/analysis-artifacts` hâlâ bağlanmadı).
- **TIER 3 deferred:** retention auto-purge, data-queue redelivery, SSE streaming e2e, tool-call
  status shadowing. Trash purge (destructive + re-auth) AYRI slice.

## Durum (2026-07-08, TIER 2 frontend — Create Package request sayfası; PR #91 MERGED)

**FRONTEND-ONLY (3 yeni + 2 edit)** — backend DEĞİŞMEDİ (1048 sabit), migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT. `/packages/create` placeholder'ı gerçek sayfa oldu:
`routes/create_package.py` yüzeyine bağlı (doc 06 §4/§5/§9). Bu dilim yalnız request **LIFECYCLE
ENTRY** — compose + own-requests listesi + salt-okunur detay projeksiyonu. Pre-Check /
generate-candidate / draft / approve AKSİYONLARI doğal sonraki dilim (detay onların salt-okunur
ipuçlarını zaten gösteriyor: `current_scan` / `precheck_fresh` / `can_generate_candidate`).
Frontend 82 → **89** (+7 vitest). main = `bda3a7f` (Merge #91), feat `79fbd24`. CI 3/3 yeşil;
review yok (self-review + yerel döngü).

**Reuse anchor'ları (kesin semboller):**
- **`frontend/src/lib/createPackage.ts`** — wire tipleri `queries/create_package.py`
  projeksiyonlarının aynası (`PackageRequestSummary`/`PackageRequestDetail`/`ScanSummary`/
  `CreateRequestResult`); enum aynaları `domain/create_package/enums.py`'den
  (`CreatePackageKind`/`CreationMode`/`SourceKind`/`SourceLanguage`); `OUTPUT_KINDS_BY_KIND`
  (`value_objects._OUTPUT_KINDS_BY_KIND` aynası — yalnız hidrasyon, sunucu her alanı yeniden
  doğrular); `sourceKindForMode` (`_CODE_MODES` aynası); `requestStateTone` (17-durumlu
  `CreatePackageState` üstünde salt-sunum rozet tonu). Hook'lar **`["package-requests"]`** altında
  (özel SSE event YOK → `resource.changed` süpürür): `usePackageRequests` (keyset cursor,
  `placeholderData`) + `usePackageRequest` (enabled-gated) + `useRationaleFamilies` (paylaşımlı
  `["rationale-families"]`, 5m staleTime). `useCreatePackageRequest` — her submit'te **taze
  `Idempotency-Key`** (OCC token YOK — create'in yarışacağı head yok), `["package-requests"]`
  invalidate.
- **`frontend/src/pages/CreatePackage.tsx`** — `CreateForm` (doc 06 §4: `source_language` yalnız
  code modlarında, `other` → label zorunlu; output kind package type'a scoped + type değişince
  RESET; rationale family Indicator/Condition için ZORUNLU + sunucudan hidrasyon, ESP'de N/A;
  declared canonical keys satır-başına → `[{key}]`; `target_runtime` sabit `python`);
  `RequestsCard` (keyset `Pager`); `RequestDetailCard`. Komut hataları kanonik `ApiError` VERBATIM.
- **`App.tsx`** — `/packages/create` REAL_PATHS + Route; **`nav.ts` DEĞİŞMEDİ** (24 item).
  **`global.css`** — `.cp-*` form grid'i.
- **Testler** — YENİ `test/createPackage.test.tsx` (+7; apiStub SIRALI — `req_new`/`req_1` detay
  route'ları `/create-package/requests` liste prefix'inden ÖNCE; create başarısı detayı otomatik
  açar → `req_new` detay stub'ı ŞART): liste+rozet / composed body+Idempotency-Key / description →
  `source_language: null` / output kind type-scoped / detay+scan ipuçları / `["package-requests"]`
  invalidation refetch / 403 verbatim.

**Dürüst sınır:** `target_runtime` `python` sabit (`SUPPORTED_TARGET_RUNTIMES`; `pine_v5`
sunucu-reddi `RuntimeUnavailable`); Pre-Check/candidate/draft/approve AKSİYONLARI +
`compatible_rationale_family_ids`/`linked_indicator` composer alanları sonraki dilime ertelendi;
Pre-Check SAYFASI (`/packages/pre-check`, doc 07) hâlâ placeholder; CP request'lerin özel SSE
event'i yok; `["jobs"]` backend liste yüzeyi YOK (kalıcı).

**SIRADAKİ İŞ ADAYLARI (BAŞLARKEN kullanıcıyla TEYİT ET):**
- **CP request AKSİYONLARI + Pre-Check sayfası** (EN DOĞAL SONRAKİ) — request detayına
  pre-check / generate-candidate / draft / approve butonları (OCC `X-Request-Version` header +
  taze Idempotency-Key; approve Admin-only CR-02 → 403 verbatim) + `/packages/pre-check` sayfası
  (doc 07 — scan çalıştır + dependency result satırları + `GET /dependency-scans/{scan_id}`
  viewer). REUSE: `lib/createPackage.ts` tipleri/hook'ları GENİŞLET (yeni dosya açma),
  `postWithIfMatch` benzeri header deseni `lib/agentLab.ts`'de.
- **Capability aktivasyonları** — `graphic_view` ilk aday (`routes/capability.py` +
  `lib/capability.ts` hazır — PR #82).
- **TIER 3 deferred:** retention auto-purge, data-queue redelivery, SSE streaming e2e, tool-call
  status shadowing. Trash purge (destructive + re-auth) AYRI slice.

## Durum (2026-07-08, CP-Gen — deterministic candidate generation; PR #89 MERGED)

**BACKEND-ONLY** (1 yeni + 1 edit + 1 test; migration YOK, alembic head `0021_local_auth` SABİT,
`ENGINE_VERSION` DEĞİŞMEDİ — CP-Gen engine'e dokunmaz). `submit_candidate_generation`'ın V1 stub
*compute*'u → DETERMINISTIK candidate-manifest hattı (doc 06 §5). **LLM YOK** — gerçek generator
Future-Dev. Backend 1036 → **1048** (+12 unit test); frontend 80 (DEĞİŞMEDİ). main = `ba533e5`
(Merge #89), feat `5cc62cc`.

- **YENİ `domain/create_package/candidate.py` (pure, I/O YOK):** `GENERATOR_VERSION =
  "cp-candidate-gen-v1"` (ENGINE_VERSION analojisi — bump `candidate_hash` namespace'ini kaydırır,
  eski generator'ın candidate'ı sessizce yeniden kullanılmaz; INF-04/INF-05). Frozen
  `CandidateManifest` (`generator_version`/`package_kind`/`source_kind`/`signal_kind`/
  `output_contract`/`resolved_dependencies`/`test_plan`/`uncertainty`) + `build_candidate_manifest(*,
  package_kind, source_kind, output_contract, resolved_refs)` → reproducible manifest;
  `candidate_hash = "sha256:" + content_hash(manifest.as_dict())` (`domain/revision/hashing`).
  `_summarize_resolved` `canonical_key`'e göre sıralar → **order-independent** hash. Fail-closed
  `_output_kind` (`kind`|`output_type` yoksa `OutputContractInvalid`) +
  `_validate_contract_against_deps` (`directional_signal`→≥1 `ta.*`; `boolean_condition`→≥1 `cond.*`;
  resolved BOŞ ise skip — description / dep-less deferred). **Katman-temiz:** `ta.`/`cond.`
  PREFIX'iyle bakar, backtest indicator taksonomisini IMPORT ETMEZ.
- **`commands/create_package.py::submit_candidate_generation`:** stub 4 satır → manifest compute;
  `candidate_hash` artık manifest'in GERÇEK content-hash'i; `candidate_output_contract =
  manifest.output_contract`. YENİ `_candidate_resolved_refs(session, detail)` (description→`[]`,
  code→current PASSED `scan.resolved_refs` — PC-13 gate zaten `_enforce_precheck_gate`'te koştu, scan
  taze). Dönüş anahtarları DEĞİŞMEDİ (`{request_id, state, candidate_hash, job_id}`); audit/outbox
  `candidate_generation_started`/`_completed`, `run_idempotent`, `session.refresh(with_for_update)`,
  state machine, durable job row hepsi aynı.
- **DEĞİŞMEDİ (zaten gerçek, DOKUNMA):** Pre-Check resolver (`_resolve_declared` → ESP registry pin),
  `DependencyScan` immutable evidence, PC-13 gate (`_enforce_precheck_gate`), job durability, state
  machine, `_draft_dependency_snapshot` (`dependency_snapshot` Pre-Check scan'den — Slice C KAYNAĞI),
  backtest engine + `resolve_indicator_plan`.
- **DÜRÜST SINIR (KALICI):** LLM generation Future-Dev (spec bile erteliyor); üretilen artifact
  backtest engine'de EXECUTE EDİLMEZ (engine `dependency_snapshot` pinlerinden native compute eder —
  ESP `_MovingAverage`/`_Rsi`/`_Vwap`…); üretilen kodu çalıştıran executor AYRI mega iş; async
  dramatiq worker'a taşınmadı (deterministik in-tx yeterli; job row yine durable); CP/Pre-Check
  FRONTEND sayfaları hâlâ placeholder (doğal sonraki dilim); `["jobs"]` backend liste yüzeyi YOK.

**SIRADAKİ İŞ ADAYLARI (kapanıştan sonra; BAŞLARKEN kullanıcıyla TEYİT ET):**
- **CP / Pre-Check frontend sayfaları** — Create Package (doc 06) + Pre-Check (doc 07) placeholder'ları
  canlı veriye bağla (`routes/create_package.py` yüzeyi + candidate/precheck akışı; `lib/*.ts` +
  `apiStub` + `Panel.tsx` kart deseni reuse). Frontend-only muhtemel; en doğal görünür sonraki dilim.
- **Capability aktivasyonları** — Future Dev slotlarını placeholder'dan çıkar (`graphic_view` ilk aday;
  `routes/capability.py` + `lib/capability.ts` hazır — PR #82).
- **TIER 3 deferred:** retention auto-purge, data-queue redelivery, SSE streaming e2e, tool-call status
  shadowing. Trash purge (destructive + `confirmation_phrase`/re-auth) AYRI re-auth slice'ı.

## Durum (2026-07-07, TIER 2 frontend — Admin Trash restore page; PR #86 MERGED)

> **Onuncu TIER 2 slice — frontend Admin Trash restore sayfası landed (PR #86, merged → main
> `09f4130`; CI yeşil; review 0 CRITICAL/HIGH).** `/trash` placeholder'ı gerçek sayfa oldu:
> backend Stage 6c restore yüzeyini (`application/queries/trash.py` + `application/commands/deletion.py`
> restore, `apps/api/routes/trash.py` ile expose; doc 20 §7) bağlar. **FRONTEND-ONLY (2 yeni + 2 edit
> + 1 test) — backend değişmedi, migration YOK, alembic head `0021_local_auth` SABİT, `ENGINE_VERSION`
> değişmedi, backend test tabanı 1036 SABİT.** Frontend 73→80.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/trash.ts`** — wire tipleri backend projeksiyonlarının aynası
>   (`TrashEntry`/`TrashEntriesPage` — `meta.recoverable_total` + `meta.object_types` — /
>   `TrashEntryDetail` — deletion+dependency snapshot, tombstone — /`RestoreResult`). Read hook'lar
>   `["trash"]` altında (**özel SSE event YOK** — restore bir entity lifecycle'ını değiştirir →
>   `resource.changed` full refresh + `audit.event.created` → `["audit"]`): `useTrashEntries(filters,
>   cursor)` (q/object_type filtre, forward-only keyset cursor, `placeholderData` sayfa flip'inde
>   tabloyu mount tutar) + `useTrashEntry(id)` (seçili id'ye enabled-gated). Restore mutation
>   `useRestoreEntry` → `POST /trash-entries/{id}/restore`; **OCC `expected_head_revision_id =
>   entry.row_version`** (bayat tab 409 verbatim) + **her denemede taze `Idempotency-Key` UUID**
>   (reddedilen bir denemeden sonra retry yeni KARAR, replay değil — doc 20 §14; body token If-Match'i
>   yener), başarıda `["trash"]`+`["audit"]` invalidate — birebir `lib/adminPanel.ts` `useAssignRole`
>   deseni. `purgeStatusTone` rozet-tonu helper'ı.
> - **`frontend/src/pages/Trash.tsx`** — `TrashCard`: object_type filtre select'i SUNUCU yanıtından
>   hidrasyon (`meta.object_types`), ASLA hard-code liste değil; q arama; keyset `Pager`
>   (`useCursorStack`); recoverable index tablosu + sunucu `recoverable_total`. **Restore YALNIZ
>   sunucu-truth `restore_eligible` satırlarda** (purge-pending satır "not restorable"); komut hatası
>   backend kanonik `ApiError`'ı VERBATIM gösterir (`mutationErrorText`; Panel/AnalysisLab aynası).
>   `TrashRow` + `TrashDetail` (immutable deletion+dependency snapshot, purge/restore kontrol durumu,
>   tombstone; `snapshotStyle` inline `pre` wrap+scroll — geniş JSON sayfayı genişletmez).
> - **`App.tsx`** — `/trash` REAL_PATHS + gerçek `Route`. **`nav.ts` DEĞİŞMEDİ** — `/trash` `adminOnly`
>   item zaten placeholder olarak vardı; sayfa arkasında canlandı.
> - **Testler** — YENİ `test/trash.test.tsx` (7; apiStub SIRALI — restore+detay route'ları
>   `/trash-entries` liste prefix'inden ÖNCE): index+recoverable total / restore_eligible gating /
>   OCC+Idempotency-Key restore / object_type query param / snapshot detay / `["trash"]` invalidation
>   refetch / 403 verbatim → **frontend 80/80**; typecheck+lint temiz; build yeşil.
> **Dürüst sınır (KALICI):** Trash **purge** (destructive — `confirmation_phrase` / re-auth proof
> gerekir) bu restore-odaklı slice'ta KAPSAM DIŞI — ayrı bir re-auth slice'ı gerektirir. Trash
> **Admin-only sunucu-tarafı** (`require_trash_admin`) — Admin olmayan 403 envelope'unu verbatim görür
> (gizli nav item asla yetkilendirme değil, doc 20 §2). `["jobs"]` için hâlâ backend liste yüzeyi YOK.
> **Sıradaki doğal slice:** (d) CP real candidate generation VEYA (opsiyonel küçük) signup başarısında
> `["auth"]` invalidate (lib/auth.ts useSignup — #84 provisioning'in doğal follow-up'ı). Aşağıdaki
> PR #84 bloğu ve öncesi tarihsel.

## Durum (2026-07-07, first-Admin provisioning dashboard + bootstrap-status endpoint — TIER 2 slice 9; PR #84 MERGED)

> **Dokuzuncu TIER 2 slice — first-Admin provisioning DASHBOARD'u + `GET /auth/bootstrap-status`
> landed (PR #84, merged → main `f7bf4a7`; CI 3/3 yeşil — Backend 13m3s / Frontend 30s / Docker
> 34s; bloklayıcı review bulgusu yok).** PR #76'nın dürüst sınırını kapatır (backend bootstrap
> mekanizması landed'di, UI yoktu): first-Admin akışı önceden yalnız signup-yanıtındaki rolden
> gözlemlenebiliyordu; bu, eksik olan tek salt-okunur sinyali + bir onboarding sayfası ekler.
> **BACKEND (2 dosya + 2 test) + FRONTEND (2 yeni + 3 edit + 1 test). Migration YOK; alembic head
> `0021_local_auth` SABİT; `ENGINE_VERSION` değişmedi.** Backend testler 1028→1036; frontend 67→73.
> **Reuse anchor'ları (kesin semboller):**
> - **Backend `application/commands/auth.py`** — saf `bootstrap_is_configured(bootstrap_email)` +
>   salt-okunur async `bootstrap_status(session, *, bootstrap_admin_email) -> {bootstrap_configured,
>   active_admin_exists}` (`active_admin_exists = await identity_repo.count_active_admins(session) > 0`);
>   YALNIZ boolean — PII/email echo YOK; KARAR değil İPUCU (`sign_up` provisioning dalı hâlâ
>   advisory-lock korumalı — bu endpoint ASLA provision etmez). İkisi de `__all__`'a eklendi.
> - **Backend `apps/api/routes/auth.py`** — `GET /auth/bootstrap-status` →
>   `BootstrapStatusResponse(bootstrap_configured, active_admin_exists)`; ANONİM entry yüzeyi
>   (sign-up/login gibi — first Admin henüz authenticated değil); `settings.bootstrap_admin_email`
>   yalnız sunucu-tarafı geçirilir (yanıt şemasında email alanı YOK).
> - **Frontend `lib/provisioning.ts`** — `BootstrapStatus` + `useBootstrapStatus()` (react-query
>   `["auth"]` key; özel SSE event YOK → `resource.changed` süpürür).
> - **Frontend `pages/Provisioning.tsx`** — `BootstrapWindow` kartı (`windowGuidance(status)` →
>   açık/kapalı × configured rehberi), `GET /me` kimlik kartı (`useMe`, `lib/hooks`), salt-okunur
>   `BootstrapExplainer` (backend docstring aynası); Admin ise Panel link (rol yönetimini TEKRARLAMAZ).
> - **`nav.ts`** — YENİ `"Admin Provisioning"` `/panel/provisioning`, `adminOnly` DEĞİL
>   (elevation-öncesi erişilir) → `ALL_NAV_ITEMS` 23→24. **`App.tsx`** — `/panel/provisioning`
>   REAL_PATHS + route.
> - **Testler** — `tests/unit/test_bootstrap_status_unit.py` + `tests/integration/test_bootstrap_status.py`
>   (+8 → backend 1036) + `test/provisioning.test.tsx` (6) + `nav.test.tsx` 23→24 (+6 → frontend 73).
> **Dürüst sınır (KALICI):** provisioning sunucu-tarafı + signup-zamanı kalır (runtime provisioning
> API YOK) — bu sayfa yalnız OKUR/belgeler, ASLA provision etmez. `active_admin_exists` anonim
> expose kasıtlı (tek boolean deployment gerçeği, PII yok, first Admin henüz authenticated değil).
> Süregelen rol yönetimi Panel'de kalır.
> **Sıradaki doğal slice:** (d) CP real candidate generation VEYA (e) frontend Trash sayfası
> (restore UI — backend Stage 6c landed; şu an placeholder + adminOnly). Aşağıdaki PR #82 bloğu ve
> öncesi tarihsel.

## Durum (2026-07-06, TIER 2 frontend — Future Dev capability registry sayfası; PR #82 MERGED)

> **Sekizinci TIER 2 (frontend) slice — Future Dev capability registry sayfası landed
> (PR #82, merged → main `1411adc`; CI 3/3 yeşil; review 0 CRITICAL/HIGH — 3 MEDIUM/LOW
> self-review bulgusu commit içinde düzeltildi).** `/future-dev` placeholder'ı gerçek sayfa oldu:
> Stage 7b'de landed olan Capability Registry yüzeyi (`routes/capability.py`, doc 22) olduğu
> gibi render ediliyor + Admin-only lifecycle geçişi bağlandı. Registry, Future Dev'in ne
> yapabileceğinin SUNUCU tarafı doğruluk kaynağı (asla frontend feature flag değil — doc 22
> §2/§15). **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test tabanı 1028 sabit.**
> alembic head hâlâ `0021_local_auth`; backend `ENGINE_VERSION` hâlâ
> `backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/capability.ts`** — wire tipleri verbatim (`Capability`/`CapabilityDetail`
>   — `dependency_snapshot` + provenance dahil —/`GraphicViewOverview`/`CapabilityTransitionResult`);
>   doc-22 §9.1/§9.2 taksonomi AYNASI: `CAPABILITY_STATES` (7 durum), `ALLOWED_TRANSITIONS`
>   (yasal edge haritası; `allowedTargets()`), `ACTIVATION_GATES` (7 gate), `STATE_TONES` —
>   yalnız select/checklist hidrasyonu; sunucu her dispatch'te edge+gate+Admin'i yeniden doğrular.
>   `gateComplete` sunucunun `_gate_complete` okumasının birebir aynası; `buildGatesSnapshot`
>   Admin checklist'ini not objelerini ve kanonik olmayan anahtarları KORUYARAK merge eder.
>   Hook'lar `["capabilities"]` altında (özel SSE event YOK — `resource.changed` süpürür):
>   `useCapabilities` / `useCapability(key)` / `useGraphicViewOverview`; `useTransitionCapability`
>   — OCC `expected_registry_version` + mutate başına taze `Idempotency-Key` UUID (komut ZORUNLU
>   kılar), başarıda `["capabilities"]`+`["audit"]` invalidate.
> - **`frontend/src/pages/FutureDev.tsx`** — registry tablosu; detay kartı (gate checklist +
>   son geçiş provenance'ı); `TransitionComposer` — hedefler YALNIZ yasal doc-22 edge'leri,
>   reason ZORUNLU, dokunulmamış checklist `dependency_snapshot`'ı OMIT eder (sunucu kayıtlı gate
>   kaydını korur), hatalar envelope VERBATIM; mutation state KARTta yaşar (başarı mesajı
>   registry_version bump'ının tetiklediği composer remount'unu atlatır); Graphic View overview
>   salt-okunur (CR-09 — sahte operasyon/ilerleme yok).
> - **`App.tsx`** — `/future-dev` REAL_PATHS'te (7→8); `nav.ts` DEĞİŞMEDİ (23 item).
> - **Testler** — YENİ `test/futureDev.test.tsx` (7; apiStub SIRALI eşleşme — detay fragment'i
>   `/capabilities` liste prefix'inden ÖNCE) + `test/capabilityLib.test.ts` (2 gate-merge unit)
>   → **frontend 67/67**; typecheck + lint temiz; build yeşil.
> **Dürüst sınır:** gated operasyonel POST'lar (`/view-datasets/query`, `/analysis-artifacts`)
> BAĞLANMADI — V1 UI iş akışı yok; capability Limited/Active altındayken sunucu zaten
> `CAPABILITY_NOT_ACTIVE` döner (CR-09/FD-02). Composer görünürlüğü rol-gate'li değil (UI
> görünürlüğü asla yetkilendirme değildir — doc 22 §3); Admin olmayan deneme 403 envelope'unu
> verbatim görür.
> **Sıradaki doğal slice:** (c) first-Admin provisioning DASHBOARD'u (backend mekanizması PR
> #76'da — yalnız UI; Panel.tsx kart deseni taban) VEYA (d) CP real candidate generation VEYA
> (e) frontend Trash sayfası (restore UI). Aşağıdaki history compare (PR #80) bloğu ve öncesi
> tarihsel.

## Durum (2026-07-06, TIER 2 frontend — history compare/soft-delete + profil-hidrasyonlu Result metrics; PR #80 MERGED)

> **Yedinci TIER 2 (frontend) slice — history compare/soft-delete + ResultDetail rebind landed
> (PR #80, merged → main `8f57151`; CI 3/3 yeşil; review 0 CRITICAL/HIGH).** Landed-ama-tüketilmemiş
> SON iki backtest yüzeyi bağlandı: doc 16 §8.3 compare + §7 soft-delete (Results History) ve
> doc 17 §9.1 profil-hidrasyonlu `GET /backtest-results/{id}/metrics` (ResultDetail'in Metrics
> bölümü ham persisted satırlardan hydrated projeksiyona geçti). Backend yüzeyi Stage 5b/5c'den
> beri hazırdı. **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test tabanı 1028
> sabit.** alembic head hâlâ `0021_local_auth`; backend `ENGINE_VERSION` hâlâ
> `backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/backtest.ts`** — YENİ wire tipleri `CompareEntry`/`CompareField`/
>   `CompareResponse` (`context.fields{a,b,differs}` + `context_differs`) +
>   `ResultMetricsProfile`/`ResultMetricsView`; YENİ hook'lar: `useCompareResults(pair)` —
>   iki immutable sonuç üzerinde READ, POST yalnız id çiftinin taşıması
>   (`["backtests","compare",a,b]`, 5dk staleTime, seçim sırası korunur) —
>   `useResultMetrics(resultId)` — anahtar BİLEREK `["metric-profile","result-metrics",id]`,
>   `["backtests"]` DEĞİL: Result satırları immutable, tek mutable girdi resolved profil →
>   Arrange Metrics Apply (`["metric-profile"]` invalidate) bu görünümü süpürür; cross-tab
>   `resource.changed` full refresh ile gelir — ve `useSoftDeleteResult`
>   (`POST /backtest-results/{id}/delete`; OCC token YOK — history projeksiyonunda row_version
>   yok, komut idempotent + server-side owner/Admin-gated; `["backtests"]` invalidate →
>   deletion-filtered index satırı düşürür).
> - **`frontend/src/pages/ResultsHistory.tsx`** — seçim sırası korunan, ikiyle sınırlı compare
>   seçimi (checkbox server `allowed_actions.compare` ile kapılı); `ComparePanel` server context
>   diff'ini VERBATIM render eder (alan başına `differs` badge, object değerler JSON, warn banner
>   "informational only; neither result is ranked" — RH-09, asla winner seçilmez); iki-adımlı
>   confirm'li Delete (`allowed_actions.soft_delete` kapılı; compare'deki satır silinirse panel
>   kapanır); kanonik hata zarfı verbatim.
> - **`frontend/src/components/ResultDetail.tsx`** — Metrics bölümü `useResultMetrics`'e bağlı:
>   profil caption'ı (personal/system default · locked · registry versiyonu); hydrated görünüm
>   yüklenirken VEYA hata alırsa ham persisted satırlar dürüst bir notla render edilmeye devam
>   eder (L4 korunur: eksik metrik ASLA 0 değil).
> - **Testler** — YENİ `test/historyActions.test.tsx` (4) + `test/resultMetricsView.test.tsx` (3)
>   → **frontend 58/58** (51 + 7); `backtestRun.test.tsx` deep-link testi metrics route'unu artık
>   İLK sırada stub'lar (apiStub fragment eşleşmesi SIRALI — detail fragment'i metrics URL'inin
>   substring'i) ve hydrated caption'ı assert eder; typecheck + lint temiz; build yeşil.
> **Dürüst sınır:** compare tam iki sonuç (server `min/max_length=2` — N-way UI yok) · soft-delete
> OCC token göndermez (history projeksiyonunda row_version yok; server optional kabul eder) ·
> restore Admin Trash akışında kalır (backend Stage 6c landed; frontend Trash sayfası hâlâ
> placeholder) · `["jobs"]` kalıcı sınırı değişmedi.
> **Sıradaki doğal slice:** (b) capability aktivasyonları (`routes/capability.py` backend yüzeyi)
> VEYA (c) first-Admin provisioning DASHBOARD'u (backend mekanizması PR #76'da — yalnız UI) VEYA
> (d) CP real candidate generation. Aşağıdaki Panel / Management / Logs (PR #78) bloğu ve öncesi
> tarihsel.

## Durum (2026-07-06, TIER 2 frontend — Panel / Management / Logs canlı sayfası; PR #78 MERGED)

> **Altıncı TIER 2 (frontend) slice — Panel / Management / Logs canlı sayfası landed (PR #78,
> merged → main `2a8de9e`; CI yeşil; review 0 CRITICAL/HIGH).** `/panel` placeholder'ı gerçek
> sayfa oldu; **SON bağlanabilir SSE forward-contract key'i `["audit"]` ilk bağlı sayfasını aldı**
> — `audit.event.created` (PR #67 map'i) artık canlı sayfayı süpürüyor. Backend yüzeyi PR #26'dan
> beri hazırdı (`routes/admin_panel.py` + `routes/audit.py`).
> **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test tabanı 1028 sabit.** alembic
> head hâlâ `0021_local_auth`; backend `ENGINE_VERSION` hâlâ
> `backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/adminPanel.ts`** *(YENİ)* — Management okumaları `["admin"]` prefix'inde:
>   `useRegisteredUsers` (keyset cursor, `placeholderData`), `useSystemActors`, `useRoleMatrix`
>   (5dk staleTime — versiyonlu policy config). Logs/Audit okumaları `["audit"]` SSE prefix'inde:
>   `useAdminLogs` (family/severity/actor_type/q/correlation_id filtreleri — boş filtre
>   parametresi ASLA gönderilmez), `useLogEvent` detay, `useAuditEvents` ham akış. Mutation
>   `useAssignRole` → `PATCH /admin/users/{id}/role`, OCC guard
>   `expected_head_revision_id = user.version` (stale tab 409 zarfını verbatim görür); rol
>   seçenekleri server role-matrix'in ASSIGNABLE satırlarından — asla hard-coded client listesi
>   değil; `["admin"]` + `["audit"]` invalidate (komut audit event üretir).
>   `LOG_FAMILIES`/`LOG_SEVERITIES`/`LOG_ACTOR_TYPES` server taksonomisinin birebir aynası.
> - **`frontend/src/pages/Panel.tsx`** *(YENİ)* — 5 kart: `UsersCard` (registry + satır içi rol
>   atama), `SystemActorsCard`, `RoleMatrixCard` (grant grid'i + `policy_revision`), `LogsCard`
>   (filtreli liste + detay + correlation-chain linki), `AuditStreamCard` (ham append-only akış).
>   Forward-only cursor-stack pagination; Admin olmayan 403 zarfını `ErrorState` ile verbatim
>   görür.
> - **`App.tsx`** — `REAL_PATHS` 6 → 7 (`/panel`); `nav.ts` DEĞİŞMEDİ (23 öğe).
> - **`test/panel.test.tsx`** *(YENİ, 6)* — apiStub reuse; OCC payload assertion'ı, filtre-param
>   hijyeni, 403 — **frontend 51/51** (45 + 6); typecheck + lint temiz; build yeşil.
> **Dürüst sınır:** `["jobs"]` için backend liste yüzeyi HİÇ yok — KALICI dürüst sınır (job
> durumu run projeksiyonları + /v1/metrics jobs-depth'te) · users/system-actors'ın özel SSE
> event'i yok (kendi mutation'ları invalidate eder; kalanını `resource.changed` full refresh
> süpürür) · history compare/soft-delete + profil-hidrasyonlu
> `GET /backtest-results/{id}/metrics` binding'i (ResultDetail rebind) hâlâ ertelendi — artık
> doğal sıradaki follow-up.
> **Sıradaki doğal slice:** (a) history compare/soft-delete + profil-hidrasyonlu Result metrics
> binding'i (ResultDetail rebind; `routes/results_history.py` compare/delete backend'de landed)
> VEYA (b) capability aktivasyonları VEYA (c) first-Admin provisioning DASHBOARD'u (backend
> mekanizması PR #76'da). Aşağıdaki first-Admin bootstrap (PR #76) bloğu ve öncesi tarihsel.

## Durum (2026-07-06, first-Admin bootstrap provisioning — TIER 2 BACKEND slice; PR #76 MERGED)

> **first-Admin bootstrap provisioning landed (PR #76, merged → main `1771f14`; CI yeşil; review
> APPROVE 0 CRITICAL/HIGH).** PR #38'in dürüst sınırı kapandı ("signup hep baseline User; ilk-Admin
> provisioning upstream'de yok"): taze bir deployment'ta ilk Admin'e giden yol artık var — açık
> operatör opt-in'iyle. **BACKEND-ONLY — frontend değişmedi (45/45 sabit); migration YOK, yeni
> tablo YOK — alembic head `0021_local_auth` SABİT; `ENGINE_VERSION`
> `backtest-engine-v2-position-size-limits` SABİT. Backend testler 1015 → 1028 (+13).**
> **Reuse anchor'ları (kesin semboller):**
> - **`config/settings.py`** — YENİ `bootstrap_admin_email` alanı (env
>   `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL`, default `""` = kapalı → opt-in yoksa SIFIR davranış
>   değişikliği).
> - **`application/commands/auth.py`** — YENİ `bootstrap_admin_matches` helper'ı (case +
>   whitespace normalize e-posta eşleşmesi) + `sign_up` içinde bootstrap branch: eşleşen signup
>   YALNIZ aktif Admin yokken Admin olur (aksi halde fail-closed → baseline rol). Yarış güvenliği:
>   last-admin demote yolunun aynı-tx advisory lock'u (`identity_repo.lock_admin_count`)
>   count+karar bölümünü eşzamanlı demote'lara VE eşzamanlı bootstrap'lara karşı serileştirir;
>   `unique(human_users.email)` ikinci nitelikli signup'ı ayrıca bloklar. Provisioning AYNI
>   transaction'da özel `user.admin_bootstrapped` audit + `admin_bootstrapped` outbox event'i
>   üretir (ev `_audit_and_outbox` pattern'i).
> - **`apps/api/routes/auth.py`** — `settings.bootstrap_admin_email`'i geçirir, yalnız
>   server-side. Route şemasında role alanı YOK → client'tan escalation yapısal olarak imkânsız.
> - **Testler** — YENİ `tests/unit/test_auth_bootstrap_unit.py` +
>   `tests/integration/test_auth_bootstrap_admin.py` (+13): env kapalı → baseline (event yok);
>   eşleşme + Admin yok → Admin + audit/outbox; aktif Admin varken → fail-closed baseline;
>   eşleşmeyen/eksik e-posta → baseline; case/whitespace normalizasyonu; settings env okuma; route
>   pass-through. İzole DB'de **1028 yeşil**; ruff + format + mypy (299 dosya) temiz.
> **Dürüst sınır:** yalnız backend MEKANİZMASI — provisioning dashboard'u yok (sonraki bir
> frontend slice) · bootstrap yalnız signup anında uygulanır; mevcut hesabı geriye dönük
> yükseltmez (operatör yeniden oluşturur veya gelecekteki admin aracını kullanır).
> **Sıradaki doğal slice:** Panel / Management / Logs canlı sayfası (SON bağlanabilir SSE key'i
> `["audit"]`; `routes/admin_panel.py` + `routes/audit.py`) VEYA capability aktivasyonları.
> Aşağıdaki Arrange Metrics/Analysis Lab (PR #74) bloğu ve öncesi tarihsel.

## Durum (2026-07-06, TIER 2 frontend — Arrange Metrics + Analysis Lab canlı sayfaları; PR #74 MERGED)

> **Beşinci TIER 2 (frontend) slice — Arrange Metrics + Analysis Lab canlı sayfaları landed
> (PR #74, merged → main `4969825`; CI 3/3 yeşil).** Backend yüzeyi tam olan SON iki placeholder
> (`/backtest/metrics` Stage 5c doc 17 + `/analysis-lab` Stage 6a doc 18) gerçek sayfa oldu;
> Analysis Lab'ın TÜM query key'leri `["agent-tasks"]` prefix'inde → **PR #67'nin
> `agent.task.updated` map'i (İKİNCİ SSE forward-contract key'i) artık canlı sayfaları süpürüyor.**
> **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test tabanı 1015 sabit.** alembic head
> hâlâ `0021_local_auth`; backend `ENGINE_VERSION` hâlâ `backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/metricProfile.ts`** *(YENİ)* — `application/queries/metric_profile.py`
>   projeksiyonlarını birebir yansıtan wire tipleri (`MetricDefinition`/`MetricRegistry`,
>   `ResolvedMetricProfile` — `editable_profile_id` ilk Apply'a kadar `"system_default"`, doc 17
>   §8.1 — `MetricProfileRevision` server-türevli geçiş `reason`'ıyla, `ApplyMetricProfileInput`);
>   hook'lar `useMetricDefinitions` (`["metric-definitions"]`, 5dk staleTime) +
>   `useResolvedMetricProfile` (`["metric-profile","resolved"]`); `useApplyMetricProfile` —
>   Apply / Apply & Lock / saf Unlock ÜÇÜ DE aynı append `POST /metric-profiles/{id}/revisions`,
>   `expected_profile_revision_id` OCC guard'ıyla (409 stale/locked verbatim); `["metric-profile"]`
>   invalidate. SUNUM-ONLY (CR-07): metrik yeniden hesaplanmaz, Result'a dokunulmaz.
> - **`frontend/src/pages/ArrangeMetrics.tsx`** *(YENİ)* — registry tablosu + üstüne resolved seçim:
>   selectable olmayan (future/experimental) metrikler görünür ama işaretlenemez; kilitli profil
>   edit'i kapatır, yalnızca SAF Unlock sunar (server'ın kendi seçimi + `is_locked=false`, doc 17
>   §7); draft her revision hareketinde server head'inden yeniden tohumlanır; boş seçimde Apply
>   disabled (server `min_length=1`); başarı `revision_no` + `reason` echo'lar.
> - **`frontend/src/lib/agentLab.ts`** *(YENİ)* — `application/queries/agent_workspace.py`
>   projeksiyonlarını yansıtan wire tipleri (`AgentRuntime`/`AgentTaskCard`/`AgentOverview`/
>   `AgentTaskDetail` checkpoint+directive'lerle/`HypothesisCard`) + komut admission'ları
>   (`DirectiveAdmission`, `LabMessageResponse`, `RuntimeControlAccepted`); TÜM query key'ler
>   `["agent-tasks"]` SSE prefix'inde: `useAgentOverview` (15sn loss-tolerant poll fallback,
>   INF-11 — SSE asıl), `useAgentTasks` (keyset, `placeholderData`), `useAgentTask`,
>   `useHypotheses`; 202 mutation'lar `useQueueDirective` (`DIRECTIVE_PRIORITIES = normal|high` —
>   `autonomous` yalnız Coordinator üretir, insana sunulmaz, doc 18 §9.1), `useSendLabMessage`,
>   `usePauseRuntime`/`useResumeRuntime`/`useStopRun` — runtime `row_version` `If-Match` OCC token
>   olarak gider (`postWithIfMatch`); hepsi `["agent-tasks"]` invalidate.
> - **`frontend/src/pages/AnalysisLab.tsx`** *(YENİ)* — `RuntimeCard` (status/mode/pending_control
>   badge'leri; Pause-at-next-safe-checkpoint / Resume / Stop-active-run — stop aktif TASK id'sini
>   geçer; bu domain'de run id ≡ task id: backend `stop_run` `get_task(session, run_id)` yapar),
>   `QueueCard` (sayaçlar + kartlar + Detail), `TaskDetailCard` (checkpoint sayısı,
>   waiting/failure, ilişkili direktifler), `DirectiveCard` (direktif + discussion-message
>   composer'ları; `delivery_policy` echo; asistan yanıtı render), `HypothesesCard` (output board).
>   Server policy otorite: Admin/Supervisor olmayan 403 zarfını `ErrorState` ile verbatim görür.
> - **`App.tsx`** — `REAL_PATHS` 4 → 6 (`/backtest/metrics`, `/analysis-lab`); `nav.ts` DEĞİŞMEDİ
>   (23 öğe).
> - **`test/arrangeMetrics.test.tsx`** *(4)* + **`test/analysisLab.test.tsx`** *(5)* — apiStub
>   reuse; mutation payload + If-Match assertion'ları, `["agent-tasks"]` invalidation refetch
>   kanıtı — **frontend 45/45** (36 + 9); typecheck + lint temiz; build yeşil.
> **Dürüst sınır:** metric-profile değişikliğinin ÖZEL SSE event'i yok (yalnız `resource.changed`
> full refresh süpürür; Apply mutation'ı aynı-tab tazeliği için `["metric-profile"]` invalidate
> eder) · lab app-level `/events` stream'ini tüketir — role-gated `GET /agent-events/stream`
> (bugün yalnız heartbeat/ready) ikinci EventSource olarak BAĞLANMADI · task/hypothesis keyset
> pagination'ın ilk sayfa ötesi + `GET /agent-tasks?status&cursor` filtre UI'ı ertelendi ·
> `GET /backtest-results/{result_id}/metrics` (profil-hidrasyonlu Result görünümü) henüz
> TÜKETİLMEDİ — `ResultDetail` ham persisted satırları gösterir; profil editörü landed olduğuna
> göre doğal follow-up budur · `["audit"]`'in bağlı sayfası hâlâ yok (Panel/Logs) ve `["jobs"]`
> için backend'de liste yüzeyi HİÇ yok (job durumu run projeksiyonları + /v1/metrics jobs-depth
> üzerinden görünür) · history compare/soft-delete affordance'ları hâlâ ertelendi.
> **Sıradaki doğal slice:** Panel / Management / Logs canlı sayfası (SON bağlanabilir SSE key'i
> `["audit"]`'i bağlar; `routes/admin_panel.py` `/admin/users|system-actors|role-matrix|logs` +
> `routes/audit.py` `/audit-events`; compare/soft-delete + profil-hidrasyonlu Result metrics
> binding'i yanında gidebilir) VEYA capability aktivasyonları / first-Admin provisioning.
> Aşağıdaki backtest-sayfaları (PR #72) bloğu ve öncesi tarihsel.

## Durum (2026-07-06, TIER 2 frontend — canlı-veri backtest sayfaları; PR #72 MERGED)

> **Dördüncü TIER 2 (frontend) slice — canlı-veri backtest sayfaları landed (PR #72, merged →
> main `c322588`; CI 3/3 yeşil; review 1 bulgu — path-param encoding — commit öncesi düzeltildi,
> 0 CRITICAL/HIGH).** Stage 5 backtest ekranları placeholder'dı; backend yüzeyi Stage 5a/5b'den beri
> hazırdı ve PR #67'nin `backtest.run.updated → ["backtests"]` map'i sayfasızdı. Bu slice RUN &
> Backtest Results (`/backtest/run`) + Results History'yi (`/backtest/history`) gerçek query'lere
> bağlar → **SSE live-invalidation payoff'u ilk kez GÖRÜNÜR.**
> **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test tabanı 1015 sabit.** alembic head
> hâlâ `0021_local_auth`; backend `ENGINE_VERSION` hâlâ `backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/backtest.ts`** *(YENİ)* — backend projection'larını birebir yansıtan wire
>   tipleri (`DefaultMainboard`/`BacktestRunAdmission`/`BacktestRun`/`BacktestResultDetail`/
>   `HistoryRow`/`HistoryPage`); `HISTORY_SORTS` (6 kanonik sort + V18 label), `KEY_METRIC_COLUMNS`,
>   `TERMINAL_RUN_STATES`; `formatMetricValue` (null değer availability label'ı gösterir, ASLA 0 —
>   L4) + locale-bağımsız `formatUtc`; hook'lar: `useDefaultMainboard` (`["mainboard","default"]`),
>   `useBacktestRun` (`["backtests","run",id]`, terminal state'te duran poll fallback — SSE asıl,
>   INF-11), `useBacktestResult` (immutable), `useResultsHistory` (`["backtests","history",sort,cursor]`,
>   keyset cursor, `placeholderData` önceki sayfayı tutar); 202 mutation'lar `useRequestBacktestRun`/
>   `useRetryBacktestRun` (ikisi de `["backtests"]` invalidate). TÜM path parametreleri
>   `encodeURIComponent`'li (review düzeltmesi — encode'suz `?result=` URL normalizasyonuyla başka
>   API GET endpoint'ine gidebilirdi).
> - **`frontend/src/pages/BacktestRun.tsx`** *(YENİ)* — iki mod: `?result=<id>` immutable deep-link
>   (yalnızca result_id'den hydrate, doc 15 §8.5 — History "View" buraya iner) + workbench
>   (composition kartı `GET /mainboards/default` → RUN admission 202 → run id `?run=`'da, refresh
>   durable row'u izlemeye devam eder, doc 15 §4); failure verbatim + Retry YENİ run id'ye geçer;
>   admission `warning_count` badge'i.
> - **`frontend/src/pages/ResultsHistory.tsx` + `components/ResultDetail.tsx`** *(YENİ)* — server-side
>   sort/keyset pagination (client asla yeniden sıralamaz), key-metric digest hücreleri, View →
>   `?result=` deep-link; ResultDetail: summary kv + metrics tablosu (value + availability) +
>   manifest excerpt + artifact sayıları.
> - **`App.tsx`** — `REAL_PATHS` set'i (`/`, `/panel/metrics`, `/backtest/run`, `/backtest/history`);
>   iki gerçek route. `nav.ts` DEĞİŞMEDİ (23 öğe).
> - **`test/backtestRun.test.tsx`** *(3)* + **`test/resultsHistory.test.tsx`** *(4)* + paylaşılan
>   **`test/helpers/apiStub.ts`** route-aware fetch double ("<METHOD> <fragment>" anahtarlı) —
>   **frontend 36/36** (29 + 7); typecheck + lint temiz; build yeşil.
> **Dürüst sınır:** Arrange Metrics (`/backtest/metrics`) + Analysis Lab (`/analysis-lab`) hâlâ
> placeholder — `["jobs"]`/`["agent-tasks"]`/`["audit"]` key'lerinin bağlı sayfası yok; history
> compare + soft-delete affordance'ları onlarla ertelendi.
> **Sıradaki doğal slice:** Arrange Metrics + Analysis Lab canlı sayfaları (kalan SSE key'lerini
> bağlar; `routes/metric_profile.py` + `routes/agent_lab.py`) VEYA capability aktivasyonları /
> first-Admin provisioning. Aşağıdaki /v1/metrics (PR #69) bloğu ve öncesi tarihsel.

## Durum (2026-07-05, TIER 2 frontend — /v1/metrics dashboard; PR #69)

> **Üçüncü TIER 2 (frontend) slice — /v1/metrics ops dashboard landed (PR #69, açık, CI: Frontend +
> Docker yeşil, backend check frontend-only diff için değişmeden yeniden koşar; kullanıcı merge'i
> bekliyor).** Backend zaten `GET /v1/metrics`'i Prometheus-text exposition olarak sunuyordu (Stage 8b,
> `apps/api/routes/metrics.py`, `PlainTextResponse`) — in-process registry golden signal'leri + scrape-time
> operational gauge'lar — ama hiçbir şey tüketmiyordu. Bu slice read-only bir ops dashboard ekler.
> **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test tabanı 1015 sabit.** alembic head hâlâ
> `0021_local_auth`; backend `ENGINE_VERSION` hâlâ `backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/metrics.ts`** *(YENİ)* — bağımsız Prometheus exposition parser'ı
>   `parsePrometheus(text) → ParsedMetrics` (`# TYPE`/`# HELP`, etiketli + skaler sample, histogram
>   `_bucket`/`_sum`/`_count` → `ownerFamily` ile taban aileye gruplanır, `+Inf`/`-Inf`/`NaN`, `\`/`"`
>   etiket escape'leri, serbest notlar) + `summarizeMetrics(parsed) → MetricsSummary`: dört golden signal
>   (`requestsTotal` trafik, `serverErrors` 5xx, `clientErrors` 4xx, `inFlight` doygunluk, `avgLatencyMs`
>   = histogram `sum/count`), sıralı `jobsDepth` + toplam, `outboxLagSeconds`, `leaseAgeSeconds`,
>   `degraded` (backend "operational gauges unavailable" DB-down notunu yakalar), `familyCount`;
>   `parseMetricsSummary(text)` kısayolu. Tüketilen metric adları: `entropia_http_requests_total`,
>   `entropia_http_request_duration_seconds_{bucket,sum,count}`, `entropia_http_requests_in_flight`,
>   `entropia_jobs_depth{queue,status}`, `entropia_outbox_lag_seconds`, `entropia_job_lease_age_seconds`
>   (backend `# TYPE` verir, `# HELP` vermez).
> - **`frontend/src/lib/apiClient.ts`** — YENİ `apiGetText` / `api.getText`: JSON-olmayan endpoint'ler
>   için ham-text GET (metrics `text/plain`, JSON envelope DEĞİL). `apiRequest` auth header'larını
>   (`Bearer` + `X-Actor-Id`) yansıtır; `textError` non-envelope hatada ham body'ye düşer. Mevcut
>   `apiRequest` / `api.{get,post,patch,del}` DEĞİŞMEDİ.
> - **`frontend/src/lib/hooks.ts`** — YENİ `useMetrics()`: react-query `["metrics"]` key,
>   `refetchInterval` 5s, `parseMetricsSummary(await api.getText("/metrics"))`. `["metrics"]` key'i SSE
>   `resource.changed` catch-all'ıyla da taranır.
> - **`frontend/src/pages/Metrics.tsx`** *(YENİ)* — dashboard: golden-signal tile'ları, status-class
>   badge'leri, operational-gauge `kv` listesi, jobs-depth `.metrics-table`, degraded banner, canlı
>   göstergesi. `Loading`/`ErrorState`/`StatusBadge` + `.card`/`.kv`/`.page-title` reuse;
>   `formatCount`/`formatMs`/`formatSeconds` sonlu-olmayan/eksik değerleri em-dash gösterir.
> - **`frontend/src/app/nav.ts` + `App.tsx`** — YENİ **adminOnly** nav öğesi **System Metrics**
>   `/panel/metrics`'te (stage 8, Agent & Admin altında); `ALL_NAV_ITEMS` 22 → 23 (`test/nav.test.tsx`
>   güncellendi). `App.tsx` gerçek `/panel/metrics` route'u ekler + o path'i Placeholder auto-map'ten
>   çıkarır. `global.css`: `.metrics-table`.
> - **`test/metrics.test.ts`** *(YENİ, 10)* + **`test/metricsPage.test.tsx`** *(YENİ, 3)* — parser/summary
>   unit (healthy/degraded/empty scrape, histogram avg 20ms, `String.raw` ile escape, malformed satır
>   toleransı) + component render (`vi.stubGlobal("fetch")` double); **frontend 29/29** (16 önceki + 13
>   yeni); typecheck + lint temiz; build yeşil.
> **Dürüst sınır:** metrics'in SSE event'i YOK → dashboard 5s POLL eder (SSE invalidate değil; `["metrics"]`
> yine `resource.changed` ile taranır). Route URL'den erişilebilir (scrape endpoint tasarımca auth'suz);
> nav öğesi admin-gated (`/panel`, `/trash` ile tutarlı). `# HELP` gösterilmez (backend vermez).
> **Sıradaki doğal slice:** canlı-veri Stage 5/6 sayfaları (RUN / Results History / Arrange Metrics /
> Analysis Lab — SSE `EVENT_QUERY_KEYS`'i bağlar → live-invalidation payoff görünür) VEYA capability
> aktivasyonları / first-Admin provisioning. Aşağıdaki SSE (PR #67) bloğu ve öncesi tarihsel.

## Durum (2026-07-05, TIER 2 frontend — SSE live-invalidation; PR #67)

> **İkinci TIER 2 (frontend) slice — SSE live-invalidation landed (PR #67, açık, CI yeşil,
> kullanıcı merge'i bekliyor).** Backend zaten transactional outbox'ı `GET /events` üzerinden tipli
> SSE frame'leri olarak fan-out ediyordu (Stage 8b, `apps/api/sse.py`); web shell bağlantıyı açıyor
> ama yalnızca `heartbeat` dinliyordu — `connectEvents`'in `queryClient` parametresi kullanılmayan
> bir Stage-1 TODO'ydu, hiçbir domain event cache'i tazelemiyordu. Bu slice `frontend/src/lib/sse.ts`
> stub'ını doldurur → her taksonomi event'i ilgili react-query key'lerini invalidate eder.
> **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test tabanı 1015 sabit.** CI: **Frontend
> + Docker check yeşil**; backend check frontend-only diff için değişmeden yeniden koşar. alembic head
> hâlâ `0021_local_auth`; backend `ENGINE_VERSION` hâlâ `backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/sse.ts`** — `connectEvents(queryClient, onStatus?)` imzası + `SseStatus`
>   DEĞİŞMEDİ (Layout call-site'a dokunulmadı). YENİ export'lar:
>   - **`SseEventName`** — backend taksonomi union'ı (`backtest.run.updated`/`job.updated`/
>     `agent.task.updated`/`audit.event.created`/`resource.changed`); `apps/api/sse.py::sse_event_name`
>     ile lockstep kalmalı.
>   - **`EVENT_QUERY_KEYS: Record<SseEventName, readonly QueryKey[]>`** — event→key-prefix map:
>     `backtest.run.updated → [["backtests"]]`, `job.updated → [["jobs"]]`,
>     `agent.task.updated → [["agent-tasks"]]`, `audit.event.created → [["audit"]]`,
>     `resource.changed → []` (boş liste = catch-all → tam `invalidateQueries()`). react-query prefix
>     eşler → `["backtests"]` ileride `["backtests", runId, …]`'i de kapsar.
>   - **`SSE_EVENT_NAMES`** — `Object.keys(EVENT_QUERY_KEYS)` (iterasyon/test).
>   - private `invalidateForEvent(qc, name)` — boş liste → tam refresh, değilse prefix-başına
>     `invalidateQueries({queryKey})`. Handler'lar event-adı-başına eklenir + **dispose'da sökülür**
>     (simetrik add/remove) → `source.close()`.
>   - **Reconnect self-heal (INF-11):** `hasOpened` flag'i İLK `open`'ı no-op yapar ama SONRAKİ `open`
>     (drop sonrası reconnect) tam `invalidateQueries()` tetikler → bağlantı boşluğunda hiçbir view stale kalmaz.
> - **`frontend/src/test/sse.test.ts`** *(YENİ)* — in-memory `EventSource` double (`vi.stubGlobal`)
>   ile 7 vitest → **frontend toplam 16/16** (9 önceki + 7 yeni); typecheck + lint temiz; build yeşil.
> **Dürüst sınır:** bu key'lere bağlanan CANLI sayfa HENÜZ yok — Stage 5/6 `RUN`/`Results History`/
> `Arrange Metrics`/`Analysis Lab` ekranları placeholder, dolayısıyla invalidation bugün zararsız
> no-op; **görünür payoff o sayfalarla gelir**, `EVENT_QUERY_KEYS` onların forward contract'ı. Kalan
> TIER 2 adayı **`/v1/metrics` Prometheus-text dashboard** bu slice'ta DEĞİL.
> **Sıradaki doğal slice: `/v1/metrics` dashboard** (Prometheus-text parser + paneller) VEYA canlı-veri
> sayfaları (Stage 5 RUN vb.). Aşağıdaki login (PR #65) bloğu ve öncesi tarihsel.

## Durum (2026-07-05, TIER 2 frontend — real-auth login/signup/logout; PR #65)

> **İlk TIER 2 (frontend) slice — gerçek auth login/signup/logout landed (PR #65, açık, CI
> yeşil, kullanıcı merge'i bekliyor).** Backend zaten gerçek local auth sunuyordu
> (`/v1/auth/signup|login|logout`, opaque Bearer session — Auth/IdP PR #38 + M1 §4) ama web
> shell (`frontend/`, **Vite 8 + React 18 + react-router 6 + @tanstack/react-query 5 + react-hook-form**)
> yalnızca dev `X-Actor-Id` header'ı gönderiyordu. Bu slice shell'i backend'e bağlar → insanlar
> gerçek Bearer session alır. **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test
> tabanı 1015 sabit.** CI: **Frontend + Docker check yeşil**; backend check frontend-only diff
> için değişmeden yeniden koşar. alembic head hâlâ `0021_local_auth`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/session.ts`** *(YENİ)* — external store: `getSessionToken()` (API client'ın
>   her istekte okuduğu ham-string fast-path), `getStoredUser()`, `setSession({token,user,expiresAt})`,
>   `clearSession()`, `subscribe(listener)`. İki `localStorage` anahtarı (`entropia.sessionToken`
>   + `entropia.session` JSON meta). React-bağımsız → `useSyncExternalStore` ile birleşir.
> - **`frontend/src/lib/apiClient.ts`** — `apiRequest` artık `getSessionToken()` non-null iken
>   mevcut `X-Actor-Id`'ye **EK OLARAK** `Authorization: Bearer <token>` ekler. İki header güvenle
>   birlikte gider: server yalnızca `AUTH_MODE`'un güvendiğini onurlandırır (`session` → Bearer
>   asıl, bare `X-Actor-Id` yok sayılır; `dev` → `X-Actor-Id`, Bearer yok sayılır — `backend
>   .../apps/api/deps.py`), ikisi de diğerini spoof edemez.
> - **`frontend/src/lib/auth.ts`** *(YENİ)* — react-query mutation'ları: `useLogin` (POST
>   `/auth/login` → `setSession`), `useSignup` (POST `/auth/signup` sonra **auto-login**),
>   `useLogout` (best-effort POST `/auth/logout`, **her durumda** `clearSession()` — başarısız/expired
>   revoke UI'ı yarı-login bırakmaz), `useSessionToken()`. Her success `queryClient.invalidateQueries()`
>   → `/me` + rol-gated nav yeni principal altında refetch.
> - **`frontend/src/pages/Login.tsx`** *(YENİ)* — standalone `/login` (app shell yok),
>   `react-hook-form`, login/signup toggle; hata backend canonical envelope'ını **verbatim** gösterir
>   (`ApiError` → `${code}: ${message}`); client asla auth mesajı uydurmaz. Zorunlu-alan validation
>   client-side submit'i bloklar.
> - **`frontend/src/app/Layout.tsx`** — yeni `AuthControl`: anonimken **Log in** link, token varken
>   kullanıcı + **Log out**; gerçek session aktifken `DevActorControl` gizli (`token ? null : <DevActorControl/>`).
> - **`frontend/src/App.tsx`** — `<Layout>` route'u DIŞINDA standalone `/login` `<Route>`.
> - **`frontend/src/lib/types.ts`** — `AuthUser` / `SignUpResponse` (= `AuthUser`) / `LoginResponse`
>   envelope'ları (`routes/auth.py` yansıması).
> - **`frontend/src/styles/global.css`** — yeni `.btn*` + `.auth-*` sınıfları (temalı, dark/light).
> - **`frontend/src/test/auth.test.tsx`** *(YENİ)* — 6 vitest → **frontend toplam 9/9**; typecheck +
>   lint temiz; production build yeşil.
> **Dürüst sınır:** anonim → `/login` zorlayan route guard YOK (dev mode anonim gezmeye izin verir;
> erişim server-side gate'lenir). First-Admin provisioning hâlâ upstream'de yok (signup hep baseline
> rol). Diğer iki TIER 2 adayı — **SSE live-invalidation** (`sse.ts` stub'ını doldur) ve
> **`/v1/metrics` dashboard** (Prometheus-text parser) — bu slice'ta DEĞİL, sıradaki doğal işler.
> **Sıradaki doğal slice: TIER 2 SSE live-invalidation** (küçük, saf infra) VEYA `/v1/metrics`
> dashboard — kullanıcı seçsin. Aşağıdaki position_size_limits (PR #63) bloğu ve öncesi tarihsel.

## Durum (2026-07-05, position_size_limits min/max cap wiring — Slice C follow-up sonrası; PR #63)

> **`position_size_limits` (min/max pozisyon cap) wiring landed (PR #63, kod `5ef5525`,
> merge `97b10b8`); MERGED → main `97b10b8`.** `PositionSizeLimits` sizing sub-config'de
> (`domain/strategy/config.py:599`) tanımlıydı ama `engine._position_size`'da **TÜM sizing
> metodlarında sessizce ignore ediliyordu** (latent bug — configure edilen cap hiçbir yolda
> hesaplanan size'ı kısıtlamıyordu). Fix, size'ı **tek bir sizing sınırında** clamp'ler →
> **base / risk_based / Kelly / notional-fallback** hepsi uniform cap'lenir. **Migration YOK**
> (config-only, JSONB — `PositionSizeLimits` değişmedi). **1015 test** (999 + 15: 7
> `_clamp_to_limits` unit / 6 per-method `_position_size` / 1 e2e / 1 ENGINE_VERSION ns).
> Review APPROVE 0 CRITICAL/HIGH. `ENGINE_VERSION=backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları:**
> - `domain/backtest/engine.py` — **YENİ `_clamp_to_limits(size, limits)`**: `limits is None`
>   VEYA `size <= _ZERO` → **no-op** (`0` = "açma" sentinel'i; bir `min` cap onu canlı pozisyona
>   diriltmez, ne de bir negatifi pozitife çeker); `min > max` yanlış-yapılandırma → `_ZERO`
>   (hiçbir size ikisini de sağlamaz → fail-closed); yoksa size'ı **DOWN-to-`max`**, sonra
>   **UP-to-`min`**, sonra `max(size, _ZERO)` (negatif cap'i de nötrler). Cap birimi = size birimi
>   (adet/coin), **unquantized** (base dalı ile simetrik). Eski `_position_size` gövdesi
>   **`_raw_position_size` olarak yeniden adlandırıldı** (mantık aynı); `_position_size` artık ince
>   wrapper = `_clamp_to_limits(_raw_position_size(config, entry_price, equity), config.position_sizing.position_size_limits)`.
>   Eksik limits alt-ağacı → pre-wiring engine ile **byte-identical**. **Tek çağrı noktası**
>   (`_open`, ~L475) → tüm sizing yolları otomatik clamp'lenir. `TYPE_CHECKING` import'una
>   `PositionSizeLimits` eklendi; `run_engine` diagnostics'e `"position_size_limits_active": bool`.
> - `domain/backtest/manifest.py` — `ENGINE_VERSION` `-kelly-sizing` → `-position-size-limits`
>   (execution_key ns shift; INF-04/INF-05 — stale UNCLAMPED sonuç reuse edilmez).
> - `domain/strategy/config.py:599` — `PositionSizeLimits(min_position_size/max_position_size: Decimal|None)`
>   **DEĞİŞMEDİ**, migration YOK.
> - `tests/unit/test_backtest_engine.py` — `_config`'e `min_size`/`max_size` kwargs; `_clamp_to_limits`
>   + `PositionSizeLimits` import; +15 test.
> **Dürüst sınır:** cap birimi = size birimi (adet), unquantized (base branch ile simetrik);
> `base_position_size` NEGATİF verilirse clamp muaf (`size <= _ZERO` guard) — pre-existing, scope
> dışı. **Slice C indikatör-compute + sizing + TIER 1 backend follow-up'ları böylece EFEKTİF TAMAM**
> (Kelly + risk_based + condition blocks + multi-TF + N-ary + VWAP + position_size_limits hepsi
> landed). **Sıradaki doğal slice: TIER 2 frontend/infra** (SSE/metrics/login, capability
> aktivasyonları, admin provisioning) — kullanıcı seçsin. Aşağıdaki Kelly (PR #60/#61) bloğu ve
> öncesi tarihsel.

## Durum (2026-07-04, formula_based Kelly sizing — Slice C follow-up sonrası; PR #60 + #61)

> **`formula_based` (Kelly criterion) sizing landed (PR #60, kod `3f254bc`) + non-finite
> fail-closed fix (PR #61, kod `3a92e7d`); ikisi de MERGED → main `54e71d2`.**
> `formula_based_sizing` + `kelly_criterion` config artık **HONORED**: fractional-Kelly capital
> fraction `f* = kelly_fraction·(W − (1−W)/R)` (alt-clamp 0), pozisyon usable equity'den boyutlanır
> (entry-price **BAĞIMLI**, `risk_based`'in stop-mesafesi boyutlamasının aksine). Diğer TÜM
> `formula_based` şekilleri (özellikle `custom_formula`) hâlâ notional fallback +
> `position_sizing_method_unsupported`. `ENGINE_VERSION=backtest-engine-v2-kelly-sizing`.
> **Migration YOK** (config-only). **999 test** (987 + 12: 9 Kelly feat / 3 non-finite fix).
> **Review (PR #60):** 1 CONFIRMED defect — non-finite `formula_params` (NaN/Inf) → Decimal
> aritmetiği `InvalidOperation` **CRASH** + Inf payoff → `(1−W)/R=0` → `f*` **SESSİZ honor**;
> **PR #61** `Decimal.is_finite()` guard'ı ile kapatıldı (non-finite → None → fail-closed) + 3
> regresyon testi. (#60 fix commit branch'e gelmeden self-merge edildi → fix ayrı PR #61 ile
> landed; ikisi de main'de.) **Reuse anchor'ları:** STAGE2_HANDOFF.md «formula_based Kelly …
> landed» + `domain/backtest/engine.py` (`_decimal_param` / `_kelly_capital_fraction` /
> `_position_size` Kelly dalı / `_sizing_is_honored`) + `manifest.py` `ENGINE_VERSION`.
> **Dürüst sınır:** adaptif/rolling Kelly (W/R backtest'ten tahmin) deferred (path-dependent +
> look-ahead); `custom_formula` unsupported (güvenli eval yok). Slice C indikatör-compute +
> sizing follow-up'ları böylece **EFEKTİF TAMAM**; sıradaki **TIER 1 kalıntısı**
> `position_size_limits` (min/max cap) wiring — `PositionSizeLimits` config'de tanımlı ama TÜM
> sizing metodlarında `engine._position_size`'da **sessizce ignore ediliyor** (latent bug;
> ENGINE_VERSION bump gerektirir). Aşağıdaki VWAP (d) bloğu ve öncesi tarihsel.

## Durum (2026-07-04, VWAP directional key — Slice C follow-up (d) sonrası; PR #58)

> **(d) VWAP directional key landed (PR #58, kod `d27b2bb`; merge KULLANICIDA, CI yeşil).**
> `ta.vwap` artık `DIRECTIONAL_KEYS` üyesi: rolling volume-ağırlıklı fiyat çizgisi, fiyat/VWAP
> cross'u native yönlü trigger (MA-cross ile aynı şekil); native trigger + reference paketi +
> N-ary chain leg olarak kullanılabilir. `ta.atr` doğası gereği non-directional kaldı (dürüst
> terminal sınır). Yeni `_Vwap` compute (bounded-memory, typical (H+L+C)/3 × volume, zero-volume
> fail-closed); volume engine `_Bar`→evaluator'lar boyunca threadlendi; `vwap_blocks` diagnostic;
> `ENGINE_VERSION=backtest-engine-v2-vwap-directional`. **Migration YOK.** **987 test** (970+17).
> Slice C indikatör-compute follow-up'ları böylece **etkin biçimde tamamlandı**; kalan TIER 1
> işi **formula_based/Kelly sizing** (hâlâ notional fallback). Aşağıdaki (ii) bölümü tarihsel.

## Durum (2026-07-04, N-ary reference chain — Slice C follow-up (ii) sonrası)

- **V1 ROADMAP COMPLETE + Auth/IdP + Parquet batch (Slice A) + Bar-replay engine (Slice B) +
  gerçek indikatör compute (Slice C) + `risk_based` sizing (a) + condition blocks (b) +
  condition extensions (b2) + two-package indicator-vs-indicator (#53) + higher-timeframe bar
  resampling (c) (#55) + per-condition multi-timeframe reference (i) + N-ary reference chain (ii) landed.** Son iş
  N-ary reference chain PR **#57** → `main` (feature kodu
  `44099a7`; #56 per-condition `1c5cca0`; #55 multi-tf kodu `def6c28`; #53 `9087c2b`; (b2) `361df4c`; condition-blocks (b)
  `8766fae`; risk_based (a) `43cee29`; Slice C `671d227`; **git log ile doğrula** — özet
  stale-by-default). Alembic head = **`0021_local_auth`** (Slice C + (a)/(b)/(b2)/(#53)/(c)/(i)/(ii)
  migration'sız). Test tabanı: **970 yeşil** (953 + #57'de 17). Backtest track artık **gerçek
  indikatör sinyalleriyle** giriş/çıkış üretiyor, `risk_based_sizing`'i modelliyor, condition
  gate'leri **crosses/between/series-vs-series** + **condition-only yön sinyali** ile
  değerlendiriyor, indikatör blok **daha kaba bir TF'de** compute edebiliyor (c), ve bir
  condition'ın **RHS reference paketi** parent bloktan **daha kaba bir TF'de** hesaplanabiliyor
  (i — `ConditionBlock.reference_timeframe`; hızlı source vs yavaş referans, look-ahead yok),
  ve bir condition'ın RHS'i **>2 paketlik sıralı bir zincir** olabiliyor (ii —
  `ConditionBlock.additional_reference_package_refs`; `fast > slow > slowest` MA fan; tek-paket
  yolu #53/#56 ile byte-identical).
  Manifest `ENGINE_VERSION = "backtest-engine-v2-nary-reference"`.
- **Test-infra notu:** integration testleri her testte şemayı drop/create eder — aynı lokal
  Postgres'i paylaşan İKİ oturum birbirini bozar. İzole DB kullan:
  `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_auth`.

## Backtest Engine Slice C'nin bıraktıkları (reuse anchor'ları — PR #45)

- **Indicators (pure, YENİ):** `domain/backtest/indicators.py` — saf, **incremental
  (bounded-memory)** `Decimal` TA compute. Seed'li canonical key'ler: `ta.sma`/`ema`/`rma`/`wma`
  (MA-cross native trigger) + `ta.rsi` (band cross); `ta.atr`/`ta.vwap` **RECOGNIZED ama
  non-directional** (unresolved). Tipler: `IndicatorSpec` / `SignalRule` / `IndicatorPlan`;
  `BlockEvaluator` (validity penceresi + per-block direction filter), `aggregate` /
  `build_evaluators`; `BUILTIN_ENTRY_MODEL = "builtin_indicator_native_trigger_v1"`. Parametreler:
  `parameter_overrides` varsa o, yoksa **engine-version default** (RSI 14, MA 20, bantlar 30/70 —
  reproducibility sabitleri).
- **Plan resolution (YENİ):** `application/queries/indicator_plan.py` —
  `resolve_indicator_plan(session, strategy_config) → IndicatorPlan`. Pinlenmiş her
  `PackageRevision.dependency_snapshot["resolved"][i]["canonical_key"]`'i built-in spec'e çözer.
  **Paket gövdeleri ÇALIŞTIRILMAZ.** NATIVE-TRIGGER-ONLY: `*_plus_condition` / timeframe override /
  non-directional key → `unresolved` diagnostics warning (asla sessizce düşmez — L4).
- **Engine dual-mode:** `domain/backtest/engine.py` — `run_engine(..., indicator_plan=None)`.
  Çözülen bir entry block varsa **gerçek sinyaller** sürer; yoksa etiketli breakout PROXY'ye
  düşer (geriye uyumlu — Slice B yolu bozulmadan durur). Exit = gerçek protection stop'lar
  (Slice B) + exit block'lar + `exit_on_opposite`.
- **Job:** `application/jobs/backtest_engine.py` — plan'ı resolve edip **enjekte eder**
  (run/manifest/result sözleşmeleri sabit). **Manifest:** `domain/backtest/manifest.py` —
  `ENGINE_VERSION = "backtest-engine-v2-indicator-compute"` (`execution_key` reprodüksiyon
  hash'ine katılır — INF-05 korunur; aynı kompozisyon aynı sonucu üretir).
- **Dürüst sınır (native-trigger-only; yüzeye çıkar, gizlenmez — L4):** yalnız
  `trigger_source == indicator_native_trigger` gerçek sinyale çözülür; `*_plus_condition`,
  timeframe override ve non-directional key'ler (`ta.atr`/`ta.vwap`) `unresolved` uyarısı olur;
  somut parametreler parse-edilmemiş kaynak gövdeden gelir → engine-version default +
  `parameter_overrides`.
- **Testler (+37):** `tests/unit/test_backtest_indicators.py` (**+24** — MA/RSI referans değerleri
  + invariant'lar, native trigger'lar, validity, aggregation), `test_backtest_engine_indicator_plan.py`
  (**+7** — gerçek `entry_model`, batch-size'lar arası determinizm, exit-on-opposite, proxy
  fallback + unresolved uyarıları), `tests/integration/test_indicator_plan_resolution.py`
  (**+6** — gerçek `package_revision` satırları, her unresolved yol dahil), `test_e2e_pipeline.py`
  (yayınlanmış RSI paketi uçtan uca gerçek compute'u sürer: `entry_model == BUILTIN_ENTRY_MODEL`).
- **Açık uçlar (Slice C follow-up'ları):** ~~`risk_based` sizing~~ ✅ **çözüldü (PR #47, aşağı bkz.)**;
  `formula_based` sizing hâlâ notional'a düşer + uyarır; `*_plus_condition` / condition block'ları
  `unresolved`; multi-timeframe (bar resampling) yok → timeframe override `unresolved`;
  `ta.atr`/`ta.vwap` directional değil.
- **NOT:** Slice C anchor'ındaki `ENGINE_VERSION = "backtest-engine-v2-indicator-compute"` follow-up
  (a)'da `"backtest-engine-v2-risk-based-sizing"`'e bump edildi (aşağı bkz.).

## `risk_based` sizing'in bıraktıkları (reuse anchor'ları — PR #47, Slice C follow-up a)

- **Engine sizing (güncellendi):** `domain/backtest/engine.py::_position_size` — YENİ `risk_based`
  bacağı: `size = max(equity, 0) * risk% / 100 / stop_loss_point` (**deterministik**, `entry_price`'tan
  **bağımsız**, non-negatif clamp — negatif size sonraki tüm trade'lerin PnL işaretini ters çevirirdi;
  önceki review CRITICAL, bust-safety testiyle sabit). YENİ helper `_sizing_is_honored(config)`:
  açık `base_position_size` **ve** sub-config'li `risk_based_sizing` = honored; `formula_based_sizing`
  **ve** sub-config'siz `risk_based` = notional fallback + L4 `position_sizing_method_unsupported:<method>`
  uyarısı. Diagnostics uyarısı artık `method != base_position_size` yerine `_sizing_is_honored(config)`'a bakıyor.
- **Manifest (güncellendi):** `domain/backtest/manifest.py` — `ENGINE_VERSION =
  "backtest-engine-v2-risk-based-sizing"` (`-indicator-compute`'tan bump). Gerekçe: `risk_based` çıktısı
  değişti → `execution_key` namespace'i kaymalı (INF-04 idempotent reuse / INF-05 reproducibility) —
  aynı kompozisyon için eski versiyon altında cache'lenmiş **stale notional-sized** sonucun yeniden
  kullanılmasını engeller.
- **Testler (+5):** `tests/unit/test_backtest_engine.py` — `_config` fixture'a `risk_pct`/`stop_point`;
  +5 test (risk formülü referans değeri, entry-price bağımsızlığı, bust clamp → 0, honored/unsupported
  uyarısı iki yön); 2 mevcut test `formula_based_sizing`'e repoint (hâlâ dürüst unsupported yolu).
  864 yeşil, ruff+mypy temiz, code-reviewer APPROVE (0 CRITICAL/0 HIGH). Migration YOK.
- **Açık uç:** `formula_based`/Kelly hâlâ `unresolved` (path-dependent istatistik; foundation'da
  belirsiz) → dürüst notional fallback + uyarı.

## Backtest Engine Slice B'nin bıraktıkları (reuse anchor'ları — PR #43)

- **Engine (pure):** `domain/backtest/engine.py` — `run_engine(*, strategy_config, bar_batches,
  execution_key, item_count=1, indicator_plan=None) → EngineOutput`. DB/clock/randomness yok;
  `bar_batches`'i BİR kez akıtır. Frozen çıktı satırları `TradeRow` / `EquityPoint` /
  `SignalEventRow` / `EngineOutput`. **Gerçek** protection stop'lar — `_initial_static_stop`
  (percentage/absolute'ün en sıkısı), `_trail_pct`+`_effective_stop` (trailing), **intrabar**
  değerlendirme (long: `bar.low ≤ stop`; short: `bar.high ≥ stop`) → `stop_loss`; veri sonu
  kapanışı → `end_of_data` (açık pozisyon asla sarkmaz). Maliyet — `_cost_params` /
  `_effective_fill` (yarım-spread + slippage oranı + fill başına komisyon ×2 gidiş-dönüş).
  **NOT:** Slice C sonrası entry/exit dual-mode — plan yoksa aşağıdaki breakout PROXY sürer.
- **Entry PROXY (fallback):** plan yoksa giriş **breakout proxy** (`_BREAKOUT_WINDOW = 20`
  look-back; yeni pencere yükseğinde long, düşüğünde short; aynı-bar beraberliğinde long kazanır),
  diagnostics'te `entry_model = deterministic_bar_breakout_proxy_v1` etiketli. Yön kısıtı →
  `suppressed_entries` → tek `filtered_no_entry` sinyal olayı.
- **Sizing:** `_position_size` — açık `base_position_size`, yoksa all-in **notional**,
  `max(equity, 0)` clamp'li (bust hesap → size 0, **asla negatif değil**; negatif size sonraki
  tüm trade'lerin PnL işaretini ters çevirirdi — review CRITICAL, deterministik bust-safety
  testiyle sabitlendi). **GÜNCEL:** `risk_based_sizing` follow-up (a)'da (PR #47) **modellendi**
  (yukarı bkz.); `formula_based_sizing` hâlâ notional'a düşer + `position_sizing_method_unsupported:<method>`
  uyarısı (L4).
- **Job:** `application/jobs/backtest_engine.py` — `run_backtest(..., stream_bars=iter_bar_batches)`;
  bar'lar **enjekte edilebilir** (default gerçek S3-backed streamer). Fail yolları: market
  revizyonu yok/çözülemez → `ASSET_UNAVAILABLE`; engine exception'ı → `ENGINE_ERROR` (ikisi de
  audit'lenir). Slice C bu job'a plan resolution'ı da ekledi.

## Parquet Slice A'nın bıraktıkları (reuse anchor'ları — PR #41)

- **Streaming:** `infrastructure/s3/parquet_stream.py` — `stream_processed_batches(object_key)`
  (S3 `download_fileobj` → `SpooledTemporaryFile` 32MB spill-to-disk cap → pyarrow
  `ParquetFile.iter_batches`); `iter_parquet_batches(source)` saf lokal I/O (infra'sız
  unit-test edilebilir batching kontratı); `DEFAULT_BATCH_SIZE = 8_192`. YALNIZ worker plane.
- **Query:** `application/queries/market_bars.py` — `resolve_bar_source(session,
  market_revision_id=...)` → `BarSourceRef` (frozen: entity_id / revision_id / object_key /
  content_digest / size_bytes / row_count; işlenmemiş revizyonda `NotFoundError`) +
  `iter_bar_batches(source)`. Read-only; 'latest'e asla dokunmaz (doc 15 no-latest-leak).
- **Repo:** `repositories/market_data.py::get_processed_asset_for_revision` — sıralama kontratı:
  re-processing ayrı tx'te koşar (farklı ULID timestamp); aynı-ms ULID tiebreak non-deterministik
  — belgelenmiş limit, deterministik testle sabitlendi.

## Auth/IdP'nin bıraktıkları (reuse anchor'ları — PR #38)

- **Transport:** `apps/api/deps.py` — `AUTH_MODE=dev|session` (`dev` default: `X-Actor-Id`
  hattı testler için aynen durur); `bearer_token(request)`; `_session_mode_actor` (Bearer →
  `auth_sessions` lookup → rol HER istekte registry'den taze, M1 §4.2); servis hattı
  `ENTROPIA_SERVICE_TOKEN` + non-human principal zorunlu (`SERVICE_LINE_FORBIDDEN`).
- **Komutlar:** `application/commands/auth.py` — `sign_up`/`login`/`logout` + `hash_token`;
  tek 401 `INVALID_CREDENTIALS` + `DUMMY_HASH` timing pad (`shared/passwords.py`, argon2id).
- **Tablolar:** `human_credentials`, `auth_sessions` (token yalnız SHA-256 digest;
  `models/auth.py`, `repositories/auth.py`, migration `0021_local_auth`).
- **L1 dersi:** principal→human_user→credential AYNI flush'ta FK ihlali veriyor — her FK
  adımında ayrı `flush()` (bkz. `sign_up`).

## Stage 8'in bıraktıkları (reuse anchor'ları)

- **e2e şablonlar:** `tests/integration/test_e2e_pipeline.py` (`_ready_pipeline` — gerçek
  ingest→publish→compose→allocate zinciri; Slice B gerçek bar-replay ile, Slice C gerçek
  indikatör compute ile sürer), `test_e2e_agent_loop.py` (UI'sız agent döngüsü),
  `test_gateway_parity.py` (insan-komutu ↔ agent-tool denklik deseni + capability walk).
- **Fan-out:** `application/jobs/outbox_relay.py` (`relay_unpublished`, `fetch_events_after`,
  `outbox_lag_seconds`); `apps/api/sse.py` (`SseHub`, `run_outbox_poller`, `sse_event_name`).
  SSE kayıp-toleranslı (INF-11).
- **Scheduler:** `application/jobs/maintenance.py` (`recover_stale_jobs` INF-09,
  `redeliverable_queued_jobs` INF-03); `apps/scheduler/__main__.py` `ACTOR_BY_QUEUE`.
- **Hardening:** `apps/api/hardening.py` (SecurityHeaders / RateLimit opt-in `RATE_LIMIT_ENABLED`
  / Metrics middleware); `infrastructure/observability/metrics.py` + `GET /v1/metrics`.

## Post-V1 aday işler (öncelik sırası önerisi)

1. ~~**Auth/IdP**~~ ✅ **LANDED (PR #38)** — yerel auth (argon2id + opaque session + `AUTH_MODE`
   + servis hattı). Not: production'a geçişte `AUTH_MODE=session` + `ENTROPIA_SERVICE_TOKEN` set
   edilmeli; ~~ilk Admin hesabı provisioning'i henüz yok (signup hep `user`)~~ ✅ **PR #76** —
   `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL` opt-in bootstrap (aktif Admin yokken eşleşen signup → Admin).
2. **Gerçek backtest engine** — ~~Slice A: Parquet batch (PR #41)~~ ✅ · ~~Slice B: bar-replay
   engine (PR #43)~~ ✅ · ~~Slice C: gerçek indikatör compute (PR #45)~~ ✅ ·
   ~~Slice C follow-up (a): `risk_based` sizing (PR #47)~~ ✅ **LANDED**.
   **▶ Slice C follow-up'ları ARTIK EFEKTİF TAMAM** (aşağıdakilerin hepsi landed; TIER 1 backend
   DONE) — `indicators.py` / `indicator_plan.py` / `engine.py` üstüne biniyordu:
   - ~~**(a)** `risk_based` sizing~~ ✅ **LANDED (PR #47)** — `_position_size` içinde izole çözüldü.
     ~~**`formula_based`/Kelly**~~ ✅ **LANDED (PR #60 + #61)** — Kelly honored; `custom_formula` +
     adaptif/rolling Kelly dürüst `unresolved`. ~~**`position_size_limits` min/max cap**~~ ✅
     **LANDED (PR #63)** — `_clamp_to_limits` TÜM sizing metodlarını (base/risk_based/Kelly/notional) cap'ler.
   - ~~**(b)** condition block'ları (threshold gate)~~ ✅ **LANDED (PR #49)** ·
     ~~**(b2)** condition genişletmeleri (crosses/between/series-vs-series + condition-only yön)~~
     ✅ **LANDED (PR #51)** · ~~**indicator-vs-indicator — İKİ AYRI paket** (fast-MA vs slow-MA,
     `reference_package_ref`)~~ ✅ **LANDED (PR #53)**. **Kalan condition işi ARTIK LANDED:**
     ~~(i) **>2 paket** karşılaştırması (N-ary reference)~~ ✅ **PR #57** · ~~(ii) **per-condition
     multi-timeframe reference** (2. paket farklı-TF RHS)~~ ✅ **PR #56** · ~~(iii) `ta.vwap`
     directional reference key~~ ✅ **PR #58** — yalnız `ta.atr` doğası gereği yönsüz kalır (terminal sınır).
   - ~~**(c)** multi-timeframe — bar resampling~~ ✅ **LANDED (PR #55)** — indikatör blok base
     bar'lardan daha kaba bir TF'de compute eder (look-ahead yok). **(ii) multi-TF reference'ı unblock etti.**
   - ~~**(d)** daha çok directional canonical key — `ta.vwap`~~ ✅ **LANDED (PR #58)**; `ta.atr`
     doğası gereği yönsüz (volatilite bandı, cross yok) → terminal sınır.
   - ~~**`position_size_limits` (min/max cap) wiring**~~ ✅ **LANDED (PR #63)** — `_clamp_to_limits`
     `_raw_position_size → _position_size` sınırında; `ENGINE_VERSION=backtest-engine-v2-position-size-limits`;
     +15 test → 1015; migration yok. **TIER 1 backend böylece EFEKTİF TAMAM → sıradaki: TIER 2 frontend/infra.**
3. **Frontend entegrasyonu** — SSE tüketimi (yeni taksonomi), `/v1/metrics` dashboard'ları,
   Trash/Panel/Manual/Future-Dev shell'leri; `/v1/auth/*` login akışı hazır.
4. ~~**Create Package gerçek candidate generation**~~ ✅ **LANDED (PR #89, merged → main `ba533e5`)** —
   stub *compute* → DETERMINISTIK candidate-manifest hattı (`domain/create_package/candidate.py`;
   `GENERATOR_VERSION` namespace + `content_hash`; **LLM YOK**, gerçek generator Future-Dev). +12 unit
   test → **1048**; migration YOK; engine DEĞİŞMEDİ. İndikatör compute'un kaynağı hâlâ Slice C plan
   resolution pinned snapshot'tan okur; **CP/Pre-Check FRONTEND sayfaları hâlâ placeholder** (doğal
   sonraki dilim).
5. **Capability aktivasyonları** — Future Dev slotlarını Placeholder'dan çıkarma (graphic_view ilk
   aday; gate'ler + Admin transition hazır).
6. **Deferred takipleri** — `summary["timeframe"]` çözümü (market-revision metadata'sından);
   `dispatch_tool_call` status-key gölgelemesi (chip açıldı); retention-window auto-purge;
   data-queue auto-redelivery; SSE HTTP-streaming e2e; audit log-projection indexleri;
   ~~ilk-Admin provisioning~~ ✅ **PR #76** (backend mekanizması; dashboard UI'ı sonraki
   frontend slice).

## two-package indicator-vs-indicator — ✅ LANDED (PR #53, merged → main `093df44`)

**İki AYRI pinlenmiş indikatör paketinin karşılaştırılması landed** (INF-12 Slice C follow-up).
(b2)'nin dürüst sınırını açar: bir nested `ConditionBlock` artık **2. bir indikatör paketi**
pinleyebilir; onun hesaplanan çıktı serisi condition'ın RHS'i olur — kanonik **fast-MA vs
slow-MA crossover**. Önceden RHS yalnız sabit `threshold` veya tek-paket bounded `reference`
serisi olabiliyordu. Geriye uyumlu: tüm tek-paket formlar (b2) ile birebir aynı; **engine
DEĞİŞMEDİ** (reference serisi evaluator içinde kendi hesaplanır). run / manifest / result
sözleşmeleri sabit. +12 test → **928**, review APPROVE 0/0, **migration YOK**.

Reuse anchor'ları:
- **`domain/strategy/config.py`** — `ConditionBlock` +`reference_package_ref: PackageReference | None`
  (default `None`; Pydantic/JSONB, geriye uyumlu, **migration YOK**). Set ise sabit threshold /
  bounded reference serisinden **önceliklidir**.
- **`domain/backtest/indicators.py`** — `ConditionSpec` +`reference_key`/`reference_length`. YENİ
  `_build_reference_indicator(key, length)` factory **`_MovingAverage`/`_Rsi`'yi reuse eder**
  (`ta.rsi` → Wilder RSI, aksi MA — `BlockEvaluator`'ın compute seçimini yansıtır).
  `ConditionEvaluator` +`_ref_indicator` slot, her bar **`close`'dan inline ilerletir**
  (`.update(close)`); `_rhs_value` precedence: **reference indikatör değeri > bounded `reference`
  serisi > sabit `threshold`**. Isınan reference indikatör `None` döner → **fail-closed** (LEVEL ve
  CROSS), tıpkı eksik seri gibi.
- **`application/queries/indicator_plan.py`** — YENİ `_resolve_reference_package(session, cond) →
  (key, length, reason)`: 2. paketin revision'ını `_primary_directional_key(revision.dependency_snapshot)`
  ile `DIRECTIONAL_KEYS` kanonik key'e + look-back'e (`_int_override(_REFERENCE_LENGTH_KEYS)` —
  `reference_length`/`compare_length`/`reference_len` — yoksa `default_length(key)`) çözer. 2. paketin
  **gövdesi ÇALIŞTIRILMAZ.** `_resolve_condition` precedence: reference paketi → bounded reference →
  threshold. **Fail-closed reason'lar:** `condition_reference_package_unresolved` (revision yok),
  `condition_reference_no_series` (key computable `DIRECTIONAL_KEYS` MA/RSI serisi değil),
  `condition_reference_package_on_range` (`cond.between` RANGE condition üstünde reference paketi =
  misconfig; sessizce yutulmaz, yüzeye çıkar). Docstring dürüst-sınır güncellendi.
- **`domain/backtest/manifest.py`** — `ENGINE_VERSION = "backtest-engine-v2-indicator-vs-indicator"`
  (`execution_key` namespace shift — yeni RHS kaynağı sonucu değiştirir, stale condition-extensions
  sonucu yeniden kullanılmaz; INF-04/INF-05). `apps/seed.py` DEĞİŞMEDİ (yeni RHS mevcut pinlenmiş
  pakete biner; yeni `cond.*` resolver key yok).
- **Testler (+12):** `tests/unit/test_backtest_indicator_vs_indicator.py` (+6: reference-pkg LEVEL/EDGE
  compute, warm-up fail-closed, threshold'a precedence, RSI reference key, **flagship condition-only
  fast(2)/slow(4) MA-cross → long entry**) + `tests/integration/test_condition_plan_resolution.py`
  (+6: `_cblock`'a `reference_package_rev`/`reference_length` parametreleri; resolve + 3 fail-closed
  yol + gerçek yayınlanmış 2-paket MA-cross e2e long entry).

**Kalan condition işi (yeni dürüst sınır):** (i) **>2 paket** karşılaştırması (N-ary reference
şeması ister, tek `reference_package_ref` yetmez); (ii) **multi-timeframe reference** (2. paket
trigger TF'inde `close`'dan hesaplanıyor — farklı-TF RHS (c) multi-TF resampling'e bağlı);
(iii) **non-MA/RSI reference key** (reference paketi `DIRECTIONAL_KEYS` MA/RSI serisine çözülmeli;
`ta.atr`/`ta.vwap` RHS (d)'ye bağlı).

## (b2) condition extensions — ✅ LANDED (PR #51, merged → main `6913b0a`)

**Crosses + between + series-vs-series + condition-only directional signals landed** (INF-12
Slice C follow-up b2). (b)'nin threshold-only gate'ini genişletir; **tek-paket** condition
compute'un dürüst sınırıdır. `indicator_output_plus_condition` artık **RESOLVED** ((b)'de
deferred'di). Geriye uyumlu: native trigger'lar ve native-gated `cond.above`/`cond.below`
(b)/(Slice C) ile birebir aynı. run / manifest / result sözleşmeleri sabit. +24 test → **916**,
review APPROVE 0/0, migration YOK.

Reuse anchor'ları:
- **`domain/backtest/indicators.py`** — `CONDITION_KEYS` artık 5: `cond.above`/`below` (LEVEL),
  `cond.crosses_above`/`crosses_below` (EDGE: prev on/under RHS → now strict over/under;
  `_prev_source`/`_prev_rhs` takibi; warm-up `None` fail-closed), `cond.between` (RANGE: strict
  `lower < source < upper`, non-directional). `CROSS_CONDITION_KEYS`/`RANGE_CONDITION_KEYS`;
  `condition_direction()` (crosses_above→long, crosses_below→short, else None). `ConditionSpec`
  +`lower`/`upper`/`reference` (threshold artık Optional); `ConditionEvaluator._rhs_value`
  (reference serisi VEYA sabit threshold) → series-vs-series. `IndicatorSpec` +`condition_only`
  (default False); `BlockEvaluator` condition_only modu: native `_detect` ATLANIR, sinyal
  `_conditions_satisfied` gate'inin **YÜKSELEN EDGE**'inde (`_prev_gate`) ateşler, yön
  `_condition_only_direction(spec)` (required cross'ların ortak polaritesi), block validity
  kadar tutulur, `block.direction` ile filtrelenir; `current_signal` condition_only'de
  `_active_dir` döner (yeniden gate yok), native mod bire bir eski.
- **`application/queries/indicator_plan.py`** — `_ACCEPTED_TRIGGERS` += `indicator_output_plus_condition`;
  `_resolve_condition`: `between` (`lower`/`upper` ZORUNLU + `lower < upper`, yoksa
  `condition_bounds_missing`/`condition_bounds_invalid`), `reference` (`_reference_override` →
  reference varsa threshold OPSİYONEL). `condition_only` validasyonu:
  `_condition_only_direction_reason` → required'da tek cross polaritesi yoksa
  `condition_only_no_directional_edge`, çelişkili crosses ise `condition_only_conflicting_direction`
  (FAIL-CLOSED, tüm blok unresolved). **DÜRÜST SINIR (docstring'de):** iki AYRI paket
  karşılaştırması 2. `package_ref` (şema genişletmesi) ister, kapsam dışı.
- **`domain/backtest/manifest.py`** — `ENGINE_VERSION = "backtest-engine-v2-condition-extensions"`
  (`execution_key` namespace shift — stale condition-blocks sonucu yeniden kullanılmaz, INF-04/INF-05).
- **`apps/seed.py`** — `_ESP_COND_RESOLVERS` += `cond.crosses_above`/`below` (`["series","float"]`)
  + `cond.between` (`["series","float","float"]`).
- **Testler (+24):** `tests/unit/test_backtest_condition_extensions.py` (crosses edge semantiği,
  between range, series-vs-series, condition_only yön + edge-fire) + `test_condition_plan_resolution.py`
  yeni fail-closed yollar; bir mevcut test repoint.

**Kalan condition işi (dürüst sınır):** ~~indicator-vs-indicator — İKİ AYRI paket karşılaştırması
(fast-MA vs slow-MA)~~ ✅ **LANDED (PR #53, yukarı bkz.)** — `reference_package_ref`. Şimdi kalan:
>2 paket / multi-timeframe reference / non-MA-RSI reference key (yukarıdaki #53 bölümüne bkz.).

## (b) condition blocks — ✅ LANDED (PR #49, merged → main `6854e06`)

**Threshold-only nested condition GATE landed** (INF-12 Slice C follow-up b). Kapsam
kararı: yalnız **`indicator_native_trigger_plus_condition`** (native trigger + threshold
gate) modellendi; **`indicator_output_plus_condition` bilinçli olarak `unresolved`
bırakıldı** (condition-only yön sinyali edge/direction mapping ister — ayrı dilim).
Reuse anchor'ları: `domain/backtest/indicators.py::ConditionSpec/ConditionEvaluator/
_conditions_satisfied` + `BlockEvaluator.current_signal` gate; `indicator_plan.py::
_resolve_conditions/_resolve_condition/_primary_condition_key/_source_override` (fail-closed);
`engine.py` full-OHLC besleme + `condition_blocks` diagnostics; `manifest.py` ENGINE_VERSION
`backtest-engine-v2-condition-blocks`; `apps/seed.py::_seed_esp_resolver` + `_ESP_COND_RESOLVERS`
(`cond.above`/`cond.below`). Threshold zorunlu (override), source default `close`. +28 test,
review APPROVE 0/0, migration yok. Kalan condition işi: `indicator_output_plus_condition`,
zengin primitive'ler (crosses, indicator-vs-indicator, ranges). Aşağıdaki **keşif bölümü
tarihsel referans** olarak duruyor.

### Keşif (tarihsel — (b) için, artık LANDED)

**KEŞİF (bu oturumda çıkarıldı — taze oturum tekrar keşfetmesin):**

- **Şema hazır (dokunma):** `domain/strategy/config.py` — `IndicatorBlock.trigger_source ∈
  {indicator_native_trigger, indicator_native_trigger_plus_condition,
  indicator_output_plus_condition}` (son ikisi bugün unresolved). `IndicatorBlock` içinde iç içe
  `condition_blocks: list[ConditionBlock] | None` + `condition_block_rule`
  (`required_condition_blocks_only` / `required_plus_any_supporting` /
  `required_plus_min_supporting` / `required_plus_all_supporting`) + `min_supporting_condition_count`.
  `ConditionBlock` = pinned **condition** `package_ref` (ayrı `condition` paket tipi,
  `domain/package/kind.py`) + `requirement` (required/supporting) + `validity` penceresi +
  `parameter_overrides`.
- **Bugünkü davranış:** `application/queries/indicator_plan.py::_resolve_block` (satır ~106)
  `trigger_source != "indicator_native_trigger"` → `trigger_source_deferred:<source>` unresolved;
  `condition_blocks` hiç okunmuyor.
- **KRİTİK — condition primitive katmanı SIFIRDAN gerekli:** bugün seed'li **hiç `cond.*`
  canonical key yok** — `indicators.py`/ESP registry yalnız `ta.*` seed'i içeriyor
  (`apps/seed.py::_ESP_TA_RESOLVERS`). Bu yüzden (b) = (1) yeni `cond.*` key ailesi + compute
  (threshold-only) + ESP seed (`apps/seed.py`), (2) plan resolution — `..._plus_condition`
  trigger'ları için `condition_blocks`'u dereference edip condition spec'lere çöz
  (`indicator_plan.py`), (3) engine gating — `BlockEvaluator`/`aggregate`'i "native trigger
  AND condition(lar) doğru" + `condition_block_rule` aggregation uygulayacak şekilde genişlet
  (`indicators.py` + `engine.py`), (4) testler (unit compute + plan resolution integration +
  engine gating + e2e yayınlanmış condition paketi).
- **Karar (taze oturumda):** `indicator_output_plus_condition` (native trigger yok, sadece
  condition sinyali) de mi kapsanacak, yoksa ilk sürüm `indicator_native_trigger_plus_condition`
  (native trigger + condition gate) ile mi sınırlı? Threshold semantiği reproducibility sabiti
  olmalı (parametre override yoksa engine-version default), ENGINE_VERSION bump gerekir.

## Yöntem (değişmedi)

- Workflow KULLANMA — doğrudan yaz; YENİ dosya Bash heredoc (gate-free), mevcut dosya Edit 4-fact.
- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  izole DB'de `uv run pytest --no-cov -q` (**1048 yeşil kalmalı**); migration gerekirse
  `0022_*` (→0021) up/down/up + parity + L1 FK proof.
- code-reviewer subagent → CRITICAL/HIGH **AMPİRİK DOĞRULA** (8a: 0; 8b: 2/2 GERÇEK; auth: 0;
  parquet: 1/1 GERÇEK; engine Slice B: 1 CRITICAL/1 GERÇEK — oran değişken, HER ZAMAN doğrula) →
  commit (conventional, attribution YOK) → PR → `gh pr checks --watch` → merge için kullanıcıya
  sor. Türkçe, MALİYET BİLİNÇLİ.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — post-V1 TIER 2 devam. STALE-BY-DEFAULT: Strategy Details (PR #117) + kapanış docs
(PR #118) MERGE EDİLDİ varsayma, git'ten doğrula.

ÖNCE DOĞRULA: git fetch && git log --oneline origin/main -6 && gh pr list --state all -L 8.
main = fcbbfb6 (Merge #117) olmalı; docs #118 merge sonrası daha ileri (açıksa önce merge iste).
alembic head 0021_local_auth (DEĞİŞMEDİ); ENGINE_VERSION = backtest-engine-v2-position-size-limits
(DEĞİŞMEDİ). Backend 1048 test, frontend 197. Yeni branch'i MUTLAKA origin/main'den aç.

ÖNCE OKU (authority order): docs/POST_V1_KICKOFF.md (en üst "Durum" bloğu — PR #117 + "SIRADAKİ İŞ
ADAYLARI" + en alttaki resume) → docs/STAGE2_HANDOFF.md ("Strategy Details page landed (PR #117)"
+ "## Next") → CLAUDE.md "Current position".

DURUM: TIER 1 backend EFEKTİF TAMAM. Packages & Data grubu TAM (#97/#99/#101/#103/#105/#107/#109);
BACKTEST GRUBU KAPANDI (#72/#74/#111/#113); DOCS GRUBU KAPANDI (#82/#115); Workspace'te Strategy
Details #117 landed (YENİ — routes/strategy.py 9/9 endpoint /strategy'ye bağlandı; lib/strategy.ts
["strategy"] hook'ları; AMPİRİK: PATCH/save/clear OCC BODY-form expected_draft_row_version INT
[body If-Match'e galip; ZORUNLU; draft row_version 0'dan başlar — 0 geçerli token; stale → 409
STRATEGY_DRAFT_CONFLICT verbatim] + taze Idempotency-Key; validate body/header OKUMAZ [saf
compiler pass, audit YOK → Idem YOK, invalidation YOK]; create OCC'siz + display_name
command-REQUIRED; save bağlı Mainboard item'larını re-pin eder →
["strategy"]+["mainboard"]+["readiness"]+["audit"] invalidate; bloklu save 422 details'te compiler
issue listesi {field,code,message} verbatim; draft_id bağımsız stratdraft ULID — root→draft lookup
YOK → draft handle URL'de [?draft=]; /strategies/{root}/revisions BARE LIST; PayloadEditor
key={row_version} remount-reseed; mutation state PARENT DraftWorkbench'te; App.tsx REAL_PATHS
20→21, nav 24 sabit; +8 vitest → 197). Önceki landed: login #65, SSE #67, /v1/metrics #69,
RUN/History #72, Arrange Metrics + Analysis Lab #74, Panel #78, compare/rebind #80, Future Dev
#82, provisioning #84, Trash #86, auth-invalidation #88, CP #91/#93, capability POST'ları #95,
User Manual #115. BACKEND: first-Admin bootstrap #76 + bootstrap-status #84 + CP-Gen #89 (LLM YOK).

SIRADAKİ İŞ (BAŞLARKEN KULLANICIYLA TEYİT ET — henüz teyitli DEĞİL): kalan 3 placeholder sayfa —
HEPSİ Workspace (hepsinin V1 backend yüzeyi landed): trading_signal.py + trade_log.py (6+6
endpoint, neredeyse simetrik ikizler — source-asset → 202 import → create → revisions → read; tek
slice'ta ikisi mantıklı) / outsource-signal; VEYA ESP registry MUTASYON slice'ı (esp.py
create/activate/deprecate — Admin-only, X-Registry-Version OCC — Rationale shared-editing /
marketData postWithOcc deseni TABAN; library.py 2/2 zaten bağlı). Hangisi seçilirse: route
İMZALARINI ÖNCE OKU (OCC/Idem her endpoint'te olmayabilir — PR #105/#111/#113/#115/#117 dersleri:
successor/deprecate header okumuyordu; readiness token composition FINGERPRINT BODY-form'du;
allocation OCC'si BODY-form expected_row_version'dı + sync POST'u pure read'di; manual'da İKİ
farklı body-form token vardı [stream_version INT / head_revision_id STR] + DELETE body'liydi +
:restore require_trash_admin'di; strategy'de validate HİÇBİR ŞEY okumuyordu + draft row_version
0'dan başlıyordu + revisions BARE LIST'ti) + queries/commands dönüş dict'lerini oku → wire tipleri
VERBATIM ayna. TIER 3 deferred: retention auto-purge, data-queue redelivery, SSE streaming e2e,
tool-call status shadowing.

DÜRÜST SINIR (KALICI): ["jobs"] backend liste yüzeyi YOK; ham baytlar sayfadan geçmez (manual
upload UTF-8 METİN taşır — route sözleşmesi content: str; PDF/DOCX V1 değil); view dataset
/ analysis artifact READ yüzeyi YOK; bundle compiler'lar pure read (kalıcı read yüzeyi yok);
capability/CP/library/esp/rationale/market-data/research-data/readiness/allocation/manual/
strategy'nin özel SSE event'i yok (resource.changed süpürür); get_manual_section HTTP'ye route
edilmemiş (Agent Tool Gateway); strateji LIST + root→draft lookup endpoint'i YOK (draft handle
create anındaki ?draft= URL'i); Mainboard ATTACH Stage-3a operasyonu (hiçbir landed sayfada
değil). RUN admission RUN sayfasında kalır (doc 14 §9.3); Portfolio/ReadyCheck/Strategy yalnız
default Mainboard composition'ını okur; Trash purge ayrı re-auth slice'ı.

FRONTEND STACK: Vite 8 + React 18 + react-router 6 + @tanstack/react-query 5 + react-hook-form +
vitest/jsdom + @testing-library. Alias @ = src; kök frontend/src/. react-query v5 →
invalidateQueries({queryKey}) object-form. tsconfig noUncheckedIndexedAccess AÇIK,
exactOptionalPropertyTypes KAPALI. Composition girişi: lib/backtest.ts useDefaultMainboard
(workspace_id = composition_id, composition_hash = current fingerprint, ready_summary); OCC/Idem
taze örnekler: lib/strategy.ts (BODY-form INT token + tokensız saf validate POST'u) + lib/manual.ts
(İKİ body-form token: stream_version INT + head_revision_id STR; DELETE body'li) +
lib/allocation.ts (body-form OCC) + lib/readiness.ts (fingerprint OCC) + lib/marketData.ts
postWithOcc (If-Match "rv-N").

YÖNTEM: Workflow KULLANMA; direct-author. Frontend loop: cd frontend (absolute path) &&
npm run typecheck && npm run lint && npm test && npm run build (197 + yeniler geçmeli) + yeni
component/unit test (test/helpers/apiStub.ts reuse — SIRALI eşleşme: detay/aksiyon route'u liste
prefix'inden ÖNCE; zincirleme yükleme için findBy* kullan, senkron getBy* değil; çift metin riski
olan assert'leri within ile scope'la ya da tekil değere bağla). YENİ dosya heredoc (gate-free);
mevcut dosya Edit → GateGuard 4-fact (importer Grep / public-API / data-schema / user-request
verbatim → gate İLK denemeyi bloklar → aynı çağrıyı aynen tekrarla; aynı dosyaya 2.+ edit gate-siz;
ARAYA mesaj/tool girerse gate RESETLENİR); ilk Bash da fact-gate'li; Edit öncesi dosyayı Read et.
CRITICAL/HIGH AMPİRİK doğrula (route/command imzasını OKU — handoff özeti yanlış olabilir) →
commit (conventional feat(post-v1), branch feat/post-v1-frontend-<slug> origin/main'den, attribution
YOK) → PR → CI background poll (gh pr checks <n> --watch) → merge KULLANICIDA (self-merge BLOKLU).
Türkçe, MALİYET BİLİNÇLİ. Kapanışta: handoff + kickoff (resume tazele) + CLAUDE.md + ecc
knowledge-graph (claude-mem manuel checkpoint worker runtime'da YAZILAMAZ — otomatik yakalanır,
deneme).
```
