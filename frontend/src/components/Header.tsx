import { CircleUserRound } from "lucide-react";

import { useAuth } from "@/components/auth";
import { Badge } from "@/components/ui/badge";

/** Global top bar: the active user + environment, and (in dev/test) a persona switcher to
 * exercise RBAC role mappings. In prod the identity is the real IAP user (no switcher). */
export function Header() {
  const { me, personas, activePersona, switchPersona } = useAuth();

  const user = me?.email ?? (me?.user_id ? `user ${me.user_id.slice(0, 8)}` : "guest");
  const roles = me?.roles?.length ? me.roles.join(", ") : "no role";

  return (
    <header className="flex h-12 shrink-0 items-center justify-end gap-3 border-b border-border px-6">
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
