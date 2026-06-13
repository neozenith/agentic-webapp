import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Sessions } from "./Sessions";

const me = http.get("/api/me", () => HttpResponse.json({ email: null, user_id: "uid", environment: "dev" }));

const renderSessions = () =>
  render(
    <MemoryRouter>
      <Sessions />
    </MemoryRouter>,
  );

describe("Sessions", () => {
  it("lists sessions most-recent first, labelled by their summariser title", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions", () =>
        HttpResponse.json([
          { id: "older", lastUpdateTime: 1000, state: { title: "Older chat" } },
          { id: "newer", lastUpdateTime: 2000, state: { title: "Fuel receipt analysis" } },
        ]),
      ),
    );
    renderSessions();
    // the title is the link text; it still navigates to /chat/<id>
    expect(await screen.findByRole("link", { name: "Fuel receipt analysis" })).toHaveAttribute("href", "/chat/newer");
    expect(screen.getByRole("link", { name: "Older chat" })).toHaveAttribute("href", "/chat/older");
    expect(screen.getAllByRole("row")).toHaveLength(3); // header + 2
  });

  it("falls back to 'Untitled session' when a session has no title yet", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions", () => HttpResponse.json([{ id: "s1", lastUpdateTime: 1000 }])),
    );
    renderSessions();
    expect(await screen.findByRole("link", { name: "Untitled session" })).toHaveAttribute("href", "/chat/s1");
  });

  it("shows an empty state when there are no sessions", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions", () => HttpResponse.json([])),
    );
    renderSessions();
    expect(await screen.findByText(/No sessions yet/i)).toBeInTheDocument();
  });

  it("surfaces an error", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions", () => new HttpResponse(null, { status: 500 })),
    );
    renderSessions();
    expect(await screen.findByText(/sessions error 500/i)).toBeInTheDocument();
  });
});
