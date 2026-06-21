import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Dashboards } from "./Dashboards";

const renderPage = () =>
  render(
    <MemoryRouter>
      <Dashboards />
    </MemoryRouter>,
  );

describe("Dashboards list", () => {
  it("lists dashboards as cards linking to their detail route", async () => {
    server.use(
      http.get("/api/dashboards", () =>
        HttpResponse.json([
          {
            dashboard_id: "sales",
            name: "Sales overview",
            description: "Revenue and orders",
            charts: [{ chart_id: "c1" }, { chart_id: "c2" }],
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
    );
    renderPage();
    const link = await screen.findByRole("link", { name: /Sales overview/i });
    expect(link).toHaveAttribute("href", "/dashboards/sales");
    expect(screen.getByText("2 charts")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    server.use(http.get("/api/dashboards", () => HttpResponse.json([])));
    renderPage();
    expect(await screen.findByText(/No dashboards defined yet/i)).toBeInTheDocument();
  });

  it("surfaces an error", async () => {
    server.use(http.get("/api/dashboards", () => new HttpResponse(null, { status: 500 })));
    renderPage();
    expect(await screen.findByText(/dashboards error 500/i)).toBeInTheDocument();
  });
});
