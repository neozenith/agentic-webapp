import { Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AssetTree } from "@/components/AssetTree";
import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { type Asset, listAssets, shareAsset, uploadAsset } from "../api";

export function Assets() {
  const { me } = useAuth();
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = () =>
    listAssets()
      .then(setAssets)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));

  async function share(asset: Asset) {
    const email = window.prompt(`Share "${asset.filename ?? asset.asset_id}" with which email?`);
    if (!email) return;
    try {
      await shareAsset(asset.asset_id, [email]);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  // Mount-only load (matches the other pages' inline pattern; refresh() is reused after upload).
  useEffect(() => {
    listAssets()
      .then(setAssets)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
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

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!assets) return <p className="text-muted-foreground">Loading assets…</p>;

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Uploaded assets</CardTitle>
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
          {assets.length === 0 ? (
            <p className="p-6 text-center text-muted-foreground">
              No assets uploaded yet. Drop a photo here or use “Upload photo”.
            </p>
          ) : (
            <AssetTree
              assets={assets}
              viewerId={me?.user_id ?? null}
              isAdmin={!!me?.roles?.includes("admin")}
              onShare={share}
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}
