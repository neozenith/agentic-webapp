import { useEffect, useRef, useState } from "react";

import { type BrowseRef, browseUi } from "../api";

/** Inline interactive MCP-UI browse panel for the web chat (ADR-0012).
 *
 * Renders the server's HTML in a sandboxed iframe (no `allow-same-origin`, so the panel is
 * isolated and can only talk back via postMessage). The drill-in contract: when the user
 * clicks a folder, the guest posts `{type:"tool", payload:{toolName:"browse", params:{folder_id}}}`,
 * which we fulfil by fetching /ui/browse directly — deterministic folder navigation that
 * doesn't cost an agent turn. Messages are matched to THIS panel's iframe via `event.source`
 * so multiple panels in one transcript don't cross-talk. */
export function ChatUIResource({ folderId: initialFolderId }: BrowseRef) {
  const [folderId, setFolderId] = useState<string | null>(initialFolderId);
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [height, setHeight] = useState(320);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Fetch (and re-fetch on drill-in) the panel HTML for the current folder.
  useEffect(() => {
    let active = true;
    setError(null);
    browseUi(folderId)
      .then((r) => active && setHtml(r.html))
      .catch((e) => active && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      active = false;
    };
  }, [folderId]);

  // Handle drill-in + size messages from THIS panel's iframe only.
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.source !== iframeRef.current?.contentWindow) return;
      const data = e.data as {
        type?: string;
        height?: number;
        payload?: { toolName?: string; params?: { folder_id?: unknown } };
      };
      if (data?.type === "tool" && data.payload?.toolName === "browse") {
        const fid = data.payload.params?.folder_id;
        setFolderId(typeof fid === "string" ? fid : null);
      } else if (data?.type === "ui-size" && typeof data.height === "number") {
        setHeight(Math.min(640, Math.max(120, data.height + 8)));
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  if (error) return <div className="text-sm text-destructive">⚠️ browse: {error}</div>;
  if (html === null) return <div className="text-sm text-muted-foreground">Loading browser…</div>;
  return (
    <iframe
      ref={iframeRef}
      title="Asset browser"
      sandbox="allow-scripts"
      srcDoc={html}
      className="w-full max-w-[680px] rounded-lg border border-border bg-white"
      style={{ height }}
    />
  );
}
