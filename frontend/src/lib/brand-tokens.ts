/**
 * W3C Design Tokens (DTCG) resolver + CSS-variable applier.
 *
 * Spec: https://www.designtokens.org/tr/2025.10/format/
 *
 * Token shape:
 *   { "$value": "<literal-or-{ref}>", "$type": "color" | "dimension" | ... }
 *
 * Group nodes can declare a `$type` that leaves inherit. References use the
 * `{path.to.token}` syntax and resolve against the *combined* token tree
 * (core + semantic), so semantic tokens (e.g. `color.background`) can point
 * at primitive entries (e.g. `color.zinc.500`).
 *
 * Ported ~verbatim from the rapid-whitelabelling reference. Per the project's
 * "no graceful degradation" rule, unresolved or cyclic references THROW.
 */

export type TokenValue = string | string[];

export interface TokenLeaf {
  $value: TokenValue;
  $type?: string;
  $description?: string;
}

export type TokenGroup = {
  $type?: string;
  $description?: string;
  [key: string]: TokenGroup | TokenLeaf | string | string[] | undefined;
};

const REF_PATTERN = /^\{([^}]+)\}$/;

const isLeaf = (node: unknown): node is TokenLeaf => typeof node === "object" && node !== null && "$value" in node;

/**
 * Walk a token tree and produce a flat map of `dot.path -> resolved value`.
 * Resolves `{ref}` references against the same combined tree, with cycle
 * detection. Throws if a reference can't be resolved or if a cycle exists —
 * those are configuration errors and should fail loudly.
 */
export const flattenTokens = (tree: TokenGroup, combined: TokenGroup = tree): Record<string, string> => {
  const out: Record<string, string> = {};

  const lookupByPath = (path: string): TokenLeaf | undefined => {
    const segments = path.split(".");
    let cursor: unknown = combined;
    for (const seg of segments) {
      if (typeof cursor !== "object" || cursor === null) return undefined;
      cursor = (cursor as Record<string, unknown>)[seg];
    }
    return isLeaf(cursor) ? cursor : undefined;
  };

  const resolveValue = (raw: TokenValue, seen: ReadonlySet<string>): string => {
    if (Array.isArray(raw)) {
      return raw.map((entry) => (entry.includes(",") ? `"${entry}"` : entry)).join(", ");
    }
    const match = REF_PATTERN.exec(raw);
    if (!match) return raw;
    const refPath = match[1];
    if (seen.has(refPath)) {
      throw new Error(`Token reference cycle detected at {${refPath}}`);
    }
    const target = lookupByPath(refPath);
    if (!target) {
      throw new Error(`Token reference {${refPath}} did not resolve`);
    }
    return resolveValue(target.$value, new Set([...seen, refPath]));
  };

  const walk = (node: TokenGroup, prefix: string[]): void => {
    for (const [key, child] of Object.entries(node)) {
      if (key.startsWith("$")) continue;
      if (child === undefined) continue;
      if (isLeaf(child)) {
        const path = [...prefix, key].join(".");
        out[path] = resolveValue(child.$value, new Set([path]));
      } else if (typeof child === "object" && !Array.isArray(child)) {
        walk(child as TokenGroup, [...prefix, key]);
      }
    }
  };

  walk(tree, []);
  return out;
};

/**
 * Map a flat token path to its corresponding shadcn/ui CSS-variable name.
 * Tokens whose path matches `color.<name>` map to `--<name>`; `radius.base`
 * maps to `--radius`; `font.sans` / `font.display` map to `--font-sans` /
 * `--font-display` (the value is already a usable CSS font-family string —
 * `flattenTokens` joins the DTCG fontFamily array and quotes any entry with a
 * comma). Unknown shapes return null and are silently skipped — the applier
 * only writes variables it knows about.
 */
export const tokenPathToCssVar = (path: string): string | null => {
  if (path.startsWith("color.")) return `--${path.slice("color.".length)}`;
  if (path === "radius.base") return "--radius";
  if (path === "font.sans") return "--font-sans";
  if (path === "font.display") return "--font-display";
  return null;
};

/**
 * Apply a resolved token set as inline CSS custom properties on the document
 * root. Inline styles override `:root` and `.dark` rule blocks regardless of
 * which class is set, so we don't need to juggle scoped style sheets.
 *
 * Returns a cleanup function that removes the applied variables (handy for
 * tests; the app itself just keeps overriding on each switch).
 */
export const applyTokensToRoot = (resolved: Record<string, string>): (() => void) => {
  const root = document.documentElement;
  const written: string[] = [];
  for (const [path, value] of Object.entries(resolved)) {
    const cssVar = tokenPathToCssVar(path);
    if (!cssVar) continue;
    root.style.setProperty(cssVar, value);
    written.push(cssVar);
  }
  return () => {
    for (const cssVar of written) root.style.removeProperty(cssVar);
  };
};

const mergeDeep = (a: TokenGroup, b: TokenGroup): TokenGroup => {
  const out: TokenGroup = { ...a };
  for (const [key, valB] of Object.entries(b)) {
    const valA = out[key];
    if (
      typeof valA === "object" &&
      valA !== null &&
      !Array.isArray(valA) &&
      !isLeaf(valA) &&
      typeof valB === "object" &&
      valB !== null &&
      !Array.isArray(valB) &&
      !isLeaf(valB)
    ) {
      out[key] = mergeDeep(valA as TokenGroup, valB as TokenGroup);
    } else {
      out[key] = valB;
    }
  }
  return out;
};

/**
 * Combine a brand's core + semantic (light or dark) tokens into a single
 * resolved map. Semantic tokens win on key collisions; references inside
 * either tree resolve against the combined tree.
 */
export const resolveBrandTokens = (core: TokenGroup, semantic: TokenGroup): Record<string, string> => {
  const combined = mergeDeep(core, semantic);
  return flattenTokens(combined, combined);
};
