import { useEffect, useState } from "react";

import { type Asset, listAssets } from "../api";

const fmtSize = (n: number | null): string => {
  if (n == null) return "—";
  return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`;
};

export function Assets() {
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAssets()
      .then(setAssets)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p className="error">⚠️ {error}</p>;
  if (!assets) return <p className="muted">Loading assets…</p>;

  return (
    <section className="card">
      <h3>Uploaded assets</h3>
      {assets.length === 0 ? (
        <p className="muted">No assets uploaded yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>file</th>
              <th>type</th>
              <th>size</th>
              <th>uploaded</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr key={a.asset_id}>
                <td>
                  <a href={`/api/assets/${a.asset_id}/content`} target="_blank" rel="noreferrer">
                    {a.filename ?? a.asset_id}
                  </a>
                </td>
                <td className="muted">{a.content_type ?? "—"}</td>
                <td>{fmtSize(a.size_bytes)}</td>
                <td className="muted">{new Date(a.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
