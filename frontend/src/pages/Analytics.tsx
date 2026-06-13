import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type AnalyticsSummary, type Extraction, fetchAnalyticsSummary, fetchExtractions } from "../api";

const fieldsPreview = (fields: Record<string, unknown>): string =>
  Object.entries(fields)
    .slice(0, 4)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(", ");

export function Analytics() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [rows, setRows] = useState<Extraction[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalyticsSummary()
      .then(setSummary)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    fetchExtractions()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!summary || !rows) return <p className="text-muted-foreground">Loading analytics…</p>;

  return (
    <section className="flex flex-col gap-4">
      <Card className="animate-fade-in-up">
        <CardHeader>
          <CardTitle>Analytics</CardTitle>
          <CardDescription>
            The AnalyticsManager warehouse (BigQuery in cloud, in-memory locally) — separate from the Firestore
            operational stores. {summary.total} extraction records. Dashboards (Plotly) can be layered on this data
            model.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Semantic layer: the field schema discovered per doc_type. */}
          {summary.by_doc_type.length === 0 ? (
            <p className="text-muted-foreground">
              No analytics records yet. Extract some details from an asset in chat.
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {summary.by_doc_type.map((d) => (
                <div key={d.doc_type} className="rounded-lg border border-border p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{d.doc_type}</span>
                    <Badge variant="muted">{d.count}</Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {d.fields.map((f) => (
                      <Badge key={f} variant="outline" className="font-mono">
                        {f}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent extractions</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>doc type</TableHead>
                <TableHead>fields</TableHead>
                <TableHead>user</TableHead>
                <TableHead>when</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-muted-foreground">
                    no extractions yet
                  </TableCell>
                </TableRow>
              )}
              {rows.map((r) => (
                <TableRow key={r.extraction_id}>
                  <TableCell>
                    <Badge variant="muted">{r.doc_type}</Badge>
                  </TableCell>
                  <TableCell className="max-w-[24rem] truncate text-muted-foreground">
                    {fieldsPreview(r.fields)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{r.user_id}</TableCell>
                  <TableCell className="text-muted-foreground">{new Date(r.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  );
}
