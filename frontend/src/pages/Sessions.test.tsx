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
  it("lists the user's sessions, most-recent first, each linking to its chat", async () => {
    server.use(
      me,
      http.get("/apps/assistant/users/uid/sessions", () =>
        HttpResponse.json([
          { id: "older", lastUpdateTime: 1000 },
          { id: "newer", lastUpdateTime: 2000 },
        ]),
      ),
    );
    renderSessions();
    expect(await screen.findByRole("link", { name: "newer" })).toHaveAttribute("href", "/chat/newer");
    expect(screen.getByRole("link", { name: "older" })).toHaveAttribute("href", "/chat/older");
    // header row + 2 session rows
    expect(screen.getAllByRole("row")).toHaveLength(3);
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
