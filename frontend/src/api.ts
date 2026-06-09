// Same-origin calls: FastAPI serves this SPA and proxies the agent endpoints.
const APP = "assistant";

export interface Me {
  email: string | null;
  user_id: string | null;
  environment: string;
}

/** The signed-in identity. `user_id` is the pseudonymous, server-authoritative id used
 * for session ownership (null when there's no IAP, e.g. a bare local run). */
export async function getMe(): Promise<Me> {
  const resp = await fetch("/api/me");
  if (!resp.ok) throw new Error(`me error ${resp.status}`);
  return resp.json();
}

interface AdkPart {
  text?: string;
}
interface AdkEvent {
  author?: string;
  content?: { parts?: AdkPart[] };
}
export interface AdkSession {
  id: string;
  events?: AdkEvent[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

/** Create a session. The SERVER mints the id (POST .../sessions with no id in the path);
 * we read it back. Never generate a session id client-side. */
export async function createSession(userId: string): Promise<string> {
  const resp = await fetch(`/apps/${APP}/users/${encodeURIComponent(userId)}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}",
  });
  if (!resp.ok) throw new Error(`create session error ${resp.status}`);
  const session: AdkSession = await resp.json();
  return session.id;
}

/** Fetch an existing session (with its events) to resume, or null if it doesn't exist. */
export async function getSession(userId: string, sessionId: string): Promise<AdkSession | null> {
  const resp = await fetch(
    `/apps/${APP}/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}`,
  );
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`get session error ${resp.status}`);
  return resp.json();
}

/** Rebuild a chat transcript from a resumed session's ADK events. */
export function sessionToMessages(session: AdkSession): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const event of session.events ?? []) {
    const text = (event.content?.parts ?? []).map((p) => p.text ?? "").join("");
    if (!text) continue; // skip function-call / empty events
    out.push({ role: event.author === "user" ? "user" : "assistant", text });
  }
  return out;
}

/** Send a message to the agent on an existing server-created session; return its reply. */
export async function runAgent(userId: string, sessionId: string, text: string): Promise<string> {
  const resp = await fetch("/run", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      app_name: APP,
      user_id: userId,
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

// --- Session explorer (ADK list-sessions; note ADK serialises camelCase) ---
export interface SessionMeta {
  id: string;
  lastUpdateTime?: number;
}

/** List the signed-in user's sessions, most-recent first. */
export async function listSessions(userId: string): Promise<SessionMeta[]> {
  const resp = await fetch(`/apps/${APP}/users/${encodeURIComponent(userId)}/sessions`);
  if (!resp.ok) throw new Error(`sessions error ${resp.status}`);
  const sessions: SessionMeta[] = await resp.json();
  return [...sessions].sort((a, b) => (b.lastUpdateTime ?? 0) - (a.lastUpdateTime ?? 0));
}

// --- Asset explorer (backend serialises snake_case) ---
export interface Asset {
  asset_id: string;
  filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  created_at: string;
}

export async function listAssets(limit = 100): Promise<Asset[]> {
  const resp = await fetch(`/api/assets?limit=${limit}`);
  if (!resp.ok) throw new Error(`assets error ${resp.status}`);
  return resp.json();
}

// --- Admin: itemised usage records (each carries a session_id to relaunch) ---
export interface UsageRecord {
  request_id: string;
  session_id: string;
  user_id: string;
  model_id: string;
  total_tokens: number;
  est_cost_usd: number;
  timestamp: string;
}

export async function fetchUsageRecords(limit = 100): Promise<UsageRecord[]> {
  const resp = await fetch(`/api/admin/usage/records?limit=${limit}`);
  if (!resp.ok) throw new Error(`records error ${resp.status}`);
  return resp.json();
}
