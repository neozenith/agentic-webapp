import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { AdminSessionRaw } from "./AdminSessionRaw";

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/users/:userId/sessions/:sessionId" element={<AdminSessionRaw />} />
      </Routes>
    </MemoryRouter>,
  );

describe("AdminSessionRaw", () => {
  it("renders the raw session JSON with chat + back links", async () => {
    server.use(
      http.get("/apps/assistant/users/web-user/sessions/s1", () =>
        HttpResponse.json({ id: "s1", state: { _attached_asset_ids: ["a1"] }, events: [] }),
      ),
    );
    renderAt("/admin/users/web-user/sessions/s1");
    expect(await screen.findByText(/_attached_asset_ids/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open chat/i })).toHaveAttribute("href", "/chat/s1");
  });

  it("surfaces an error", async () => {
    server.use(http.get("/apps/assistant/users/web-user/sessions/gone", () => new HttpResponse(null, { status: 404 })));
    renderAt("/admin/users/web-user/sessions/gone");
    expect(await screen.findByText(/session error 404/i)).toBeInTheDocument();
  });
});
