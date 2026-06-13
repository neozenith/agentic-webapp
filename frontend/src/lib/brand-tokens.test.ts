import { afterEach, describe, expect, it } from "vitest";

import {
  applyTokensToRoot,
  flattenTokens,
  resolveBrandTokens,
  type TokenGroup,
  tokenPathToCssVar,
} from "./brand-tokens";

describe("flattenTokens", () => {
  it("flattens nested groups to dot-paths and skips $-meta keys", () => {
    const tree: TokenGroup = {
      color: {
        $type: "color",
        $description: "ignored",
        white: { $value: "#FFFFFF" },
        zinc: { 500: { $value: "#71717A" } },
      },
      radius: { base: { $value: "0.5rem" } },
    };
    expect(flattenTokens(tree)).toEqual({
      "color.white": "#FFFFFF",
      "color.zinc.500": "#71717A",
      "radius.base": "0.5rem",
    });
  });

  it("resolves a {ref} against the combined tree, following chains", () => {
    const tree: TokenGroup = {
      color: {
        $type: "color",
        yellow: { 400: { $value: "#FEC40E" } },
        primary: { $value: "{color.yellow.400}" },
        ring: { $value: "{color.primary}" },
      },
    };
    const flat = flattenTokens(tree);
    expect(flat["color.primary"]).toBe("#FEC40E");
    expect(flat["color.ring"]).toBe("#FEC40E");
  });

  it("joins array values, quoting entries that contain commas", () => {
    const tree: TokenGroup = {
      font: {
        sans: { $type: "fontFamily", $value: ["Outfit", "Segoe, UI", "sans-serif"] },
      },
    };
    expect(flattenTokens(tree)["font.sans"]).toBe('Outfit, "Segoe, UI", sans-serif');
  });

  it("THROWS on an unresolvable reference (no graceful degradation)", () => {
    const tree: TokenGroup = {
      color: { primary: { $value: "{color.does.not.exist}" } },
    };
    expect(() => flattenTokens(tree)).toThrow(/did not resolve/);
  });

  it("THROWS on a reference cycle", () => {
    const tree: TokenGroup = {
      color: {
        a: { $value: "{color.b}" },
        b: { $value: "{color.a}" },
      },
    };
    expect(() => flattenTokens(tree)).toThrow(/cycle detected/);
  });
});

describe("tokenPathToCssVar", () => {
  it("maps color.<name> to --<name>", () => {
    expect(tokenPathToCssVar("color.primary")).toBe("--primary");
    expect(tokenPathToCssVar("color.card-foreground")).toBe("--card-foreground");
    expect(tokenPathToCssVar("color.destructive-foreground")).toBe("--destructive-foreground");
  });

  it("maps radius.base to --radius", () => {
    expect(tokenPathToCssVar("radius.base")).toBe("--radius");
  });

  it("returns null for paths it doesn't recognise", () => {
    expect(tokenPathToCssVar("font.sans")).toBeNull();
    expect(tokenPathToCssVar("radius.lg")).toBeNull();
  });
});

describe("applyTokensToRoot", () => {
  afterEach(() => {
    document.documentElement.removeAttribute("style");
  });

  it("writes known vars onto <html> and the cleanup removes exactly those", () => {
    const cleanup = applyTokensToRoot({
      "color.primary": "#FEC40E",
      "radius.base": "0.5rem",
      "font.sans": "Outfit", // unknown shape — must be skipped, not written
    });
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--primary")).toBe("#FEC40E");
    expect(root.style.getPropertyValue("--radius")).toBe("0.5rem");
    expect(root.style.getPropertyValue("--sans")).toBe("");

    cleanup();
    expect(root.style.getPropertyValue("--primary")).toBe("");
    expect(root.style.getPropertyValue("--radius")).toBe("");
  });
});

describe("resolveBrandTokens", () => {
  it("deep-merges core+semantic (semantic wins) and resolves refs against the union", () => {
    const core: TokenGroup = {
      color: {
        $type: "color",
        white: { $value: "#FFFFFF" },
        yellow: { 400: { $value: "#FEC40E" } },
      },
      radius: { base: { $value: "0.5rem" } },
    };
    const semantic: TokenGroup = {
      color: {
        background: { $value: "{color.white}" },
        primary: { $value: "{color.yellow.400}" },
      },
    };
    const resolved = resolveBrandTokens(core, semantic);
    expect(resolved["color.background"]).toBe("#FFFFFF");
    expect(resolved["color.primary"]).toBe("#FEC40E");
    // core primitives survive the merge
    expect(resolved["color.white"]).toBe("#FFFFFF");
  });
});
