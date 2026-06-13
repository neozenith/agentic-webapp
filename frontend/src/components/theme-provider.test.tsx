import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { ThemeProvider, useTheme } from "./theme-provider";

const Probe = () => {
  const { theme, toggleTheme } = useTheme();
  return (
    <button type="button" onClick={toggleTheme}>
      theme:{theme}
    </button>
  );
};

const defaultMatchMedia = globalThis.matchMedia;

afterEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove("dark");
  globalThis.matchMedia = defaultMatchMedia;
});

describe("ThemeProvider", () => {
  it("defaults to light (no stored value, OS reports no dark preference)", () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole("button")).toHaveTextContent("theme:light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggling adds/removes the .dark class on <html> and persists to localStorage", async () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    const button = screen.getByRole("button");

    await userEvent.click(button);
    expect(button).toHaveTextContent("theme:dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("ui-theme")).toBe("dark");

    await userEvent.click(button);
    expect(button).toHaveTextContent("theme:light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("ui-theme")).toBe("light");
  });

  it("reads the initial theme from localStorage", () => {
    localStorage.setItem("ui-theme", "dark");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole("button")).toHaveTextContent("theme:dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("falls back to prefers-color-scheme when nothing is stored", () => {
    globalThis.matchMedia = ((query: string) =>
      ({
        matches: true,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList) as typeof globalThis.matchMedia;
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole("button")).toHaveTextContent("theme:dark");
  });

  it("useTheme throws outside a ThemeProvider", () => {
    expect(() => render(<Probe />)).toThrow(/useTheme must be used inside ThemeProvider/);
  });
});
