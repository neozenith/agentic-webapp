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
  it("renders each conversation turn as a card with role, text, and tool-call summary", async () => {
    server.use(
      http.get("/apps/assistant/users/web-user/sessions/s1", () =>
        HttpResponse.json({
          id: "s1",
          state: { title: "My receipts" },
          events: [
            { author: "user", content: { parts: [{ text: "list my assets" }] } },
            { author: "assistant", content: { parts: [{ functionCall: { name: "list_assets", args: {} } }] } },
            { author: "assistant", content: { parts: [{ functionResponse: { name: "list_assets" } }] } },
            { author: "assistant", content: { parts: [{ text: "Here are **2** assets." }] } },
          ],
        }),
      ),
    );
    renderAt("/admin/users/web-user/sessions/s1");
    // Title comes from session state; both turn roles are labelled.
    expect(await screen.findByText("My receipts")).toBeInTheDocument();
    expect(screen.getByText("list my assets")).toBeInTheDocument();
    expect(screen.getByText("you")).toBeInTheDocument();
    expect(screen.getAllByText("agent").length).toBeGreaterThan(0);
    // The tool-call turn is summarised (not invisible) and the tool result is flagged.
    expect(screen.getByText("list_assets")).toBeInTheDocument();
    expect(screen.getByText(/called/i)).toBeInTheDocument();
    expect(screen.getByText(/tool result/i)).toBeInTheDocument();
    // The agent's prose still renders as Markdown (bold → <strong>).
    expect(screen.getByText("2").tagName).toBe("STRONG");
    // The collapsible raw-JSON fallback is present.
    expect(screen.getByText("Raw JSON")).toBeInTheDocument();
  });

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
