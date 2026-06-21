import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Dbt } from "./Dbt";

const PROJECT = {
  name: "warehouse",
  profile: "bq",
  version: "1.8.0",
  target: "dev",
  project_dir: "/dbt",
  dbt_cli_available: true,
  model_count: 2,
  models: [
    {
      name: "stg_orders",
      resource_type: "model",
      db_schema: "staging",
      materialized: "view",
      description: "",
      depends_on: [],
      tags: [],
      path: "models/staging/stg_orders.sql",
    },
    {
      name: "fct_orders",
      resource_type: "model",
      db_schema: "marts",
      materialized: "table",
      description: "",
      depends_on: ["stg_orders"],
      tags: ["finance"],
      path: "models/marts/fct_orders.sql",
    },
  ],
};

describe("Dbt page", () => {
  it("shows the project header, models, and a run result panel", async () => {
    server.use(
      http.get("/api/dbt/project", () => HttpResponse.json(PROJECT)),
      http.post("/api/dbt/run", () =>
        HttpResponse.json({
          command: "run",
          success: true,
          return_code: 0,
          stdout: "Completed successfully",
          stderr: "a warning",
          nodes: [{ unique_id: "model.warehouse.fct_orders", status: "success" }],
          elapsed_seconds: 1.23,
        }),
      ),
    );
    const user = userEvent.setup();
    render(<Dbt />);

    expect(await screen.findByText("warehouse")).toBeInTheDocument();
    expect(screen.getByText("dbt CLI available")).toBeInTheDocument();
    expect(screen.getByText("2 models")).toBeInTheDocument();
    expect(screen.getByText("fct_orders")).toBeInTheDocument();
    // stg_orders appears both as a model row and as fct_orders' depends_on badge
    expect(screen.getAllByText("stg_orders").length).toBeGreaterThanOrEqual(2);

    await user.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByText("success")).toBeInTheDocument();
    expect(screen.getByText("exit 0")).toBeInTheDocument();
    expect(screen.getByText("Completed successfully")).toBeInTheDocument();
    expect(screen.getByText("a warning")).toBeInTheDocument();
    expect(screen.getByText(/1 nodes/)).toBeInTheDocument();
  });

  it("renders the unavailable badge and an empty model table", async () => {
    server.use(
      http.get("/api/dbt/project", () =>
        HttpResponse.json({ ...PROJECT, dbt_cli_available: false, model_count: 0, models: [] }),
      ),
    );
    render(<Dbt />);
    expect(await screen.findByText("dbt CLI unavailable")).toBeInTheDocument();
    expect(screen.getByText(/no models in this project/i)).toBeInTheDocument();
  });

  it("surfaces a failed run", async () => {
    server.use(
      http.get("/api/dbt/project", () => HttpResponse.json(PROJECT)),
      http.post("/api/dbt/build", () => new HttpResponse(null, { status: 500 })),
    );
    const user = userEvent.setup();
    render(<Dbt />);
    await user.click(await screen.findByRole("button", { name: /build/i }));
    expect(await screen.findByText(/dbt build error 500/i)).toBeInTheDocument();
  });

  it("surfaces a project load error", async () => {
    server.use(http.get("/api/dbt/project", () => new HttpResponse(null, { status: 500 })));
    render(<Dbt />);
    expect(await screen.findByText(/dbt project error 500/i)).toBeInTheDocument();
  });
});
