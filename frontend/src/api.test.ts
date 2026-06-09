import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { createSession, fetchUsage, getMe, getSession, runAgent, sessionToMessages } from "./api";
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
