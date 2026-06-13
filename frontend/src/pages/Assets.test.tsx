import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "../components/auth";
import { server } from "../test/server";
import { Assets } from "./Assets";

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
    // Category folders are open by default, so files are visible as content links.
    expect(await screen.findByRole("link", { name: "pic.png" })).toHaveAttribute("href", "/api/assets/a1/content");
    expect(screen.getByText("2.0 KB")).toBeInTheDocument(); // KB branch
    expect(screen.getByText("500 B")).toBeInTheDocument(); // bytes branch
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
    expect(screen.getByText("—")).toBeInTheDocument(); // null size
  });

  it("shows an empty state when there are no assets", async () => {
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
    await screen.findByText(/No assets uploaded/i); // initially empty
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["png"], "receipt.png", { type: "image/png" }));
    // After the upload, the list re-fetches and the new asset appears as a content link.
    expect(await screen.findByRole("link", { name: "receipt.png" })).toHaveAttribute("href", "/api/assets/a1/content");
  });

  it("uploads a photo via drag-and-drop onto the tree", async () => {
    server.use(...statefulAssets(asset));
    const { container } = render(<Assets />, { wrapper: AuthProvider });
    await screen.findByText(/No assets uploaded/i);
    const zone = container.querySelector(".border-dashed") as HTMLElement;
    const file = new File(["png"], "receipt.png", { type: "image/png" });
    fireEvent.dragOver(zone); // sets the dragging highlight
    fireEvent.dragLeave(zone);
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(await screen.findByRole("link", { name: "receipt.png" })).toBeInTheDocument();
  });
});
