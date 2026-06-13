import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { Home } from "./pages/Home";
import { server } from "./test/server";

const renderApp = (path = "/chat") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<App />}>
          <Route path="/chat" element={<div>chat-content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

describe("App shell", () => {
  it("renders the brand, nav tabs, the active route, and the outlet", () => {
    renderApp("/chat");
    expect(screen.getByText(/agentic-webapp/i)).toBeInTheDocument();
    // NavLink marks the active route with aria-current="page".
    expect(screen.getByRole("link", { name: "Chat" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("chat-content")).toBeInTheDocument();
  });

  it("shows the signed-in user and environment in the header", async () => {
    server.use(
      http.get("/api/me", () => HttpResponse.json({ email: "alice@example.com", user_id: "u1", environment: "prod" })),
    );
    renderApp("/chat");
    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("prod")).toBeInTheDocument();
  });

  it("falls back to 'guest' when there is no signed-in identity", async () => {
    renderApp("/chat"); // default /api/me handler returns null identity
    expect(await screen.findByText("guest")).toBeInTheDocument();
  });
});

describe("Home", () => {
  it("renders the heading and primary links", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "agentic-webapp" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Chat with the agent/i })).toHaveAttribute("href", "/chat");
  });
});
