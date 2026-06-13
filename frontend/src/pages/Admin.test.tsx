import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Admin } from "./Admin";

const totals = { totals: { calls: 5, total_tokens: 300, est_cost_usd: 0.001234 }, by_model: {}, by_user: {} };

const renderAdmin = () =>
  render(
    <MemoryRouter>
      <Admin />
    </MemoryRouter>,
  );

describe("Admin overview", () => {
  it("shows totals and a per-user table linking into each user", async () => {
    server.use(
      http.get("/api/admin/usage", () => HttpResponse.json(totals)),
      http.get("/api/admin/users", () =>
        HttpResponse.json([
          {
            user_id: "alice@example.com",
            sessions: 2,
            calls: 3,
            total_tokens: 200,
            est_cost_usd: 0.001,
            name: "Alice Smith",
            email: "alice@corp.example",
          },
          { user_id: "bob@example.com", sessions: 1, calls: 2, total_tokens: 100, est_cost_usd: 0.0002 },
        ]),
      ),
    );
    renderAdmin();
    expect(await screen.findByText("$0.001234")).toBeInTheDocument(); // totals stat
    // Known identity: name + email render alongside the (still clickable) pseudonymous user_id.
    expect(await screen.findByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("alice@corp.example")).toBeInTheDocument();
    const alice = screen.getByRole("link", { name: "alice@example.com" });
    expect(alice).toHaveAttribute("href", "/admin/users/alice%40example.com");
    // Unknown identity: falls back to just the user_id link.
    expect(screen.getByRole("link", { name: "bob@example.com" })).toBeInTheDocument();
  });

  it("shows an empty users row when there is no usage", async () => {
    server.use(
      http.get("/api/admin/usage", () => HttpResponse.json(totals)),
      http.get("/api/admin/users", () => HttpResponse.json([])),
    );
    renderAdmin();
    expect(await screen.findByText(/no usage yet/i)).toBeInTheDocument();
  });

  it("surfaces a fetch error", async () => {
    server.use(
      http.get("/api/admin/usage", () => new HttpResponse(null, { status: 500 })),
      http.get("/api/admin/users", () => HttpResponse.json([])),
    );
    renderAdmin();
    expect(await screen.findByText(/error/i)).toBeInTheDocument();
  });
});
