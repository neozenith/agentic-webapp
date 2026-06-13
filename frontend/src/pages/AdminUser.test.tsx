import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { AdminUser } from "./AdminUser";

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/users/:userId" element={<AdminUser />} />
      </Routes>
    </MemoryRouter>,
  );

describe("AdminUser drilldown", () => {
  it("lists the user's sessions with links to the chat and the raw view", async () => {
    server.use(
      http.get("/api/admin/users/:userId/sessions", () =>
        HttpResponse.json([
          {
            session_id: "sess-123456789012",
            calls: 2,
            total_tokens: 150,
            est_cost_usd: 0.0009,
            last_timestamp: "2026-06-12T00:00:00Z",
          },
        ]),
      ),
    );
    renderAt("/admin/users/alice%40example.com");
    // header shows the user
    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    // open-chat link relaunches the persisted session
    const chat = screen.getByRole("link", { name: /open chat/i });
    expect(chat).toHaveAttribute("href", "/chat/sess-123456789012");
    // raw-logs link
    const raw = screen.getByRole("link", { name: /raw session logs/i });
    expect(raw).toHaveAttribute("href", "/admin/users/alice%40example.com/sessions/sess-123456789012");
  });

  it("shows an empty state with no sessions", async () => {
    server.use(http.get("/api/admin/users/:userId/sessions", () => HttpResponse.json([])));
    renderAt("/admin/users/x");
    expect(await screen.findByText(/No sessions for this user/i)).toBeInTheDocument();
  });
});
