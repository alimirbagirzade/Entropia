import { Routes, Route } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ALL_NAV_ITEMS } from "./app/nav";
import { Mainboard } from "./pages/Mainboard";
import { Placeholder } from "./pages/Placeholder";
import { NotFound } from "./pages/NotFound";
import { ErrorBoundary } from "./components/ErrorBoundary";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route
          index
          element={
            <ErrorBoundary>
              <Mainboard />
            </ErrorBoundary>
          }
        />
        {ALL_NAV_ITEMS.filter((item) => item.path !== "/").map((item) => (
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
