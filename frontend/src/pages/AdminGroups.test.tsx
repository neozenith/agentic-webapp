import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import type { Group } from "../api";
import { server } from "../test/server";
import { AdminGroups } from "./AdminGroups";

// Pseudonymous member_id -> conventional identity (the /api/directory shape).
const DIRECTORY = {
  "uid-alice-1234567890": { name: "Alice Smith", email: "alice@example.com" },
  "uid-bob-1234567890": { name: "Bob Jones", email: "bob@example.com" },
};

const renderGroups = () =>
  render(
    <MemoryRouter>
      <AdminGroups />
    </MemoryRouter>,
  );

// A stateful, network-level fake (per the no-mock rule): GET reflects the live array,
// POST/PATCH/DELETE mutate it, so create/add/remove/delete actually re-render.
let groups: Group[] = [];

beforeEach(() => {
  groups = [
    {
      group_id: "g1",
      name: "Engineering",
      member_ids: ["uid-alice-1234567890", "uid-unknown-9999"],
      created_at: "2026-01-01T00:00:00Z",
    },
    { group_id: "g2", name: "Marketing", member_ids: [], created_at: "2026-02-01T00:00:00Z" },
  ];
  server.use(
    http.get("/api/admin/groups", () => HttpResponse.json(groups)),
    http.get("/api/directory", () => HttpResponse.json(DIRECTORY)),
    http.post("/api/admin/groups", async ({ request }) => {
      const body = (await request.json()) as { name: string; member_emails?: string[] };
      const g: Group = {
        group_id: `g${groups.length + 1}`,
        name: body.name,
        member_ids: [],
        created_at: "2026-03-01T00:00:00Z",
      };
      groups.push(g);
      return HttpResponse.json(g);
    }),
    http.patch("/api/admin/groups/:id", async ({ params, request }) => {
      const body = (await request.json()) as { add_member_emails?: string[]; remove_member_ids?: string[] };
      const g = groups.find((x) => x.group_id === params.id);
      if (!g) return new HttpResponse(null, { status: 404 });
      if (body.add_member_emails?.length) g.member_ids = [...g.member_ids, "uid-bob-1234567890"];
      if (body.remove_member_ids) g.member_ids = g.member_ids.filter((m) => !body.remove_member_ids?.includes(m));
      return HttpResponse.json(g);
    }),
    http.delete("/api/admin/groups/:id", ({ params }) => {
      groups = groups.filter((x) => x.group_id !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
  );
});

describe("AdminGroups management", () => {
  it("renders group names and resolves member display names from the directory", async () => {
    renderGroups();
    expect(await screen.findByText("Engineering")).toBeInTheDocument();
    expect(screen.getByText("Marketing")).toBeInTheDocument();
    // known member -> "name <email>"
    expect(screen.getByText("Alice Smith <alice@example.com>")).toBeInTheDocument();
    // unknown member -> raw id truncated to 8 chars + ellipsis
    expect(screen.getByText("uid-unkn…")).toBeInTheDocument();
    // the empty group shows the no-members hint
    expect(screen.getByText("No members")).toBeInTheDocument();
  });

  it("creates a group and re-renders it", async () => {
    const user = userEvent.setup();
    renderGroups();
    await screen.findByText("Engineering");
    await user.type(screen.getByLabelText("Group name"), "Design");
    await user.type(screen.getByLabelText("Member emails"), "carol@example.com dan@example.com");
    await user.click(screen.getByRole("button", { name: "Create group" }));
    expect(await screen.findByText("Design")).toBeInTheDocument();
  });

  it("adds a member to a group by email", async () => {
    const user = userEvent.setup();
    renderGroups();
    await screen.findByText("Engineering");
    await user.type(screen.getByLabelText("Add member to Marketing"), "bob@example.com");
    const addButtons = screen.getAllByRole("button", { name: "Add" });
    await user.click(addButtons[1]); // the Marketing card's Add button
    expect(await screen.findByText("Bob Jones <bob@example.com>")).toBeInTheDocument();
  });

  it("removes a member from a group", async () => {
    const user = userEvent.setup();
    renderGroups();
    await screen.findByText("Alice Smith <alice@example.com>");
    await user.click(screen.getByRole("button", { name: "Remove Alice Smith <alice@example.com>" }));
    await waitFor(() => expect(screen.queryByText("Alice Smith <alice@example.com>")).not.toBeInTheDocument());
  });

  it("deletes a group", async () => {
    const user = userEvent.setup();
    renderGroups();
    await screen.findByText("Marketing");
    const deleteButtons = screen.getAllByRole("button", { name: "Delete group" });
    await user.click(deleteButtons[1]); // Marketing is the second group
    await waitFor(() => expect(screen.queryByText("Marketing")).not.toBeInTheDocument());
  });

  it("shows an empty state when there are no groups", async () => {
    server.use(http.get("/api/admin/groups", () => HttpResponse.json([])));
    renderGroups();
    expect(await screen.findByText("No groups yet.")).toBeInTheDocument();
  });

  it("surfaces a fetch error", async () => {
    server.use(http.get("/api/admin/groups", () => new HttpResponse(null, { status: 500 })));
    renderGroups();
    expect(await screen.findByText(/error/i)).toBeInTheDocument();
  });
});
