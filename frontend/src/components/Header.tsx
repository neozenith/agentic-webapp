import { CircleUserRound } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { getMe, type Me } from "../api";

/** Global top bar showing the actively signed-in user (from the IAP-derived /api/me) and
 * the environment. In non-prod (no IAP) the identity may be empty — shown as "guest". */
export function Header() {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  const user = me?.email ?? (me?.user_id ? `user ${me.user_id.slice(0, 8)}` : "guest");

  return (
    <header className="flex h-12 shrink-0 items-center justify-end gap-3 border-b border-border px-6">
      {me?.environment && (
        <Badge variant="muted" className="uppercase">
          {me.environment}
        </Badge>
      )}
      <div className="flex items-center gap-2 text-sm" title={me?.email ?? me?.user_id ?? "not signed in"}>
        <CircleUserRound className="size-4 text-muted-foreground" aria-hidden />
        <span className="max-w-[16rem] truncate">{user}</span>
      </div>
    </header>
  );
}
