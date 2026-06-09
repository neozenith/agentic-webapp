import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Admin } from "./Admin";

const bucket = { calls: 3, total_tokens: 100, est_cost_usd: 0.001234 };
const noRecords = http.get("/api/admin/usage/records", () => HttpResponse.json([]));

const renderAdmin = () =>
  render(
    <MemoryRouter>
      <Admin />
    </MemoryRouter>,
  );

describe("Admin", () => {
  it("renders totals plus per-model and per-user tables", async () => {
    server.use(
      http.get("/api/admin/usage", () =>
        HttpResponse.json({ totals: bucket, by_model: { "gemini-2.5-flash-lite": bucket }, by_user: { uid: bucket } }),
      ),
      noRecords,
    );
    renderAdmin();
    expect(await screen.findByText("gemini-2.5-flash-lite")).toBeInTheDocument();
    expect(screen.getByText("uid")).toBeInTheDocument();
    expect(screen.getAllByText("$0.001234").length).toBeGreaterThan(0);
  });

  it("links each usage record's session id to its chat (relaunch)", async () => {
    server.use(
      http.get("/api/admin/usage", () => HttpResponse.json({ totals: bucket, by_model: {}, by_user: {} })),
      http.get("/api/admin/usage/records", () =>
        HttpResponse.json([
          {
            request_id: "r1",
            session_id: "sess-42",
            user_id: "uid",
            model_id: "gemini-2.5-flash-lite",
            total_tokens: 10,
            est_cost_usd: 0.000001,
            timestamp: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
    );
    renderAdmin();
    expect(await screen.findByRole("link", { name: "sess-42" })).toHaveAttribute("href", "/chat/sess-42");
  });

  it("shows an empty-state row in each table when there is no usage", async () => {
    server.use(
      http.get("/api/admin/usage", () =>
        HttpResponse.json({ totals: { calls: 0, total_tokens: 0, est_cost_usd: 0 }, by_model: {}, by_user: {} }),
      ),
      noRecords,
    );
    renderAdmin();
    expect((await screen.findAllByText(/no usage yet/i)).length).toBe(2);
    expect(screen.getByText(/no calls yet/i)).toBeInTheDocument();
  });

  it("surfaces a fetch error", async () => {
    server.use(
      http.get("/api/admin/usage", () => new HttpResponse(null, { status: 500 })),
      noRecords,
    );
    renderAdmin();
    expect(await screen.findByText(/usage error 500/i)).toBeInTheDocument();
  });
});
