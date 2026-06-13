import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchPersonas, getMe, getPersona, type Me, type Persona, setPersona } from "../api";

interface AuthValue {
  me: Me | null;
  personas: Persona[];
  loading: boolean;
  /** True if the active user's roles grant the given area. */
  can: (area: string) => boolean;
  /** Switch the simulated identity (dev/test) and reload so gating re-resolves everywhere. */
  switchPersona: (email: string) => void;
  activePersona: string | null;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);
  const [activePersona, setActivePersona] = useState<string | null>(getPersona());

  const load = useCallback(() => {
    setLoading(true);
    // Fetch personas first: in non-prod, default to the first persona (admin) when none is
    // chosen, so the app is usable out of the box. Then resolve identity (apiFetch sends the
    // persona as the IAP header). In prod personas is [] — the real IAP identity is used.
    return fetchPersonas()
      .catch(() => [])
      .then((p) => {
        setPersonas(p);
        if (!getPersona() && p.length > 0) {
          setPersona(p[0].email);
          setActivePersona(p[0].email);
        }
        return getMe().catch(() => null);
      })
      .then((m) => setMe(m))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const can = useCallback((area: string) => !!me?.permissions?.includes(area), [me]);

  // Switch the simulated identity and re-resolve roles/permissions (apiFetch now sends the
  // new persona header), so nav + page gating update without a full reload.
  const switchPersona = useCallback(
    (email: string) => {
      setPersona(email);
      setActivePersona(email);
      load();
    },
    [load],
  );

  return (
    <AuthContext.Provider value={{ me, personas, loading, can, switchPersona, activePersona }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Gate a page on an RBAC area — shows a clear "no access" card when the active user's
 * roles don't grant it. The backend also enforces this (defense-in-depth). */
export function RequireArea({ area, children }: { area: string; children: ReactNode }) {
  const { can, loading } = useAuth();
  if (loading) return <p className="text-muted-foreground">Checking access…</p>;
  if (!can(area)) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No access</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground">
          Your role doesn’t grant access to <span className="font-medium text-foreground">{area}</span>. Switch to a
          user with the right role, or ask an admin to grant it.
        </CardContent>
      </Card>
    );
  }
  return <>{children}</>;
}
