import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { AuthProvider } from "./components/auth";
import { BrandProvider } from "./components/brand-provider";
import { ThemeProvider } from "./components/theme-provider";
import { Home } from "./pages/Home";
import { server } from "./test/server";

// The header (rendered inside App) consumes Theme + Brand context, so the shell is wrapped
// exactly as in main.tsx (ThemeProvider outermost, then BrandProvider).
const renderApp = (path = "/chat") =>
  render(
    <ThemeProvider>
      <BrandProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route element={<App />}>
                <Route path="/chat" element={<div>chat-content</div>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </BrandProvider>
    </ThemeProvider>,
  );

afterEach(() => localStorage.clear());

describe("App shell", () => {
  it("renders the brand, nav tabs, the active route, and the outlet", () => {
    renderApp("/chat");
    expect(screen.getByText(/agentic-webapp/i)).toBeInTheDocument();
    // NavLink marks the active route with aria-current="page".
    expect(screen.getByRole("link", { name: "Chat" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("chat-content")).toBeInTheDocument();
  });

  it("shows the signed-in user and environment in the header", async () => {
    server.use(
      http.get("/api/me", () => HttpResponse.json({ email: "alice@example.com", user_id: "u1", environment: "prod" })),
    );
    renderApp("/chat");
    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("prod")).toBeInTheDocument();
  });

  it("falls back to 'guest' when there is no signed-in identity", async () => {
    renderApp("/chat"); // default /api/me handler returns null identity
    expect(await screen.findByText("guest")).toBeInTheDocument();
  });
});

// The shell carries no fixed-width column on mobile: the rail is `hidden md:flex` (out of the
// flex row), and a hamburger in the header opens an off-canvas drawer instead. jsdom has no
// layout engine, so we assert the structural/aria contract (toggle state, drawer mount, nav
// reachability) rather than pixel widths — the e2e mobile suite owns the overflow measurement.
describe("mobile nav drawer", () => {
  it("opens from the header hamburger, exposes the nav, and closes via the backdrop", async () => {
    const user = userEvent.setup();
    renderApp("/chat");

    const hamburger = screen.getByRole("button", { name: /toggle navigation menu/i });
    expect(hamburger).toHaveAttribute("aria-expanded", "false");
    expect(hamburger).toHaveAttribute("aria-controls", "mobile-nav-drawer");
    // Closed: the drawer (and its backdrop) is not mounted, so it can't add to the scroll width.
    expect(screen.queryByRole("button", { name: /close navigation menu/i })).not.toBeInTheDocument();

    await user.click(hamburger);
    expect(hamburger).toHaveAttribute("aria-expanded", "true");
    const backdrop = screen.getByRole("button", { name: /close navigation menu/i });
    expect(backdrop).toBeInTheDocument();
    // Nav is reachable inside the drawer (a second "Chat" link, in addition to the desktop rail).
    const drawer = screen.getByRole("complementary", { name: "Navigation" });
    expect(within(drawer).getByRole("link", { name: "Chat" })).toBeInTheDocument();

    await user.click(backdrop);
    expect(hamburger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: /close navigation menu/i })).not.toBeInTheDocument();
  });

  it("closes the drawer when a nav item is tapped", async () => {
    const user = userEvent.setup();
    renderApp("/chat");
    await user.click(screen.getByRole("button", { name: /toggle navigation menu/i }));

    const drawer = screen.getByRole("complementary", { name: "Navigation" });
    await user.click(within(drawer).getByRole("link", { name: "Home" }));

    expect(screen.queryByRole("complementary", { name: "Navigation" })).not.toBeInTheDocument();
  });

  it("closes the drawer on Escape", async () => {
    const user = userEvent.setup();
    renderApp("/chat");
    const hamburger = screen.getByRole("button", { name: /toggle navigation menu/i });
    await user.click(hamburger);
    expect(screen.getByRole("complementary", { name: "Navigation" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(hamburger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: "Navigation" })).not.toBeInTheDocument();
  });
});

describe("Home", () => {
  it("renders the heading and primary links", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "agentic-webapp" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Chat with the agent/i })).toHaveAttribute("href", "/chat");
  });
});
