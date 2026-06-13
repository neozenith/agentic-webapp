import { ChevronRight, Folder, FolderOpen } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buildTree, displayName, fmtSize, iconFor, type TreeNode, type ViewMode } from "@/lib/assetTree";
import { cn } from "@/lib/utils";
import type { Asset } from "../api";

const MODES: { value: ViewMode; label: string }[] = [
  { value: "type", label: "Type" },
  { value: "folder", label: "Folder" },
  { value: "date", label: "Date" },
];

const INDENT = 16; // px per depth level
const fmtDate = (iso: string): string => new Date(iso).toLocaleDateString();

function FileRow({ asset, depth }: { asset: Asset; depth: number }) {
  const Icon = iconFor(asset.content_type);
  return (
    <div
      className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/60"
      style={{ paddingLeft: depth * INDENT + 8 }}
    >
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <a
        href={`/api/assets/${asset.asset_id}/content`}
        target="_blank"
        rel="noreferrer"
        className="truncate text-secondary-foreground hover:underline"
      >
        {displayName(asset)}
      </a>
      <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">{fmtSize(asset.size_bytes)}</span>
      <span className="hidden shrink-0 text-xs text-muted-foreground tabular-nums sm:inline">
        {fmtDate(asset.created_at)}
      </span>
    </div>
  );
}

function FolderRow({
  node,
  depth,
  open,
  toggle,
}: {
  node: TreeNode;
  depth: number;
  open: Set<string>;
  toggle: (path: string) => void;
}) {
  const isOpen = open.has(node.path);
  const FolderIcon = isOpen ? FolderOpen : Folder;
  return (
    <div>
      <button
        type="button"
        onClick={() => toggle(node.path)}
        aria-expanded={isOpen}
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/60"
        style={{ paddingLeft: depth * INDENT + 8 }}
      >
        <ChevronRight
          className={cn("size-4 shrink-0 text-muted-foreground transition-transform", isOpen && "rotate-90")}
          aria-hidden
        />
        <FolderIcon className="size-4 shrink-0 text-primary" aria-hidden />
        <span className="truncate font-medium">{node.name}</span>
        <Badge variant="muted" className="ml-auto shrink-0">
          {node.count}
        </Badge>
      </button>
      {isOpen && <TreeLevel folders={node.folders} files={node.files} depth={depth + 1} open={open} toggle={toggle} />}
    </div>
  );
}

function TreeLevel({
  folders,
  files,
  depth,
  open,
  toggle,
}: {
  folders: TreeNode[];
  files: Asset[];
  depth: number;
  open: Set<string>;
  toggle: (path: string) => void;
}) {
  return (
    <div className="flex flex-col">
      {folders.map((f) => (
        <FolderRow key={f.path} node={f} depth={depth} open={open} toggle={toggle} />
      ))}
      {files.map((a) => (
        <FileRow key={a.asset_id} asset={a} depth={depth} />
      ))}
    </div>
  );
}

export function AssetTree({ assets }: { assets: Asset[] }) {
  const [mode, setMode] = useState<ViewMode>("type");
  const tree = useMemo(() => buildTree(assets, mode), [assets, mode]);
  const [open, setOpen] = useState<Set<string>>(new Set());

  // Default to top-level folders expanded; re-default whenever the grouping (and thus
  // the folder set) changes so a fresh view never opens fully collapsed.
  useEffect(() => {
    setOpen(new Set(tree.folders.map((f) => f.path)));
  }, [tree]);

  const toggle = (path: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Group by</span>
        <div className="inline-flex gap-1 rounded-lg border border-border p-1">
          {MODES.map((m) => (
            <Button
              key={m.value}
              type="button"
              size="sm"
              variant={mode === m.value ? "secondary" : "ghost"}
              aria-pressed={mode === m.value}
              onClick={() => setMode(m.value)}
            >
              {m.label}
            </Button>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-border bg-card/40 p-1.5">
        <TreeLevel folders={tree.folders} files={tree.files} depth={0} open={open} toggle={toggle} />
      </div>
    </div>
  );
}
