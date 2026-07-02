import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("renders the timespine controls and re-requests /render with the grain param", async () => {
    const grains: (string | null)[] = [];
    server.use(
      http.get("/api/dashboards/:id/render", ({ request }) => {
        grains.push(new URL(request.url).searchParams.get("grain"));
        return HttpResponse.json({
          dashboard_id: "sales",
          name: "Sales overview",
          description: "Revenue and orders",
          semantic_model_id: "sales",
          charts: [],
        });
      }),
    );
    const user = userEvent.setup();
    renderAt("/dashboards/sales");

    expect(await screen.findByText("Sales overview")).toBeInTheDocument();
    // Controls render.
    expect(screen.getByLabelText("Grain")).toBeInTheDocument();
    expect(screen.getByLabelText("Start date")).toBeInTheDocument();
    expect(screen.getByLabelText("End date")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /last 12 months/i })).toBeInTheDocument();
    // Initial render had no grain override.
    expect(grains).toEqual([null]);

    await user.selectOptions(screen.getByLabelText("Grain"), "month");

    // The change re-requests /render with grain=month, and the control reflects it.
    await waitFor(() => expect(grains).toContain("month"));
    expect((screen.getByLabelText("Grain") as HTMLSelectElement).value).toBe("month");
  });

  it("applies the Last 12 months preset by sending start+end to /render", async () => {
    const ranges: { start: string | null; end: string | null }[] = [];
    server.use(
      http.get("/api/dashboards/:id/render", ({ request }) => {
        const sp = new URL(request.url).searchParams;
        ranges.push({ start: sp.get("start"), end: sp.get("end") });
        return HttpResponse.json({
          dashboard_id: "sales",
          name: "Sales overview",
          description: "",
          semantic_model_id: "sales",
          charts: [],
        });
      }),
    );
    const user = userEvent.setup();
    renderAt("/dashboards/sales");
    await screen.findByText("Sales overview");

    await user.click(screen.getByRole("button", { name: /last 12 months/i }));
    await waitFor(() => {
      const last = ranges[ranges.length - 1];
      expect(last.start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(last.end).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });
  });
});
