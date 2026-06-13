import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { AuthProvider } from "./auth";
import { BrandProvider } from "./brand-provider";
import { Header } from "./Header";
import { ThemeProvider } from "./theme-provider";

const renderHeader = () =>
  render(
    <ThemeProvider>
      <BrandProvider>
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

describe("Header theme + brand controls", () => {
  it("renders a dark/light toggle and a brand picker listing every discovered brand", () => {
    renderHeader();
    expect(screen.getByRole("button", { name: /toggle dark mode/i })).toBeInTheDocument();
    const select = screen.getByLabelText(/switch brand/i) as HTMLSelectElement;
    expect(select.value).toBe("default-v2ai");
    expect(screen.getByRole("option", { name: "Zurich Australia" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Woolworths Group" })).toBeInTheDocument();
  });

  it("toggling the theme button flips .dark on <html> and aria-pressed", async () => {
    renderHeader();
    const toggle = screen.getByRole("button", { name: /toggle dark mode/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("choosing a brand swaps the live tokens and persists the selection", async () => {
    renderHeader();
    const select = screen.getByLabelText(/switch brand/i) as HTMLSelectElement;

    await userEvent.selectOptions(select, "fsi-zurich");
    expect(select.value).toBe("fsi-zurich");
    expect(document.documentElement.dataset.brand).toBe("fsi-zurich");
    expect(document.documentElement.style.getPropertyValue("--primary").toLowerCase()).toBe("#2167ae");
    expect(localStorage.getItem("brand-id")).toBe("fsi-zurich");
  });
});
