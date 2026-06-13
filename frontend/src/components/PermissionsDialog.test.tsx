import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server } from "../test/server";
import { PermissionsDialog, type ShareTarget } from "./PermissionsDialog";

const DIRECTORY = { u1: { email: "alice@example.com", name: "Alice" } };
const GROUPS = [
  { group_id: "g1", name: "Engineering", member_ids: [], created_at: "2026-06-01T00:00:00Z" },
  { group_id: "g2", name: "Finance", member_ids: [], created_at: "2026-06-01T00:00:00Z" },
];

const directoryAndGroups = () => [
  http.get("/api/directory", () => HttpResponse.json(DIRECTORY)),
  http.get("/api/admin/groups", () => HttpResponse.json(GROUPS)),
];

const target: ShareTarget = {
  kind: "asset",
  id: "a1",
  name: "report.pdf",
  sharedUserIds: ["u1"],
  sharedGroupIds: ["g1"],
};

describe("PermissionsDialog", () => {
  it("renders nothing when closed or target-less", () => {
    const { container, rerender } = render(
      <PermissionsDialog open={false} onOpenChange={() => {}} target={target} onSaved={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
    rerender(<PermissionsDialog open onOpenChange={() => {}} target={null} onSaved={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("loads current users/groups, adds an email, and POSTs add_user_emails on save", async () => {
    server.use(...directoryAndGroups());
    let body: unknown = null;
    server.use(
      http.post("/api/assets/a1/share", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ asset_id: "a1" });
      }),
    );
    const onSaved = vi.fn();
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(<PermissionsDialog open onOpenChange={onOpenChange} target={target} onSaved={onSaved} />);

    // Existing share state resolves from the directory + groups.
    expect(await screen.findByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Engineering")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Add by email"), "bob@example.com");
    await user.click(screen.getByRole("button", { name: "Add email" }));
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(body).toEqual({ add_user_emails: ["bob@example.com"] });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("removes a user + group and adds a group, sending the full change-set (folder kind)", async () => {
    server.use(...directoryAndGroups());
    let body: unknown = null;
    server.use(
      http.post("/api/folders/f1/share", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ folder_id: "f1" });
      }),
    );
    const user = userEvent.setup();
    const folderTarget: ShareTarget = {
      kind: "folder",
      id: "f1",
      name: "Reports",
      sharedUserIds: ["u1"],
      sharedGroupIds: ["g1"],
    };
    render(<PermissionsDialog open onOpenChange={() => {}} target={folderTarget} onSaved={() => {}} />);

    await screen.findByText("Alice");
    await user.click(screen.getByRole("button", { name: "Remove Alice" }));
    expect(screen.queryByText("Alice")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove group Engineering" }));
    // g2 (Finance) is the only addable group; pick it.
    await user.click(screen.getByLabelText("Finance"));

    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect(body).toEqual({ remove_user_ids: ["u1"], add_group_ids: ["g2"], remove_group_ids: ["g1"] });
  });

  it("drops a pending email before saving", async () => {
    server.use(...directoryAndGroups());
    const user = userEvent.setup();
    render(<PermissionsDialog open onOpenChange={() => {}} target={target} onSaved={() => {}} />);
    await screen.findByText("Alice");
    await user.type(screen.getByLabelText("Add by email"), "bob@example.com");
    await user.click(screen.getByRole("button", { name: "Add email" }));
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove bob@example.com" }));
    expect(screen.queryByText("bob@example.com")).not.toBeInTheDocument();
  });

  it("shows empty states when nothing is shared yet", async () => {
    server.use(...directoryAndGroups());
    const empty: ShareTarget = { kind: "asset", id: "a9", name: "fresh.pdf", sharedUserIds: [], sharedGroupIds: [] };
    render(<PermissionsDialog open onOpenChange={() => {}} target={empty} onSaved={() => {}} />);
    expect(await screen.findByText(/Not shared with anyone yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No groups yet/i)).toBeInTheDocument();
  });

  it("surfaces a load error when the directory fetch fails", async () => {
    server.use(
      http.get("/api/directory", () => new HttpResponse(null, { status: 500 })),
      http.get("/api/admin/groups", () => HttpResponse.json(GROUPS)),
    );
    render(<PermissionsDialog open onOpenChange={() => {}} target={target} onSaved={() => {}} />);
    expect(await screen.findByText(/directory error 500/i)).toBeInTheDocument();
  });

  it("surfaces a save error inline without closing", async () => {
    server.use(...directoryAndGroups());
    server.use(http.post("/api/assets/a1/share", () => new HttpResponse(null, { status: 500 })));
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(<PermissionsDialog open onOpenChange={onOpenChange} target={target} onSaved={() => {}} />);
    await screen.findByText("Alice");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/share error 500/i)).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("closes on Escape, overlay click, and the Cancel button", async () => {
    server.use(...directoryAndGroups());
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(<PermissionsDialog open onOpenChange={onOpenChange} target={target} onSaved={() => {}} />);
    await screen.findByText("Alice");

    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);

    await user.click(screen.getByRole("button", { name: "Close dialog" })); // overlay backdrop
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onOpenChange.mock.calls.filter(([v]) => v === false).length).toBeGreaterThanOrEqual(3);
  });
});
