// Same-origin calls: FastAPI serves this SPA and proxies the agent endpoints.
const APP = "assistant";
const USER = "web-user";

export async function ensureSession(sessionId: string): Promise<void> {
  await fetch(`/apps/${APP}/users/${USER}/sessions/${sessionId}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}",
  });
}

interface AdkPart {
  text?: string;
}
interface AdkEvent {
  content?: { parts?: AdkPart[] };
}

/** Send a message to the agent and return its full text reply. */
export async function runAgent(sessionId: string, text: string): Promise<string> {
  const resp = await fetch("/run", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      app_name: APP,
      user_id: USER,
      session_id: sessionId,
      new_message: { role: "user", parts: [{ text }] },
    }),
  });
  if (!resp.ok) throw new Error(`agent error ${resp.status}`);
  const events: AdkEvent[] = await resp.json();
  const parts: string[] = [];
  for (const event of events) {
    for (const part of event.content?.parts ?? []) {
      if (part.text) parts.push(part.text);
    }
  }
  return parts.join("");
}

export interface UsageBucket {
  calls: number;
  total_tokens: number;
  est_cost_usd: number;
}
export interface UsageSummary {
  totals: UsageBucket;
  by_model: Record<string, UsageBucket>;
  by_user: Record<string, UsageBucket>;
}

export async function fetchUsage(): Promise<UsageSummary> {
  const resp = await fetch("/api/admin/usage");
  if (!resp.ok) throw new Error(`usage error ${resp.status}`);
  return resp.json();
}
