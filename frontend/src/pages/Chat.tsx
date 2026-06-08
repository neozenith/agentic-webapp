import { useRef, useState } from "react";

import { ensureSession, runAgent } from "../api";

interface Message {
  role: "user" | "assistant";
  text: string;
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useRef(`web-${Date.now()}`);
  const started = useRef(false);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      if (!started.current) {
        await ensureSession(sessionId.current);
        started.current = true;
      }
      const reply = await runAgent(sessionId.current, text);
      setMessages((m) => [...m, { role: "assistant", text: reply || "(no reply)" }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card chat">
      <div className="messages">
        {messages.length === 0 && <p className="muted">Ask the agent something…</p>}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <span className="who">{m.role === "user" ? "you" : "agent"}</span>
            <div className="bubble">{m.text}</div>
          </div>
        ))}
        {busy && <div className="msg assistant"><span className="who">agent</span><div className="bubble muted">…thinking</div></div>}
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
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
