import Plotly from "plotly.js-dist-min";
import type * as React from "react";
import createPlotlyComponent from "react-plotly.js/factory";

// Build the React wrapper from the lightweight dist-min bundle (the default react-plotly.js
// entrypoint pulls in the full plotly.js, which we don't install). We type the produced
// component with our own minimal prop shape so consuming code never depends on plotly.js types.
/** A Plotly click event, narrowed to what we consume: each clicked point may carry the
 * `customdata` we tagged it with (used to map a marker back to its domain id). */
export interface PlotClickEvent {
  points?: { customdata?: unknown }[];
}

interface PlotProps {
  data: unknown[];
  layout: Record<string, unknown>;
  config?: Record<string, unknown>;
  style?: React.CSSProperties;
  useResizeHandler?: boolean;
  className?: string;
  onClick?: (event: PlotClickEvent) => void;
}

const Plot = createPlotlyComponent(Plotly) as unknown as React.ComponentType<PlotProps>;

export interface PlotlyChartProps {
  figure: { data: unknown[]; layout: Record<string, unknown> };
  className?: string;
  height?: string;
  onClick?: (event: PlotClickEvent) => void;
}

/** Theme-aware Plotly chart: transparent paper/plot backgrounds let the card's surface show
 * through in both light and dark themes; fills its container and re-layouts on resize. */
export function PlotlyChart({ figure, className, height = "320px", onClick }: PlotlyChartProps) {
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
      style={{ width: "100%", height }}
      config={{ displayModeBar: false, responsive: true }}
      className={className}
      onClick={onClick}
    />
  );
}
