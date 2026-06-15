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

interface AdkFunctionCall {
  name?: string;
  args?: Record<string, unknown>;
}
interface AdkPart {
  text?: string;
  // A tool the agent invoked this turn, and/or the result coming back from one.
  functionCall?: AdkFunctionCall;
  functionResponse?: { name?: string };
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

/** A `browse` tool invocation surfaced from the agent's events: the folder it opened
 * (null = root). The web chat renders an interactive MCP-UI panel for each by fetching
 * /ui/browse (ADR-0012) — the same renderer Claude Desktop gets from the MCP tool. */
export interface BrowseRef {
  folderId: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  // Interactive browse panels the agent opened this turn (rendered inline under the text).
  browses?: BrowseRef[];
}

/** The MCP-UI resource backing one browse panel: `html` is the sandboxed-iframe content. */
export interface UiResource {
  uri: string;
  mimeType: string;
  html: string;
}

/** Fetch a browse panel's UI resource (root or a specific folder) for inline rendering and
 * drill-in. Hits the web-only /ui/browse proxy, which reuses the server's render_browse with
 * the caller's identity — so contents are RBAC-scoped exactly like the MCP `browse` tool. */
export async function browseUi(folderId: string | null = null): Promise<UiResource> {
  const query = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  const resp = await apiFetch(`/ui/browse${query}`);
  if (!resp.ok) throw new Error(`browse ui error ${resp.status}`);
  const block = (await resp.json()) as { resource: { uri: string; mimeType: string; text: string } };
  return { uri: block.resource.uri, mimeType: block.resource.mimeType, html: block.resource.text };
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

/** One conversation turn for the admin detail view: the prose plus any tool activity, so
 * function-call turns (which have no user-visible text) are still represented. */
export interface SessionTurn {
  role: "user" | "agent";
  text: string;
  toolCalls: { name: string; args: Record<string, unknown> }[];
  hasResponse: boolean;
}

/** Map a resumed session's ADK events to typed turns (mirrors sessionToMessages, but keeps
 * tool calls / responses instead of discarding text-less events). */
export function sessionToTurns(session: AdkSession): SessionTurn[] {
  const turns: SessionTurn[] = [];
  for (const event of session.events ?? []) {
    const parts = event.content?.parts ?? [];
    const text = parts.map((p) => p.text ?? "").join("");
    const toolCalls = parts
      .filter((p): p is AdkPart & { functionCall: AdkFunctionCall } => Boolean(p.functionCall))
      .map((p) => ({ name: p.functionCall.name ?? "(unknown)", args: p.functionCall.args ?? {} }));
    const hasResponse = parts.some((p) => Boolean(p.functionResponse));
    if (!text && toolCalls.length === 0 && !hasResponse) continue; // skip truly empty events
    turns.push({ role: event.author === "user" ? "user" : "agent", text, toolCalls, hasResponse });
  }
  return turns;
}

/** The agent's reply to one turn: the prose plus any interactive browse panels it opened. */
export interface AgentReply {
  text: string;
  browses: BrowseRef[];
}

/** Pull the user-visible text and any `browse` tool-calls out of a turn's ADK events. The
 * browse panel is rendered from the tool CALL (which ADK reliably surfaces), not its result
 * — so the web host never depends on ADK forwarding the embedded ui:// resource. */
export function eventsToReply(events: AdkEvent[]): AgentReply {
  const parts: string[] = [];
  const browses: BrowseRef[] = [];
  for (const event of events) {
    for (const part of event.content?.parts ?? []) {
      if (part.text) parts.push(part.text);
      if (part.functionCall?.name === "browse") {
        const fid = part.functionCall.args?.folder_id;
        browses.push({ folderId: typeof fid === "string" ? fid : null });
      }
    }
  }
  return { text: parts.join(""), browses };
}

/** Send a message to the agent on an existing server-created session; return its reply. */
export async function runAgent(userId: string, sessionId: string, text: string): Promise<AgentReply> {
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
  return eventsToReply(events);
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
  folder_id?: string | null;
  shared_user_ids?: string[];
  shared_group_ids?: string[];
}

export interface Folder {
  folder_id: string;
  name: string;
  parent_id?: string | null;
  owner_id?: string | null;
  shared_user_ids?: string[];
  shared_group_ids?: string[];
  created_at: string;
}

export interface Group {
  group_id: string;
  name: string;
  member_ids: string[];
  created_at: string;
}

/** A change-set for sharing a file OR folder with users (by email) and/or groups. */
export interface ShareEdit {
  add_user_emails?: string[];
  remove_user_ids?: string[];
  add_group_ids?: string[];
  remove_group_ids?: string[];
}

export async function shareAsset(assetId: string, edit: ShareEdit): Promise<Asset> {
  const resp = await apiFetch(`/api/assets/${assetId}/share`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(edit),
  });
  if (!resp.ok) throw new Error(`share error ${resp.status}`);
  return resp.json();
}

/** Move a file into a folder (null = root). Owner or admin only (server-enforced). */
export async function moveAsset(assetId: string, folderId: string | null): Promise<Asset> {
  const resp = await apiFetch(`/api/assets/${assetId}/move`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ folder_id: folderId }),
  });
  if (!resp.ok) throw new Error(`move error ${resp.status}`);
  return resp.json();
}

// --- Folders ---
export async function listFolders(): Promise<Folder[]> {
  const resp = await apiFetch("/api/folders");
  if (!resp.ok) throw new Error(`folders error ${resp.status}`);
  return resp.json();
}

export async function createFolder(name: string, parentId: string | null = null): Promise<Folder> {
  const resp = await apiFetch("/api/folders", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, parent_id: parentId }),
  });
  if (!resp.ok) throw new Error(`create folder error ${resp.status}`);
  return resp.json();
}

export async function deleteFolder(folderId: string): Promise<void> {
  const resp = await apiFetch(`/api/folders/${folderId}`, { method: "DELETE" });
  if (!resp.ok && resp.status !== 204) throw new Error(`delete folder error ${resp.status}`);
}

export async function shareFolder(folderId: string, edit: ShareEdit): Promise<Folder> {
  const resp = await apiFetch(`/api/folders/${folderId}/share`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(edit),
  });
  if (!resp.ok) throw new Error(`share folder error ${resp.status}`);
  return resp.json();
}

// --- Groups: shareable listing (top-level, any signed-in user) vs admin CRUD ---

/** A group as exposed by the public /api/groups picker route: id + name only, NO membership. */
export interface ShareableGroup {
  group_id: string;
  name: string;
}

/** List groups any signed-in user may share with (group_id + name only). Unlike listGroups
 * (admin-only, includes membership), this hits the top-level read-only /api/groups route so
 * non-admins can still discover groups in the sharing modal. */
export async function listShareableGroups(): Promise<ShareableGroup[]> {
  const resp = await apiFetch("/api/groups");
  if (!resp.ok) throw new Error(`groups error ${resp.status}`);
  return resp.json();
}

// --- Groups (admin) ---
export async function listGroups(): Promise<Group[]> {
  const resp = await apiFetch("/api/admin/groups");
  if (!resp.ok) throw new Error(`groups error ${resp.status}`);
  return resp.json();
}

export async function createGroup(name: string, memberEmails: string[] = []): Promise<Group> {
  const resp = await apiFetch("/api/admin/groups", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, member_emails: memberEmails }),
  });
  if (!resp.ok) throw new Error(`create group error ${resp.status}`);
  return resp.json();
}

export async function updateGroup(
  groupId: string,
  edit: { name?: string; add_member_emails?: string[]; remove_member_ids?: string[] },
): Promise<Group> {
  const resp = await apiFetch(`/api/admin/groups/${groupId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(edit),
  });
  if (!resp.ok) throw new Error(`update group error ${resp.status}`);
  return resp.json();
}

export async function deleteGroup(groupId: string): Promise<void> {
  const resp = await apiFetch(`/api/admin/groups/${groupId}`, { method: "DELETE" });
  if (!resp.ok && resp.status !== 204) throw new Error(`delete group error ${resp.status}`);
}

// --- Directory: pseudonymous user_id -> conventional name/email (known identities) ---
export type Directory = Record<string, { email: string; name: string }>;

export async function fetchDirectory(): Promise<Directory> {
  const resp = await apiFetch("/api/directory");
  if (!resp.ok) throw new Error(`directory error ${resp.status}`);
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
  // Conventional identity from the directory (when the user_id is a known persona/IAP user).
  email?: string | null;
  name?: string | null;
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
