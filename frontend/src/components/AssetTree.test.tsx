import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Asset } from "../api";
import { AssetTree } from "./AssetTree";

const asset = (over: Partial<Asset>): Asset => ({
  asset_id: "id",
  filename: null,
  content_type: null,
  size_bytes: null,
  created_at: "2026-06-01T00:00:00Z",
  ...over,
});

const ASSETS: Asset[] = [
  asset({ asset_id: "a1", filename: "logo.png", content_type: "image/png", size_bytes: 2048 }),
  asset({ asset_id: "a2", filename: "reports/q1.pdf", content_type: "application/pdf", size_bytes: 500 }),
];

describe("AssetTree ownership + sharing", () => {
  const owned: Asset[] = [
    asset({ asset_id: "mine", filename: "mine.png", content_type: "image/png", owner_id: "me" }),
    asset({ asset_id: "theirs", filename: "theirs.png", content_type: "image/png", owner_id: "other" }),
  ];

  it("badges your assets and (for admins) shows the owner of others, with a share action", async () => {
    const onShare = vi.fn();
    render(<AssetTree assets={owned} viewerId="me" isAdmin onShare={onShare} />);
    expect(screen.getByText("you")).toBeInTheDocument(); // your own asset
    expect(screen.getByText(/owner other/)).toBeInTheDocument(); // admin sees the other owner
    await userEvent.click(screen.getByRole("button", { name: /Share mine\.png/i }));
    expect(onShare).toHaveBeenCalledWith(expect.objectContaining({ asset_id: "mine" }));
  });

  it("marks shared-with-you assets and hides others' owners from non-admins", () => {
    const shared = [
      asset({ asset_id: "s", filename: "s.png", content_type: "image/png", owner_id: "other", shared_with: ["me"] }),
    ];
    render(<AssetTree assets={shared} viewerId="me" isAdmin={false} />);
    expect(screen.getByText("shared")).toBeInTheDocument();
    // non-admin, non-owner: no share button
    expect(screen.queryByRole("button", { name: /Share/i })).not.toBeInTheDocument();
  });
});

describe("AssetTree", () => {
  it("renders category folders open by default, linking files to their content", () => {
    render(<AssetTree assets={ASSETS} />);
    // Images expanded by default → its file is visible as a content link.
    const link = screen.getByRole("link", { name: "logo.png" });
    expect(link).toHaveAttribute("href", "/api/assets/a1/content");
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    // Documents folder is present with its count badge.
    expect(screen.getByRole("button", { name: /Documents/ })).toBeInTheDocument();
  });

  it("collapses and expands a folder on click", async () => {
    const user = userEvent.setup();
    render(<AssetTree assets={ASSETS} />);
    const images = screen.getByRole("button", { name: /Images/ });
    expect(images).toHaveAttribute("aria-expanded", "true");
    await user.click(images);
    expect(images).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "logo.png" })).not.toBeInTheDocument();
  });

  it("reshapes the tree when switching the group-by mode to Folder", async () => {
    const user = userEvent.setup();
    render(<AssetTree assets={ASSETS} />);
    // Type view has a category folder; Folder view does not.
    expect(screen.getByRole("button", { name: /Images/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Folder" }));
    expect(screen.queryByRole("button", { name: /Images/ })).not.toBeInTheDocument();
    // logo.png has no slash → sits at the root, directly visible.
    expect(screen.getByRole("link", { name: "logo.png" })).toBeInTheDocument();
    // reports/ is a derived folder.
    expect(screen.getByRole("button", { name: /reports/ })).toBeInTheDocument();
  });
});
