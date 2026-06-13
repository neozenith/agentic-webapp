import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { Brand } from "@/lib/brands";
import { BrandProvider, useBrand } from "./brand-provider";
import { ThemeProvider, useTheme } from "./theme-provider";

const cssVar = (name: string): string => document.documentElement.style.getPropertyValue(name).toLowerCase();

// Synthetic brands used to prove switching WITHOUT shipping throwaway
// brandpack dirs. The provider's `brands` prop defaults to the real glob
// registry; injecting these keeps the switching contract under test even when
// only a single real brand (V2 AI) exists on disk.
const makeBrand = (id: string, name: string, primary: string, background: string): Brand => ({
  id,
  name,
  tagline: "",
  description: "",
  swatches: [],
  logoLightUrl: "/logo.svg",
  logoDarkUrl: "/logo-dark.svg",
  iconUrl: "/icon.svg",
  tokens: {
    core: {},
    light: {
      color: {
        primary: { $value: primary, $type: "color" },
        background: { $value: background, $type: "color" },
      },
    },
    dark: {
      color: {
        primary: { $value: primary, $type: "color" },
        background: { $value: "#111111", $type: "color" },
      },
    },
  },
});

const FIXTURE_BRANDS: readonly Brand[] = [
  makeBrand("acme", "Acme", "#112233", "#ffffff"),
  makeBrand("globex", "Globex", "#445566", "#ffffff"),
];

const Probe = () => {
  const { brand, brands, setBrandId } = useBrand();
  const { toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="brand">{brand.id}</span>
      <button type="button" onClick={toggleTheme}>
        toggle-theme
      </button>
      {brands.map((b) => (
        <button key={b.id} type="button" onClick={() => setBrandId(b.id)}>
          pick-{b.id}
        </button>
      ))}
    </div>
  );
};

const renderProbe = (brands?: readonly Brand[]) =>
  render(
    <ThemeProvider>
      <BrandProvider brands={brands}>
        <Probe />
      </BrandProvider>
    </ThemeProvider>,
  );

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("style");
  document.documentElement.removeAttribute("data-brand");
  document.documentElement.classList.remove("dark");
});

describe("BrandProvider", () => {
  it("applies the default brand's inline CSS vars and data-brand on <html>", () => {
    renderProbe();
    expect(screen.getByTestId("brand")).toHaveTextContent("default-v2ai");
    expect(document.documentElement.dataset.brand).toBe("default-v2ai");
    // default-v2ai LIGHT: primary = yellow.400 (#FEC40E), background = white.
    expect(cssVar("--primary")).toBe("#fec40e");
    expect(cssVar("--background")).toBe("#ffffff");
  });

  it("switching brand repaints the inline vars, data-brand, and persists the choice", async () => {
    renderProbe(FIXTURE_BRANDS);
    // Starts on the first injected brand.
    expect(screen.getByTestId("brand")).toHaveTextContent("acme");
    expect(cssVar("--primary")).toBe("#112233");

    await userEvent.click(screen.getByRole("button", { name: "pick-globex" }));

    expect(screen.getByTestId("brand")).toHaveTextContent("globex");
    expect(document.documentElement.dataset.brand).toBe("globex");
    expect(cssVar("--primary")).toBe("#445566");
    expect(localStorage.getItem("brand-id")).toBe("globex");
  });

  it("re-resolves to the dark semantic layer when the theme flips", async () => {
    renderProbe();
    expect(cssVar("--background")).toBe("#ffffff"); // light

    await userEvent.click(screen.getByRole("button", { name: "toggle-theme" }));
    // default-v2ai DARK: background = black (#000000).
    expect(cssVar("--background")).toBe("#000000");
  });

  it("restores a previously chosen brand from localStorage", () => {
    localStorage.setItem("brand-id", "globex");
    renderProbe(FIXTURE_BRANDS);
    expect(screen.getByTestId("brand")).toHaveTextContent("globex");
    expect(cssVar("--primary")).toBe("#445566");
  });

  it("useBrand throws outside a BrandProvider", () => {
    const Bare = () => {
      useBrand();
      return null;
    };
    expect(() =>
      render(
        <ThemeProvider>
          <Bare />
        </ThemeProvider>,
      ),
    ).toThrow(/useBrand must be used inside BrandProvider/);
  });
});
