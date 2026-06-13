# ADR-0009: Dark/light theming and live brandpack design tokens

**Status:** Accepted · implemented

## Context

The webapp needs (a) a dark/light theme and (b) the ability to re-skin the entire UI
to a different brand's design tokens **at runtime**, with no rebuild — so a single
deployment can be white-labelled live. shadcn components consume their colours through
CSS custom properties (`--primary`, `--background`, …) that Tailwind v4's `@theme inline`
block re-exports as utilities (`bg-primary` → `var(--color-primary)` → `var(--primary)`).
The pattern was researched from the sibling `rapid-whitelabelling` project (same stack).

## Decision

**Two orthogonal axes, both expressed as state on `<html>`:**

1. **Theme (dark/light)** — a `ThemeProvider` toggles the `.dark` class on
   `document.documentElement`, persisted to `localStorage["ui-theme"]`, initialised from
   `prefers-color-scheme`. A pre-hydration inline script in `index.html` applies the same
   class before first paint (no FOUC). `index.css` carries a light `:root` palette and a
   `.dark` override block.

2. **Brand (design tokens)** — a `BrandProvider` resolves a brand's
   [W3C DTCG](https://www.w3.org/community/design-tokens/) tokens (core primitives + a
   semantic light/dark layer, with `{ref}` aliases resolved recursively, **cycles throw**)
   and writes the results as **inline CSS variables on `<html>`**. Because inline styles on
   the element outrank the `:root`/`.dark` rule blocks, a brand swap repaints every utility
   with **zero React re-render**. Brands are filesystem directories under `frontend/brandpacks/<id>/`
   auto-discovered via `import.meta.glob` (drop a folder to add a brand; missing assets throw).

`ThemeProvider` wraps `BrandProvider` (brand reads the active theme to pick its light/dark
semantic layer). The Header exposes a theme toggle + brand picker.

## Consequences

- Re-skinning is O(1) and rebuild-free; adding a brand is adding a directory, not code.
- Brand token files must map to **exactly** the app's shadcn variable set (this app's set is
  smaller than the reference — no `sidebar-*`/`chart-*`; it adds `destructive-foreground`).
- **Fonts are not yet swapped live**: token files declare `font.sans`, but the path→CSS-var
  mapper only emits `color.*` and `radius.base`. Per-brand fonts need a `--font-sans` mapping
  + webfont loading — deferred, faithful to the reference.
- The `import.meta.glob` and `?url` types require an ambient `vite-env.d.ts`; the project's
  pinned `tsconfig.types` allowlist means the editor may not pick it up even when `tsc` is clean.

## Lens

When a capability must vary **per-deployment without a rebuild**, push the variation into
**data the runtime reads** (token files + inline CSS vars on a root element), not into
build-time configuration. Keep independent concerns on **orthogonal axes** (theme ⟂ brand)
so they compose instead of multiplying into a combinatorial config. Degrade on *environment*
capability, never on *requirement*: a missing brand asset throws loudly rather than silently
falling back to a default skin.
