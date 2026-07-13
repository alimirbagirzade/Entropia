# Entropia — Post-V1 Spec-Gap Backlog, ROUND 2

> **Kaynak:** 2026-07-13, GAP-01..23 (PR #152–177) merge edildikten SONRA yapılan ikinci
> kapsamlı spec-vs-implementation denetimi (6 paralel read-only ajan, her bulgu grep+read
> ile ampirik `file:line` kanıtlı). Kod tabanı = `main` @ `05e76e4`, alembic head `0028`
> (lineer, tek head). Bu tur, 27 GAP fix'inin **gerçekten doğru/tam** kapatıp kapatmadığını
> denetledi.
>
> **Sonuç:** Çoğu fix CLEAN (GAP-01/02/03/04/05/09/11/13/15/17/18/20/21/22 + migration zinciri).
> Aşağıdaki 9 madde (R1–R9) **hâlâ açık** olan gerçek işlerdir — bir kısmı GAP fix'inin yarım
> kalması, bir kısmı hiç ele alınmamış eksik.
>
> **Amaç:** Her bölüm ayrı bir sohbete **paste-ready** çalışma birimidir; ayrı `feat/…` branch +
> ayrı PR. Bu dosya fix DEĞİL, backlog'tur.

## Çalışma kuralları (ortak)
- Direct-author (Workflow yok), önceki slice desenini aynala (one-tx no-commit, `run_idempotent`,
  `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- Her CRITICAL/HIGH bulgusunu fix'ten önce ampirik doğrula.
- Backend verify: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q`
  \+ migration varsa alembic up/down/up (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`)
  \+ migration↔model parite. İzole DB: `TEST_DATABASE_URL=...entropia_<slug>`.
- Frontend verify: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`.
- Git: `feat/<slug>`; commit `<type>(<slug>): <subject>`; **NO AI attribution**; PR aç → checks → self-merge yok, kullanıcıdan merge iste.

## Önerilen sıra (değer/maliyet)
R4 (ucuz, sessiz bug) → R3 (correctness, motora besleniyor) → R7 (ucuz, ölü state) → R5 (lab konuşma) →
R8 (ESP evidence) → R9 (research validation) → R6 (strategy form, büyük) → R1 (instrument wiring, büyük) →
R2 (Library aksiyonları, epic).

---

## R4 — Panel Logs: resource_type filtre listesi drift (sessiz boş sonuç) 🟠
**Boyut:** Küçük (frontend-only). **Öncelik:** İlk (ucuz, gerçek fonksiyonel bug).

**Doğrulanan durum:** `frontend/src/lib/adminPanel.ts:156` `LOG_RESOURCE_TYPES` elle kürlenmiş ve server'ın
gerçek `target_entity_type` string'lerinden sapmış. Server filtresi TAM eşleşme
(`application/queries/log_projection.py:98` `AuditEvent.target_entity_type == resource_type`). 10 seçeneğin 6'sı
hiç eşleşmiyor → operatör seçince **sessizce boş log**, hata yok:
`user`→gerçek `human_user` · `package_revision`→`package` · `dataset_revision`→`market_dataset`/`research_dataset` ·
`artifact`→`analysis_artifact`/`hypothesis_artifact`/`export_artifact`/`view_dataset` · `allocation_plan`→`portfolio_allocation_plan` ·
`system`→(yok). Çalışanlar: `strategy`, `backtest_run`, `backtest_result`, `manual_document`.

**Kapsam:** `LOG_RESOURCE_TYPES`'ı gerçek `target_entity_type` değerleriyle değiştir. İdeali: backend'in distinct
`target_entity_type` kümesini bir endpoint'ten hydrate et (role-matrix deseni) → drift bir daha olmaz. +drift'i
yakalayan test (her `LOG_RESOURCE_TYPES` değeri gerçek bir emitted target olmalı).

**Paste-ready prompt:**
```
Entropia — R4: Panel Logs resource_type filtre drift. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R4, mevcut frontend/src/lib/adminPanel.ts:156 (LOG_RESOURCE_TYPES) +
application/queries/log_projection.py:98 (exact match) + gerçek emitter'lar (role_assignment.py human_user,
package _TARGET_KIND, market/research repo ENTITY_TYPE, portfolio_allocation_plan _PLAN_TARGET). Ampirik doğrula:
10 seçenekten 6'sı eşleşmiyor. Fix: LOG_RESOURCE_TYPES'ı gerçek target_entity_type değerlerine güncelle (ya da
backend distinct-set endpoint + hydrate). +vitest (her opsiyon gerçek target). Frontend verify.
feat/r4-logs-resource-type-drift, ayrı PR, NO AI attribution.
```

---

## R3 — Cross-row market-data validation (doc 11 §7.4) 🟠
**Boyut:** Orta (backend job). **Öncelik:** Yüksek (correctness — artık para-boyutlandıran motora besleniyor).

**Doğrulanan durum:** `application/jobs/market_data.py` OHLCV'yi **yalnız per-row** doğruluyor (`validate_ohlcv_row`,
ör. high≥low). Cross-row hiç yok: timestamp monotonluğu, duplicate-timestamp, cadence-gap, tick sıralaması,
spread-unit. `grep monoton|duplicate.*timestamp|gap` = 0. Sonuç: non-monotonik/duplicate/gap içeren bir dataset
APPROVED olabilir ve **GAP-02 allocation-execution motoruna** (para boyutlandırma) beslenir → sessizce yanlış
equity eğrisi. NOT: GAP-14 yanlış kapsanmıştı — strategy semantic check ekledi (`domain/strategy/compiler.py`),
market/research değil.

**Kapsam:** `jobs/market_data.py::evaluate_rows`'a cross-row aggregate katmanı: timestamp monotonluk (BLOCKER),
duplicate (instrument+ts+resolution) (BLOCKER), cadence-gap tespiti (WARNING/coverage slice — `add_coverage_slice`
zaten var ama çağrılmıyor), spread-unit tutarlılığı. Doc 11 §7.4 severity'lerine uy.

**Verify:** integration — non-monotonik/duplicate dataset → BLOCKER, APPROVED olamaz; temiz dataset → PASSED.

**Paste-ready prompt:**
```
Entropia — R3: Cross-row market-data validation. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R3, doc 11 §7.4, mevcut jobs/market_data.py (per-row only) +
domain/market_data/validation_rules.py + repo add_coverage_slice (çağrılmıyor). Ampirik doğrula: cross-row check
yok. Fix: evaluate_rows sonrası cross-row aggregate — monotonluk/duplicate BLOCKER, cadence-gap coverage slice,
spread-unit. NOT: bu artık GAP-02 para-motoruna besleniyor, correctness kritik. +integration (kirli→BLOCKER/
temiz→PASSED). Backend verify. feat/r3-market-crossrow-validation, ayrı PR, NO AI attribution.
```

---

## R7 — Ölü CreatePackage state'leri: EXPERIMENTAL + SUPERSEDED 🟠
**Boyut:** Küçük. **Öncelik:** Orta (ya wire ya sil — teknik borç).

**Doğrulanan durum:** GAP-07 3 ölü state'i canlandırdı (`VALIDATION_RUNNING`/`ELIGIBLE_FOR_APPROVAL`/`REVISION_REQUIRED`)
ama `state_machine.py:85,93,98` `EXPERIMENTAL` ve `:109` `APPROVED→SUPERSEDED` legal edge'leri var, **hiçbir komut
geçmiyor** (`grep next_request_state.*EXPERIMENTAL` = 0). "4 ölü state canlandı" iddiası aslında 3/4.

**Kapsam:** İki karar: (a) EXPERIMENTAL'a geçiren bir komut/akış (doc 06 experimental yayın yolu) wire et VEYA
(b) kullanılmayacaksa state_machine'den edge'leri + enum değerlerini kaldır. SUPERSEDED için: yeni approve bir
öncekini SUPERSEDED yapmalı mı? (doc 06'ya bak). Slice başında spec'e göre karar ver.

**Paste-ready prompt:**
```
Entropia — R7: Ölü CreatePackage state'leri (EXPERIMENTAL/SUPERSEDED). Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R7, doc 06 (experimental/superseded semantiği), mevcut
domain/create_package/state_machine.py:85,93,98,109 + application/commands/create_package.py. Ampirik doğrula:
EXPERIMENTAL/SUPERSEDED'e geçen komut yok. Karar ver (spec'e göre): wire et ya da edge+enum'ı sil. Uygula.
+test. Backend verify. feat/r7-createpackage-dead-states, ayrı PR, NO AI attribution.
```

---

## R5 — Analysis Lab Conversation kartları paneli (doc 18 §3.2) 🟠
**Boyut:** Küçük-Orta (orphan-close deseni). **Öncelik:** Orta.

**Doğrulanan durum:** GAP-12 task/hypothesis geçmişini bağladı ama doc 18 §3.2 Lab Conversation paneli
(assistant/message/directive/system tipli read-only kartlar) yok. Sadece `POST /lab/messages` var; GET list /
`list_lab_messages` query yok; `pages/AnalysisLab.tsx:625` yalnız son assistant yanıtını inline gösteriyor.
Yazılan-ama-okunamayan log — PR #144/#146 orphan-close deseni.

**Kapsam:** `queries/agent_workspace.py::list_lab_messages` (task-scoped, bounded newest-first, role-gated) +
`GET /agent-tasks/{id}/messages` (ya da `/lab/messages?task=`) + frontend `useLabMessages` (`["agent-tasks"]`) +
AnalysisLab konuşma kartları (§3.2 tip/tag/time/text). Write path değişmez.

**Verify:** integration (persisted messages → list; cross-owner not-found) + vitest.

**Paste-ready prompt:**
```
Entropia — R5: Analysis Lab Conversation kartları paneli. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R5, doc 18 §3.2, mevcut commands/lab_message.py (yazıyor) +
queries/agent_workspace.py (list yok) + routes/agent_lab.py + pages/AnalysisLab.tsx:625. Orphan-close deseni
(#144/#146 template: projection + gated GET, write aynı). Fix: list_lab_messages query + GET route + useLabMessages
hook + AnalysisLab konuşma kartları (assistant/message/directive/system). +integration + vitest.
Backend+frontend verify. feat/r5-lab-conversation-cards, ayrı PR, NO AI attribution.
```

---

## R8 — ESP validation-run planı (doc 09 §7) 🟠
**Boyut:** Orta. **Öncelik:** Orta.

**Doğrulanan durum:** GAP-07c inversion'ı düzeltti — `activate_resolver` artık `validation_state=PASSED`
damgalamıyor (`esp.py:222-226` yorumu açık), `_ensure_activation_evidence` (`esp.py:366`) evidence **varlığını**
`ResolverEvidenceRequired` ile kontrol ediyor. AMA evidence sadece presence-checked, **PASS doğrulaması yok**
(`esp.py:200-204` docstring: validation-run planı "out of scope"). Komutla aktive edilen resolver `validation_state`
`pending`'de kalıyor. Doc 09 §7 ("tek başarılı örnek yeterli evidence değildir") yalnız kısmen sağlanıyor.

**Kapsam:** ESP için validation-run planı — test-vector'ları gerçekten çalıştırıp `validation_state`'i `passed`'a
taşıyan bir komut/job; aktivasyon gate'ini presence yerine PASS'e bağla.

**Paste-ready prompt:**
```
Entropia — R8: ESP validation-run planı. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R8, doc 09 §7, mevcut commands/esp.py:185-262,366-378 (evidence presence-only).
Ampirik doğrula: validation_state passed'a taşıyan run yok, aktivasyon presence-check. Fix: ESP validation-run
command/job (test-vector çalıştır → validation_state=passed) + aktivasyon gate'ini PASS'e bağla. +test.
Backend verify (migration gerekebilir → alembic up/down/up). feat/r8-esp-validation-run, ayrı PR, NO AI attribution.
```

---

## R9 — Research Data semantic validation derinliği (doc 12 §10) 🟡
**Boyut:** Orta. **Öncelik:** Orta-Düşük.

**Doğrulanan durum:** `jobs/research_data.py::evaluate_research` sığ — yalnız "≥1 native field" (schema integrity) +
time-policy. Doc 12 §10 daha derin semantik check'ler (duplicates, coverage, nulls, types, ranges, instrument mapping)
yok.

**Kapsam:** doc 12 §10 check ailelerini `evaluate_research`'e ekle (market ingest deseni). Severity'lere uy.

**Paste-ready prompt:**
```
Entropia — R9: Research Data semantic validation. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R9, doc 12 §10, mevcut jobs/research_data.py::evaluate_research (sığ).
Fix: eksik check ailelerini ekle (duplicates/coverage/nulls/types/ranges/instrument). +integration. Backend verify.
feat/r9-research-validation-depth, ayrı PR, NO AI attribution.
```

---

## R6 — GAP-08 strategy form: package-graph bölümleri + logic-based stop 🟡
**Boyut:** BÜYÜK (frontend; indicator/condition package-picker gerektirir). **Öncelik:** Orta-Düşük.

**Doğrulanan durum:** GAP-08 flat §5 bölümlerini (Data&Execution, Protection, Sizing, Conflict) gerçek structured form +
~23 ⓘ panel olarak getirdi. AMA package-graph bölümleri — **§5.3 Position Entry Logic, §5.4 Exit Logic, §5.7 Scaling,
§5.8 Restrictions/Filters + §5.5 logic-based stop block** — hâlâ raw JSON textarea'da (`StrategyDetails.tsx:327` yorumu;
`strategyForm.ts:4-8`). ~70 panelli §5/§6 katalog kısmen yüzeyde.

**Kapsam:** package-graph bölümlerini structured form'a ekle — indicator/condition **package-picker** komponenti
(Library'den usable paketleri seçme) + §5.3/5.4/5.7/5.8 alan UI + logic-based stop block + ilgili ⓘ paneller.
JSON textarea gerçek fallback'e döner.

**Paste-ready prompt:**
```
Entropia — R6: GAP-08 strategy form package-graph bölümleri. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R6, doc 02 §5.3/5.4/5.5/5.7/5.8 + §6, mevcut components/StrategyConfigForm.tsx +
lib/strategyForm.ts + pages/StrategyDetails.tsx:327 (JSON escape hatch). Fix (frontend, büyük): indicator/condition
package-picker + Entry/Exit Logic/Scaling/Restrictions structured alanları + logic-based stop + ⓘ paneller; JSON
textarea gerçek fallback. Alt-sekme PR'larına bölünebilir. +vitest. Frontend verify. feat/r6-strategy-form-graph,
ayrı PR(lar), NO AI attribution.
```

---

## R1 — Instrument Registry çözümlemesini akışlara bağla 🔴
**Boyut:** BÜYÜK (cross-cutting). **Öncelik:** Yüksek (GAP-16'nın asıl amacı).

**Doğrulanan durum:** GAP-16 kanonik registry + resolver + tablo (`0027`) + `/instruments` sayfasını getirdi ve
`resolve_scope` fail-closed çalışıyor. AMA çözümlemenin tek çağrısı `commands/market_data.py:128` (o da opt-in,
`instrument_scope` default None). **Strategy save/compile, `commands/trading_signal.py:183/211`,
`commands/trade_log.py:187/215`, readiness = free-text `instrument_id`.** TS/TL config'i zaten bir `instrument_scope`
objesi taşıyor ama registry'ye reconcile edilmiyor. Asıl hedef (BTCUSD-spot vs BTCUSDT-perp belirsizliğini öldürmek)
4 yüzeyin 3'ünde açık.

**Kapsam:** `resolve_scope`'u TS import, TL import, strategy save/compile ve readiness path'lerine bağla; free-text
scope tek kanonik instrument'a çözülsün, unresolvable → 422 fail-closed. TS/TL'nin mevcut `instrument_scope`
payload'ını gerçek çözüm noktasına yönlendir.

**Verify:** integration — aynı sembolde spot vs perpetual strategy/TS/TL'de **farklı** instrument_id'ye çözülür;
unresolvable → 422.

**Paste-ready prompt:**
```
Entropia — R1: Instrument Registry çözümlemesini akışlara bağla. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R1, doc 02/04/05/11 instrument scope, mevcut queries/instrument.py::resolve_scope
(fail-closed) + tek çağrı commands/market_data.py:128 + commands/trading_signal.py:183/211 + trade_log.py:187/215
(free-text). Ampirik doğrula: resolver strategy/TS/TL/readiness'te çağrılmıyor. Fix: resolve_scope'u bu 4 akışa bağla
(unresolvable→422 fail-closed); TS/TL instrument_scope payload'ını gerçek çözüme yönlendir. +integration (spot vs
perp aynı sembol → farklı instrument_id). Backend verify. feat/r1-instrument-registry-wiring, ayrı PR, NO AI attribution.
```

---

## R2 — Package Library aksiyonlarını tamamla (GAP-06 devamı) 🔴
**Boyut:** BÜYÜK (epic; alt-slice'lara böl). **Öncelik:** Yüksek.

**Doğrulanan durum:** GAP-06 sadece **Deprecate + Move-to-Trash** getirdi. doc 08 §4.3 aksiyon setinden eksik:
**Derive (package), Create Revision, Request Approval, Export (package manifest).** `permissions.py:6-13,55-66`
`can_derive`/`can_create_revision`/`can_request_validation`/`can_request_approval`/`can_export` flag'lerini hesaplıyor
ama **hiçbir hook/endpoint tüketmiyor** → orphan flag'ler yapılamayan aksiyonu reklam ediyor. **Latent bug:**
`can_approve_publish` `approval_state==APPROVAL_REQUESTED` gerektiriyor ama hiçbir komut o state'e geçirmiyor →
Library-plane Admin approve hiç aktifleşemez. Request Validation / Approve&Publish yalnız CreatePackage-request
planında var, Library'ye bağlı değil.

**Kapsam (alt-slice'lara böl):**
- **R2a:** `derive_package` (paketten paket türet) + `create_package_revision` (Library-plane) komut+route+UI.
- **R2b:** `request_approval` komutu (→ `ApprovalState.APPROVAL_REQUESTED` set eder, `can_approve_publish` latent bug'ını da açar) + Library-plane approve wiring.
- **R2c:** package-manifest `export_package` komut+route+UI (result_export DEĞİL — paket revision manifest'i).
- Her biri OCC (`row_version`/ETag) + Idempotency + policy server-side re-check + audit/outbox. UI pre-gate etmez.
- Ayrıca: orphan `can_*` flag'lerini ya tüket ya emit etmeyi durdur (UI yapılamayan aksiyon göstermesin).

**Verify:** her komut için integration (yetkili→başarı+provenance / yetkisiz→403 / stale→409) + vitest.

**Paste-ready prompt:**
```
Entropia — R2: Package Library aksiyonlarını tamamla (GAP-06 devamı). Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND2.md R2, doc 08 §4.3/§7/§14, mevcut domain/package/permissions.py (orphan flag'ler +
can_approve_publish latent bug) + application/commands/package_lifecycle.py (sadece deprecate+soft_delete) +
routes/library.py + lib/library.ts. Ampirik doğrula: derive/create_revision/request_approval/export komutları yok;
can_approve_publish'i açacak APPROVAL_REQUESTED transition'ı yok. Fix (alt-slice'lara böl): R2a derive_package+
create_package_revision, R2b request_approval(→APPROVAL_REQUESTED, latent bug'ı açar)+approve wiring, R2c export_package
manifest (result_export DEĞİL); her biri OCC+Idempotency+policy+audit, UI pre-gate yok; orphan can_* flag'lerini
tüket ya da emit etme. +integration+vitest. Backend+frontend verify. feat/r2-library-actions-*, ayrı PR'lar, NO AI attribution.
```

---

## LOW (opsiyonel, tek satırlık)
- **Export 201 vs "202 admission" yorumu** (`routes/result_export.py` / `ResultDetail.tsx`) — yorumu senkron 201 davranışına hizala.
- **GAP-18 structured HTTPException detail** — `raise HTTPException(detail={...})` callsite'ı yok; naming/envelope testine bir grep-guard ekle ki oluşmasın.
- **GAP-15 gözlemlenebilirlik** — single-flight collapse'ı için debug sayaç/log (prod'da dedup'ı doğrulamak için).
