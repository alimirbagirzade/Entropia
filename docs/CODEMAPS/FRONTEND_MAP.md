# FRONTEND_MAP — sayfa / lib / query-key haritası

React 18 + Vite + react-router 6 + `@tanstack/react-query` 5.
Router: `frontend/src/App.tsx` (`REAL_PATHS:39`, rotalar `:73-346`). Nav: `frontend/src/app/nav.ts`.
Import alias: `@/` → `frontend/src/`.

---

## Sayfalar (31 dosya `pages/*.tsx`)

| Route path | Sayfa | Kullandığı `lib/*` | react-query key prefix | Backend endpoint grubu |
|---|---|---|---|---|
| `/login` `App.tsx:73` | `Login.tsx` | `auth`, `apiClient` | (mutasyon; `["me"]` invalidasyonu) | `routes/auth.py` |
| `/` (index) `:79` | `Mainboard.tsx` | `mainboard`, `backtest`, `strategy` | `["mainboard"]`, `["readiness"]`, `["audit"]`, `["trash"]` | `routes/mainboard.py` |
| `/packages/create` `:85` | `CreatePackage.tsx` | `createPackage` | `["package-requests"]`, `["rationale-families"]`, `["audit"]` | `routes/create_package.py` |
| `/packages/pre-check` `:94` | `PreCheck.tsx` | `createPackage`, `backtest` | `["package-requests"]` | `routes/create_package.py` (scan) |
| `/packages/library` `:103` | `Library.tsx` | `library`, `sharing`, `packageImport`, `createPackage`, `strategy`, `backtest` | `["library"]`, `["package-imports"]`, `["jobs"]`, `["trash"]`, `["audit"]` | `routes/library.py`, `sharing.py`, `package_import.py` |
| `/packages/embedded` `:112` | `Embedded.tsx` | `esp`, `library`, `backtest` | `["esp"]`, `["audit"]` | `routes/esp.py` |
| `/panel` `:122` | → `Navigate` `/panel/management` | — | — | — |
| `/panel/management` `:124` | `PanelManagement.tsx` | `adminPanel`, `hooks`, `backtest` | `["admin"]`, `["audit"]` | `routes/admin_panel.py` |
| `/panel/logs` `:132` | `PanelLogs.tsx` | `adminPanel`, `hooks`, `backtest` | `["audit"]` | `routes/admin_panel.py` (logs), `audit.py` |
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
| `adminPanel.ts` | `["admin","users",cursor]`, `["admin","system-actors"]`, `["admin","role-matrix"]`, `["audit","events",cursor]`, `["audit","log",eventId]`, `["audit","resource-types"]` | `["admin"]`, `["audit"]` |
| `agentLab.ts` | `["agent-tasks",...]` — `overview`/`list`/`detail`/`messages`/`hypotheses`/`tool-calls`/`tool-call` | `["agent-tasks"]` |
| `allocation.ts` | `["allocation","draft",compositionId]` | `["allocation"]`, `["readiness"]`, `["mainboard"]`, `["audit"]` |
| `backtest.ts` | `["backtests","run"\|"result"\|"history"\|"compare"\|"artifact"]`, `["mainboard","default"]`, `["metric-profile","result-metrics",resultId]` | `["backtests"]`, `["audit"]` |
| `capability.ts` | `["capabilities",...]`, `["view-datasets",...]`, `["analysis-artifacts",...]` | `["capabilities"]`, `["audit"]` |
| `createPackage.ts` | `["package-requests",...]` (`list`/`detail`/`scan`/`validation-run`/`baseline-asset`), `["rationale-families",cursor]` | `["package-requests"]`, `["audit"]` |
| `esp.ts` | `["esp","list"\|"detail"]` | `["esp"]`, `["audit"]` |
| `hooks.ts` | `["me"]`, `["meta"]`, `["metrics"]`, `["health","ready"]` | — |
| `instrument.ts` | `["instruments","list"\|"detail"]` | `["instruments"]`, `["audit"]` |
| `library.ts` | `["library","list",filters,cursor]`, `["library","detail",entityId]` | `["library"]`, `["trash"]`, `["audit"]` |
| `mainboard.ts` | (`backtest.ts`'ten re-export `["mainboard","default"]`) | `["mainboard"]`, `["readiness"]`, `["audit"]`, `["trash"]` |
| `manual.ts` | `["manual","stream",cursor]`, `["manual","search",needle,cursor]` | `["manual"]`, `["trash"]`, `["audit"]` |
| `marketData.ts` | `["market-data","registry"\|"detail"\|"approved-bundle"]` | `["market-data"]`, `["audit"]` |
| `metricProfile.ts` | `["metric-definitions"]`, `["metric-profile","resolved"]` | `["metric-profile"]` |
| `packageImport.ts` | `["jobs","package-import",importJobId]` | `["package-imports"]`, `["jobs"]`, `["library"]`, `["audit"]` |
| `provisioning.ts` | `["auth","bootstrap-status"]` | — |
| `rationale.ts` | `["rationale-families","registry",state,cursor]`, `["rationale-assignments",cursor]` | `["rationale-families"]`, `["rationale-assignments"]`, `["audit"]` |
| `readiness.ts` | `["readiness","current",compositionId]`, `["readiness","report",reportId]` | `["readiness"]`, `["mainboard"]` |
| `researchData.ts` | `["research-data","registry"\|"detail"]` | `["research-data"]`, `["audit"]` |
| `sharing.ts` | `["library","shares",entityId]`, `["library","shared-with-me"]` | `["library"]`, `["audit"]` |
| `strategy.ts` | `["strategy","draft"\|"drafts"\|"root"\|"revisions"\|"revision"]` | `["strategy"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` |
| `tradeLog.ts` | `["trade-logs","root",rootId]`, `["jobs","trade-log-import",jobId]` | `["trade-logs"]`, `["jobs"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` |
| `tradingSignal.ts` | `["trading-signals","root",rootId]`, `["jobs","trading-signal-import",jobId]` | `["trading-signals"]`, `["jobs"]`, `["mainboard"]`, `["readiness"]`, `["audit"]` |
| `trash.ts` | `["trash","entries",q,object_type,cursor]`, `["trash","entry",id]` | `["trash"]`, `["audit"]` |

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

**Sunucu tarafı projeksiyon** (`apps/api/sse.py:33-44` `sse_event_name`):
`resource_type` `backtest*` → `backtest.run.updated`; `job` → `job.updated`;
`agent*` veya `hypothesis_artifact` → `agent.task.updated`;
`event_type` `audit.` ile başlıyorsa → `audit.event.created`; aksi hâlde → `resource.changed`.

**Reconnect davranışı** (`lib/sse.ts:50-68`): `readyState === CONNECTING` iken tarayıcının kendi
retry'si çalışır; `CLOSED` olduğunda kendi üstel backoff'u devreye girer
(`RECONNECT_BASE_MS=1000` → `RECONNECT_MAX_MS=30000`). Her başarılı yeniden açılış
**tam refresh** tetikler (INF-11 kayıp-toleransı).

---

## Doğrulanmamış noktalar (`?`)

- Sayfa başına "backend endpoint grubu" sütunu, sayfanın import ettiği `lib` modülünden türetildi;
  bir sayfanın import ettiği her lib'in tüm endpoint'lerini gerçekten çağırdığı **doğrulanmadı**
  (ör. birçok sayfa `@/lib/backtest`'i yalnız `formatUtc`/`formatMetricValue` için import ediyor olabilir).
- `FUTURE_DEV_SUBPAGES` rotalarının tam listesi `app/nav.ts:122` içinde; burada tek satırda özetlendi.
- `["jobs"]` anahtarının HTTP liste yüzeyi yoktur — yalnız job-detay/rapor okumaları bu prefix'i taşır.
