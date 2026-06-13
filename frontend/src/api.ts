// Same-origin calls: FastAPI serves this SPA and proxies the agent endpoints.
const APP = "assistant";

const PERSONA_KEY = "persona-email";

/** The simulated identity (dev/test persona) the user picked, sent as the IAP header so
 * the backend resolves their RBAC roles. Empty in prod (real IAP identity is used). */
export function getPersona(): string | null {
  try {
    return localStorage.getItem(PERSONA_KEY);
  } catch {
    return null;
  }
}

export function setPersona(email: string | null): void {
  try {
    if (email) localStorage.setItem(PERSONA_KEY, email);
    else localStorage.removeItem(PERSONA_KEY);
  } catch {
    /* no storage — persona just won't persist */
  }
}

/** fetch wrapper that injects the chosen persona as the IAP identity header (ADR-0004).
 * All API calls go through this so the simulated user is consistent across the app. */
function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const persona = getPersona();
  if (persona) headers.set("X-Goog-Authenticated-User-Email", persona);
  return fetch(input, { ...init, headers });
}

export interface Me {
  email: string | null;
  user_id: string | null;
  environment: string;
  roles: string[];
  permissions: string[];
}

export interface Persona {
  email: string;
  name: string;
  roles: string[];
}

/** The signed-in identity + resolved RBAC roles/permissions. */
export async function getMe(): Promise<Me> {
  const resp = await apiFetch("/api/me");
  if (!resp.ok) throw new Error(`me error ${resp.status}`);
  return resp.json();
}

/** Switchable test identities (non-prod only; [] in prod). */
export async function fetchPersonas(): Promise<Persona[]> {
  const resp = await apiFetch("/api/auth/personas");
  if (!resp.ok) throw new Error(`personas error ${resp.status}`);
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
  // The background summariser writes a short title into the session state.
  state?: { title?: string };
}

/** The human-friendly title the summariser gave a session, if any. */
export function sessionTitle(session: AdkSession | null): string | null {
  return session?.state?.title ?? null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

/** Create a session. The SERVER mints the id (POST .../sessions with no id in the path);
 * we read it back. Never generate a session id client-side. */
export async function createSession(userId: string): Promise<string> {
  const resp = await apiFetch(`/apps/${APP}/users/${encodeURIComponent(userId)}/sessions`, {
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
  const resp = await apiFetch(
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
  const resp = await apiFetch("/run", {
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
  const resp = await apiFetch("/api/admin/usage");
  if (!resp.ok) throw new Error(`usage error ${resp.status}`);
  return resp.json();
}

// --- Session explorer (ADK list-sessions; note ADK serialises camelCase) ---
export interface SessionMeta {
  id: string;
  lastUpdateTime?: number;
  // list_sessions surfaces only the title from session state (see firestore_session.py).
  state?: { title?: string };
}

/** List the signed-in user's sessions, most-recent first. */
export async function listSessions(userId: string): Promise<SessionMeta[]> {
  const resp = await apiFetch(`/apps/${APP}/users/${encodeURIComponent(userId)}/sessions`);
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
  owner_id?: string | null;
  shared_with?: string[];
}

/** Share an asset with other users (by email). Owner or admin only (server-enforced). */
export async function shareAsset(assetId: string, emails: string[]): Promise<Asset> {
  const resp = await apiFetch(`/api/assets/${assetId}/share`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ emails }),
  });
  if (!resp.ok) throw new Error(`share error ${resp.status}`);
  return resp.json();
}

export async function listAssets(limit = 100): Promise<Asset[]> {
  const resp = await apiFetch(`/api/assets?limit=${limit}`);
  if (!resp.ok) throw new Error(`assets error ${resp.status}`);
  return resp.json();
}

/** Upload a file as an asset. The SERVER mints the asset_id (we read it back) and stores
 * the bytes in GCS — the single source of truth shared by this page and the chat agent. */
export async function uploadAsset(file: File): Promise<Asset> {
  const body = new FormData();
  body.append("file", file);
  const resp = await apiFetch("/api/assets", { method: "POST", body });
  if (!resp.ok) throw new Error(`upload error ${resp.status}`);
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
  const resp = await apiFetch(`/api/admin/usage/records?limit=${limit}`);
  if (!resp.ok) throw new Error(`records error ${resp.status}`);
  return resp.json();
}

// --- Admin: per-user roll-up + per-session drilldown ---
export interface UserSummary {
  user_id: string;
  sessions: number;
  calls: number;
  total_tokens: number;
  est_cost_usd: number;
}

export interface SessionSummary {
  session_id: string;
  calls: number;
  total_tokens: number;
  est_cost_usd: number;
  last_timestamp: string;
}

export async function fetchUsers(): Promise<UserSummary[]> {
  const resp = await apiFetch("/api/admin/users");
  if (!resp.ok) throw new Error(`users error ${resp.status}`);
  return resp.json();
}

export async function fetchUserSessions(userId: string): Promise<SessionSummary[]> {
  const resp = await apiFetch(`/api/admin/users/${encodeURIComponent(userId)}/sessions`);
  if (!resp.ok) throw new Error(`user sessions error ${resp.status}`);
  return resp.json();
}

// --- Analytics: the AnalyticsManager warehouse (extractions + discovered schema) ---
export interface Extraction {
  extraction_id: string;
  asset_id: string;
  doc_type: string;
  user_id: string;
  session_id: string;
  fields: Record<string, unknown>;
  model_id: string | null;
  created_at: string;
}

export interface AnalyticsSummary {
  total: number;
  by_doc_type: { doc_type: string; count: number; fields: string[] }[];
}

export async function fetchExtractions(limit = 200): Promise<Extraction[]> {
  const resp = await apiFetch(`/api/analytics/extractions?limit=${limit}`);
  if (!resp.ok) throw new Error(`extractions error ${resp.status}`);
  return resp.json();
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const resp = await apiFetch("/api/analytics/summary");
  if (!resp.ok) throw new Error(`analytics error ${resp.status}`);
  return resp.json();
}

/** Fetch a raw ADK session (events + state) for the admin raw-logs view. */
export async function fetchRawSession(userId: string, sessionId: string): Promise<unknown> {
  const resp = await apiFetch(
    `/apps/assistant/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}`,
  );
  if (!resp.ok) throw new Error(`session error ${resp.status}`);
  return resp.json();
}
