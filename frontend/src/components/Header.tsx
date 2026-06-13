import { CircleUserRound, Moon, Sun } from "lucide-react";

import { useAuth } from "@/components/auth";
import { useBrand } from "@/components/brand-provider";
import { useTheme } from "@/components/theme-provider";
import { Badge } from "@/components/ui/badge";

/** Global top bar: the active user + environment, a dark/light toggle, a live brand picker,
 * and (in dev/test) a persona switcher to exercise RBAC role mappings. In prod the identity
 * is the real IAP user (no switcher). */
export function Header() {
  const { me, personas, activePersona, switchPersona } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { brand, brands, setBrandId } = useBrand();

  const user = me?.email ?? (me?.user_id ? `user ${me.user_id.slice(0, 8)}` : "guest");
  const roles = me?.roles?.length ? me.roles.join(", ") : "no role";

  return (
    <header className="flex h-12 shrink-0 items-center justify-end gap-3 border-b border-border px-6">
      {/* The brand picker only earns its place when there's more than one brand
          to switch between; with a single brand it would be a dead control. */}
      {brands.length > 1 && (
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          brand
          <select
            aria-label="Switch brand"
            className="rounded-md border border-input bg-transparent px-2 py-1 text-xs text-foreground"
            value={brand.id}
            onChange={(e) => setBrandId(e.target.value)}
          >
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
      )}
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
      {personas.length > 0 && (
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          persona
          <select
            aria-label="Switch test persona"
            className="rounded-md border border-input bg-transparent px-2 py-1 text-xs text-foreground"
            value={activePersona ?? ""}
            onChange={(e) => switchPersona(e.target.value)}
          >
            <option value="" disabled>
              choose…
            </option>
            {personas.map((p) => (
              <option key={p.email} value={p.email}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {me?.environment && (
        <Badge variant="muted" className="uppercase">
          {me.environment}
        </Badge>
      )}
      <div className="flex items-center gap-2 text-sm" title={`${user} · roles: ${roles}`}>
        <CircleUserRound className="size-4 text-muted-foreground" aria-hidden />
        <span className="max-w-[16rem] truncate">{user}</span>
        <span className="hidden text-xs text-muted-foreground sm:inline">({roles})</span>
      </div>
    </header>
  );
}
