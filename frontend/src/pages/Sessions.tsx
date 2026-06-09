import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

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

  if (error) return <p className="error">⚠️ {error}</p>;
  if (!sessions) return <p className="muted">Loading sessions…</p>;

  return (
    <section className="card">
      <div className="chat-header">
        <h3>Your sessions</h3>
        <Link className="btn ghost" to="/chat">
          New chat
        </Link>
      </div>
      {sessions.length === 0 ? (
        <p className="muted">
          No sessions yet. <Link to="/chat">Start one →</Link>
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>session</th>
              <th>last updated</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id}>
                <td>
                  <Link to={`/chat/${s.id}`}>{s.id}</Link>
                </td>
                <td className="muted">{s.lastUpdateTime ? new Date(s.lastUpdateTime * 1000).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
