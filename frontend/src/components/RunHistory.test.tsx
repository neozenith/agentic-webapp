import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

// Stub the 3rd-party Plotly bundle (jsdom can't run it). The wrapper renders a div that
// reports its point count and forwards a click as a synthetic Plotly point-select event,
// so the marker-click → gantt flow is exercised for real component code.
vi.mock("plotly.js-dist-min", () => ({ default: {} }));
vi.mock("react-plotly.js/factory", () => ({
  default: () => (props: { data?: { x?: unknown[]; customdata?: unknown[] }[]; onClick?: (e: unknown) => void }) => {
    const points = (props.data ?? []).reduce((n, t) => n + (t.x?.length ?? 0), 0);
    return (
      <button
        type="button"
        data-testid="plot"
        data-points={points}
        onClick={() => props.onClick?.({ points: [{ customdata: props.data?.[0]?.customdata?.[0] }] })}
      />
    );
  },
}));

import { server } from "../test/server";
import { RunHistory } from "./RunHistory";

const INVOCATIONS = [
  {
    invocation_id: "inv1",
    command: "build",
    run_started_at: "2026-06-01T10:00:00Z",
    run_completed_at: "2026-06-01T10:05:00Z",
    target_name: "dev",
    dbt_version: "1.8.0",
    n_nodes: 3,
    wall_secs: 300,
    has_failures: false,
  },
  {
    invocation_id: "inv2",
    command: "run",
    run_started_at: "2026-06-02T10:00:00Z",
    run_completed_at: "2026-06-02T10:02:00Z",
    target_name: "dev",
    dbt_version: "1.8.0",
    n_nodes: 2,
    wall_secs: 120,
    has_failures: true,
  },
];

const GANTT = {
  invocation_id: "inv1",
  wall_secs: 300,
  threads: ["1", "2"],
  nodes: [
    {
      thread_id: "1",
      node_id: "model.x",
      name: "stg_orders",
      resource_type: "model",
      status: "success",
      start_offset_secs: 0,
      duration_secs: 120,
    },
    {
      thread_id: "2",
      node_id: "test.y",
      name: "not_null",
      resource_type: "test",
      status: "fail",
      start_offset_secs: 120,
      duration_secs: 30,
    },
  ],
};

describe("RunHistory", () => {
  it("renders the overview points and loads a gantt when a marker is clicked", async () => {
    server.use(
      http.get("/api/dbt/observability/invocations", () => HttpResponse.json(INVOCATIONS)),
      http.get("/api/dbt/observability/invocations/:id", () => HttpResponse.json(GANTT)),
    );
    const user = userEvent.setup();
    render(<RunHistory />);

    const overview = await screen.findByTestId("plot");
    // Both invocations rendered as points (across the pass/fail traces).
    expect(overview).toHaveAttribute("data-points", "2");
    expect(screen.getByText(/Select an invocation above/i)).toBeInTheDocument();

    await user.click(overview);

    // A second plot (the gantt) appears, and the selected invocation's summary shows.
    await waitFor(() => expect(screen.getAllByTestId("plot").length).toBe(2));
    expect(screen.getByText(/3 nodes · 300s/)).toBeInTheDocument();
  });

  it("shows the empty state when there is no run history", async () => {
    server.use(http.get("/api/dbt/observability/invocations", () => HttpResponse.json([])));
    render(<RunHistory />);
    expect(await screen.findByText(/No run history yet/i)).toBeInTheDocument();
  });

  it("surfaces an error loading invocations", async () => {
    server.use(http.get("/api/dbt/observability/invocations", () => new HttpResponse(null, { status: 500 })));
    render(<RunHistory />);
    expect(await screen.findByText(/dbt invocations error 500/i)).toBeInTheDocument();
  });
});
