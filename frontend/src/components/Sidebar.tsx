import { BarChart3, FolderTree, History, House, type LucideIcon, MessagesSquare, PanelLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

// `end` on Home so "/" isn't marked active for every nested route.
const NAV: NavItem[] = [
  { to: "/", label: "Home", icon: House },
  { to: "/chat", label: "Chat", icon: MessagesSquare },
  { to: "/sessions", label: "Sessions", icon: History },
  { to: "/assets", label: "Assets", icon: FolderTree },
  { to: "/admin", label: "Admin", icon: BarChart3 },
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

export function Sidebar() {
  const [collapsed, toggle] = useCollapsed();
  return (
    <aside
      data-collapsed={collapsed}
      className={cn(
        "flex h-screen shrink-0 flex-col gap-2 border-r border-border bg-card/40 p-3 transition-[width] duration-200",
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

      <nav className="flex flex-col gap-1">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
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
    </aside>
  );
}
