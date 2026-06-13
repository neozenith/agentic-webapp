import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { Sidebar } from "./Sidebar";

const renderSidebar = (path = "/") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>,
  );

afterEach(() => localStorage.clear());

describe("Sidebar", () => {
  it("renders the brand and a link per route, marking the active one", () => {
    renderSidebar("/assets");
    expect(screen.getByText(/agentic-webapp/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Assets" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("collapses to an icon rail, hides the brand, and persists the choice", async () => {
    const user = userEvent.setup();
    renderSidebar();
    expect(screen.getByText(/agentic-webapp/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /collapse sidebar/i }));
    expect(screen.queryByText(/agentic-webapp/i)).not.toBeInTheDocument();
    expect(localStorage.getItem("sidebar-collapsed")).toBe("1");
    // The toggle now offers to expand again.
    expect(screen.getByRole("button", { name: /expand sidebar/i })).toBeInTheDocument();
  });

  it("starts collapsed when localStorage says so", () => {
    localStorage.setItem("sidebar-collapsed", "1");
    renderSidebar();
    expect(screen.queryByText(/agentic-webapp/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /expand sidebar/i })).toBeInTheDocument();
  });
});
