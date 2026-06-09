import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Admin } from "./Admin";

describe("Admin", () => {
  it("renders totals plus per-model and per-user tables", async () => {
    const bucket = { calls: 3, total_tokens: 100, est_cost_usd: 0.001234 };
    server.use(
      http.get("/api/admin/usage", () =>
        HttpResponse.json({
          totals: bucket,
          by_model: { "gemini-2.5-flash-lite": bucket },
          by_user: { uid: bucket },
        }),
      ),
    );
    render(<Admin />);
    expect(await screen.findByText("gemini-2.5-flash-lite")).toBeInTheDocument();
    expect(screen.getByText("uid")).toBeInTheDocument();
    expect(screen.getAllByText("$0.001234").length).toBeGreaterThan(0);
  });

  it("shows an empty-state row in each table when there is no usage", async () => {
    server.use(
      http.get("/api/admin/usage", () =>
        HttpResponse.json({ totals: { calls: 0, total_tokens: 0, est_cost_usd: 0 }, by_model: {}, by_user: {} }),
      ),
    );
    render(<Admin />);
    expect((await screen.findAllByText(/no usage yet/i)).length).toBe(2);
  });

  it("surfaces a fetch error", async () => {
    server.use(http.get("/api/admin/usage", () => new HttpResponse(null, { status: 500 })));
    render(<Admin />);
    expect(await screen.findByText(/usage error 500/i)).toBeInTheDocument();
  });
});
