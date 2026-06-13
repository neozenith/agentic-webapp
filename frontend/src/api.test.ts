import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import {
  createSession,
  fetchUsage,
  fetchUsageRecords,
  getMe,
  getSession,
  listAssets,
  listSessions,
  runAgent,
  sessionToMessages,
  sessionToTurns,
} from "./api";
import { server } from "./test/server";

describe("sessionToMessages", () => {
  it("maps ADK events by author and skips text-less events", () => {
    const msgs = sessionToMessages({
      id: "s",
      events: [
        { author: "user", content: { parts: [{ text: "hi" }] } },
        { author: "assistant", content: { parts: [{ text: "hello" }] } },
        { author: "assistant", content: { parts: [{}] } }, // e.g. function call -> no text -> skipped
      ],
    });
    expect(msgs).toEqual([
      { role: "user", text: "hi" },
      { role: "assistant", text: "hello" },
    ]);
  });

  it("returns an empty transcript when there are no events", () => {
    expect(sessionToMessages({ id: "s" })).toEqual([]);
  });
});

describe("sessionToTurns", () => {
  it("maps events to typed turns, preserving tool calls and responses", () => {
    const turns = sessionToTurns({
      id: "s",
      events: [
        { author: "user", content: { parts: [{ text: "list assets" }] } },
        { author: "assistant", content: { parts: [{ functionCall: { name: "list_assets", args: { limit: 5 } } }] } },
        { author: "assistant", content: { parts: [{ functionResponse: { name: "list_assets" } }] } },
        { author: "assistant", content: { parts: [{ text: "done" }] } },
        { author: "assistant", content: { parts: [{}] } }, // truly empty -> skipped
      ],
    });
    expect(turns).toEqual([
      { role: "user", text: "list assets", toolCalls: [], hasResponse: false },
      { role: "agent", text: "", toolCalls: [{ name: "list_assets", args: { limit: 5 } }], hasResponse: false },
      { role: "agent", text: "", toolCalls: [], hasResponse: true },
      { role: "agent", text: "done", toolCalls: [], hasResponse: false },
    ]);
  });

  it("defaults a nameless tool call and empty args", () => {
    const turns = sessionToTurns({
      id: "s",
      events: [{ author: "assistant", content: { parts: [{ functionCall: {} }] } }],
    });
    expect(turns).toEqual([
      { role: "agent", text: "", toolCalls: [{ name: "(unknown)", args: {} }], hasResponse: false },
    ]);
  });

  it("returns an empty list when there are no events", () => {
    expect(sessionToTurns({ id: "s" })).toEqual([]);
  });
});

describe("getMe", () => {
  it("returns the identity payload", async () => {
    server.use(http.get("/api/me", () => HttpResponse.json({ email: "a@b.com", user_id: "uid", environment: "dev" })));
    expect(await getMe()).toEqual({ email: "a@b.com", user_id: "uid", environment: "dev" });
  });

  it("throws on a non-ok status", async () => {
    server.use(http.get("/api/me", () => new HttpResponse(null, { status: 500 })));
    await expect(getMe()).rejects.toThrow("me error 500");
  });
});

describe("createSession", () => {
  it("POSTs with no id in the path and returns the server-issued id", async () => {
    server.use(http.post("/apps/assistant/users/uid/sessions", () => HttpResponse.json({ id: "srv-123" })));
    expect(await createSession("uid")).toBe("srv-123");
  });

  it("throws on failure", async () => {
    server.use(http.post("/apps/assistant/users/uid/sessions", () => new HttpResponse(null, { status: 502 })));
    await expect(createSession("uid")).rejects.toThrow("create session error 502");
  });
});

describe("getSession", () => {
  it("returns the session when present", async () => {
    server.use(http.get("/apps/assistant/users/uid/sessions/s1", () => HttpResponse.json({ id: "s1", events: [] })));
    expect(await getSession("uid", "s1")).toEqual({ id: "s1", events: [] });
  });

  it("returns null on 404", async () => {
    server.use(http.get("/apps/assistant/users/uid/sessions/missing", () => new HttpResponse(null, { status: 404 })));
    expect(await getSession("uid", "missing")).toBeNull();
  });

  it("throws on other errors", async () => {
    server.use(http.get("/apps/assistant/users/uid/sessions/s", () => new HttpResponse(null, { status: 500 })));
    await expect(getSession("uid", "s")).rejects.toThrow("get session error 500");
  });
});

describe("runAgent", () => {
  it("concatenates the text parts of the returned events", async () => {
    server.use(
      http.post("/run", () =>
        HttpResponse.json([
          { content: { parts: [{ text: "Hello " }, { text: "world" }] } },
          { content: { parts: [{}] } },
        ]),
      ),
    );
    expect(await runAgent("uid", "s1", "hi")).toBe("Hello world");
  });

  it("throws on agent error", async () => {
    server.use(http.post("/run", () => new HttpResponse(null, { status: 500 })));
    await expect(runAgent("uid", "s1", "hi")).rejects.toThrow("agent error 500");
  });
});

describe("fetchUsage", () => {
  const summary = { totals: { calls: 1, total_tokens: 2, est_cost_usd: 0.1 }, by_model: {}, by_user: {} };

  it("returns the usage summary", async () => {
    server.use(http.get("/api/admin/usage", () => HttpResponse.json(summary)));
    expect(await fetchUsage()).toEqual(summary);
  });

  it("throws on error", async () => {
    server.use(http.get("/api/admin/usage", () => new HttpResponse(null, { status: 500 })));
    await expect(fetchUsage()).rejects.toThrow("usage error 500");
  });
});

describe("listSessions", () => {
  it("returns sessions sorted by lastUpdateTime descending", async () => {
    server.use(
      http.get("/apps/assistant/users/uid/sessions", () =>
        HttpResponse.json([
          { id: "a", lastUpdateTime: 1 },
          { id: "c", lastUpdateTime: 3 },
          { id: "b" }, // missing time -> treated as 0
        ]),
      ),
    );
    expect((await listSessions("uid")).map((s) => s.id)).toEqual(["c", "a", "b"]);
  });

  it("throws on error", async () => {
    server.use(http.get("/apps/assistant/users/uid/sessions", () => new HttpResponse(null, { status: 500 })));
    await expect(listSessions("uid")).rejects.toThrow("sessions error 500");
  });
});

describe("listAssets", () => {
  it("returns the asset list", async () => {
    const assets = [{ asset_id: "a1", filename: "f", content_type: "text/plain", size_bytes: 1, created_at: "x" }];
    server.use(http.get("/api/assets", () => HttpResponse.json(assets)));
    expect(await listAssets()).toEqual(assets);
  });

  it("throws on error", async () => {
    server.use(http.get("/api/assets", () => new HttpResponse(null, { status: 500 })));
    await expect(listAssets()).rejects.toThrow("assets error 500");
  });
});

describe("fetchUsageRecords", () => {
  it("returns the records", async () => {
    const records = [
      {
        request_id: "r",
        session_id: "s",
        user_id: "u",
        model_id: "m",
        total_tokens: 1,
        est_cost_usd: 0,
        timestamp: "t",
      },
    ];
    server.use(http.get("/api/admin/usage/records", () => HttpResponse.json(records)));
    expect(await fetchUsageRecords()).toEqual(records);
  });

  it("throws on error", async () => {
    server.use(http.get("/api/admin/usage/records", () => new HttpResponse(null, { status: 500 })));
    await expect(fetchUsageRecords()).rejects.toThrow("records error 500");
  });
});
