import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Assets } from "./Assets";

describe("Assets", () => {
  it("lists uploaded assets with a content link and human-readable sizes", async () => {
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
    render(<Assets />);
    expect(await screen.findByRole("link", { name: "pic.png" })).toHaveAttribute("href", "/api/assets/a1/content");
    expect(screen.getByText("2.0 KB")).toBeInTheDocument(); // KB branch
    expect(screen.getByText("500 B")).toBeInTheDocument(); // bytes branch
  });

  it("falls back to the asset id and dashes when fields are null", async () => {
    server.use(
      http.get("/api/assets", () =>
        HttpResponse.json([
          { asset_id: "a3", filename: null, content_type: null, size_bytes: null, created_at: "2026-06-01T00:00:00Z" },
        ]),
      ),
    );
    render(<Assets />);
    expect(await screen.findByRole("link", { name: "a3" })).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0); // null type + null size
  });

  it("shows an empty state when there are no assets", async () => {
    server.use(http.get("/api/assets", () => HttpResponse.json([])));
    render(<Assets />);
    expect(await screen.findByText(/No assets uploaded/i)).toBeInTheDocument();
  });

  it("surfaces an error", async () => {
    server.use(http.get("/api/assets", () => new HttpResponse(null, { status: 500 })));
    render(<Assets />);
    expect(await screen.findByText(/assets error 500/i)).toBeInTheDocument();
  });
});
