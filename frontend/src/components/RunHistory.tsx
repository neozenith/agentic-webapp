import { useEffect, useState } from "react";

import { PlotlyChart } from "@/components/PlotlyChart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type DbtGantt, type DbtGanttNode, type DbtInvocation, getDbtGantt, listDbtInvocations } from "../api";

const PASS = "#10b981";
const FAIL = "#ef4444";

const RESOURCE_COLORS: Record<string, string> = {
  model: "#3b82f6",
  test: "#a855f7",
  seed: "#10b981",
  snapshot: "#f59e0b",
  source: "#6b7280",
};

const isFailedStatus = (status: string): boolean => /error|fail/i.test(status);

/** Scatter of wall-clock duration over time, split into pass/fail traces. Each marker
 * carries its invocation_id as customdata so a click selects that run. */
const overviewFigure = (invocations: DbtInvocation[]) => {
  const trace = (rows: DbtInvocation[], name: string, color: string) => ({
    type: "scatter",
    mode: "markers",
    name,
    x: rows.map((r) => r.run_started_at),
    y: rows.map((r) => r.wall_secs),
    customdata: rows.map((r) => r.invocation_id),
    marker: { color, size: 11 },
  });
  return {
    data: [
      trace(
        invocations.filter((i) => !i.has_failures),
        "Pass",
        PASS,
      ),
      trace(
        invocations.filter((i) => i.has_failures),
        "Fail",
        FAIL,
      ),
    ],
    layout: {
      xaxis: { title: "run started" },
      yaxis: { title: "wall secs" },
      showlegend: true,
      hovermode: "closest" as const,
    },
  };
};

/** Horizontal bars (base = start offset, width = duration) form a per-thread gantt;
 * bar fill encodes resource_type, a red outline flags errored nodes. */
const ganttFigure = (gantt: DbtGantt) => {
  const nodes: DbtGanttNode[] = gantt.nodes;
  return {
    data: [
      {
        type: "bar",
        orientation: "h",
        base: nodes.map((n) => n.start_offset_secs),
        x: nodes.map((n) => n.duration_secs),
        y: nodes.map((n) => n.thread_id),
        text: nodes.map((n) => n.name),
        hovertext: nodes.map((n) => `${n.name} (${n.resource_type}) · ${n.status} · ${n.duration_secs}s`),
        hoverinfo: "text",
        marker: {
          color: nodes.map((n) => RESOURCE_COLORS[n.resource_type] ?? "#6b7280"),
          line: {
            color: nodes.map((n) => (isFailedStatus(n.status) ? FAIL : "rgba(0,0,0,0)")),
            width: nodes.map((n) => (isFailedStatus(n.status) ? 2 : 0)),
          },
        },
      },
    ],
    layout: {
      barmode: "overlay" as const,
      xaxis: { title: "seconds from start" },
      yaxis: { title: "thread", automargin: true },
      showlegend: false,
    },
  };
};

/** dbt run-history observability: an overview scatter of every invocation plus a per-run
 * gantt for the selected invocation, both Elementary-backed (may be empty until dbt runs). */
export function RunHistory() {
  const [invocations, setInvocations] = useState<DbtInvocation[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [gantt, setGantt] = useState<DbtGantt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDbtInvocations()
      .then(setInvocations)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    if (!selected) {
      setGantt(null);
      return;
    }
    getDbtGantt(selected)
      .then(setGantt)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [selected]);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!invocations) return <p className="text-muted-foreground">Loading run history…</p>;

  if (invocations.length === 0) {
    return <p className="text-muted-foreground">No run history yet — run dbt to populate Elementary observability.</p>;
  }

  const selectedInvocation = invocations.find((i) => i.invocation_id === selected) ?? null;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Invocations</CardTitle>
          <CardDescription>Wall-clock duration over time — click a point for its gantt.</CardDescription>
        </CardHeader>
        <CardContent>
          <PlotlyChart
            figure={overviewFigure(invocations)}
            onClick={(e) => {
              const id = e.points?.[0]?.customdata;
              if (typeof id === "string") setSelected(id);
            }}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Gantt{selectedInvocation ? ` · ${selectedInvocation.command}` : ""}
          </CardTitle>
          <CardDescription>
            {selectedInvocation
              ? `${selectedInvocation.target_name} · ${selectedInvocation.n_nodes} nodes · ${selectedInvocation.wall_secs}s`
              : "Select an invocation above to see its per-thread timeline."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {gantt ? (
            <PlotlyChart figure={ganttFigure(gantt)} height="420px" />
          ) : (
            <p className="text-muted-foreground">No invocation selected.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
