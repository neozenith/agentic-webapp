import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { AuthProvider } from "../components/auth";
import { server } from "../test/server";
import { Assets } from "./Assets";

// The page loads BOTH assets and folders on mount; default folders to empty so each
// test only has to declare the assets it cares about.
beforeEach(() => {
  server.use(http.get("/api/folders", () => HttpResponse.json([])));
});

const statefulAssets = (asset: Record<string, unknown>) => {
  let stored: unknown[] = [];
  return [
    http.get("/api/assets", () => HttpResponse.json(stored)),
    http.post("/api/assets", () => {
      stored = [asset];
      return HttpResponse.json(asset, { status: 201 });
    }),
  ];
};

describe("Assets", () => {
  it("renders uploaded assets in the folder tree with content links and human sizes", async () => {
    server.use(
      http.get("/api/assets", () =>
        HttpResponse.json([
          {
            asset_id: "a1",
            filename: "pic.png",
            content_type: "image/png",
            size_bytes: 2048,
            created_at: "2026-06-01T00:00:00Z",
          },
          {
            asset_id: "a2",
            filename: "note.txt",
            content_type: "text/plain",
            size_bytes: 500,
            created_at: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
    );
    render(<Assets />, { wrapper: AuthProvider });
    expect(await screen.findByRole("link", { name: "pic.png" })).toHaveAttribute("href", "/api/assets/a1/content");
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("500 B")).toBeInTheDocument();
  });

  it("falls back to the asset id and a dash when fields are null", async () => {
    server.use(
      http.get("/api/assets", () =>
        HttpResponse.json([
          { asset_id: "a3", filename: null, content_type: null, size_bytes: null, created_at: "2026-06-01T00:00:00Z" },
        ]),
      ),
    );
    render(<Assets />, { wrapper: AuthProvider });
    expect(await screen.findByRole("link", { name: "a3" })).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows an empty state when there are no assets or folders", async () => {
    server.use(http.get("/api/assets", () => HttpResponse.json([])));
    render(<Assets />, { wrapper: AuthProvider });
    expect(await screen.findByText(/No assets uploaded/i)).toBeInTheDocument();
  });

  it("surfaces an error", async () => {
    server.use(http.get("/api/assets", () => new HttpResponse(null, { status: 500 })));
    render(<Assets />, { wrapper: AuthProvider });
    expect(await screen.findByText(/assets error 500/i)).toBeInTheDocument();
  });

  const asset = {
    asset_id: "a1",
    filename: "receipt.png",
    content_type: "image/png",
    size_bytes: 3,
    created_at: "2026-06-10T00:00:00Z",
  };

  it("uploads a photo via the button and shows it after the list refetches", async () => {
    server.use(...statefulAssets(asset));
    const user = userEvent.setup();
    const { container } = render(<Assets />, { wrapper: AuthProvider });
    await screen.findByText(/No assets uploaded/i);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["png"], "receipt.png", { type: "image/png" }));
    expect(await screen.findByRole("link", { name: "receipt.png" })).toHaveAttribute("href", "/api/assets/a1/content");
  });

  it("uploads a photo via drag-and-drop onto the tree", async () => {
    server.use(...statefulAssets(asset));
    const { container } = render(<Assets />, { wrapper: AuthProvider });
    await screen.findByText(/No assets uploaded/i);
    const zone = container.querySelector(".border-dashed") as HTMLElement;
    const file = new File(["png"], "receipt.png", { type: "image/png" });
    fireEvent.dragOver(zone);
    fireEvent.dragLeave(zone);
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(await screen.findByRole("link", { name: "receipt.png" })).toBeInTheDocument();
  });

  it("creates a folder via the inline input and shows it after refetch", async () => {
    let folders: unknown[] = [];
    server.use(
      http.get("/api/assets", () => HttpResponse.json([])),
      http.get("/api/folders", () => HttpResponse.json(folders)),
      http.post("/api/folders", async ({ request }) => {
        const { name } = (await request.json()) as { name: string };
        const created = { folder_id: "f-new", name, parent_id: null, created_at: "2026-06-12T00:00:00Z" };
        folders = [created];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    render(<Assets />, { wrapper: AuthProvider });
    await screen.findByText(/No assets uploaded/i);
    await user.click(screen.getByRole("button", { name: /New folder/i }));
    await user.type(screen.getByLabelText("Folder name"), "Invoices");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("button", { name: /^Invoices/ })).toBeInTheDocument();
  });

  it("opens the permissions dialog from a file's share action", async () => {
    server.use(
      http.get("/api/assets", () =>
        HttpResponse.json([
          {
            asset_id: "a1",
            filename: "pic.png",
            content_type: "image/png",
            size_bytes: 2048,
            created_at: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
      http.get("/api/directory", () => HttpResponse.json({})),
      http.get("/api/admin/groups", () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    render(<Assets />, { wrapper: AuthProvider });
    // Default persona is admin → every file carries a Share action.
    await user.click(await screen.findByRole("button", { name: "Share pic.png" }));
    const dialog = await screen.findByRole("dialog", { name: /Share pic\.png/ });
    expect(dialog).toBeInTheDocument();
  });

  it("opens the permissions dialog from a folder's share action", async () => {
    server.use(
      http.get("/api/assets", () => HttpResponse.json([])),
      http.get("/api/folders", () =>
        HttpResponse.json([{ folder_id: "f1", name: "Archive", parent_id: null, created_at: "2026-06-01T00:00:00Z" }]),
      ),
      http.get("/api/directory", () => HttpResponse.json({})),
      http.get("/api/admin/groups", () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    render(<Assets />, { wrapper: AuthProvider });
    await user.click(await screen.findByRole("button", { name: "Share folder Archive" }));
    expect(await screen.findByRole("dialog", { name: /Share Archive/ })).toBeInTheDocument();
  });

  it("cancels new-folder creation when the name is left blank", async () => {
    server.use(http.get("/api/assets", () => HttpResponse.json([])));
    const user = userEvent.setup();
    render(<Assets />, { wrapper: AuthProvider });
    await screen.findByText(/No assets uploaded/i);
    await user.click(screen.getByRole("button", { name: /New folder/i }));
    // Click Create with an empty input → no POST, the inline editor closes.
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("button", { name: /New folder/i })).toBeInTheDocument();
    expect(screen.queryByLabelText("Folder name")).not.toBeInTheDocument();
  });

  it("surfaces a move error", async () => {
    server.use(
      http.get("/api/assets", () =>
        HttpResponse.json([
          {
            asset_id: "a1",
            filename: "pic.png",
            content_type: "image/png",
            size_bytes: 1,
            created_at: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
      http.get("/api/folders", () =>
        HttpResponse.json([{ folder_id: "f1", name: "Archive", parent_id: null, created_at: "2026-06-01T00:00:00Z" }]),
      ),
      http.post("/api/assets/a1/move", () => new HttpResponse(null, { status: 500 })),
    );
    const user = userEvent.setup();
    render(<Assets />, { wrapper: AuthProvider });
    const select = await screen.findByRole("combobox", { name: "Move pic.png" });
    await user.selectOptions(select, "f1");
    expect(await screen.findByText(/move error 500/i)).toBeInTheDocument();
  });

  it("moves a file into a folder, hitting the move endpoint then refetching", async () => {
    let moved: unknown = null;
    server.use(
      http.get("/api/assets", () =>
        HttpResponse.json([
          {
            asset_id: "a1",
            filename: "pic.png",
            content_type: "image/png",
            size_bytes: 2048,
            created_at: "2026-06-01T00:00:00Z",
          },
        ]),
      ),
      http.get("/api/folders", () =>
        HttpResponse.json([{ folder_id: "f1", name: "Archive", parent_id: null, created_at: "2026-06-01T00:00:00Z" }]),
      ),
      http.post("/api/assets/a1/move", async ({ request }) => {
        moved = await request.json();
        return HttpResponse.json({ asset_id: "a1" });
      }),
    );
    const user = userEvent.setup();
    render(<Assets />, { wrapper: AuthProvider });
    const select = await screen.findByRole("combobox", { name: "Move pic.png" });
    await user.selectOptions(select, "f1");
    await waitFor(() => expect(moved).toEqual({ folder_id: "f1" }));
  });
});
