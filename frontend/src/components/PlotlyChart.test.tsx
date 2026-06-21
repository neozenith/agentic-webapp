import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Stub the 3rd-party chart lib so jsdom doesn't try to run plotly's full bundle. The factory
// returns a component that records the layout it was handed, so we can assert our merge logic.
vi.mock("plotly.js-dist-min", () => ({ default: {} }));
vi.mock("react-plotly.js/factory", () => ({
  default: () => (props: { layout: Record<string, unknown> }) => (
    <div data-testid="plot" data-layout={JSON.stringify(props.layout)} />
  ),
}));

import { PlotlyChart } from "./PlotlyChart";

describe("PlotlyChart", () => {
  it("merges transparent theme defaults with the figure's own layout", () => {
    render(<PlotlyChart figure={{ data: [{ type: "bar" }], layout: { title: "Sales" } }} />);
    const plot = screen.getByTestId("plot");
    const layout = JSON.parse(plot.getAttribute("data-layout") ?? "{}");
    expect(layout.paper_bgcolor).toBe("transparent");
    expect(layout.plot_bgcolor).toBe("transparent");
    expect(layout.title).toBe("Sales");
  });
});
