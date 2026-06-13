import { describe, expect, it } from "vitest";

import type { Asset } from "../api";
import { buildTree, categoryOf, displayName, fmtSize, iconFor } from "./assetTree";

const asset = (over: Partial<Asset>): Asset => ({
  asset_id: "id",
  filename: null,
  content_type: null,
  size_bytes: null,
  created_at: "2026-06-01T00:00:00Z",
  ...over,
});

describe("fmtSize", () => {
  it.each([
    [null, "—"],
    [500, "500 B"],
    [2048, "2.0 KB"],
    [5 * 1024 * 1024, "5.0 MB"],
  ])("formats %s as %s", (input, expected) => {
    expect(fmtSize(input)).toBe(expected);
  });
});

describe("displayName", () => {
  it("uses the filename leaf, the path leaf, or the id", () => {
    expect(displayName(asset({ filename: "logo.png" }))).toBe("logo.png");
    expect(displayName(asset({ filename: "a/b/c.png" }))).toBe("c.png");
    expect(displayName(asset({ asset_id: "x9", filename: null }))).toBe("x9");
  });
});

describe("categoryOf", () => {
  it.each([
    ["image/png", "Images"],
    ["audio/mpeg", "Audio/Video"],
    ["video/mp4", "Audio/Video"],
    ["application/json", "Data"],
    ["text/csv", "Data"],
    ["application/xml", "Data"],
    ["application/pdf", "Documents"],
    ["text/plain", "Documents"],
    ["application/msword", "Documents"],
    ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Documents"],
    ["application/zip", "Archives"],
    ["application/x-tar", "Archives"],
    ["application/gzip", "Archives"],
    ["application/x-rar-compressed", "Archives"],
    ["application/octet-stream", "Other"],
    [null, "Other"],
  ])("maps %s to %s", (ct, expected) => {
    expect(categoryOf(ct)).toBe(expected);
  });
});

describe("iconFor", () => {
  it.each([
    ["image/png"],
    ["video/mp4"],
    ["audio/mpeg"],
    ["application/json"],
    ["application/pdf"],
    ["application/zip"],
    ["application/octet-stream"],
    [null],
  ])("returns a renderable component for %s", (ct) => {
    expect(typeof iconFor(ct)).not.toBe("undefined");
  });
});

const SAMPLE: Asset[] = [
  asset({ asset_id: "a1", filename: "logo.png", content_type: "image/png", created_at: "2026-06-01T00:00:00Z" }),
  asset({
    asset_id: "a2",
    filename: "screenshots/home.png",
    content_type: "image/png",
    created_at: "2026-05-10T00:00:00Z",
  }),
  asset({
    asset_id: "a3",
    filename: "export.json",
    content_type: "application/json",
    created_at: "2025-12-01T00:00:00Z",
  }),
  asset({
    asset_id: "a4",
    filename: "reports/q1.pdf",
    content_type: "application/pdf",
    created_at: "2026-06-20T00:00:00Z",
  }),
];

describe("buildTree — type view", () => {
  const tree = buildTree(SAMPLE, "type");
  it("groups by category (sorted) with the right counts", () => {
    expect(tree.folders.map((f) => f.name)).toEqual(["Data", "Documents", "Images"]);
    const images = tree.folders.find((f) => f.name === "Images");
    expect(images?.count).toBe(2);
    // filename slashes nest inside the category
    expect(images?.folders.map((f) => f.name)).toEqual(["screenshots"]);
    expect(images?.files.map((a) => a.asset_id)).toEqual(["a1"]);
  });
});

describe("buildTree — folder view", () => {
  const tree = buildTree(SAMPLE, "folder");
  it("nests purely on filename slashes; slashless files sit at the root", () => {
    expect(tree.folders.map((f) => f.name)).toEqual(["reports", "screenshots"]);
    // root files sorted by display name: export.json before logo.png
    expect(tree.files.map((a) => a.asset_id)).toEqual(["a3", "a1"]);
    expect(tree.count).toBe(4);
  });
});

describe("buildTree — date view", () => {
  const tree = buildTree(SAMPLE, "date");
  it("creates year → month folders, most recent first", () => {
    expect(tree.folders.map((f) => f.name)).toEqual(["2026", "2025"]);
    const y2026 = tree.folders.find((f) => f.name === "2026");
    expect(y2026?.folders.map((f) => f.name)).toEqual(["06 June", "05 May"]);
  });
});
