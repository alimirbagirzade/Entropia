import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { NAV } from "./nav";
import { connectEvents, type SseStatus } from "@/lib/sse";
import { StatusBadge } from "@/components/StatusBadge";
import { useMe, useMeta } from "@/lib/hooks";
import { useLogout, useSessionToken } from "@/lib/auth";
import { getDevActorId, setDevActorId } from "@/lib/devActor";
import { getStoredUser } from "@/lib/session";

function DevActorControl() {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(getDevActorId());

  function apply() {
    setDevActorId(value.trim());
    // Re-fetch identity-dependent data under the new principal.
    queryClient.invalidateQueries();
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        apply();
      }}
      style={{ display: "flex", gap: 6, alignItems: "center" }}
      title="Dev-mode: act as a principal (sent as X-Actor-Id). Role is resolved server-side."
    >
      <label htmlFor="dev-actor" style={{ fontSize: 12, color: "var(--text-dim)" }}>
        act as
      </label>
      <input
        id="dev-actor"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="user_admin"
        style={{
          background: "var(--bg-elev-2)",
          border: "1px solid var(--border)",
          color: "var(--text)",
          borderRadius: 6,
          padding: "3px 8px",
          fontSize: 12,
          width: 120,
        }}
      />
    </form>
  );
}

// Real-session control: shows the signed-in user + a Log out action when a Bearer
// session token is present, and a Log in link otherwise. In dev mode (X-Actor-Id)
// no token exists, so this stays a Log in link and DevActorControl drives identity.
function AuthControl() {
  const token = useSessionToken();
  const logout = useLogout();

  if (!token) {
    return (
      <NavLink to="/login" className="btn btn-ghost">
        Log in
      </NavLink>
    );
  }

  const user = getStoredUser();
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
        {user?.display_name || user?.username || "signed in"}
      </span>
      <button
        type="button"
        className="btn btn-ghost"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
      >
        {logout.isPending ? "…" : "Log out"}
      </button>
    </div>
  );
}

export function Layout() {
  const queryClient = useQueryClient();
  const [sse, setSse] = useState<SseStatus>("connecting");
  const meta = useMeta();
  const me = useMe();
  const token = useSessionToken();

  useEffect(() => {
    return connectEvents(queryClient, setSse);
  }, [queryClient]);

  const sseTone = sse === "open" ? "ok" : sse === "connecting" ? "warn" : "down";
  const isAdmin = me.data?.is_admin ?? false;

  return (
    <div className="app-shell">
      <header className="app-header">
        <StatusBadge
          label={meta.data ? `${meta.data.name} · ${meta.data.environment}` : "Entropia V18"}
          tone={meta.isSuccess ? "ok" : meta.isError ? "down" : "warn"}
        />
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          {token ? null : <DevActorControl />}
          <StatusBadge
            label={me.data?.is_authenticated ? `${me.data.role}` : "anonymous"}
            tone={me.data?.is_authenticated ? "ok" : "neutral"}
          />
          <AuthControl />
          <StatusBadge label={`events: ${sse}`} tone={sseTone} />
        </div>
      </header>

      <nav className="app-sidebar" aria-label="Primary">
        <div className="brand" style={{ padding: "4px 10px 18px" }}>
          <span className="logo" aria-hidden="true" />
          <span>ENTROPIA</span>
        </div>
        {NAV.map((section) => {
          const items = section.items.filter((item) => !item.adminOnly || isAdmin);
          if (items.length === 0) return null;
          return (
            <div className="nav-section" key={section.title}>
              <h4>{section.title}</h4>
              {items.map((item) => (
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
          );
        })}
      </nav>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
