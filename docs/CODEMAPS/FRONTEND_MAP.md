# FRONTEND_MAP — sayfa / lib / query-key haritası

React 18 + Vite + react-router 6 + `@tanstack/react-query` 5.
Router: `frontend/src/App.tsx` (`REAL_PATHS:39`, rotalar `:73-346`). Nav: `frontend/src/app/nav.ts`.
Import alias: `@/` → `frontend/src/`.

---

## Sayfalar (31 dosya `pages/*.tsx`, 40 dosya `lib/*.ts` — 2026-07-29 ampirik)

| Route path | Sayfa | Kullandığı `lib/*` | react-query key prefix | Backend endpoint grubu |
|---|---|---|---|---|
| `/login` `App.tsx:73` | `Login.tsx` | `auth`, `apiClient` | (mutasyon; `["me"]` invalidasyonu) | `routes/auth.py` |
| `/` (index) `:79` | `Mainboard.tsx` | `mainboard`, `backtest`, `strategy` | `["mainboard"]`, `["readiness"]`, `["audit"]`, `["trash"]` | `routes/mainboard.py` |
| `/packages/create` `:85` | `CreatePackage.tsx` | `createPackage` | `["package-requests"]`, `["rationale-families"]` (+ **`"suggest"`** alt anahtarı — `pages/CreatePackage.tsx:502`'deki chip'ler; bir chip'e tıklamak **yalnız seçiciyi doldurur**, Family yaratmaz), `["audit"]` | `routes/create_package.py` (Pre-Check + C.D.P + validation + baseline-parse = **admission**, sonuç `resource.changed` refetch'i ile gelir — F-01a/b/c; in-flight kilit `baselineParseRunning`) |
| `/packages/pre-check` `:94` | `PreCheck.tsx` | `createPackage`, `backtest` | `["package-requests"]` | `routes/create_package.py` (scan) |
| `/packages/library` `:103` | `Library.tsx` | `library`, `sharing`, `packageImport`, `createPackage`, `strategy`, `backtest` | `["library"]`, `["package-imports"]`, `["jobs"]`, `["trash"]`, `["audit"]`, **`["package-requests","validation-run",id]`** (G-04: Request Validation admission'ı CP düzlemindeki koşuyu **sarar**, bu yüzden durable durum CP okuma modelinden okunur — Library'ye özel ikinci read model YOK) | `routes/library.py`, `sharing.py`, `package_import.py` |
| `/packages/embedded` `:112` | `Embedded.tsx` | `esp`, `library`, `backtest` | `["esp"]`, `["audit"]` | `routes/esp.py` |
| `/panel` `:122` | → `Navigate` `/panel/management` | — | — | — |
| `/panel/management` `:124` | `PanelManagement.tsx` | `adminPanel`, `hooks`, `backtest` | `["admin"]`, `["audit"]` | `routes/admin_panel.py` |
| `/panel/logs` `:132` | `PanelLogs.tsx` | `adminPanel`, `hooks`, `backtest` | `["audit"]` (hem `events` hem **`backtest-logs`** alt anahtarları) | `routes/admin_panel.py` (`/admin/backtest-logs` **PRIMARY** + `/admin/logs` ikincil), `audit.py` |
| `/panel/provisioning` `:141` | `Provisioning.tsx` | `provisioning`, `hooks` | `["auth"]`, `["me"]` | `routes/auth.py` (bootstrap-status) |
| `/panel/metrics` `:150` | `Metrics.tsx` | `metrics`, `hooks` | `["metrics"]` (5 sn poll) | `routes/metrics.py` (text/plain) |
| `/portfolio` `:159` | `Portfolio.tsx` | `allocation`, `readiness`, `backtest` | `["allocation"]`, `["readiness"]`, `["mainboard"]`, `["audit"]` | `routes/allocation.py` |
| `/backtest/ready-check` `:168` | `ReadyCheck.tsx` | `readiness`, `backtest` | `["readiness"]`, `["mainboard"]` | `routes/readiness.py` |
| `/backtest/run` `:177` | `BacktestRun.tsx` | `backtest`, `mainboard` | `["backtests"]`, `["mainboard","default"]`, `["metric-profile","result-metrics"]` | `routes/backtest.py` |
| `/backtest/history` `:185` | `ResultsHistory.tsx` | `backtest` | `["backtests","history"]`, `["backtests","compare"]` | `routes/results_history.py` |
| `/backtest/metrics` `:194` | `ArrangeMetrics.tsx` | `metricProfile` | `["metric-definitions"]`, `["metric-profile"]` | `routes/metric_profile.py` |
| `/analysis-lab` `:203` | `AnalysisLab.tsx` | `agentLab` | `["agent-tasks"]` (tüm alt anahtarlar) | `routes/agent_lab.py` |
| `/future-dev` `:212` | `FutureDev.tsx` | `capability`, `hooks`, `backtest` | `["capabilities"]`, `["analysis-artifacts"]`, `["view-datasets"]`, `["audit"]` | `routes/capability.py` |
| `/future-dev/graphic-view` `:225` | `FutureDevGraphicView.tsx` | `capability`, `hooks`, `backtest` | `["capabilities","graphic-view-overview"]` | `routes/capability.py` |
| `FUTURE_DEV_SUBPAGES[*].path` `:236` | `FutureDevCapability.tsx` | `capability`, `backtest` | `["capabilities","detail"]` | `routes/capability.py` |
| `/user-manual` `:247` | `UserManual.tsx` | `manual`, `trash` | `["manual"]`, `["trash"]`, `["audit"]` | `routes/manual.py` |
| `/trash` `:256` | `Trash.tsx` | `trash`, `auth`, `backtest` | `["trash"]`, `["audit"]` | `routes/trash.py` |
| `/rationale-families` `:265` | `RationaleFamilies.tsx` | `rationale`, `backtest` | `["rationale-families"]`, `["rationale-assignments"]`, `["audit"]` | `routes/rationale.py` |
| `/market-data` `:274` | `MarketData.tsx` | `marketData`, `upload`, `backtest` | `["market-data"]`, `["audit"]` | `routes/market_data.py` |
| `/research-data` `:283` | `ResearchData.tsx` | `researchData`, `upload`, `backtest` | `["research-data"]`, `["audit"]` | `routes/research_data.py` |
| `/instruments` `:292` | `Instruments.tsx` | `instrument` | `["instruments"]`, `["audit"]` | `routes/instrument.py` |
| `/strategy` `:301` | `StrategyDetails.tsx` | `strategy`, `mainboard`, `createPackage`, `backtest` | `["strategy"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` | `routes/strategy.py` |
| `/outsource-signal` `:310` | `OutsourceSignal.tsx` | **hiçbiri** (saf sunum, tip seçici) | — | — (backend router yok) |
| `/trading-signal` `:319` | `TradingSignal.tsx` (ince wrapper) → `components/TradingSignalEditor.tsx` (`mode="page"`) | `tradingSignal`, `backtest` | `["trading-signals"]`, `["jobs","trading-signal-import"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` | `routes/trading_signal.py` |
| `/trade-log` `:328` | `TradeLog.tsx` (ince wrapper) → `components/TradeLogEditor.tsx` (`mode="page"`) | `tradeLog`, `backtest` | `["trade-logs"]`, `["jobs","trade-log-import"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` | `routes/trade_log.py` |
| `*` `:346` | `NotFound.tsx` | — | — | — |
| (nav item, `REAL_PATHS` dışı) `:338` | `Placeholder.tsx` | — | — | — |

---

## `lib/*.ts` → query key prefix'leri (gözlemlenen `queryKey` literalleri)

| lib modülü | Okuma anahtarları | Mutasyonun invalidate ettikleri |
|---|---|---|
| `adminPanel.ts` | `["admin","users",cursor]`, `["admin","system-actors"]`, `["admin","role-matrix"]`, `["audit","events",cursor]`, `["audit","log",eventId]`, `["audit","resource-types"]`, **`["audit","backtest-logs",cursor]`** (`:334` → `GET /admin/backtest-logs`, P-14 PRIMARY görünüm) | `["admin"]`, `["audit"]` |
| `agentLab.ts` | `["agent-tasks",...]` — `overview`/`list`/`detail`/`messages`/`hypotheses`/`tool-calls`/`tool-call`. **G-05:** iki tool-call okuması sunucuda `AgentToolCallListResponse` / `AgentToolCallDetailResponse` ile yayımlandı; `AgentToolCallCard` (13 alan) ve `AgentToolCallDetail` (kart + 6) TS tarafıyla **birebir** eşleşiyor. `request` / `response_ref` bilerek açık `Record<string, unknown>` kalır — `response_ref` `tool_name` ile ayrışır ve arkasındaki komutun dönüşünü aynen taşır | `["agent-tasks"]` |
| `allocation.ts` | `["allocation","draft",compositionId]` | `["allocation"]`, `["readiness"]`, `["mainboard"]`, `["audit"]` |
| `backtest.ts` | `["backtests","run"\|"result"\|"history"\|"compare"\|"artifact"]`, `["mainboard","default"]`, `["metric-profile","result-metrics",resultId]` | `["backtests"]`, `["audit"]` |
| `capability.ts` | `["capabilities",...]`, `["view-datasets",...]`, `["analysis-artifacts",...]` | `["capabilities"]`, `["audit"]` |
| `createPackage.ts` | `["package-requests",...]` (`list`/`detail`/`scan`/`validation-run`/`baseline-asset`), `["rationale-families",cursor]`, **`["rationale-families","suggest",needle]`** (`useRationaleFamilySuggestions:867` → `GET /rationale-families:suggest`; `enabled: needle.length >= 2` — 2 karakterin altında sunucu zaten `[]` döner, round-trip atlanır; `staleTime` 5 dk). **G-04:** `useValidationRun(id, {live})` — `live` verilmezse davranış eskisi gibi (değişmez kanıt, `staleTime` 5 dk, poll yok); `live: true` ise `status` terminal olana (`passed`/`failed`/`stale`) kadar 3 sn poll eder. Poll **birincil sinyal değil**, SSE (`job.updated` + `resource.changed` catch-all) kapalı olduğunda kayıp-toleranslı yedektir (INF-11) | `["package-requests"]`, `["audit"]` |
| `esp.ts` | `["esp","list"\|"detail"]` — **G-05:** `EspPackageDetail` artık sunucunun **R8'den beri gönderdiği** `latest_validation_run`'ı (`EspValidationRunSummary`) tipler; alan daha önce hiç bildirilmemişti. `lifecycle_state` `string \| null`'a **genişletildi** (`entity_registry.lifecycle_state` nullable serbest-metin kolon, enum değil) — Embedded sayfası null'da `UNSTATED_LIFECYCLE_LABEL` basar, asla uydurma `"active"`. Sunucu tarafı `apps/api/schemas/esp.py` ile yayımlanır; parite `backend/tests/contract/test_wire_contract_parity.py` ile makine kontrollüdür. **Dürüst sınır:** `latest_validation_run` henüz hiçbir yerde RENDER edilmiyor — wire tipi bildirmek UI yapmak değildir | `["esp"]`, `["audit"]` |
| `hooks.ts` | `["me"]`, `["meta"]`, `["metrics"]`, `["health","ready"]` | — |
| `instrument.ts` | `["instruments","list"\|"detail"]` | `["instruments"]`, `["audit"]` |
| `library.ts` | `["library","list",filters,cursor]`, `["library","detail",entityId]` — **S-L3:** detay projeksiyonu artık `permissions.can_request_validation` bayrağını da tipler (`:80-103`). **G-04 (bu slice):** `useRequestPackageValidation` → `POST /library/{id}/validation-runs`; OCC **body-form `expected_head_revision_id`** (= ekrandaki head), her submit'te **taze `Idempotency-Key`**, yanıt `RequestValidationResult` (8 alan, iki düzlemin kimliği). `onSuccess` → `["library"]` + `["audit"]` + **`["package-requests"]`** + **`["jobs"]`** (tek koşu iki düzlemden aynı görünsün diye). **Doğrulanmış sınır:** koşu uçuştayken aynı `Idempotency-Key` ile tekrar gönderim **201 replay DEĞİL**, 409 `VALIDATION_ALREADY_RUNNING` verir — wrapper'ın in-flight guard'ı `run_idempotent`'tan önce çalışır; UI bunu recovery yolu olarak render eder (`tests/integration/test_library_validation_run_route.py`). **G-02:** `ExportPackageResult` artık `export_schema_version` + `registry_observation` (`RegistryObservation`) taşır; `useExportPackage`'ın route'u, `Idempotency-Key` üretimi ve `["audit"]` invalidation'ı **değişmedi**. `manifest` bilerek açık `Record<string, unknown>` — artifact kendi şeklini `export_schema_version` ile bildirir, UI verbatim basar **ve `POST /package-imports`'a aynen geri gönderilir** (bir alan düşerse import artifact'i sessizce bozulur). **G-05:** `/library` ve `/library/{id}` dahil dokuz Library ucunun tamamı artık sunucuda `response_model` taşır (`apps/api/schemas/library.py`); `LibraryPackageRow.lifecycle_state` `string \| null`'a **genişletildi** (nullable serbest-metin kolon), `ProvenanceScan.registry_fingerprint`/`context_hash` ise `string`'e **daraltıldı** (kolonlar NOT NULL). `lifecycleTone` artık `string \| null` alır; null etiket `UNSTATED_LIFECYCLE_LABEL` ile basılır. Parite `backend/tests/contract/test_wire_contract_parity.py` ile makine kontrollü | `["library"]`, `["trash"]`, `["audit"]` |
| `mainboard.ts` | (`backtest.ts`'ten re-export `["mainboard","default"]`) | `["mainboard"]`, `["readiness"]`, `["audit"]`, `["trash"]` |
| `manual.ts` | `["manual","stream",cursor]`, `["manual","search",needle,cursor]` | `["manual"]`, `["trash"]`, `["audit"]` |
| `marketData.ts` | `["market-data","registry"\|"detail"\|"approved-bundle"]` | `["market-data"]`, `["audit"]` |
| `metricProfile.ts` | `["metric-definitions"]`, `["metric-profile","resolved"]` | `["metric-profile"]` |
| `packageImport.ts` | `["jobs","package-import",importJobId]` | `["package-imports"]`, `["jobs"]`, `["library"]`, `["audit"]` |
| `provisioning.ts` | `["auth","bootstrap-status"]` (yanıt: `login_capable_admin_exists` — PROV-05/#357) | — |
| `rationale.ts` | `["rationale-families","registry",state,cursor]`, `["rationale-assignments",cursor]` | `["rationale-families"]`, `["rationale-assignments"]`, `["audit"]` |
| `readiness.ts` | `["readiness","current",compositionId]`, `["readiness","report",reportId]` | `["readiness"]`, `["mainboard"]` |
| `researchData.ts` | `["research-data","registry"\|"detail"]` | `["research-data"]`, `["audit"]` |
| `sharing.ts` | `["library","shares",entityId]`, `["library","shared-with-me"]` | `["library"]`, `["audit"]` |
| `strategy.ts` | `["strategy","draft"\|"drafts"\|"root"\|"revisions"\|"revision"]`. Mutasyon: **`POST /strategies/{root}/rationale-family`** (`:350`) — tek seferlik family set'i, **OCC token'ı yok** (`:335` yorumu); UI'daki tetik `components/StrategyDetailsPanel.tsx:186` tek-seferlik picker'ı | `["strategy"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` |
| `tradeLog.ts` | `["trade-logs","root",rootId]`, `["jobs","trade-log-import",jobId]` | `["trade-logs"]`, `["jobs"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` |
| `tradingSignal.ts` | `["trading-signals","root",rootId]`, `["jobs","trading-signal-import",jobId]` | `["trading-signals"]`, `["jobs"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` |
| `trash.ts` | `["trash","entries",q,object_type,cursor]`, `["trash","entry",id]`, **O-17** `["trash","restore-preflight",id]` (staleTime/gcTime 0 — salt-okuma preflight, doc 20 §5/§8.2) | `["trash"]`, `["audit"]` |

**Anahtarsız yardımcı modüller** (hook barındırmaz): `apiClient.ts`, `auth.ts`, `session.ts`,
`devActor.ts`, `queryClient.ts`, `metrics.ts` (Prometheus parser), `sse.ts`, `types.ts`,
`upload.ts`, `strategyForm.ts`, `strategyGraph.ts`.

---

## SSE → react-query invalidation (`lib/sse.ts:27-33`)

| SSE event adı | Invalidate edilen key | Not |
|---|---|---|
| `backtest.run.updated` | `[["backtests"]]` | react-query prefix eşleşir → `["backtests", runId, …]` da kapsanır |
| `job.updated` | `[["jobs"]]` | import raporlarını besleyen tek anahtar |
| `agent.task.updated` | `[["agent-tasks"]]` | Analysis Lab'in tüm alt anahtarları |
| `audit.event.created` | `[["audit"]]` | Panel/Logs |
| `resource.changed` | `[]` → **tam refresh** (`invalidateForEvent:39-43`) | catch-all: strategy, packages, market/research data, portfolio … |

**Kontrol çerçeveleri** (taksonominin **dışında**, `EVENT_QUERY_KEYS`'te yoktur):
`heartbeat` → etkisiz (akış canlı sinyali); `stream.resync` (`STREAM_RESYNC`) → **tam refresh**
(sunucu "veremediğim olaylar var" diyor, O-21).

**Sunucu tarafı projeksiyon** (`apps/api/sse.py:33-44` `sse_event_name`):
`resource_type` `backtest*` → `backtest.run.updated`; `job` → `job.updated`;
`agent*` veya `hypothesis_artifact` → `agent.task.updated`;
`event_type` `audit.` ile başlıyorsa → `audit.event.created`; aksi hâlde → `resource.changed`.

**Reconnect davranışı**: client native `EventSource` **değil** `fetch` stream'i kullanır (AUTH-11 —
kimlik header'da taşınmalı), bu yüzden yeniden bağlanmayı kendi üstel backoff'u yürütür
(`RECONNECT_BASE_MS=1000` → `RECONNECT_MAX_MS=30000`).

**Resume (O-21)**: tarayıcının otomatik `Last-Event-ID` davranışı `fetch` yolunda yoktur, bu yüzden
client işlediği son `id:`'yi kendi tutar ve her yeniden açılışta **`Last-Event-ID` header'ı** olarak
gönderir → sunucu boşluğu outbox'tan replay eder. Boş `id:` cursor'ı silmez; `heartbeat` /
`stream.resync` cursor'ı ilerletmez. Her başarılı yeniden açılıştaki **tam refresh** *fallback olarak
korunur* (ilk bağlantı, resync ve replay penceresini aşan boşluk için) — INF-11 kayıp-toleransı.

---

## Shell iskeleti — `app/Layout.tsx` (her rotanın etrafını saran sabit yapı)

Tek `Layout` her rotayı sarar; sayfalar `<Outlet />` içine düşer. Sırası **anlamlıdır**:

| Sıra | Düğüm | Neden bu sırada |
|---|---|---|
| 1 | `<a class="skip-link" href="#main-content">` | **Shell'in ilk tabbable düğümü** olmak zorunda (K-2 / WCAG 2.4.1). Önüne tabbable bir şey koyarsan kapı kırılır: `src/test/a11ySkipLink.test.tsx`. CSS'te **iki durumda da `position:absolute`** — akıştan çıkmadığı an 23 görsel baseline kayar; `position:fixed` yaparsan `offsetParent` null olur ve precheck probu linki hiç görmez |
| 2 | `<header class="top-title">` | `AuthControl` (eski ilk tabbable: "Log out"), marka, `topbar-status` rozetleri |
| 3 | `<nav class="menu-bar" aria-label="Primary">` | `MENU_BAR` grupları; `aria-label` precheck'te **bloklayıcı** (adsız nav = kırmızı) |
| 4 | `.backend-banner` (koşullu) | `role="alert"` — backend erişilemezken |
| 5 | `<main id="main-content" class="workspace" tabIndex={-1}>` | Skip link'in hedefi. `id` olmadan link hiçbir yere gitmez; `tabIndex={-1}` olmadan odak linkte kalır ve sonraki Tab menü çubuğuna geri girer. **-1**, 0 değil: `<main>` kendisi tab durağı olmamalı |

Sayfa başlığı deseni: her rota kendini **`<h1 class="page-title">`** ile adlandırır
(ADIM 48'den beri istisnasız — `/user-manual` son sapmaydı). `.page-title` sınıf tabanlıdır
(margin / font-size / font-weight / color `global.css`'te açıkça yazılı), yani **etiket
değişimi hesaplanmış stili değiştirmez**; tersi de doğru — sınıfı düşürürsen görünüm bozulur.
`e2e/utils/pageTruth.ts::PageContract.level` kaçış kapağı **bugün hiçbir contract tarafından
kullanılmıyor**.

---

## Doğrulanmamış noktalar (`?`)

- Sayfa başına "backend endpoint grubu" sütunu, sayfanın import ettiği `lib` modülünden türetildi;
  bir sayfanın import ettiği her lib'in tüm endpoint'lerini gerçekten çağırdığı **doğrulanmadı**
  (ör. birçok sayfa `@/lib/backtest`'i yalnız `formatUtc`/`formatMetricValue` için import ediyor olabilir).
- `FUTURE_DEV_SUBPAGES` rotalarının tam listesi `app/nav.ts:122` içinde; burada tek satırda özetlendi.
- `["jobs"]` anahtarının HTTP liste yüzeyi yoktur — yalnız job-detay/rapor okumaları bu prefix'i taşır.
