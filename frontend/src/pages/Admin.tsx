import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchUsage, fetchUsageRecords, type UsageBucket, type UsageRecord, type UsageSummary } from "../api";

const usd = (n: number) => `$${n.toFixed(6)}`;

function RecordsTable({ records }: { records: UsageRecord[] }) {
  return (
    <div className="card">
      <h3>recent calls</h3>
      <table>
        <thead>
          <tr>
            <th>session</th>
            <th>model</th>
            <th>tokens</th>
            <th>cost</th>
          </tr>
        </thead>
        <tbody>
          {records.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                no calls yet
              </td>
            </tr>
          )}
          {records.map((r) => (
            <tr key={r.request_id}>
              <td>
                {/* clicking a session relaunches it in the chat */}
                <Link to={`/chat/${r.session_id}`}>{r.session_id}</Link>
              </td>
              <td className="muted">{r.model_id}</td>
              <td>{r.total_tokens}</td>
              <td>{usd(r.est_cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsage()
      .then(setData)
      .catch((e) => setError(String(e)));
    fetchUsageRecords()
      .then(setRecords)
      .catch(() => {
        /* records are supplementary; the summary above is the primary view */
      });
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
      <RecordsTable records={records} />
    </section>
  );
}
