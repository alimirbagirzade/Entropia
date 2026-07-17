import { Routes, Route } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ALL_NAV_ITEMS, FUTURE_DEV_SUBPAGES } from "./app/nav";
import { AnalysisLab } from "./pages/AnalysisLab";
import { ArrangeMetrics } from "./pages/ArrangeMetrics";
import { BacktestRun } from "./pages/BacktestRun";
import { CreatePackage } from "./pages/CreatePackage";
import { Embedded } from "./pages/Embedded";
import { FutureDev } from "./pages/FutureDev";
import { FutureDevCapability } from "./pages/FutureDevCapability";
import { FutureDevGraphicView } from "./pages/FutureDevGraphicView";
import { Instruments } from "./pages/Instruments";
import { Library } from "./pages/Library";
import { Mainboard } from "./pages/Mainboard";
import { MarketData } from "./pages/MarketData";
import { Metrics } from "./pages/Metrics";
import { OutsourceSignal } from "./pages/OutsourceSignal";
import { Panel } from "./pages/Panel";
import { Portfolio } from "./pages/Portfolio";
import { PreCheck } from "./pages/PreCheck";
import { Provisioning } from "./pages/Provisioning";
import { RationaleFamilies } from "./pages/RationaleFamilies";
import { ReadyCheck } from "./pages/ReadyCheck";
import { ResearchData } from "./pages/ResearchData";
import { StrategyDetails } from "./pages/StrategyDetails";
import { TradeLog } from "./pages/TradeLog";
import { TradingSignal } from "./pages/TradingSignal";
import { Placeholder } from "./pages/Placeholder";
import { Login } from "./pages/Login";
import { NotFound } from "./pages/NotFound";
import { ResultsHistory } from "./pages/ResultsHistory";
import { Trash } from "./pages/Trash";
import { UserManual } from "./pages/UserManual";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Paths served by a real page below — excluded from the auto-generated
// placeholder routes.
const REAL_PATHS = new Set([
  "/",
  "/packages/create",
  "/packages/pre-check",
  "/packages/library",
  "/packages/embedded",
  "/panel",
  "/panel/provisioning",
  "/panel/metrics",
  "/portfolio",
  "/backtest/ready-check",
  "/backtest/run",
  "/backtest/history",
  "/backtest/metrics",
  "/analysis-lab",
  "/future-dev",
  "/user-manual",
  "/trash",
  "/rationale-families",
  "/market-data",
  "/research-data",
  "/instruments",
  "/strategy",
  "/outsource-signal",
  "/trading-signal",
  "/trade-log",
]);

export default function App() {
  return (
    <Routes>
      {/* Standalone auth page — rendered outside the app shell (no sidebar/header). */}
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route
          index
          element={
            <ErrorBoundary>
              <Mainboard />
            </ErrorBoundary>
          }
        />
        {/* Create Package (doc 06): compose a request, list own requests, open detail. */}
        <Route
          path="/packages/create"
          element={
            <ErrorBoundary>
              <CreatePackage />
            </ErrorBoundary>
          }
        />
        {/* Pre-Check (doc 07): immutable dependency scans + scan artifact viewer. */}
        <Route
          path="/packages/pre-check"
          element={
            <ErrorBoundary>
              <PreCheck />
            </ErrorBoundary>
          }
        />
        {/* Package Library (doc 08): read-only catalog of the four canonical kinds. */}
        <Route
          path="/packages/library"
          element={
            <ErrorBoundary>
              <Library />
            </ErrorBoundary>
          }
        />
        {/* Embedded System Packages (doc 09): resolver registry + resolve probe. */}
        <Route
          path="/packages/embedded"
          element={
            <ErrorBoundary>
              <Embedded />
            </ErrorBoundary>
          }
        />
        {/* Panel / Management / Logs (doc 19): Admin-only registry + immutable logs. */}
        <Route
          path="/panel"
          element={
            <ErrorBoundary>
              <Panel />
            </ErrorBoundary>
          }
        />
        {/* First-Admin provisioning onboarding (post-V1 TIER 2) — reachable pre-elevation. */}
        <Route
          path="/panel/provisioning"
          element={
            <ErrorBoundary>
              <Provisioning />
            </ErrorBoundary>
          }
        />
        {/* Real ops dashboard — replaces the auto-generated placeholder for this path. */}
        <Route
          path="/panel/metrics"
          element={
            <ErrorBoundary>
              <Metrics />
            </ErrorBoundary>
          }
        />
        {/* Portfolio / Equity Allocation (Stage 4a doc 13): draft editor + validation + revisions. */}
        <Route
          path="/portfolio"
          element={
            <ErrorBoundary>
              <Portfolio />
            </ErrorBoundary>
          }
        />
        {/* Backtest Ready Check (Stage 4b doc 14): composition validator + immutable report. */}
        <Route
          path="/backtest/ready-check"
          element={
            <ErrorBoundary>
              <ReadyCheck />
            </ErrorBoundary>
          }
        />
        {/* Live-data backtest pages (Stage 5): RUN admission/status + history index. */}
        <Route
          path="/backtest/run"
          element={
            <ErrorBoundary>
              <BacktestRun />
            </ErrorBoundary>
          }
        />
        <Route
          path="/backtest/history"
          element={
            <ErrorBoundary>
              <ResultsHistory />
            </ErrorBoundary>
          }
        />
        {/* Arrange Metrics (Stage 5c): presentation-only Result View Metric Profile. */}
        <Route
          path="/backtest/metrics"
          element={
            <ErrorBoundary>
              <ArrangeMetrics />
            </ErrorBoundary>
          }
        />
        {/* Analysis Lab (Stage 6a): Agent Workspace observation/control plane. */}
        <Route
          path="/analysis-lab"
          element={
            <ErrorBoundary>
              <AnalysisLab />
            </ErrorBoundary>
          }
        />
        {/* Future Dev (doc 22): server-side capability registry + Graphic View overview. */}
        <Route
          path="/future-dev"
          element={
            <ErrorBoundary>
              <FutureDev />
            </ErrorBoundary>
          }
        />
        {/* UI-22: every Future Dev submenu target is a dedicated valid route (spec
            §UI-22 — no menu click may resolve to NotFound). Graphic View is the
            documented intro + six static placeholder cards with the server-truth
            gated View Dataset surface; the other capabilities render the shared
            pure-placeholder page (no input, table, lifecycle control or form). */}
        <Route
          path="/future-dev/graphic-view"
          element={
            <ErrorBoundary>
              <FutureDevGraphicView />
            </ErrorBoundary>
          }
        />
        {FUTURE_DEV_SUBPAGES.filter((subpage) => subpage.capabilityKey !== "graphic_view").map(
          (subpage) => (
            <Route
              key={subpage.path}
              path={subpage.path}
              element={
                <ErrorBoundary>
                  <FutureDevCapability subpage={subpage} />
                </ErrorBoundary>
              }
            />
          ),
        )}
        {/* User Manual (Stage 7a doc 21): published reader stream + search + Admin publish surface. */}
        <Route
          path="/user-manual"
          element={
            <ErrorBoundary>
              <UserManual />
            </ErrorBoundary>
          }
        />
        {/* Admin Trash (Stage 6c doc 20): recoverable soft-deleted index + OCC restore. */}
        <Route
          path="/trash"
          element={
            <ErrorBoundary>
              <Trash />
            </ErrorBoundary>
          }
        />
        {/* Rationale Families (doc 10): shared taxonomy — family CRUD + package assignment. */}
        <Route
          path="/rationale-families"
          element={
            <ErrorBoundary>
              <RationaleFamilies />
            </ErrorBoundary>
          }
        />
        {/* Market Data (doc 11): registry + detail reads and the owner ingest chain. */}
        <Route
          path="/market-data"
          element={
            <ErrorBoundary>
              <MarketData />
            </ErrorBoundary>
          }
        />
        {/* Research Data (doc 12): role-aware registry + detail reads and the owner ingest chain. */}
        <Route
          path="/research-data"
          element={
            <ErrorBoundary>
              <ResearchData />
            </ErrorBoundary>
          }
        />
        {/* Instrument Registry (GAP-16, Master §8.1): canonical instruments + free-text scope resolver. */}
        <Route
          path="/instruments"
          element={
            <ErrorBoundary>
              <Instruments />
            </ErrorBoundary>
          }
        />
        {/* Strategy Details (Stage 3b doc 02): editor draft workflow + revision history. */}
        <Route
          path="/strategy"
          element={
            <ErrorBoundary>
              <StrategyDetails />
            </ErrorBoundary>
          }
        />
        {/* Add Outsource Signal (Stage 3 doc 03): external-work type chooser — no backend surface. */}
        <Route
          path="/outsource-signal"
          element={
            <ErrorBoundary>
              <OutsourceSignal />
            </ErrorBoundary>
          }
        />
        {/* Trading Signal (Stage 3c doc 04): source-import chain + native work object. */}
        <Route
          path="/trading-signal"
          element={
            <ErrorBoundary>
              <TradingSignal />
            </ErrorBoundary>
          }
        />
        {/* Trade Log (Stage 3d doc 05): historical ledger import + native work object. */}
        <Route
          path="/trade-log"
          element={
            <ErrorBoundary>
              <TradeLog />
            </ErrorBoundary>
          }
        />
        {ALL_NAV_ITEMS.filter((item) => !REAL_PATHS.has(item.path)).map((item) => (
          <Route
            key={item.path}
            path={item.path}
            element={
              <ErrorBoundary>
                <Placeholder item={item} />
              </ErrorBoundary>
            }
          />
        ))}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
