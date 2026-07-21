import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Modal } from "@/components/Modal";
import { MENU_BAR, type MenuGroup, type MenuLink } from "./nav";
import { connectEvents, type SseStatus } from "@/lib/sse";
import { BASE_URL } from "@/lib/apiClient";
import { useApiHealth, useMe, useMeta } from "@/lib/hooks";
import { useLogout, useSessionToken } from "@/lib/auth";
import { useAuthMode, type AuthMode } from "@/lib/authMode";
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

// Auth control, driven by the SERVER's runtime auth mode (/meta.auth_mode) — never
// by "a token exists in localStorage". In dev mode the backend ignores Bearer
// tokens entirely, so offering Login / Log out there would hand the user a
// credential the API discards; DevActorControl is the real identity control and
// this slot just says so. While the mode is unknown (/meta in flight) the slot
// stays neutral so the wrong control never flashes on first paint.
function AuthControl({ mode }: { mode: AuthMode | null }) {
  const token = useSessionToken();
  const logout = useLogout();

  if (mode === null) {
    return (
      <span className="top-auth-line" aria-busy="true">
        …
      </span>
    );
  }

  if (mode === "dev") {
    return (
      <span
        className="top-auth-line"
        title="Local development: identity is selected with the “act as” field and sent as X-Actor-Id. Sign Up / Log In are inactive because the API ignores session tokens in this mode."
      >
        local dev — identity via “act as”
      </span>
    );
  }

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
  onClose,
}: {
  item: MenuLink;
  isAdmin: boolean;
  onAbout: () => void;
  onClose: () => void;
}) {
  const subItems = (item.items ?? []).filter((i) => !i.adminOnly || isAdmin);
  const [subOpen, setSubOpen] = useState(false);
  const navigate = useNavigate();
  if (subItems.length > 0) {
    return (
      <div className="has-sub-wrap" onMouseLeave={() => setSubOpen(false)}>
        <button
          type="button"
          className="item has-sub"
          aria-haspopup="true"
          aria-expanded={subOpen}
          onClick={() => setSubOpen((v) => !v)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") {
              e.preventDefault();
              setSubOpen(true);
            } else if ((e.key === "ArrowLeft" || e.key === "Escape") && subOpen) {
              e.stopPropagation();
              setSubOpen(false);
            }
          }}
        >
          {item.label}
        </button>
        <div className={`submenu${subOpen ? " sub-open" : ""}`}>
          {subItems.map((sub) => (
            <MenuItem key={sub.label} item={sub} isAdmin={isAdmin} onAbout={onAbout} onClose={onClose} />
          ))}
        </div>
      </div>
    );
  }
  if (item.addIntent) {
    // R2-02 (GAP madde 6): Add actions dispatch to the Mainboard add flow via
    // router state instead of route-linking to the standalone editor pages —
    // the Mainboard consumes the intent on mount and runs its own "+ Add"
    // handler, so the top menu and the Mainboard menu are ONE action model.
    const intent = item.addIntent;
    return (
      <button
        type="button"
        className="item"
        onClick={() => {
          navigate("/", { state: { add: intent } });
          onClose();
        }}
      >
        {item.label}
      </button>
    );
  }
  if (item.path) {
    return (
      <NavLink to={item.path} className="item" onClick={onClose}>
        {item.label}
      </NavLink>
    );
  }
  if (item.action === "about") {
    return (
      <button
        type="button"
        className="item"
        onClick={() => {
          onAbout();
          onClose();
        }}
      >
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

// One top-level menu: a dropdown that opens on hover (mouse) OR keyboard focus.
// The trigger is a real focusable control (a <button>, or the clickable NavLink
// title for Mainboard) carrying aria-haspopup/aria-expanded; ArrowDown opens and
// moves into the list, Escape closes and returns focus to the trigger, and focus
// leaving the menu closes it — so the primary nav is fully keyboard-operable
// (WCAG 2.1.1) without changing the v18 look for mouse users.
export function Menu({ group, isAdmin, onAbout }: { group: MenuGroup; isAdmin: boolean; onAbout: () => void }) {
  const items = (group.items ?? []).filter((i) => !i.adminOnly || isAdmin);
  const blue = group.accent === "blue";
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

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

  const assignTrigger = (el: HTMLElement | null) => {
    triggerRef.current = el;
  };
  const focusFirstItem = () => {
    containerRef.current?.querySelector<HTMLElement>(".dropdown .item")?.focus();
  };
  const onTriggerKeyDown = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      requestAnimationFrame(focusFirstItem);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };
  const onContainerKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      triggerRef.current?.focus();
    }
  };
  const onBlur = (e: FocusEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false);
  };

  return (
    <div
      ref={containerRef}
      className={`menu${open ? " open" : ""}${blue ? " menu-blue" : ""}`}
      onMouseLeave={() => setOpen(false)}
      onBlur={onBlur}
      onKeyDown={onContainerKeyDown}
    >
      {group.path ? (
        <NavLink
          to={group.path}
          end={group.path === "/"}
          className="menu-title"
          ref={assignTrigger}
          aria-haspopup="true"
          aria-expanded={open}
          onKeyDown={onTriggerKeyDown}
          onClick={() => setOpen(false)}
        >
          {group.label}
        </NavLink>
      ) : (
        <button
          type="button"
          className="menu-trigger"
          ref={assignTrigger}
          aria-haspopup="true"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          onKeyDown={onTriggerKeyDown}
        >
          {group.label}
        </button>
      )}
      <div className={`dropdown${blue ? " dropdown-blue" : ""}`}>
        {items.map((item) => (
          <MenuItem
            key={item.label}
            item={item}
            isAdmin={isAdmin}
            onAbout={onAbout}
            onClose={() => setOpen(false)}
          />
        ))}
      </div>
    </div>
  );
}

// About dialog. Delegates to the shared accessible Modal (Escape to close, focus
// trapped while open, focus restored to the trigger on close) rather than a
// hand-rolled overlay, so the Help ▸ About affordance matches every other dialog.
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
  // R2-11 (GAP madde 15): on narrow viewports the horizontal menu bar becomes a
  // hamburger disclosure so the shell stops imposing a ~513px minimum width.
  // Desktop (>760px) never renders the toggle and ignores this state entirely.
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const meta = useMeta();
  const me = useMe();
  const health = useApiHealth();
  const token = useSessionToken();
  const authMode = useAuthMode();
  const navigate = useNavigate();

  useEffect(() => {
    return connectEvents(queryClient, setSse);
  }, [queryClient]);

  // Stale-session landing. The API client clears the local session exactly once
  // when the server answers SESSION_INVALID (expired / revoked / unknown token),
  // which surfaces here as a token transition from present to absent. Logout
  // produces the same transition and the same destination, so one effect covers
  // both. Only session mode redirects — in dev mode /login is not a usable
  // credential path. The guard is the transition itself (not "no token"), so an
  // anonymous visitor browsing without ever having logged in is never bounced,
  // and the redirect cannot loop: /login renders outside this Layout, so leaving
  // unmounts the effect.
  const hadToken = useRef(token !== null);
  useEffect(() => {
    const lost = hadToken.current && token === null;
    hadToken.current = token !== null;
    if (!lost || authMode !== "session") return;
    void queryClient.invalidateQueries(); // drop every identity-dependent read
    navigate("/login", { replace: true });
  }, [token, authMode, queryClient, navigate]);

  const isAdmin = me.data?.is_admin ?? false;
  const menus = MENU_BAR.filter((g) => !g.adminOnly || isAdmin);
  const sseTone = sse === "open" ? "ok" : sse === "connecting" ? "warn" : "down";
  // R2-10 (GAP madde 14): API reachability is its OWN indicator, separate from
  // SSE and authentication. Pending = warn (probing), error = down.
  const apiTone = health.isSuccess ? "ok" : health.isError ? "down" : "warn";
  const apiLabel = health.isSuccess ? "api" : health.isError ? "api down" : "api …";

  // Retry is a USER action (no automatic retry storm): re-probe health, and once
  // the backend answers again refetch everything so stalled pages recover.
  async function retryBackend() {
    const result = await health.refetch();
    if (result.isSuccess) {
      void queryClient.invalidateQueries();
    }
  }

  return (
    <div className="app-shell">
      <header className="top-title">
        <AuthControl mode={authMode} />
        <span className="brand-title">entropia</span>
        <div className="topbar-status">
          {/* Dev-mode ONLY, and never gated on a stored token: under AUTH_MODE=dev
              this is the sole identity control the API honours, so a leftover
              Bearer token from a previous session-mode run must not hide it. */}
          {authMode === "dev" ? <DevActorControl /> : null}
          <span className={`topbar-badge ${me.data?.is_authenticated ? "ok" : "neutral"}`}>
            {me.data?.is_authenticated ? me.data.role : "anonymous"}
          </span>
          <span className={`topbar-badge ${meta.isSuccess ? "ok" : "warn"}`}>
            {meta.data ? meta.data.environment : "…"}
          </span>
          <span className={`topbar-badge ${apiTone}`} title={`API readiness: GET ${BASE_URL}/health/live`}>
            ● {apiLabel}
          </span>
          <span className={`topbar-badge ${sseTone}`} title={`live events: ${sse}`}>
            ● {sse}
          </span>
        </div>
      </header>

      <nav className={`menu-bar${mobileNavOpen ? " nav-open" : ""}`} aria-label="Primary">
        <button
          type="button"
          className="menu-hamburger"
          aria-expanded={mobileNavOpen}
          aria-controls="primary-menu-groups"
          onClick={() => setMobileNavOpen((v) => !v)}
        >
          <span aria-hidden="true">☰</span> Menu
        </button>
        <div
          id="primary-menu-groups"
          className="menu-bar-menus"
          // Delegated close: any navigation / action inside the disclosure
          // collapses it, so the drawer never lingers over the next page.
          onClick={(e) => {
            if (mobileNavOpen && (e.target as HTMLElement).closest("a.item, button.item, a.menu-link, a.menu-title")) {
              setMobileNavOpen(false);
            }
          }}
        >
          {menus.map((group) => (
            <Menu key={group.label} group={group} isAdmin={isAdmin} onAbout={() => setAboutOpen(true)} />
          ))}
        </div>
      </nav>

      {health.isError ? (
        <div className="backend-banner" role="alert">
          <strong>Backend unavailable</strong>
          <span className="backend-banner-addr">API: {BASE_URL}</span>
          <button
            type="button"
            className="page-button"
            onClick={() => void retryBackend()}
            disabled={health.isFetching}
          >
            {health.isFetching ? "Retrying…" : "Retry"}
          </button>
        </div>
      ) : null}

      <main className="workspace">
        <Outlet />
      </main>

      {/* The fixed lower-right Ready Check / RUN dock is owned by the Mainboard page
          (v18: .run-controls lives inside #mainboardView), where its status strip is
          bound to the real readiness state and RUN stays F-16-locked until a current
          Ready Check passes. Rendering a second static dock here would paint over that
          gated one on the Mainboard and overlap page content elsewhere, so the shell
          intentionally has no global dock. */}

      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}
