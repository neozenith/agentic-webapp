import {
  Archive,
  File as FileIcon,
  FileJson,
  FileText,
  Image as ImageIcon,
  type LucideIcon,
  Music,
  Video,
} from "lucide-react";

import type { Asset } from "../api";

// NOTE: this module is pure (no React, no DOM) so the grouping logic is trivially
// unit-testable across all three view modes — see assetTree.test.ts.

export type ViewMode = "type" | "folder" | "date";

/** A derived folder. `path` is a stable id used as the expand/collapse key. */
export interface TreeNode {
  name: string;
  path: string;
  count: number; // total files at and below this folder (recursive)
  folders: TreeNode[];
  files: Asset[]; // files directly in this folder
}

export interface Tree {
  folders: TreeNode[];
  files: Asset[]; // files at the root (no derived folder)
  count: number;
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** Human-readable byte size. `—` for unknown. */
export const fmtSize = (n: number | null): string => {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
};

/** What the asset is called in the tree (filename's leaf, falling back to the id). */
export const displayName = (asset: Asset): string => {
  if (!asset.filename) return asset.asset_id;
  const parts = asset.filename.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? asset.asset_id;
};

/** Broad category bucket from a MIME type — the top level of the "type" view. */
export const categoryOf = (contentType: string | null): string => {
  const ct = (contentType ?? "").toLowerCase();
  if (ct.startsWith("image/")) return "Images";
  if (ct.startsWith("audio/") || ct.startsWith("video/")) return "Audio/Video";
  // Office docs (e.g. .docx = openXMLformats) must match before the xml/data check.
  if (ct.includes("word") || ct.includes("document")) return "Documents";
  if (ct.includes("json") || ct.includes("csv") || ct.includes("xml")) return "Data";
  if (ct === "application/pdf" || ct.startsWith("text/")) return "Documents";
  if (
    ct.includes("zip") ||
    ct.includes("tar") ||
    ct.includes("gzip") ||
    ct.includes("compress") ||
    ct.includes("rar")
  ) {
    return "Archives";
  }
  return "Other";
};

/** The lucide icon that best represents an asset's MIME type. */
export const iconFor = (contentType: string | null): LucideIcon => {
  const ct = (contentType ?? "").toLowerCase();
  if (ct.startsWith("image/")) return ImageIcon;
  if (ct.startsWith("video/")) return Video;
  if (ct.startsWith("audio/")) return Music;
  // Office docs (e.g. .docx = openXMLformats) must match before the xml/data check.
  if (ct.includes("word") || ct.includes("document")) return FileText;
  if (ct.includes("json") || ct.includes("csv") || ct.includes("xml")) return FileJson;
  if (ct === "application/pdf" || ct.startsWith("text/")) return FileText;
  if (
    ct.includes("zip") ||
    ct.includes("tar") ||
    ct.includes("gzip") ||
    ct.includes("compress") ||
    ct.includes("rar")
  ) {
    return Archive;
  }
  return FileIcon;
};

/** Leading directory segments of a filename (everything before the leaf). */
const dirSegments = (filename: string | null): string[] => {
  if (!filename) return [];
  return filename.split("/").filter(Boolean).slice(0, -1);
};

/** Year + zero-padded "MM Month" segments parsed straight from the ISO date string
 * (substring, not Date, so it's timezone-independent and deterministic in tests). */
const dateSegments = (createdAt: string): string[] => {
  const year = createdAt.slice(0, 4);
  const mm = createdAt.slice(5, 7);
  const monthName = MONTHS[Number(mm) - 1] ?? mm;
  return [year, `${mm} ${monthName}`];
};

/** The folder segments an asset lives under for a given view mode. */
const segmentsFor = (asset: Asset, mode: ViewMode): string[] => {
  if (mode === "folder") return dirSegments(asset.filename);
  if (mode === "date") return dateSegments(asset.created_at);
  // type: category, then any nested path embedded in the filename.
  return [categoryOf(asset.content_type), ...dirSegments(asset.filename)];
};

interface MutableNode {
  name: string;
  path: string;
  folderMap: Map<string, MutableNode>;
  files: Asset[];
}

const newNode = (name: string, path: string): MutableNode => ({ name, path, folderMap: new Map(), files: [] });

/** Recursively total the files at and below a node. */
const countOf = (node: MutableNode): number =>
  node.files.length + [...node.folderMap.values()].reduce((sum, c) => sum + countOf(c), 0);

/** Finalise a mutable node into the immutable, sorted public shape. Folders sort
 * descending for the date view (recent first) and ascending otherwise; files sort
 * by display name. */
const finalize = (node: MutableNode, mode: ViewMode): TreeNode => {
  const folders = [...node.folderMap.values()]
    .map((c) => finalize(c, mode))
    .sort((a, b) => (mode === "date" ? b.name.localeCompare(a.name) : a.name.localeCompare(b.name)));
  const files = [...node.files].sort((a, b) => displayName(a).localeCompare(displayName(b)));
  return { name: node.name, path: node.path, count: countOf(node), folders, files };
};

/** Build the derived folder tree for the chosen view mode. */
export const buildTree = (assets: Asset[], mode: ViewMode): Tree => {
  const root = newNode("", "");
  for (const asset of assets) {
    let node = root;
    let path = "";
    for (const seg of segmentsFor(asset, mode)) {
      path = path ? `${path}/${seg}` : seg;
      let child = node.folderMap.get(seg);
      if (!child) {
        child = newNode(seg, path);
        node.folderMap.set(seg, child);
      }
      node = child;
    }
    node.files.push(asset);
  }
  const finalized = finalize(root, mode);
  return { folders: finalized.folders, files: finalized.files, count: finalized.count };
};
