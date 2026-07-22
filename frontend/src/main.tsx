import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { RuntimeAuthProvider } from "./app/RuntimeAuthProvider";
import { queryClient } from "./lib/queryClient";
import "./styles/global.css";

const root = document.getElementById("root");
if (!root) throw new Error("Root element #root not found");

// RuntimeAuthProvider sits above the router so it covers BOTH /login and the app
// shell: it loads the anonymous GET /meta boot contract and holds back every
// mode-dependent render (and every protected query) until dev|session is known.
// It lives inside QueryClientProvider (it drives the load through react-query) and
// outside BrowserRouter (the boot gate needs no routing).
createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RuntimeAuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </RuntimeAuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
