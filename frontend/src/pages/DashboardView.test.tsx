import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

// Stub the chart lib (jsdom can't run plotly's bundle); KpiCard + error paths are real code.
vi.mock("plotly.js-dist-min", () => ({ default: {} }));
vi.mock("react-plotly.js/factory", () => ({
  default: () => () => <div data-testid="plot" />,
}));

import { server } from "../test/server";
import { DashboardView } from "./DashboardView";

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/dashboards/:dashboardId" element={<DashboardView />} />
      </Routes>
    </MemoryRouter>,
  );

const emptyResult = { columns: [], rows: [], sql: "", row_count: 0 };

describe("DashboardView", () => {
  it("renders KPI, Plotly, and error charts", async () => {
    server.use(
      http.get("/api/dashboards/:id/render", () =>
        HttpResponse.json({
          dashboard_id: "sales",
          name: "Sales overview",
          description: "Revenue and orders",
          semantic_model_id: "sales",
          charts: [
            {
              chart_id: "kpi1",
              title: "Total revenue",
              chart_type: "kpi",
              figure: { data: [], layout: { unit: "$" } },
              value: 4200,
              result: emptyResult,
              error: null,
            },
            {
              chart_id: "bar1",
              title: "Revenue by region",
              chart_type: "bar",
              figure: { data: [{ type: "bar" }], layout: {} },
              value: null,
              result: emptyResult,
              error: null,
            },
            {
              chart_id: "bad1",
              title: "Broken chart",
              chart_type: "line",
              figure: { data: [], layout: {} },
              value: null,
              result: emptyResult,
              error: "query failed",
            },
          ],
        }),
      ),
    );
    renderAt("/dashboards/sales");
    expect(await screen.findByText("Sales overview")).toBeInTheDocument();
    expect(screen.getByText("$4,200")).toBeInTheDocument();
    expect(screen.getByTestId("plot")).toBeInTheDocument();
    expect(screen.getByText(/query failed/)).toBeInTheDocument();
  });

  it("shows an empty state when a dashboard has no charts", async () => {
    server.use(
      http.get("/api/dashboards/:id/render", () =>
        HttpResponse.json({
          dashboard_id: "empty",
          name: "Empty",
          description: "",
          semantic_model_id: null,
          charts: [],
        }),
      ),
    );
    renderAt("/dashboards/empty");
    expect(await screen.findByText(/This dashboard has no charts/i)).toBeInTheDocument();
  });

  it("surfaces a render error", async () => {
    server.use(http.get("/api/dashboards/:id/render", () => new HttpResponse(null, { status: 500 })));
    renderAt("/dashboards/x");
    expect(await screen.findByText(/dashboard render error 500/i)).toBeInTheDocument();
  });
});
