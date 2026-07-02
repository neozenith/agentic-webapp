import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Semantic } from "./Semantic";

const MODEL = {
  model_id: "sales",
  name: "Sales",
  description: "Sales semantic model",
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
  entities: [
    {
      name: "orders",
      description: "Customer orders",
      table: "fct_orders",
      primary_key: "order_id",
      time_dimension: "ordered_at",
      dimensions: [{ name: "region", column: "region", dtype: "string", description: "Sales region" }],
      measures: [{ name: "total_revenue", column: "amount", agg: "sum", description: "Total revenue", unit: "$" }],
    },
  ],
};

describe("Semantic page", () => {
  it("lists models, shows entities, and runs a query rendering rows + sql", async () => {
    server.use(
      http.get("/api/semantic/models", () => HttpResponse.json([MODEL])),
      http.post("/api/semantic/query", () =>
        HttpResponse.json({
          columns: ["region", "total_revenue"],
          rows: [{ region: "West", total_revenue: 5000 }],
          sql: "SELECT region, SUM(amount) FROM fct_orders GROUP BY region",
          row_count: 1,
        }),
      ),
    );
    const user = userEvent.setup();
    render(<Semantic />);

    // model card
    await user.click(await screen.findByText("Sales"));
    // entity exploration + query runner appear
    expect(await screen.findByText("fct_orders")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "region" })).toBeInTheDocument();

    // pick a measure and run
    await user.click(screen.getByRole("checkbox", { name: "total_revenue" }));
    await user.selectOptions(screen.getByLabelText("Time grain"), "month");
    await user.click(screen.getByRole("button", { name: /run/i }));

    expect(await screen.findByText("West")).toBeInTheDocument();
    expect(screen.getByText("1 rows")).toBeInTheDocument();
    expect(screen.getByText(/SELECT region, SUM\(amount\)/)).toBeInTheDocument();
  });

  it("surfaces a query error without crashing the page", async () => {
    server.use(
      http.get("/api/semantic/models", () => HttpResponse.json([MODEL])),
      http.post("/api/semantic/query", () => new HttpResponse(null, { status: 500 })),
    );
    const user = userEvent.setup();
    render(<Semantic />);
    await user.click(await screen.findByText("Sales"));
    await user.click(await screen.findByRole("button", { name: /run/i }));
    expect(await screen.findByText(/semantic query error 500/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no models", async () => {
    server.use(http.get("/api/semantic/models", () => HttpResponse.json([])));
    render(<Semantic />);
    expect(await screen.findByText(/No semantic models defined yet/i)).toBeInTheDocument();
  });

  it("surfaces a load error", async () => {
    server.use(http.get("/api/semantic/models", () => new HttpResponse(null, { status: 500 })));
    render(<Semantic />);
    expect(await screen.findByText(/semantic models error 500/i)).toBeInTheDocument();
  });
});
