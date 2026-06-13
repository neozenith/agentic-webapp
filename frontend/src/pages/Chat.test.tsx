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

  it("renders the agent reply as markdown, including an asset preview image", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions/s1", () => HttpResponse.json({ id: "s1", events: [] })),
      http.post("/run", () =>
        HttpResponse.json([
          {
            content: {
              parts: [{ text: "**Done.** Here is your receipt:\n\n![preview](/api/assets/a1/content)" }],
            },
          },
        ]),
      ),
    );
    const user = userEvent.setup();
    renderChat("/chat/s1");
    await screen.findByText(/Ask the agent something/i);
    await user.type(screen.getByPlaceholderText(/Type a message/i), "show it");
    await user.click(screen.getByRole("button", { name: /send/i }));
    // Bold markdown renders as <strong>, and the preview_url renders as an <img>.
    expect(await screen.findByText("Done.")).toBeInTheDocument();
    const img = await screen.findByRole("img", { name: "preview" });
    expect(img).toHaveAttribute("src", "/api/assets/a1/content");
  });

  it("attaches a photo (upload → asset) and references its id in the message", async () => {
    let sentText = "";
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions/s1", () => HttpResponse.json({ id: "s1", events: [] })),
      http.post("/api/assets", () =>
        HttpResponse.json(
          {
            asset_id: "asset-9",
            filename: "receipt.png",
            content_type: "image/png",
            size_bytes: 3,
            created_at: "2026-06-10T00:00:00Z",
          },
          { status: 201 },
        ),
      ),
      http.post("/run", async ({ request }) => {
        const body = (await request.json()) as { new_message: { parts: { text: string }[] } };
        sentText = body.new_message.parts[0].text;
        return HttpResponse.json([{ content: { parts: [{ text: "got it" }] } }]);
      }),
    );
    const user = userEvent.setup();
    const { container } = renderChat("/chat/s1");
    await screen.findByText(/Ask the agent something/i); // loaded
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["png"], "receipt.png", { type: "image/png" }));
    // The attachment chip shows the uploaded filename.
    expect(await screen.findByText("receipt.png")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText(/Type a message/i), "read this receipt");
    await user.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("got it");
    // The agent received the typed text PLUS a parseable asset reference.
    expect(sentText).toContain("read this receipt");
    expect(sentText).toContain("asset-9");
    // The sent user message keeps an inline image preview of the attachment (the bug fix).
    const preview = await screen.findByRole("img", { name: "receipt.png" });
    expect(preview).toHaveAttribute("src", "/api/assets/asset-9/content");
    // …and the typed prose still shows, without the raw "[attached asset …]" reference.
    expect(screen.getByText("read this receipt")).toBeInTheDocument();
    expect(screen.queryByText(/\[attached asset/)).not.toBeInTheDocument();
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
