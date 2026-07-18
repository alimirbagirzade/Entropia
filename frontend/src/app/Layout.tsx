import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Modal } from "@/components/Modal";
import { MENU_BAR, type MenuGroup, type MenuLink } from "./nav";
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
  onClose,
}: {
  item: MenuLink;
  isAdmin: boolean;
  onAbout: () => void;
  onClose: () => void;
}) {
  const subItems = (item.items ?? []).filter((i) => !i.adminOnly || isAdmin);
  const [subOpen, setSubOpen] = useState(false);
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
