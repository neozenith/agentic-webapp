import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import type { Asset, Folder } from "../api";
import { AssetTree } from "./AssetTree";

const asset = (over: Partial<Asset>): Asset => ({
  asset_id: "id",
  filename: null,
  content_type: null,
  size_bytes: null,
  created_at: "2026-06-01T00:00:00Z",
  ...over,
});

const folder = (over: Partial<Folder>): Folder => ({
  folder_id: "f",
  name: "Folder",
  parent_id: null,
  created_at: "2026-06-01T00:00:00Z",
  ...over,
});

const FOLDERS: Folder[] = [
  folder({ folder_id: "f1", name: "Reports", owner_id: "me" }),
  folder({ folder_id: "f2", name: "Q1", parent_id: "f1" }),
];

const ASSETS: Asset[] = [
  asset({ asset_id: "a1", filename: "logo.png", content_type: "image/png", size_bytes: 2048 }), // root
  asset({ asset_id: "a2", filename: "summary.pdf", content_type: "application/pdf", folder_id: "f1" }),
  asset({ asset_id: "a3", filename: "deep.txt", content_type: "text/plain", folder_id: "f2" }),
];

const noop = () => {};

const renderTree = (over: Partial<ComponentProps<typeof AssetTree>> = {}) =>
  render(
    <AssetTree
      assets={ASSETS}
      folders={FOLDERS}
      viewerId={null}
      isAdmin={false}
      onShareAsset={noop}
      onShareFolder={noop}
      onMoveAsset={noop}
      {...over}
    />,
  );

describe("AssetTree folder tree", () => {
  it("nests folders by parent_id, files by folder_id, with recursive counts", () => {
    renderTree();
    // Root file is directly visible and links to its content.
    expect(screen.getByRole("link", { name: "logo.png" })).toHaveAttribute("href", "/api/assets/a1/content");
    // Folders expanded by default → nested files visible.
    expect(screen.getByRole("link", { name: "summary.pdf" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "deep.txt" })).toBeInTheDocument();
    // Reports counts its own file (a2) + its subfolder's file (a3) = 2.
    expect(screen.getByRole("button", { name: /^Reports/ })).toHaveTextContent("2");
    expect(screen.getByRole("button", { name: /^Q1/ })).toHaveTextContent("1");
  });

  it("collapses and expands a folder on click", async () => {
    const user = userEvent.setup();
    renderTree();
    const reports = screen.getByRole("button", { name: /^Reports/ });
    expect(reports).toHaveAttribute("aria-expanded", "true");
    await user.click(reports);
    expect(reports).toHaveAttribute("aria-expanded", "false");
    // Both the direct file and the nested folder's file disappear.
    expect(screen.queryByRole("link", { name: "summary.pdf" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "deep.txt" })).not.toBeInTheDocument();
  });

  it("moves a file via the select, to a folder and back to root", async () => {
    const user = userEvent.setup();
    const onMoveAsset = vi.fn();
    renderTree({ onMoveAsset });
    // a2 currently lives in f1 → move it to root.
    const moveA2 = screen.getByRole("combobox", { name: "Move summary.pdf" });
    await user.selectOptions(moveA2, within(moveA2).getByRole("option", { name: "— root —" }));
    expect(onMoveAsset).toHaveBeenCalledWith(expect.objectContaining({ asset_id: "a2" }), null);
    // a1 at root → move it into Reports (f1).
    const moveA1 = screen.getByRole("combobox", { name: "Move logo.png" });
    await user.selectOptions(moveA1, within(moveA1).getByRole("option", { name: "Reports" }));
    expect(onMoveAsset).toHaveBeenCalledWith(expect.objectContaining({ asset_id: "a1" }), "f1");
  });
});

describe("AssetTree ownership + sharing", () => {
  it("badges your/shared/owner and shows share actions for admins", async () => {
    const user = userEvent.setup();
    const onShareAsset = vi.fn();
    const onShareFolder = vi.fn();
    const assets: Asset[] = [
      asset({ asset_id: "mine", filename: "mine.png", content_type: "image/png", owner_id: "me" }),
      asset({ asset_id: "theirs", filename: "theirs.png", content_type: "image/png", owner_id: "other" }),
      asset({
        asset_id: "shared",
        filename: "shared.png",
        content_type: "image/png",
        owner_id: "other",
        shared_user_ids: ["me"],
      }),
    ];
    render(
      <AssetTree
        assets={assets}
        folders={FOLDERS}
        viewerId="me"
        isAdmin
        onShareAsset={onShareAsset}
        onShareFolder={onShareFolder}
        onMoveAsset={noop}
      />,
    );
    expect(screen.getByText("you")).toBeInTheDocument();
    expect(screen.getByText("shared")).toBeInTheDocument();
    expect(screen.getByText(/owner other/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Share mine.png" }));
    expect(onShareAsset).toHaveBeenCalledWith(expect.objectContaining({ asset_id: "mine" }));

    // Reports is owned by "me" → it carries a folder share action.
    await user.click(screen.getByRole("button", { name: "Share folder Reports" }));
    expect(onShareFolder).toHaveBeenCalledWith(expect.objectContaining({ folder_id: "f1" }));
  });

  it("hides owners and share controls from non-admin non-owners", () => {
    const assets: Asset[] = [
      asset({ asset_id: "x", filename: "x.png", content_type: "image/png", owner_id: "other" }),
      asset({ asset_id: "legacy", filename: "legacy.png", content_type: "image/png" }), // no owner_id
    ];
    render(
      <AssetTree
        assets={assets}
        folders={[]}
        viewerId="me"
        isAdmin={false}
        onShareAsset={noop}
        onShareFolder={noop}
        onMoveAsset={noop}
      />,
    );
    expect(screen.queryByText(/owner/)).not.toBeInTheDocument();
    expect(screen.queryByText("you")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Share/ })).not.toBeInTheDocument();
  });
});
