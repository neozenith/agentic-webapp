import type { TokenGroup } from "./brand-tokens";

/**
 * Brand registry — auto-discovered at build time via Vite glob imports.
 *
 * To add a new brand: drop a folder into `brandpacks/<id>/` (resolved relative
 * to the Vite root, i.e. `frontend/brandpacks/`) containing the standard
 * layout (brand.json, logo.svg, logo-dark.svg, icon.svg, and
 * tokens/{core,light,dark}.tokens.json). No registration step needed —
 * `import.meta.glob` picks it up on the next dev-server restart or build.
 *
 * Missing assets/tokens THROW loudly at discovery time (no silent fallback).
 */

interface BrandManifest {
  id: string;
  name: string;
  tagline?: string;
  description?: string;
  version?: string;
  swatches?: string[];
  assets: { logo: string; logoDark?: string; icon: string };
  tokens: { core: string; light: string; dark: string };
}

export interface Brand {
  id: string;
  name: string;
  tagline: string;
  description: string;
  swatches: string[];
  logoLightUrl: string;
  logoDarkUrl: string;
  iconUrl: string;
  tokens: {
    core: TokenGroup;
    light: TokenGroup;
    dark: TokenGroup;
  };
}

// Eager glob: bundles every brand's JSON into the chunk. The bundle cost is
// tiny (~few KB per brand) and makes brand-switching synchronous.
const manifestModules = import.meta.glob<BrandManifest>("/brandpacks/*/brand.json", {
  eager: true,
  import: "default",
});

const coreTokenModules = import.meta.glob<TokenGroup>("/brandpacks/*/tokens/core.tokens.json", {
  eager: true,
  import: "default",
});

const lightTokenModules = import.meta.glob<TokenGroup>("/brandpacks/*/tokens/light.tokens.json", {
  eager: true,
  import: "default",
});

const darkTokenModules = import.meta.glob<TokenGroup>("/brandpacks/*/tokens/dark.tokens.json", {
  eager: true,
  import: "default",
});

// SVG assets imported as resolved URLs (Vite hashes them at build time).
const logoLightUrls = import.meta.glob<string>("/brandpacks/*/logo.svg", {
  eager: true,
  import: "default",
  query: "?url",
});

const logoDarkUrls = import.meta.glob<string>("/brandpacks/*/logo-dark.svg", {
  eager: true,
  import: "default",
  query: "?url",
});

const iconUrls = import.meta.glob<string>("/brandpacks/*/icon.svg", {
  eager: true,
  import: "default",
  query: "?url",
});

const brandIdFromManifestPath = (path: string): string => {
  // "/brandpacks/default-v2ai/brand.json" -> "default-v2ai"
  const parts = path.split("/");
  return parts[parts.length - 2] ?? "unknown";
};

const requireUrl = (bag: Record<string, string>, brandId: string, filename: string): string => {
  const key = `/brandpacks/${brandId}/${filename}`;
  const url = bag[key];
  if (!url) throw new Error(`Brand "${brandId}" is missing ${filename}`);
  return url;
};

const requireTokens = (bag: Record<string, TokenGroup>, brandId: string, rel: string): TokenGroup => {
  const key = `/brandpacks/${brandId}/${rel}`;
  const tokens = bag[key];
  if (!tokens) throw new Error(`Brand "${brandId}" is missing ${rel}`);
  return tokens;
};

const buildBrand = (manifestPath: string, manifest: BrandManifest): Brand => {
  const id = brandIdFromManifestPath(manifestPath);
  const logoLightUrl = requireUrl(logoLightUrls, id, manifest.assets.logo);
  const logoDarkUrl = manifest.assets.logoDark ? requireUrl(logoDarkUrls, id, manifest.assets.logoDark) : logoLightUrl;
  const iconUrl = requireUrl(iconUrls, id, manifest.assets.icon);
  return {
    id,
    name: manifest.name,
    tagline: manifest.tagline ?? "",
    description: manifest.description ?? "",
    swatches: manifest.swatches ?? [],
    logoLightUrl,
    logoDarkUrl,
    iconUrl,
    tokens: {
      core: requireTokens(coreTokenModules, id, manifest.tokens.core),
      light: requireTokens(lightTokenModules, id, manifest.tokens.light),
      dark: requireTokens(darkTokenModules, id, manifest.tokens.dark),
    },
  };
};

const _brandsByDiscovery: Brand[] = Object.entries(manifestModules)
  .map(([path, manifest]) => buildBrand(path, manifest))
  .sort((a, b) => {
    // joshs-karaoke-bar is the pinned default (brands[0]); then alphabetical by id.
    if (a.id === "joshs-karaoke-bar") return -1;
    if (b.id === "joshs-karaoke-bar") return 1;
    return a.id.localeCompare(b.id);
  });

if (_brandsByDiscovery.length === 0) {
  throw new Error("No brand packs discovered under brandpacks/");
}

export const BRANDS: readonly Brand[] = _brandsByDiscovery;

export const DEFAULT_BRAND_ID = BRANDS[0]?.id ?? "joshs-karaoke-bar";

export const findBrand = (id: string, brands: readonly Brand[] = BRANDS): Brand | undefined =>
  brands.find((b) => b.id === id);

// `brands` defaults to the glob-discovered registry; tests inject a synthetic
// list to prove brand-switching without shipping throwaway brandpack dirs.
export const getBrandOrDefault = (id: string | null | undefined, brands: readonly Brand[] = BRANDS): Brand => {
  if (id) {
    const found = findBrand(id, brands);
    if (found) return found;
  }
  const fallback = brands[0];
  if (!fallback) throw new Error("Brand registry is empty");
  return fallback;
};
