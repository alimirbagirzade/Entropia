import { Routes, Route } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ALL_NAV_ITEMS } from "./app/nav";
import { BacktestRun } from "./pages/BacktestRun";
import { Mainboard } from "./pages/Mainboard";
import { Metrics } from "./pages/Metrics";
import { Placeholder } from "./pages/Placeholder";
import { Login } from "./pages/Login";
import { NotFound } from "./pages/NotFound";
import { ResultsHistory } from "./pages/ResultsHistory";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Paths served by a real page below — excluded from the auto-generated
// placeholder routes.
const REAL_PATHS = new Set(["/", "/panel/metrics", "/backtest/run", "/backtest/history"]);

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
        {/* Real ops dashboard — replaces the auto-generated placeholder for this path. */}
        <Route
          path="/panel/metrics"
          element={
            <ErrorBoundary>
              <Metrics />
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
