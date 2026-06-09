import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { type ChatMessage, createSession, getMe, getSession, runAgent, sessionToMessages } from "../api";

export function Chat() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
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

  async function send() {
    const text = input.trim();
    if (!text || busy || !sessionId || !userId) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const reply = await runAgent(userId, sessionId, text);
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
    <section className="card chat">
      <div className="chat-header">
        <span className="muted">{sessionId ? `session ${sessionId.slice(0, 8)}…` : "starting…"}</span>
        <button type="button" className="btn ghost" onClick={() => void newChat()} disabled={busy}>
          New chat
        </button>
      </div>
      <div className="messages">
        {loading && <p className="muted">Loading session…</p>}
        {!loading && messages.length === 0 && <p className="muted">Ask the agent something…</p>}
        {messages.map((m, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the chat log is append-only and never reordered
          <div key={i} className={`msg ${m.role}`}>
            <span className="who">{m.role === "user" ? "you" : "agent"}</span>
            <div className="bubble">{m.text}</div>
          </div>
        ))}
        {busy && (
          <div className="msg assistant">
            <span className="who">agent</span>
            <div className="bubble muted">…thinking</div>
          </div>
        )}
      </div>
      {error && <p className="error">⚠️ {error}</p>}
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={busy || loading}
        />
        <button type="submit" disabled={busy || loading || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
