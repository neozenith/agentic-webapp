import {
  BarChart3,
  Boxes,
  Database,
  FolderTree,
  History,
  House,
  LayoutDashboard,
  LineChart,
  type LucideIcon,
  MessagesSquare,
  PanelLeft,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { useAuth } from "@/components/auth";
import { BrandSelect, PersonaSelect } from "@/components/nav-controls";
import { useNavDrawer } from "@/components/nav-drawer";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  area: string;
}

// `end` on Home so "/" isn't marked active for every nested route. `area` gates the item
// against the active user's RBAC permissions.
const NAV: NavItem[] = [
  { to: "/", label: "Home", icon: House, area: "home" },
  { to: "/chat", label: "Chat", icon: MessagesSquare, area: "chat" },
  { to: "/sessions", label: "Sessions", icon: History, area: "sessions" },
  { to: "/assets", label: "Assets", icon: FolderTree, area: "assets" },
  { to: "/analytics", label: "Analytics", icon: LineChart, area: "analytics" },
  { to: "/semantic", label: "Semantic", icon: Boxes, area: "semantic" },
  { to: "/dbt", label: "dbt", icon: Database, area: "dbt" },
  { to: "/dashboards", label: "Dashboards", icon: LayoutDashboard, area: "dashboards" },
  { to: "/admin", label: "Admin", icon: BarChart3, area: "admin" },
];

const STORAGE_KEY = "sidebar-collapsed";

/** Read/persist the collapsed state so the rail survives reloads. */
function useCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
    } catch {
      /* private mode / no storage — collapse still works for the session */
    }
  }, [collapsed]);
  return [collapsed, () => setCollapsed((c) => !c)];
}

/** The RBAC-gated route links. Shared by the desktop rail and the mobile drawer; in the drawer
 * `onNavigate` closes it after a tap, and `collapsed` is always false (the drawer is full-width). */
function NavItems({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const { can, loading } = useAuth();
  return (
    <nav className="flex flex-col gap-1">
      {/* Only show areas the active user's roles permit (RBAC); none until loaded. */}
      {NAV.filter(({ area }) => loading || can(area)).map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          onClick={onNavigate}
          title={collapsed ? label : undefined}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors",
              "hover:bg-accent hover:text-accent-foreground",
              isActive && "bg-accent text-accent-foreground",
              collapsed && "justify-center px-0",
            )
          }
        >
          <Icon className="size-4 shrink-0" aria-hidden />
          {!collapsed && <span>{label}</span>}
        </NavLink>
      ))}
    </nav>
  );
}

/** Persistent left rail — desktop only (md+). On mobile it is display:none and `MobileNavDrawer`
 * provides navigation instead, so the rail never forces a fixed column wider than a phone. */
export function Sidebar() {
  const [collapsed, toggle] = useCollapsed();
  return (
    <aside
      data-collapsed={collapsed}
      className={cn(
        "hidden h-screen shrink-0 flex-col gap-2 border-r border-border bg-card/40 p-3 transition-[width] duration-200 md:flex",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className={cn("flex items-center px-1 py-2", collapsed ? "justify-center" : "justify-between")}>
        {!collapsed && (
          <span className="flex items-center gap-2 font-bold">
            <span aria-hidden>🛡️</span>
            <span>agentic-webapp</span>
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-pressed={collapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <PanelLeft />
        </Button>
      </div>

      <NavItems collapsed={collapsed} />
    </aside>
  );
}

/** Off-canvas navigation drawer for mobile (< md). Hidden by default; opened by the Header
 * hamburger (shared state via `useNavDrawer`), and closed on backdrop click, Escape, or a
 * nav-item tap. Mounted only while open, so it never adds to the page's scroll width when shut.
 * On md+ it is display:none — the persistent rail is used instead. */
export function MobileNavDrawer() {
  const { open, close } = useNavDrawer();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  if (!open) return null;

  return (
    <div className="md:hidden">
      {/* Backdrop: a real button so dismiss-on-tap is keyboard- and screen-reader-accessible. */}
      <button
        type="button"
        aria-label="Close navigation menu"
        className="fixed inset-0 z-40 bg-black/50"
        onClick={close}
      />
      <aside
        id="mobile-nav-drawer"
        aria-label="Navigation"
        className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[80vw] flex-col gap-2 border-r border-border bg-card p-3 shadow-lg"
      >
        <div className="flex items-center px-1 py-2">
          <span className="flex items-center gap-2 font-bold">
            <span aria-hidden>🛡️</span>
            <span>agentic-webapp</span>
          </span>
        </div>

        <NavItems onNavigate={close} />

        {/* The pickers that live in the Header on md+ move here on mobile so they stay reachable. */}
        <div className="mt-auto flex flex-col gap-3 border-t border-border pt-3">
          <BrandSelect />
          <PersonaSelect />
        </div>
      </aside>
    </div>
  );
}
