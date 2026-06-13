import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { BrandProvider, useBrand } from "./brand-provider";
import { ThemeProvider, useTheme } from "./theme-provider";

const cssVar = (name: string): string => document.documentElement.style.getPropertyValue(name).toLowerCase();

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

const renderProbe = () =>
  render(
    <ThemeProvider>
      <BrandProvider>
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
    renderProbe();
    await userEvent.click(screen.getByRole("button", { name: "pick-fsi-zurich" }));

    expect(screen.getByTestId("brand")).toHaveTextContent("fsi-zurich");
    expect(document.documentElement.dataset.brand).toBe("fsi-zurich");
    // fsi-zurich LIGHT: primary = zurich-blue.500 (#2167AE).
    expect(cssVar("--primary")).toBe("#2167ae");
    expect(localStorage.getItem("brand-id")).toBe("fsi-zurich");
  });

  it("re-resolves to the dark semantic layer when the theme flips", async () => {
    renderProbe();
    expect(cssVar("--background")).toBe("#ffffff"); // light

    await userEvent.click(screen.getByRole("button", { name: "toggle-theme" }));
    // default-v2ai DARK: background = black (#000000).
    expect(cssVar("--background")).toBe("#000000");
  });

  it("restores a previously chosen brand from localStorage", () => {
    localStorage.setItem("brand-id", "retail-woolworths");
    renderProbe();
    expect(screen.getByTestId("brand")).toHaveTextContent("retail-woolworths");
    // retail-woolworths LIGHT: primary = ww-blue.500 (#1971ED).
    expect(cssVar("--primary")).toBe("#1971ed");
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
