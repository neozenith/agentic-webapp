import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { server } from "../test/server";
import { AuthProvider, RequireArea } from "./auth";
import { Sidebar } from "./Sidebar";

const me = (permissions: string[], extra: Record<string, unknown> = {}) =>
  http.get("/api/me", () =>
    HttpResponse.json({
      email: "u@example.com",
      user_id: "u",
      environment: "test",
      roles: ["x"],
      permissions,
      ...extra,
    }),
  );

const renderWithAuth = (ui: React.ReactNode) =>
  render(
    <AuthProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </AuthProvider>,
  );

afterEach(() => localStorage.clear());

describe("RBAC gating", () => {
  it("hides nav areas the active user's role doesn't grant", async () => {
    server.use(me(["home", "chat", "sessions"])); // a viewer: no assets/analytics/admin
    renderWithAuth(<Sidebar />);
    expect(await screen.findByRole("link", { name: "Chat" })).toBeInTheDocument();
    // wait for load, then assert the gated items are absent
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Analytics" })).not.toBeInTheDocument();
  });

  it("RequireArea blocks a page the user can't access", async () => {
    server.use(me(["home", "chat", "sessions"]));
    renderWithAuth(
      <RequireArea area="admin">
        <div>secret-admin</div>
      </RequireArea>,
    );
    expect(await screen.findByText(/No access/i)).toBeInTheDocument();
    expect(screen.queryByText("secret-admin")).not.toBeInTheDocument();
  });

  it("RequireArea allows a page the user can access", async () => {
    server.use(me(["home", "admin"]));
    renderWithAuth(
      <RequireArea area="admin">
        <div>secret-admin</div>
      </RequireArea>,
    );
    expect(await screen.findByText("secret-admin")).toBeInTheDocument();
  });

  it("offers a persona switcher (dev/test) that sets the simulated identity on change", async () => {
    server.use(
      me(["home"]),
      http.get("/api/auth/personas", () =>
        HttpResponse.json([{ email: "ada.admin@example.com", name: "Ada — Admin", roles: ["admin"] }]),
      ),
    );
    const { Header } = await import("./Header");
    renderWithAuth(<Header />);
    const select = await screen.findByLabelText(/Switch test persona/i);
    await userEvent.selectOptions(select, "ada.admin@example.com");
    // the chosen persona is persisted and sent as the IAP header on subsequent calls
    expect(localStorage.getItem("persona-email")).toBe("ada.admin@example.com");
    expect((select as HTMLSelectElement).value).toBe("ada.admin@example.com");
  });
});
