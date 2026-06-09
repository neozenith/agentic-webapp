import { Link } from "react-router-dom";

export function Home() {
  return (
    <section className="card">
      <h1>agentic-webapp</h1>
      <p>
        A scale-to-zero Cloud Run app: an async FastAPI backend serving this React UI, with a Google ADK agent running
        as a sidecar. Every LLM call is itemised (tokens + estimated cost) into BigQuery.
      </p>
      <div className="row">
        <Link className="btn" to="/chat">
          💬 Chat with the agent
        </Link>
        <Link className="btn" to="/admin">
          📊 Usage &amp; billing
        </Link>
        <a className="btn ghost" href="/dev-ui/" target="_blank" rel="noreferrer">
          🛠️ ADK debug UI
        </a>
      </div>
    </section>
  );
}
