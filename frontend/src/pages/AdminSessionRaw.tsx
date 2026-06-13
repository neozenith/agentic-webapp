import { ArrowLeft, MessageSquare } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Markdown } from "@/components/Markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type AdkSession, fetchRawSession, getSession, type SessionTurn, sessionTitle, sessionToTurns } from "../api";

/** One conversation turn as a formatted card: role, prose (as Markdown) and a compact
 * summary of any tool activity so function-call turns aren't invisible. */
function TurnCard({ turn }: { turn: SessionTurn }) {
  return (
    <Card className="bg-background/60">
      <CardHeader className="pb-2">
        <span className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
          {turn.role === "user" ? "you" : "agent"}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {turn.text && <Markdown>{turn.text}</Markdown>}
        {turn.toolCalls.map((call, i) => (
          <Badge
            // biome-ignore lint/suspicious/noArrayIndexKey: tool calls within a turn are fixed and never reordered
            key={`${call.name}-${i}`}
            variant="muted"
            className="font-mono"
          >
            🔧 called <span className="font-semibold">{call.name}</span>
          </Badge>
        ))}
        {turn.hasResponse && (
          <Badge variant="outline" className="font-mono">
            ↩︎ tool result
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}

/** Per-turn formatted view of one session — the detailed logs view for debugging, with a
 * collapsible raw-JSON fallback so nothing is lost. */
export function AdminSessionRaw() {
  const { userId = "", sessionId = "" } = useParams<{ userId: string; sessionId: string }>();
  const [session, setSession] = useState<AdkSession | null>(null);
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // The typed session drives the turn cards; the raw payload backs the collapsible fallback.
    getSession(userId, sessionId)
      .then(setSession)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    fetchRawSession(userId, sessionId)
      .then(setRaw)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [userId, sessionId]);

  const title = session ? sessionTitle(session) : null;
  const turns = session ? sessionToTurns(session) : [];

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <div className="flex flex-col">
          <CardTitle>{title ?? "Session"}</CardTitle>
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
      <CardContent className="flex flex-col gap-3">
        {error && <p className="text-destructive">⚠️ {error}</p>}
        {!error && !session && <p className="text-muted-foreground">Loading session…</p>}
        {session && turns.length === 0 && <p className="text-muted-foreground">No conversation turns yet.</p>}
        {turns.map((turn, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the event log is append-only and never reordered
          <TurnCard key={i} turn={turn} />
        ))}
        {raw != null && (
          <details className="rounded-lg border border-border bg-background/60">
            <summary className="cursor-pointer px-3 py-2 text-sm text-muted-foreground">Raw JSON</summary>
            <pre className="max-h-[60vh] overflow-auto border-t border-border p-3 text-xs">
              {JSON.stringify(raw, null, 2)}
            </pre>
          </details>
        )}
      </CardContent>
    </Card>
  );
}
