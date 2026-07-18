import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { MENU_BAR, type MenuGroup, type MenuLink } from "./nav";
import { Modal } from "@/components/Modal";
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

// A dropdown leaf, or a nested submenu parent (v18 two-level tree). A leaf with
// no path/action/submenu is a passive placeholder (mockup "Live Trade").
function MenuItem({
  item,
  isAdmin,
  onAbout,
}: {
  item: MenuLink;
  isAdmin: boolean;
  onAbout: () => void;
}) {
  const subItems = (item.items ?? []).filter((i) => !i.adminOnly || isAdmin);
  if (subItems.length > 0) {
    return (
      <div className="item has-sub">
        {item.label}
        <div className="submenu">
          {subItems.map((sub) => (
            <MenuItem key={sub.label} item={sub} isAdmin={isAdmin} onAbout={onAbout} />
          ))}
        </div>
      </div>
    );
  }
  if (item.path) {
    return (
      <NavLink to={item.path} className="item">
        {item.label}
      </NavLink>
    );
  }
  if (item.action === "about") {
    return (
      <button type="button" className="item" onClick={onAbout}>
        {item.label}
      </button>
    );
  }
  return (
    <span className="item" aria-disabled="true">
      {item.label}
    </span>
  );
}

// One top-level menu: a hover dropdown, optionally with a clickable title
// (Mainboard opens the index on click and reveals its dropdown on hover).
function Menu({ group, isAdmin, onAbout }: { group: MenuGroup; isAdmin: boolean; onAbout: () => void }) {
  const items = (group.items ?? []).filter((i) => !i.adminOnly || isAdmin);
  const blue = group.accent === "blue";

  if (items.length === 0) {
    return group.path ? (
      <NavLink
        to={group.path}
        end={group.path === "/"}
        className={`menu menu-link${blue ? " menu-blue" : ""}`}
      >
        {group.label}
      </NavLink>
    ) : null;
  }

  return (
    <div className={`menu${blue ? " menu-blue" : ""}`}>
      {group.path ? (
        <NavLink to={group.path} end={group.path === "/"} className="menu-title">
          {group.label}
        </NavLink>
      ) : (
        group.label
      )}
      <div className={`dropdown${blue ? " dropdown-blue" : ""}`}>
        {items.map((item) => (
          <MenuItem key={item.label} item={item} isAdmin={isAdmin} onAbout={onAbout} />
        ))}
      </div>
    </div>
  );
}

// About dialog — reuses the shared Modal chrome so it inherits full focus
// management (accessibility.md): Escape closes, Tab/Shift+Tab are trapped inside
// while open, focus moves into the dialog on open, and focus is restored to the
// Help ▸ About trigger on close. The visible <h3> is the accessible name via
// aria-labelledby (stronger than a static aria-label). Presentation-only — no
// route/key/OCC/hook/lib change.
function AboutModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} titleId="about-modal-title">
      <h3 id="about-modal-title" style={{ marginTop: 0 }}>
        Entropia V18
      </h3>
      <p style={{ color: "var(--text-dim)" }}>
        Backtest-first strategy composition workspace. Compose strategies and packages, verify
        readiness, run deterministic backtests, and review results.
      </p>
      <div style={{ marginTop: 16, textAlign: "right" }}>
        <button type="button" className="page-button" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
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
      {/* Top strip is the page banner landmark (Login / brand / act-as + status). */}
      <header className="top-title">
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
      </header>

      <nav className="menu-bar" aria-label="Primary">
        {menus.map((group) => (
          <Menu key={group.label} group={group} isAdmin={isAdmin} onAbout={() => setAboutOpen(true)} />
        ))}
      </nav>

      <main className="workspace">
        <Outlet />
      </main>

      {/* The fixed lower-right Ready Check / RUN dock is Mainboard-scoped (v18   */}
      {/* mockup: .run-controls lives inside #mainboardView). Mainboard renders    */}
      {/* the real F-16-gated dock (live readiness strip + RUN locked until a      */}
      {/* current Ready Check passes); the shell must not render a second one.     */}

      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}
