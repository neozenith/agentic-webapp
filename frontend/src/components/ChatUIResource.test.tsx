import { render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { ChatUIResource } from "./ChatUIResource";

// /ui/browse returns folder-specific HTML so we can see drill-in swap the panel.
const browseHandler = http.get("/ui/browse", ({ request }) => {
  const fid = new URL(request.url).searchParams.get("folder_id") ?? "root";
  return HttpResponse.json({
    type: "resource",
    resource: { uri: `ui://browse/${fid}`, mimeType: "text/html", text: `<h1>folder:${fid}</h1>` },
  });
});

describe("ChatUIResource", () => {
  it("renders the root panel as a sandboxed iframe", async () => {
    server.use(browseHandler);
    render(<ChatUIResource folderId={null} />);
    const frame = (await screen.findByTitle("Asset browser")) as HTMLIFrameElement;
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts");
    expect(frame.getAttribute("srcdoc")).toContain("folder:root");
  });

  it("drills into a folder when its iframe posts a browse tool action", async () => {
    server.use(browseHandler);
    render(<ChatUIResource folderId={null} />);
    const frame = (await screen.findByTitle("Asset browser")) as HTMLIFrameElement;

    // Simulate the guest clicking a folder: a postMessage from THIS iframe's window.
    const evt = new MessageEvent("message", {
      data: { type: "tool", payload: { toolName: "browse", params: { folder_id: "f1" } } },
      source: frame.contentWindow,
    });
    window.dispatchEvent(evt);

    await waitFor(() => expect(frame.getAttribute("srcdoc")).toContain("folder:f1"));
  });

  it("ignores messages that do not come from its own iframe", async () => {
    server.use(browseHandler);
    render(<ChatUIResource folderId={null} />);
    const frame = (await screen.findByTitle("Asset browser")) as HTMLIFrameElement;

    // A message with no/foreign source must not trigger a drill (panel stays at root).
    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "tool", payload: { toolName: "browse", params: { folder_id: "evil" } } },
        source: null,
      }),
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(frame.getAttribute("srcdoc")).toContain("folder:root");
  });

  it("shows an error when the panel fails to load", async () => {
    server.use(http.get("/ui/browse", () => new HttpResponse(null, { status: 500 })));
    render(<ChatUIResource folderId={null} />);
    expect(await screen.findByText(/browse: browse ui error 500/i)).toBeInTheDocument();
  });
});
