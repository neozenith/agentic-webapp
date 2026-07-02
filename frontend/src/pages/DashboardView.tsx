import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { KpiCard } from "@/components/KpiCard";
import { PlotlyChart } from "@/components/PlotlyChart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { type ChartRender, type DashboardRender, type RenderParams, renderDashboard } from "../api";

const isKpi = (chart: ChartRender): boolean => chart.chart_type === "kpi";

const GRAINS: { value: string; label: string }[] = [
  { value: "", label: "Default" },
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
  { value: "year", label: "Year" },
];

/** YYYY-MM-DD for a Date, as <input type="date"> expects. */
const isoDate = (d: Date): string => d.toISOString().slice(0, 10);

function ChartTile({ chart }: { chart: ChartRender }) {
  return (
    <Card className={isKpi(chart) ? "" : "md:col-span-2"}>
      <CardHeader>
        <CardTitle className="text-base">{chart.title}</CardTitle>
      </CardHeader>
      <CardContent>
        {chart.error ? (
          <p className="text-destructive">⚠️ {chart.error}</p>
        ) : isKpi(chart) ? (
          <KpiCard label={chart.title} value={chart.value} unit={chart.figure.layout.unit as string | undefined} />
        ) : (
          <PlotlyChart figure={chart.figure} />
        )}
      </CardContent>
    </Card>
  );
}

export function DashboardView() {
  const { dashboardId = "" } = useParams<{ dashboardId: string }>();
  const [dashboard, setDashboard] = useState<DashboardRender | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [grain, setGrain] = useState<string>("");
  const [start, setStart] = useState<string>("");
  const [end, setEnd] = useState<string>("");

  useEffect(() => {
    const params: RenderParams = { grain, start, end };
    renderDashboard(dashboardId, params)
      .then(setDashboard)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [dashboardId, grain, start, end]);

  const applyPreset = (preset: "last12" | "ytd" | "all") => {
    const now = new Date();
    if (preset === "all") {
      setStart("");
      setEnd("");
      return;
    }
    setEnd(isoDate(now));
    if (preset === "last12") {
      const from = new Date(now);
      from.setFullYear(from.getFullYear() - 1);
      setStart(isoDate(from));
    } else {
      setStart(isoDate(new Date(now.getFullYear(), 0, 1)));
    }
  };

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!dashboard) return <p className="text-muted-foreground">Loading dashboard…</p>;

  const grainLabel = GRAINS.find((g) => g.value === grain)?.label ?? "Default";
  const rangeLabel = start || end ? `${start || "…"} → ${end || "…"}` : "All dates";

  return (
    <section className="flex flex-col gap-4">
      <Card className="animate-fade-in-up">
        <CardHeader className="flex-row items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <CardTitle>{dashboard.name}</CardTitle>
            <CardDescription>{dashboard.description}</CardDescription>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/dashboards">
              <ArrowLeft /> All dashboards
            </Link>
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Grain</span>
              <select
                aria-label="Grain"
                className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                value={grain}
                onChange={(e) => setGrain(e.target.value)}
              >
                {GRAINS.map((g) => (
                  <option key={g.value || "default"} value={g.value}>
                    {g.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm" htmlFor="ts-start">
              <span className="text-muted-foreground">Start</span>
              <Input
                id="ts-start"
                aria-label="Start date"
                type="date"
                className="w-40"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm" htmlFor="ts-end">
              <span className="text-muted-foreground">End</span>
              <Input
                id="ts-end"
                aria-label="End date"
                type="date"
                className="w-40"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => applyPreset("last12")}>
                Last 12 months
              </Button>
              <Button variant="outline" size="sm" onClick={() => applyPreset("ytd")}>
                YTD
              </Button>
              <Button variant="outline" size="sm" onClick={() => applyPreset("all")}>
                All
              </Button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Grain: <span className="font-mono text-foreground">{grainLabel}</span> · Range:{" "}
            <span className="font-mono text-foreground">{rangeLabel}</span>
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          {dashboard.charts.length === 0 ? (
            <p className="text-muted-foreground">This dashboard has no charts.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {dashboard.charts.map((c) => (
                <ChartTile key={c.chart_id} chart={c} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
