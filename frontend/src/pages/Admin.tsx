import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchUsage, fetchUsageRecords, type UsageBucket, type UsageRecord, type UsageSummary } from "../api";

const usd = (n: number) => `$${n.toFixed(6)}`;

function RecordsTable({ records }: { records: UsageRecord[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>recent calls</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>session</TableHead>
              <TableHead>model</TableHead>
              <TableHead>tokens</TableHead>
              <TableHead>cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  no calls yet
                </TableCell>
              </TableRow>
            )}
            {records.map((r) => (
              <TableRow key={r.request_id}>
                <TableCell>
                  {/* clicking a session relaunches it in the chat */}
                  <Link className="text-secondary-foreground hover:underline" to={`/chat/${r.session_id}`}>
                    {r.session_id}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{r.model_id}</TableCell>
                <TableCell>{r.total_tokens}</TableCell>
                <TableCell>{usd(r.est_cost_usd)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function BucketTable({ title, rows }: { title: string; rows: Record<string, UsageBucket> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1].est_cost_usd - a[1].est_cost_usd);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{title.includes("model") ? "model" : "user"}</TableHead>
              <TableHead>calls</TableHead>
              <TableHead>tokens</TableHead>
              <TableHead>est. cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  no usage yet
                </TableCell>
              </TableRow>
            )}
            {entries.map(([k, v]) => (
              <TableRow key={k}>
                <TableCell>{k}</TableCell>
                <TableCell>{v.calls}</TableCell>
                <TableCell>{v.total_tokens}</TableCell>
                <TableCell>{usd(v.est_cost_usd)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-3xl font-bold text-primary tabular-nums">{value}</span>
      <span className="text-muted-foreground text-sm">{label}</span>
    </div>
  );
}

export function Admin() {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsage()
      .then(setData)
      .catch((e) => setError(String(e)));
    fetchUsageRecords()
      .then(setRecords)
      .catch(() => {
        /* records are supplementary; the summary above is the primary view */
      });
  }, []);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!data) return <p className="text-muted-foreground">Loading usage…</p>;

  return (
    <section className="flex flex-col gap-4">
      <Card>
        <CardContent className="flex gap-10 pt-6">
          <Stat value={data.totals.calls} label="calls" />
          <Stat value={data.totals.total_tokens} label="tokens" />
          <Stat value={usd(data.totals.est_cost_usd)} label="est. cost" />
        </CardContent>
      </Card>
      <BucketTable title="by model" rows={data.by_model} />
      <BucketTable title="by user" rows={data.by_user} />
      <RecordsTable records={records} />
    </section>
  );
}
