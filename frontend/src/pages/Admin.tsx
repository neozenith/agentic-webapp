import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchUsage, fetchUsers, type UsageSummary, type UserSummary } from "../api";

const usd = (n: number) => `$${n.toFixed(6)}`;

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-3xl font-bold text-primary tabular-nums">{value}</span>
      <span className="text-muted-foreground text-sm">{label}</span>
    </div>
  );
}

export function Admin() {
  const [totals, setTotals] = useState<UsageSummary | null>(null);
  const [users, setUsers] = useState<UserSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsage()
      .then(setTotals)
      .catch((e) => setError(String(e)));
    fetchUsers()
      .then(setUsers)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!totals || !users) return <p className="text-muted-foreground">Loading usage…</p>;

  return (
    <section className="flex flex-col gap-4">
      <Card>
        <CardContent className="flex gap-10 pt-6">
          <Stat value={totals.totals.calls} label="calls" />
          <Stat value={totals.totals.total_tokens} label="tokens" />
          <Stat value={usd(totals.totals.est_cost_usd)} label="est. cost" />
          <Stat value={users.length} label="users" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2">
          <CardTitle>Users</CardTitle>
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/groups">Manage groups</Link>
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>user</TableHead>
                <TableHead>sessions</TableHead>
                <TableHead>calls</TableHead>
                <TableHead>tokens</TableHead>
                <TableHead>est. cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground">
                    no usage yet
                  </TableCell>
                </TableRow>
              )}
              {users.map((u) => (
                <TableRow key={u.user_id}>
                  <TableCell>
                    {/* drill into a single user's sessions; show the conventional identity when known */}
                    {u.name || u.email ? (
                      <div className="flex flex-col">
                        {u.name && <span className="font-medium">{u.name}</span>}
                        {u.email && <span className="text-xs text-muted-foreground">{u.email}</span>}
                        <Link
                          className="font-mono text-xs text-muted-foreground hover:underline"
                          to={`/admin/users/${encodeURIComponent(u.user_id)}`}
                        >
                          {u.user_id}
                        </Link>
                      </div>
                    ) : (
                      <Link
                        className="text-secondary-foreground hover:underline"
                        to={`/admin/users/${encodeURIComponent(u.user_id)}`}
                      >
                        {u.user_id}
                      </Link>
                    )}
                  </TableCell>
                  <TableCell>{u.sessions}</TableCell>
                  <TableCell>{u.calls}</TableCell>
                  <TableCell>{u.total_tokens}</TableCell>
                  <TableCell>{usd(u.est_cost_usd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  );
}
