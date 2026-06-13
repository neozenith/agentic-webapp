import { FolderPlus, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AssetTree } from "@/components/AssetTree";
import { useAuth } from "@/components/auth";
import { PermissionsDialog, type ShareTarget } from "@/components/PermissionsDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { type Asset, createFolder, type Folder, listAssets, listFolders, moveAsset, uploadAsset } from "../api";

export function Assets() {
  const { me } = useAuth();
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [folders, setFolders] = useState<Folder[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [newFolderName, setNewFolderName] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [target, setTarget] = useState<ShareTarget | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  // Any mutation re-fetches BOTH assets and folders so the tree stays consistent.
  const refresh = () =>
    Promise.all([listAssets(), listFolders()])
      .then(([a, f]) => {
        setAssets(a);
        setFolders(f);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));

  // Mount-only load (matches the other pages' inline pattern; refresh() is reused after mutations).
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional mount-only load
  useEffect(() => {
    void refresh();
  }, []);

  async function upload(files: FileList | null) {
    if (!files || files.length === 0 || busy) return;
    setBusy(true);
    setError(null);
    try {
      // Upload sequentially; each lands in GCS via POST /api/assets (server mints the id).
      for (const file of Array.from(files)) await uploadAsset(file);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function createNewFolder() {
    const name = (newFolderName ?? "").trim();
    if (!name) {
      setNewFolderName(null);
      return;
    }
    try {
      await createFolder(name, null);
      setNewFolderName(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const shareAssetTarget = (a: Asset) => {
    setTarget({
      kind: "asset",
      id: a.asset_id,
      name: a.filename ?? a.asset_id,
      sharedUserIds: a.shared_user_ids ?? [],
      sharedGroupIds: a.shared_group_ids ?? [],
    });
    setDialogOpen(true);
  };

  const shareFolderTarget = (f: Folder) => {
    setTarget({
      kind: "folder",
      id: f.folder_id,
      name: f.name,
      sharedUserIds: f.shared_user_ids ?? [],
      sharedGroupIds: f.shared_group_ids ?? [],
    });
    setDialogOpen(true);
  };

  const move = (a: Asset, folderId: string | null) => {
    moveAsset(a.asset_id, folderId)
      .then(refresh)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!assets || !folders) return <p className="text-muted-foreground">Loading assets…</p>;

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Uploaded assets</CardTitle>
        <div className="flex items-center gap-2">
          {newFolderName === null ? (
            <Button size="sm" variant="outline" onClick={() => setNewFolderName("")}>
              <FolderPlus /> New folder
            </Button>
          ) : (
            <div className="flex items-center gap-1">
              <Input
                autoFocus
                placeholder="Folder name"
                aria-label="Folder name"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void createNewFolder();
                  } else if (e.key === "Escape") {
                    setNewFolderName(null);
                  }
                }}
                className="h-8 w-40"
              />
              <Button size="sm" onClick={() => void createNewFolder()}>
                Create
              </Button>
            </div>
          )}
          <input
            ref={fileInput}
            type="file"
            accept="image/*,application/pdf"
            multiple
            className="hidden"
            onChange={(e) => void upload(e.target.files)}
          />
          <Button size="sm" disabled={busy} onClick={() => fileInput.current?.click()}>
            <Upload /> {busy ? "Uploading…" : "Upload photo"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* biome-ignore lint/a11y/noStaticElementInteractions: drop zone wraps the tree; the button is the accessible control */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void upload(e.dataTransfer.files);
          }}
          className={cn(
            "rounded-lg border border-dashed border-transparent transition-colors",
            dragging && "border-primary bg-primary/5",
          )}
        >
          {assets.length === 0 && folders.length === 0 ? (
            <p className="p-6 text-center text-muted-foreground">
              No assets uploaded yet. Drop a photo here or use “Upload photo”.
            </p>
          ) : (
            <AssetTree
              assets={assets}
              folders={folders}
              viewerId={me?.user_id ?? null}
              isAdmin={!!me?.roles?.includes("admin")}
              onShareAsset={shareAssetTarget}
              onShareFolder={shareFolderTarget}
              onMoveAsset={move}
            />
          )}
        </div>
      </CardContent>
      <PermissionsDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        target={target}
        onSaved={() => void refresh()}
      />
    </Card>
  );
}
