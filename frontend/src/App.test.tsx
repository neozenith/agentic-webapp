import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { Home } from "./pages/Home";

describe("App shell", () => {
  it("renders the brand, nav tabs, the active route, and the outlet", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <Routes>
          <Route element={<App />}>
            <Route path="/chat" element={<div>chat-content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/agentic-webapp/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chat" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveClass("active");
    expect(screen.getByText("chat-content")).toBeInTheDocument();
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
