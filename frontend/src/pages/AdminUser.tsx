import { ArrowLeft, FileText, MessageSquare } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchUserSessions, listSessions, type SessionSummary } from "../api";

const usd = (n: number) => `$${n.toFixed(6)}`;

export function AdminUser() {
  const { userId = "" } = useParams<{ userId: string }>();
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [titles, setTitles] = useState<Map<string, string | undefined>>(new Map());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUserSessions(userId)
      .then(setSessions)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    // Titles are supplementary: a failed fetch must not block the cost rows.
    listSessions(userId)
      .then((metas) => setTitles(new Map(metas.map((m) => [m.id, m.state?.title]))))
      .catch(() => setTitles(new Map()));
  }, [userId]);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!sessions) return <p className="text-muted-foreground">Loading sessions…</p>;

  const totalCost = sessions.reduce((a, s) => a + s.est_cost_usd, 0);

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <div className="flex flex-col">
          <CardTitle className="break-all">{userId}</CardTitle>
          <span className="text-sm text-muted-foreground">
            {sessions.length} sessions · {usd(totalCost)} total
          </span>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/admin">
            <ArrowLeft /> All users
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {sessions.length === 0 ? (
          <p className="text-muted-foreground">No sessions for this user.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>session</TableHead>
                <TableHead>id</TableHead>
                <TableHead>calls</TableHead>
                <TableHead>tokens</TableHead>
                <TableHead>cost</TableHead>
                <TableHead>last activity</TableHead>
                <TableHead> </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((s) => (
                <TableRow key={s.session_id}>
                  <TableCell>{titles.get(s.session_id) || "Untitled session"}</TableCell>
                  <TableCell className="font-mono text-xs">{s.session_id.slice(0, 12)}…</TableCell>
                  <TableCell>{s.calls}</TableCell>
                  <TableCell>{s.total_tokens}</TableCell>
                  <TableCell>{usd(s.est_cost_usd)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {s.last_timestamp ? new Date(s.last_timestamp).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {/* relaunch the persisted chat session */}
                      <Button asChild variant="ghost" size="sm" title="Open chat">
                        <Link to={`/chat/${s.session_id}`}>
                          <MessageSquare />
                        </Link>
                      </Button>
                      {/* raw events + state */}
                      <Button asChild variant="ghost" size="sm" title="Raw session logs">
                        <Link to={`/admin/users/${encodeURIComponent(userId)}/sessions/${s.session_id}`}>
                          <FileText />
                        </Link>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
