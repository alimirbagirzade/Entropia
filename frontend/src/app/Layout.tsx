import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { MENU_BAR, type MenuGroup } from "./nav";
import { connectEvents, type SseStatus } from "@/lib/sse";
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
      className="topbar-actor"
      title="Dev-mode: act as a principal (sent as X-Actor-Id). Role is resolved server-side."
    >
      <label htmlFor="dev-actor">act as</label>
      <input
        id="dev-actor"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="user_admin"
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
      <NavLink to="/login" className="top-auth-line">
        Login / Sign Up
      </NavLink>
    );
  }

  const user = getStoredUser();
  return (
    <span className="top-auth-line" style={{ display: "inline-flex", gap: 8 }}>
      <span>{user?.display_name || user?.username || "signed in"}</span>
      <button type="button" className="link-btn" onClick={() => logout.mutate()} disabled={logout.isPending}>
        {logout.isPending ? "…" : "Log out"}
      </button>
    </span>
  );
}

// One top-level menu: a direct link (Mainboard) or a hover dropdown (Edit, …).
function Menu({ group, isAdmin, onAbout }: { group: MenuGroup; isAdmin: boolean; onAbout: () => void }) {
  if (group.path) {
    return (
      <NavLink to={group.path} end={group.path === "/"} className="menu menu-link">
        {group.label}
      </NavLink>
    );
  }

  const items = (group.items ?? []).filter((i) => !i.adminOnly || isAdmin);
  if (items.length === 0) return null;

  return (
    <div className={`menu${group.accent === "blue" ? " menu-blue" : ""}`}>
      {group.label}
      <div className={`dropdown${group.accent === "blue" ? " dropdown-blue" : ""}`}>
        {items.map((item) =>
          item.path ? (
            <NavLink key={item.label} to={item.path} className="item">
              {item.label}
            </NavLink>
          ) : (
            <button
              key={item.label}
              type="button"
              className="item"
              onClick={() => item.action === "about" && onAbout()}
            >
              {item.label}
            </button>
          )
        )}
      </div>
    </div>
  );
}

function AboutModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="About" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Entropia V18</h3>
        <p style={{ color: "var(--text-dim)" }}>
          Backtest-first strategy composition workspace. Compose strategies and packages, verify
          readiness, run deterministic backtests, and review results.
        </p>
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <button type="button" className="page-button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export function Layout() {
  const queryClient = useQueryClient();
  const [sse, setSse] = useState<SseStatus>("connecting");
  const [aboutOpen, setAboutOpen] = useState(false);
  const meta = useMeta();
  const me = useMe();
  const token = useSessionToken();

  useEffect(() => {
    return connectEvents(queryClient, setSse);
  }, [queryClient]);

  const isAdmin = me.data?.is_admin ?? false;
  const menus = MENU_BAR.filter((g) => !g.adminOnly || isAdmin);
  const sseTone = sse === "open" ? "ok" : sse === "connecting" ? "warn" : "down";

  return (
    <div className="app-shell">
      <div className="top-title">
        <AuthControl />
        <span className="brand-title">entropia</span>
        <div className="topbar-status">
          {token ? null : <DevActorControl />}
          <span className={`topbar-badge ${me.data?.is_authenticated ? "ok" : "neutral"}`}>
            {me.data?.is_authenticated ? me.data.role : "anonymous"}
          </span>
          <span className={`topbar-badge ${meta.isSuccess ? "ok" : "warn"}`}>
            {meta.data ? meta.data.environment : "…"}
          </span>
          <span className={`topbar-badge ${sseTone}`} title={`live events: ${sse}`}>
            ● {sse}
          </span>
        </div>
      </div>

      <nav className="menu-bar" aria-label="Primary">
        {menus.map((group) => (
          <Menu key={group.label} group={group} isAdmin={isAdmin} onAbout={() => setAboutOpen(true)} />
        ))}
      </nav>

      <main className="workspace">
        <Outlet />
      </main>

      {/* Fixed global RUN / Ready-Check panel (v18 mockup, bottom-right). */}
      <div className="run-controls">
        <NavLink to="/backtest/ready-check" className="ready-button">
          Backtest
          <br />
          Ready
          <br />
          Check
        </NavLink>
        <div className="ready-status" title="Backtest readiness — open Ready Check to compute" />
        <NavLink to="/backtest/run" className="run-button">
          RUN
        </NavLink>
      </div>

      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}
