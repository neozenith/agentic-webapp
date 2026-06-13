import { ChevronRight, Folder as FolderIcon, FolderOpen, Share2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { displayName, fmtSize, iconFor } from "@/lib/assetTree";
import { cn } from "@/lib/utils";
import type { Asset, Folder } from "../api";

const INDENT = 16; // px per depth level
const fmtDate = (iso: string): string => new Date(iso).toLocaleDateString();

/** Everything the recursive rows need, bundled so module-level row components stay
 * stable (defining components inline would remount the tree on every render). */
interface TreeCtx {
  viewerId: string | null;
  isAdmin: boolean;
  foldersByParent: Map<string | null, Folder[]>;
  assetsByFolder: Map<string | null, Asset[]>;
  folderOptions: Folder[];
  open: Set<string>;
  toggle: (id: string) => void;
  countFor: (folderId: string) => number;
  onShareAsset: (a: Asset) => void;
  onShareFolder: (f: Folder) => void;
  onMoveAsset: (a: Asset, folderId: string | null) => void;
}

function OwnerBadge({ asset, ctx }: { asset: Asset; ctx: TreeCtx }) {
  if (!asset.owner_id) return null; // legacy/unowned
  if (asset.owner_id === ctx.viewerId) return <Badge variant="outline">you</Badge>;
  if (ctx.viewerId && asset.shared_user_ids?.includes(ctx.viewerId)) return <Badge variant="muted">shared</Badge>;
  // Admin viewing someone else's asset: surface the (pseudonymous) owner.
  if (ctx.isAdmin) return <Badge variant="muted">owner {asset.owner_id.slice(0, 8)}…</Badge>;
  return null;
}

function FileRow({ asset, depth, ctx }: { asset: Asset; depth: number; ctx: TreeCtx }) {
  const Icon = iconFor(asset.content_type);
  const canShare = ctx.isAdmin || (!!asset.owner_id && asset.owner_id === ctx.viewerId);
  const name = displayName(asset);
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
        {name}
      </a>
      <OwnerBadge asset={asset} ctx={ctx} />
      <select
        aria-label={`Move ${name}`}
        value={asset.folder_id ?? ""}
        onChange={(e) => ctx.onMoveAsset(asset, e.target.value === "" ? null : e.target.value)}
        className="ml-1 h-6 rounded-md border border-border bg-transparent px-1 text-xs text-muted-foreground"
      >
        <option value="">— root —</option>
        {ctx.folderOptions.map((f) => (
          <option key={f.folder_id} value={f.folder_id}>
            {f.name}
          </option>
        ))}
      </select>
      {canShare && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-6"
          aria-label={`Share ${name}`}
          onClick={() => ctx.onShareAsset(asset)}
        >
          <Share2 className="size-3.5" />
        </Button>
      )}
      <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">{fmtSize(asset.size_bytes)}</span>
      <span className="hidden shrink-0 text-xs text-muted-foreground tabular-nums sm:inline">
        {fmtDate(asset.created_at)}
      </span>
    </div>
  );
}

function FolderRow({ folder, depth, ctx }: { folder: Folder; depth: number; ctx: TreeCtx }) {
  const isOpen = ctx.open.has(folder.folder_id);
  const Icon = isOpen ? FolderOpen : FolderIcon;
  const childFolders = ctx.foldersByParent.get(folder.folder_id) ?? [];
  const childFiles = ctx.assetsByFolder.get(folder.folder_id) ?? [];
  const canShare = ctx.isAdmin || (!!folder.owner_id && folder.owner_id === ctx.viewerId);
  return (
    <div>
      <div
        className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/60"
        style={{ paddingLeft: depth * INDENT + 8 }}
      >
        <button
          type="button"
          onClick={() => ctx.toggle(folder.folder_id)}
          aria-expanded={isOpen}
          className="flex flex-1 items-center gap-2 text-left"
        >
          <ChevronRight
            className={cn("size-4 shrink-0 text-muted-foreground transition-transform", isOpen && "rotate-90")}
            aria-hidden
          />
          <Icon className="size-4 shrink-0 text-primary" aria-hidden />
          <span className="truncate font-medium">{folder.name}</span>
          <Badge variant="muted" className="shrink-0">
            {ctx.countFor(folder.folder_id)}
          </Badge>
        </button>
        {canShare && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-6"
            aria-label={`Share folder ${folder.name}`}
            onClick={() => ctx.onShareFolder(folder)}
          >
            <Share2 className="size-3.5" />
          </Button>
        )}
      </div>
      {isOpen && (
        <div className="flex flex-col">
          {childFolders.map((f) => (
            <FolderRow key={f.folder_id} folder={f} depth={depth + 1} ctx={ctx} />
          ))}
          {childFiles.map((a) => (
            <FileRow key={a.asset_id} asset={a} depth={depth + 1} ctx={ctx} />
          ))}
        </div>
      )}
    </div>
  );
}

export function AssetTree({
  assets,
  folders,
  viewerId,
  isAdmin,
  onShareAsset,
  onShareFolder,
  onMoveAsset,
}: {
  assets: Asset[];
  folders: Folder[];
  viewerId: string | null;
  isAdmin: boolean;
  onShareAsset: (a: Asset) => void;
  onShareFolder: (f: Folder) => void;
  onMoveAsset: (a: Asset, folderId: string | null) => void;
}) {
  const foldersByParent = useMemo(() => {
    const map = new Map<string | null, Folder[]>();
    for (const f of folders) {
      const key = f.parent_id ?? null;
      const arr = map.get(key);
      if (arr) arr.push(f);
      else map.set(key, [f]);
    }
    for (const arr of map.values()) arr.sort((a, b) => a.name.localeCompare(b.name));
    return map;
  }, [folders]);

  const assetsByFolder = useMemo(() => {
    const map = new Map<string | null, Asset[]>();
    for (const a of assets) {
      const key = a.folder_id ?? null;
      const arr = map.get(key);
      if (arr) arr.push(a);
      else map.set(key, [a]);
    }
    for (const arr of map.values()) arr.sort((a, b) => displayName(a).localeCompare(displayName(b)));
    return map;
  }, [assets]);

  const folderOptions = useMemo(() => [...folders].sort((a, b) => a.name.localeCompare(b.name)), [folders]);

  const countFor = useMemo(() => {
    const fn = (folderId: string): number => {
      const direct = (assetsByFolder.get(folderId) ?? []).length;
      const kids = (foldersByParent.get(folderId) ?? []).reduce((s, f) => s + fn(f.folder_id), 0);
      return direct + kids;
    };
    return fn;
  }, [assetsByFolder, foldersByParent]);

  // Default every folder expanded so nested files are visible; re-default whenever the
  // folder set changes (e.g. after creating a folder or moving a file).
  const [open, setOpen] = useState<Set<string>>(new Set());
  useEffect(() => {
    setOpen(new Set(folders.map((f) => f.folder_id)));
  }, [folders]);

  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const ctx: TreeCtx = {
    viewerId,
    isAdmin,
    foldersByParent,
    assetsByFolder,
    folderOptions,
    open,
    toggle,
    countFor,
    onShareAsset,
    onShareFolder,
    onMoveAsset,
  };

  const rootFolders = foldersByParent.get(null) ?? [];
  const rootFiles = assetsByFolder.get(null) ?? [];

  return (
    <div className="rounded-lg border border-border bg-card/40 p-1.5">
      <div className="flex flex-col">
        {rootFolders.map((f) => (
          <FolderRow key={f.folder_id} folder={f} depth={0} ctx={ctx} />
        ))}
        {rootFiles.map((a) => (
          <FileRow key={a.asset_id} asset={a} depth={0} ctx={ctx} />
        ))}
      </div>
    </div>
  );
}
