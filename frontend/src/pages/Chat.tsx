import { Paperclip, SendHorizontal, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { type ChatMessage, createSession, getMe, getSession, runAgent, sessionToMessages, uploadAsset } from "../api";

interface Attached {
  asset_id: string;
  filename: string | null;
}

export function Chat() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [attached, setAttached] = useState<Attached | null>(null);
  const [attaching, setAttaching] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  // Guards against React StrictMode running the resolve effect twice (which would
  // otherwise create two server sessions for one /chat visit).
  const resolving = useRef(false);

  // Resolve the pseudonymous user id once. Falls back to a shared local id when there
  // is no IAP identity (bare local run) — non-prod holds no sensitive data (ADR-0003).
  useEffect(() => {
    getMe()
      .then((me) => setUserId(me.user_id ?? "web-user"))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  // Once we know the user and the URL, resume the session (or create one server-side
  // and put its server-issued id in the URL).
  useEffect(() => {
    if (!userId || resolving.current) return;
    resolving.current = true;
    void (async () => {
      try {
        if (!sessionId) {
          const id = await createSession(userId); // server mints the id
          navigate(`/chat/${id}`, { replace: true }); // effect re-runs with the new param
          return;
        }
        const session = await getSession(userId, sessionId);
        if (!session) {
          const id = await createSession(userId);
          navigate(`/chat/${id}`, { replace: true });
          return;
        }
        setMessages(sessionToMessages(session));
        setLoading(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      } finally {
        resolving.current = false;
      }
    })();
  }, [userId, sessionId, navigate]);

  // Upload a photo straight to the asset store (POST /api/assets — the same endpoint the
  // Asset Manager uses, so it's immediately visible there too). We then reference it by id
  // in the message, rather than streaming raw bytes through the agent.
  async function attach(files: FileList | null) {
    if (!files || files.length === 0 || attaching) return;
    setAttaching(true);
    setError(null);
    try {
      const asset = await uploadAsset(files[0]);
      setAttached({ asset_id: asset.asset_id, filename: asset.filename });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAttaching(false);
    }
  }

  async function send() {
    const text = input.trim();
    if ((!text && !attached) || busy || !sessionId || !userId) return;
    // The visible bubble shows what the user typed (or the attachment); the agent receives
    // the text plus a parseable asset reference it can pass to attach_asset.
    const ref = attached
      ? `\n\n[attached asset ${attached.asset_id}${attached.filename ? ` — ${attached.filename}` : ""}]`
      : "";
    const outgoing = `${text}${ref}`.trim();
    const shown = text || (attached ? `📎 ${attached.filename ?? attached.asset_id}` : "");
    setInput("");
    setAttached(null);
    setError(null);
    setMessages((m) => [...m, { role: "user", text: shown }]);
    setBusy(true);
    try {
      const reply = await runAgent(userId, sessionId, outgoing);
      setMessages((m) => [...m, { role: "assistant", text: reply || "(no reply)" }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function newChat() {
    if (!userId || busy) return;
    setError(null);
    try {
      const id = await createSession(userId);
      setMessages([]);
      navigate(`/chat/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <Card className="flex min-h-[70vh] flex-col gap-4 p-5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{sessionId ? `session ${sessionId.slice(0, 8)}…` : "starting…"}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => void newChat()} disabled={busy}>
          New chat
        </Button>
      </div>
      <div className="flex flex-1 flex-col gap-3">
        {loading && <p className="text-muted-foreground">Loading session…</p>}
        {!loading && messages.length === 0 && <p className="text-muted-foreground">Ask the agent something…</p>}
        {messages.map((m, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the chat log is append-only and never reordered
          <div key={i} className={cn("flex flex-col gap-1", m.role === "user" && "items-end")}>
            <span className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
              {m.role === "user" ? "you" : "agent"}
            </span>
            <div
              className={cn(
                "max-w-[80%] whitespace-pre-wrap rounded-xl px-3.5 py-2.5",
                m.role === "user" ? "bg-secondary text-secondary-foreground" : "border border-border bg-background/60",
              )}
            >
              {m.text}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex flex-col gap-1">
            <span className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">agent</span>
            <div className="max-w-[80%] rounded-xl border border-border bg-background/60 px-3.5 py-2.5 text-muted-foreground">
              …thinking
            </div>
          </div>
        )}
      </div>
      {error && <p className="text-destructive">⚠️ {error}</p>}
      {attached && (
        <div className="flex w-fit items-center gap-2 rounded-md border border-border bg-muted/40 px-2 py-1 text-sm">
          <Paperclip className="size-3.5 text-muted-foreground" aria-hidden />
          <span className="truncate">{attached.filename ?? attached.asset_id}</span>
          <button
            type="button"
            aria-label="Remove attachment"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => setAttached(null)}
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          ref={fileInput}
          type="file"
          accept="image/*,application/pdf"
          className="hidden"
          onChange={(e) => void attach(e.target.files)}
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label="Attach photo"
          disabled={busy || loading || attaching}
          onClick={() => fileInput.current?.click()}
        >
          <Paperclip />
        </Button>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={busy || loading}
        />
        <Button type="submit" disabled={busy || loading || (!input.trim() && !attached)}>
          <SendHorizontal /> Send
        </Button>
      </form>
    </Card>
  );
}
