import { LayoutDashboard } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type DashboardSpec, listDashboards } from "../api";

export function Dashboards() {
  const [dashboards, setDashboards] = useState<DashboardSpec[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDashboards()
      .then(setDashboards)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!dashboards) return <p className="text-muted-foreground">Loading dashboards…</p>;

  return (
    <section className="flex flex-col gap-4">
      <Card className="animate-fade-in-up">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LayoutDashboard className="size-5" /> Dashboards
          </CardTitle>
          <CardDescription>
            Saved dashboards built on the semantic layer. Open one to render its charts (Plotly + KPIs).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {dashboards.length === 0 ? (
            <p className="text-muted-foreground">No dashboards defined yet.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {dashboards.map((d) => (
                <Link
                  key={d.dashboard_id}
                  to={`/dashboards/${d.dashboard_id}`}
                  className="flex flex-col items-start gap-2 rounded-lg border border-border p-4 transition-colors hover:bg-accent"
                >
                  <span className="font-medium">{d.name}</span>
                  <span className="text-sm text-muted-foreground">{d.description}</span>
                  <Badge variant="muted">
                    {d.charts.length} chart{d.charts.length === 1 ? "" : "s"}
                  </Badge>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
