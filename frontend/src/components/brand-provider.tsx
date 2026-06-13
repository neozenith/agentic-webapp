import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { useTheme } from "@/components/theme-provider";
import { applyTokensToRoot, resolveBrandTokens } from "@/lib/brand-tokens";
import { BRANDS, type Brand, DEFAULT_BRAND_ID, getBrandOrDefault } from "@/lib/brands";

const STORAGE_KEY = "brand-id";

interface BrandContextValue {
  brand: Brand;
  brands: readonly Brand[];
  setBrandId: (id: string) => void;
}

const BrandContext = createContext<BrandContextValue | null>(null);

const readInitialBrandId = (defaultId: string): string => {
  if (typeof window === "undefined") return defaultId;
  return window.localStorage.getItem(STORAGE_KEY) ?? defaultId;
};

// `brands` defaults to the glob-discovered registry (production behavior is
// unchanged); tests pass a synthetic list to exercise multi-brand switching.
export const BrandProvider = ({
  children,
  brands = BRANDS,
}: {
  children: React.ReactNode;
  brands?: readonly Brand[];
}) => {
  const { theme } = useTheme();
  const defaultId = brands[0]?.id ?? DEFAULT_BRAND_ID;
  const [brandId, setBrandIdState] = useState<string>(() => readInitialBrandId(defaultId));

  const brand = useMemo(() => getBrandOrDefault(brandId, brands), [brandId, brands]);

  useEffect(() => {
    // Pick the light or dark semantic layer for the active theme, resolve the
    // DTCG refs, and write the result as inline CSS vars on <html>. Inline vars
    // outrank the :root/.dark rule blocks, so this repaints every utility class
    // without re-rendering the React tree.
    const semantic = theme === "dark" ? brand.tokens.dark : brand.tokens.light;
    const resolved = resolveBrandTokens(brand.tokens.core, semantic);
    const cleanup = applyTokensToRoot(resolved);
    document.documentElement.dataset.brand = brand.id;
    return cleanup;
  }, [brand, theme]);

  const setBrandId = useCallback((id: string) => {
    setBrandIdState(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const value = useMemo<BrandContextValue>(() => ({ brand, brands, setBrandId }), [brand, brands, setBrandId]);

  return <BrandContext.Provider value={value}>{children}</BrandContext.Provider>;
};

export const useBrand = (): BrandContextValue => {
  const ctx = useContext(BrandContext);
  if (!ctx) throw new Error("useBrand must be used inside BrandProvider");
  return ctx;
};
