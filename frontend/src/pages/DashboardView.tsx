import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { KpiCard } from "@/components/KpiCard";
import { PlotlyChart } from "@/components/PlotlyChart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChartRender, type DashboardRender, renderDashboard } from "../api";

const isKpi = (chart: ChartRender): boolean => chart.chart_type === "kpi";

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

  useEffect(() => {
    renderDashboard(dashboardId)
      .then(setDashboard)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [dashboardId]);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!dashboard) return <p className="text-muted-foreground">Loading dashboard…</p>;

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
        <CardContent>
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
