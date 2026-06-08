import { useEffect, useState } from "react";

import { fetchUsage, type UsageBucket, type UsageSummary } from "../api";

const usd = (n: number) => `$${n.toFixed(6)}`;

function BucketTable({ title, rows }: { title: string; rows: Record<string, UsageBucket> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1].est_cost_usd - a[1].est_cost_usd);
  return (
    <div className="card">
      <h3>{title}</h3>
      <table>
        <thead>
          <tr>
            <th>{title.includes("model") ? "model" : "user"}</th>
            <th>calls</th>
            <th>tokens</th>
            <th>est. cost</th>
          </tr>
        </thead>
        <tbody>
          {entries.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                no usage yet
              </td>
            </tr>
          )}
          {entries.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{v.calls}</td>
              <td>{v.total_tokens}</td>
              <td>{usd(v.est_cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Admin() {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsage().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">⚠️ {error}</p>;
  if (!data) return <p className="muted">Loading usage…</p>;

  return (
    <section>
      <div className="card stats">
        <div>
          <span className="big">{data.totals.calls}</span>
          <span className="muted">calls</span>
        </div>
        <div>
          <span className="big">{data.totals.total_tokens}</span>
          <span className="muted">tokens</span>
        </div>
        <div>
          <span className="big">{usd(data.totals.est_cost_usd)}</span>
          <span className="muted">est. cost</span>
        </div>
      </div>
      <BucketTable title="by model" rows={data.by_model} />
      <BucketTable title="by user" rows={data.by_user} />
    </section>
  );
}
