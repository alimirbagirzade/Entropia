import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { NAV } from "./nav";
import { connectEvents, type SseStatus } from "@/lib/sse";
import { StatusBadge } from "@/components/StatusBadge";
import { useMeta } from "@/lib/hooks";

export function Layout() {
  const queryClient = useQueryClient();
  const [sse, setSse] = useState<SseStatus>("connecting");
  const meta = useMeta();

  useEffect(() => {
    return connectEvents(queryClient, setSse);
  }, [queryClient]);

  const sseTone = sse === "open" ? "ok" : sse === "connecting" ? "warn" : "down";

  return (
    <div className="app-shell">
      <header className="app-header">
        <StatusBadge
          label={meta.data ? `${meta.data.name} · ${meta.data.environment}` : "Entropia V18"}
          tone={meta.isSuccess ? "ok" : meta.isError ? "down" : "warn"}
        />
        <div style={{ display: "flex", gap: 16 }}>
          <StatusBadge label={`API ${meta.data?.version ?? "…"}`} tone={meta.isSuccess ? "ok" : "warn"} />
          <StatusBadge label={`events: ${sse}`} tone={sseTone} />
        </div>
      </header>

      <nav className="app-sidebar" aria-label="Primary">
        <div className="brand" style={{ padding: "4px 10px 18px" }}>
          <span className="logo" aria-hidden="true" />
          <span>ENTROPIA</span>
        </div>
        {NAV.map((section) => (
          <div className="nav-section" key={section.title}>
            <h4>{section.title}</h4>
            {section.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <span>{item.label}</span>
                <span className="stage-pill">S{item.stage}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
