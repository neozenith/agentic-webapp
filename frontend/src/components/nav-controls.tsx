import { useAuth } from "@/components/auth";
import { useBrand } from "@/components/brand-provider";

// Shared by the desktop Header (right rail) and the mobile nav drawer. The min-h-9 keeps the
// <select> tap target above the WCAG 2.5.8 (AA) 24px floor (it lands at ~36px, near the 44px goal).
const SELECT_CLASS = "min-h-9 rounded-md border border-input bg-transparent px-2 py-1 text-xs text-foreground";

/** Live brand picker — only renders when there's more than one brand to switch between. */
export function BrandSelect() {
  const { brand, brands, setBrandId } = useBrand();
  if (brands.length <= 1) return null;
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      brand
      <select
        aria-label="Switch brand"
        className={SELECT_CLASS}
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
  );
}

/** Dev/test persona switcher to exercise RBAC role mappings — empty (and absent) in prod. */
export function PersonaSelect() {
  const { personas, activePersona, switchPersona } = useAuth();
  if (personas.length === 0) return null;
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      persona
      <select
        aria-label="Switch test persona"
        className={SELECT_CLASS}
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
  );
}
