import { CircleUserRound, Menu, Moon, Sun } from "lucide-react";

import { useAuth } from "@/components/auth";
import { BrandSelect, PersonaSelect } from "@/components/nav-controls";
import { useNavDrawer } from "@/components/nav-drawer";
import { useTheme } from "@/components/theme-provider";
import { Badge } from "@/components/ui/badge";

/** Global top bar: a mobile menu toggle, the active user + environment, a dark/light toggle,
 * a live brand picker, and (in dev/test) a persona switcher to exercise RBAC role mappings.
 * On mobile (< md) the brand/persona pickers move into the nav drawer to keep the bar from
 * overflowing; on md+ they live here. In prod the identity is the real IAP user (no switcher). */
export function Header() {
  const { me } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { open, toggle } = useNavDrawer();

  const user = me?.email ?? (me?.user_id ? `user ${me.user_id.slice(0, 8)}` : "guest");
  const roles = me?.roles?.length ? me.roles.join(", ") : "no role";

  return (
    <header className="flex h-12 shrink-0 items-center justify-end gap-3 border-b border-border px-4 md:px-6">
      {/* Hamburger: mobile only. `mr-auto` parks it at the left edge and pushes the rest right;
          on md+ it is display:none and the persistent rail provides navigation instead. */}
      <button
        type="button"
        aria-label="Toggle navigation menu"
        aria-expanded={open}
        aria-controls="mobile-nav-drawer"
        title="Navigation menu"
        className="mr-auto rounded-md border border-input p-2 text-foreground hover:bg-accent hover:text-accent-foreground md:hidden"
        onClick={toggle}
      >
        <Menu className="size-5" aria-hidden />
      </button>

      {/* Brand + persona pickers live in the bar on md+, and in the drawer on mobile. */}
      <div className="hidden items-center gap-3 md:flex">
        <BrandSelect />
        <PersonaSelect />
      </div>

      <button
        type="button"
        aria-label="Toggle dark mode"
        aria-pressed={theme === "dark"}
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="rounded-md border border-input p-1.5 text-foreground hover:bg-accent hover:text-accent-foreground"
        onClick={toggleTheme}
      >
        {theme === "dark" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
      </button>
      {me?.environment && (
        <Badge variant="muted" className="uppercase">
          {me.environment}
        </Badge>
      )}
      <div className="flex min-w-0 items-center gap-2 text-sm" title={`${user} · roles: ${roles}`}>
        <CircleUserRound className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="truncate">{user}</span>
        <span className="hidden text-xs text-muted-foreground sm:inline">({roles})</span>
      </div>
    </header>
  );
}
