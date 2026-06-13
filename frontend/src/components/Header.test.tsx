import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { Brand } from "@/lib/brands";
import { AuthProvider } from "./auth";
import { BrandProvider } from "./brand-provider";
import { Header } from "./Header";
import { ThemeProvider } from "./theme-provider";

// Two synthetic brands to exercise the multi-brand picker without shipping
// throwaway brandpack dirs (the provider's `brands` prop defaults to the real
// single-brand glob registry in production).
const makeBrand = (id: string, name: string, primary: string): Brand => ({
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
    light: { color: { primary: { $value: primary, $type: "color" } } },
    dark: { color: { primary: { $value: primary, $type: "color" } } },
  },
});

const FIXTURE_BRANDS: readonly Brand[] = [
  makeBrand("acme", "Acme", "#112233"),
  makeBrand("globex", "Globex", "#445566"),
];

const renderHeader = (brands?: readonly Brand[]) =>
  render(
    <ThemeProvider>
      <BrandProvider brands={brands}>
        <AuthProvider>
          <MemoryRouter>
            <Header />
          </MemoryRouter>
        </AuthProvider>
      </BrandProvider>
    </ThemeProvider>,
  );

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("style");
  document.documentElement.removeAttribute("data-brand");
  document.documentElement.classList.remove("dark");
});

const cssVar = (name: string): string => document.documentElement.style.getPropertyValue(name).toLowerCase();

describe("Header theme + brand controls", () => {
  it("renders the dark/light toggle and shows the brand picker now that 2 real brands exist", () => {
    renderHeader(); // real registry = Josh's Karaoke Bar + V2 AI
    expect(screen.getByRole("button", { name: /toggle dark mode/i })).toBeInTheDocument();
    const select = screen.getByLabelText(/switch brand/i) as HTMLSelectElement;
    // joshs-karaoke-bar is the pinned default (brands[0]).
    expect(select.value).toBe("joshs-karaoke-bar");
    expect(screen.getByRole("option", { name: "Josh's Karaoke Bar" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "V2 AI" })).toBeInTheDocument();
  });

  it("defaults to the karaoke brand and switches to V2 AI, repainting --primary", async () => {
    renderHeader(); // real registry
    // Karaoke default LIGHT primary = neon magenta.
    expect(cssVar("--primary")).toBe("#e91e63");

    const select = screen.getByLabelText(/switch brand/i) as HTMLSelectElement;
    await userEvent.selectOptions(select, "default-v2ai");

    expect(select.value).toBe("default-v2ai");
    expect(document.documentElement.dataset.brand).toBe("default-v2ai");
    // V2 AI LIGHT primary = signature yellow.
    expect(cssVar("--primary")).toBe("#fec40e");
    expect(localStorage.getItem("brand-id")).toBe("default-v2ai");
  });

  it("toggling the theme button flips .dark on <html> and aria-pressed", async () => {
    renderHeader();
    const toggle = screen.getByRole("button", { name: /toggle dark mode/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("shows the brand picker and swaps live tokens when multiple brands exist", async () => {
    renderHeader(FIXTURE_BRANDS);
    const select = screen.getByLabelText(/switch brand/i) as HTMLSelectElement;
    expect(select.value).toBe("acme");
    expect(screen.getByRole("option", { name: "Acme" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Globex" })).toBeInTheDocument();

    await userEvent.selectOptions(select, "globex");
    expect(select.value).toBe("globex");
    expect(document.documentElement.dataset.brand).toBe("globex");
    expect(document.documentElement.style.getPropertyValue("--primary").toLowerCase()).toBe("#445566");
    expect(localStorage.getItem("brand-id")).toBe("globex");
  });
});
