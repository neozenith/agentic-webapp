import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getMe, listSessions, type SessionMeta } from "../api";

export function Sessions() {
  const [sessions, setSessions] = useState<SessionMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then((me) => listSessions(me.user_id ?? "web-user"))
      .then(setSessions)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!sessions) return <p className="text-muted-foreground">Loading sessions…</p>;

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Your sessions</CardTitle>
        <Button asChild variant="outline" size="sm">
          <Link to="/chat">
            <Plus /> New chat
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {sessions.length === 0 ? (
          <p className="text-muted-foreground">
            No sessions yet.{" "}
            <Link className="text-secondary-foreground underline-offset-4 hover:underline" to="/chat">
              Start one →
            </Link>
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>session</TableHead>
                <TableHead>last updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link className="text-secondary-foreground hover:underline" to={`/chat/${s.id}`}>
                      {s.id}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {s.lastUpdateTime ? new Date(s.lastUpdateTime * 1000).toLocaleString() : "—"}
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
