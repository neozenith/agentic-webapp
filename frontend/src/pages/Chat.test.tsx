import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Chat } from "./Chat";

const me = http.get("/api/me", () => HttpResponse.json({ email: null, user_id: "uid", environment: "dev" }));

function renderChat(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/chat" element={<Chat />} />
        <Route path="/chat/:sessionId" element={<Chat />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Chat", () => {
  it("creates a server session and shows the empty state when opened at /chat", async () => {
    server.use(
      me,
      http.post("/apps/assistant/users/uid/sessions", () => HttpResponse.json({ id: "new-1" })),
      http.get("/apps/assistant/users/uid/sessions/new-1", () => HttpResponse.json({ id: "new-1", events: [] })),
    );
    renderChat("/chat");
    expect(await screen.findByText(/Ask the agent something/i)).toBeInTheDocument();
  });

  it("rehydrates the transcript when resuming an existing session", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions/s1", () =>
        HttpResponse.json({
          id: "s1",
          events: [
            { author: "user", content: { parts: [{ text: "earlier question" }] } },
            { author: "assistant", content: { parts: [{ text: "earlier answer" }] } },
          ],
        }),
      ),
    );
    renderChat("/chat/s1");
    expect(await screen.findByText("earlier question")).toBeInTheDocument();
    expect(await screen.findByText("earlier answer")).toBeInTheDocument();
  });

  it("creates a fresh session when the resumed id is gone (404)", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions/gone", () => new HttpResponse(null, { status: 404 })),
      http.post("/apps/assistant/users/uid/sessions", () => HttpResponse.json({ id: "replacement" })),
      http.get("/apps/assistant/users/uid/sessions/replacement", () =>
        HttpResponse.json({ id: "replacement", events: [] }),
      ),
    );
    renderChat("/chat/gone");
    expect(await screen.findByText(/Ask the agent something/i)).toBeInTheDocument();
  });

  it("sends a message and renders the agent reply", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions/s1", () => HttpResponse.json({ id: "s1", events: [] })),
      http.post("/run", () => HttpResponse.json([{ content: { parts: [{ text: "pong" }] } }])),
    );
    const user = userEvent.setup();
    renderChat("/chat/s1");
    await screen.findByText(/Ask the agent something/i); // wait until loaded (input enabled)
    await user.type(screen.getByPlaceholderText(/Type a message/i), "ping");
    await user.click(screen.getByRole("button", { name: /send/i }));
    expect(await screen.findByText("ping")).toBeInTheDocument(); // user bubble
    expect(await screen.findByText("pong")).toBeInTheDocument(); // agent reply
  });

  it("surfaces an error when the agent call fails", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions/s1", () => HttpResponse.json({ id: "s1", events: [] })),
      http.post("/run", () => new HttpResponse(null, { status: 500 })),
    );
    const user = userEvent.setup();
    renderChat("/chat/s1");
    await screen.findByText(/Ask the agent something/i); // wait until loaded (input enabled)
    await user.type(screen.getByPlaceholderText(/Type a message/i), "boom");
    await user.click(screen.getByRole("button", { name: /send/i }));
    expect(await screen.findByText(/agent error 500/i)).toBeInTheDocument();
  });

  it("starts a new chat via the New chat button", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions/s1", () =>
        HttpResponse.json({ id: "s1", events: [{ author: "user", content: { parts: [{ text: "old message" }] } }] }),
      ),
      http.post("/apps/assistant/users/uid/sessions", () => HttpResponse.json({ id: "fresh" })),
      http.get("/apps/assistant/users/uid/sessions/fresh", () => HttpResponse.json({ id: "fresh", events: [] })),
    );
    const user = userEvent.setup();
    renderChat("/chat/s1");
    expect(await screen.findByText("old message")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    await waitFor(() => expect(screen.queryByText("old message")).not.toBeInTheDocument());
  });
});
