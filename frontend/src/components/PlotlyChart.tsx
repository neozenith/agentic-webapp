import Plotly from "plotly.js-dist-min";
import type * as React from "react";
import createPlotlyComponent from "react-plotly.js/factory";

// Build the React wrapper from the lightweight dist-min bundle (the default react-plotly.js
// entrypoint pulls in the full plotly.js, which we don't install). We type the produced
// component with our own minimal prop shape so consuming code never depends on plotly.js types.
interface PlotProps {
  data: unknown[];
  layout: Record<string, unknown>;
  config?: Record<string, unknown>;
  style?: React.CSSProperties;
  useResizeHandler?: boolean;
  className?: string;
}

const Plot = createPlotlyComponent(Plotly) as unknown as React.ComponentType<PlotProps>;

export interface PlotlyChartProps {
  figure: { data: unknown[]; layout: Record<string, unknown> };
  className?: string;
}

/** Theme-aware Plotly chart: transparent paper/plot backgrounds let the card's surface show
 * through in both light and dark themes; fills its container and re-layouts on resize. */
export function PlotlyChart({ figure, className }: PlotlyChartProps) {
  const layout: Record<string, unknown> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    margin: { t: 24, r: 16, b: 40, l: 48 },
    ...figure.layout,
  };
  return (
    <Plot
      data={figure.data}
      layout={layout}
      useResizeHandler
      style={{ width: "100%", height: "320px" }}
      config={{ displayModeBar: false, responsive: true }}
      className={className}
    />
  );
}
