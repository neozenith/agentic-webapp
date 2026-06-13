import { ArrowLeft, MessageSquare } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchRawSession } from "../api";

/** Raw events + state for one session — the detailed logs view for debugging. */
export function AdminSessionRaw() {
  const { userId = "", sessionId = "" } = useParams<{ userId: string; sessionId: string }>();
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRawSession(userId, sessionId)
      .then(setRaw)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [userId, sessionId]);

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <div className="flex flex-col">
          <CardTitle>Raw session</CardTitle>
          <span className="font-mono text-xs text-muted-foreground break-all">{sessionId}</span>
        </div>
        <div className="flex gap-1">
          <Button asChild variant="outline" size="sm">
            <Link to={`/chat/${sessionId}`}>
              <MessageSquare /> Open chat
            </Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to={`/admin/users/${encodeURIComponent(userId)}`}>
              <ArrowLeft /> Back
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && <p className="text-destructive">⚠️ {error}</p>}
        {!error && !raw && <p className="text-muted-foreground">Loading raw session…</p>}
        {raw != null && (
          <pre className="max-h-[60vh] overflow-auto rounded-lg border border-border bg-background/60 p-3 text-xs">
            {JSON.stringify(raw, null, 2)}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
