import { expect, test } from "@playwright/test";

// Evidence that the MCP-UI browse panel (ADR-0012) renders INLINE in the deployed web chat
// and that drill-in works: the agent calls the `browse` tool, the SPA mounts the returned
// folder/asset UI as a sandboxed iframe, and clicking a folder re-renders it (no agent turn).
// Screenshots are attached as durable evidence.
//
// Self-seeding: the test creates its own parent/child folder pair for the `ada.admin` persona
// (set in localStorage, the key api.ts reads), so it depends on no pre-existing data and runs
// against any deployed env. The child is only visible AFTER drilling into the parent — an
// unambiguous proof the panel actually re-rendered.

const PERSONA = "ada.admin@example.com";
const PROMPT = "Open the file browser so I can see my folders and assets.";
const SUFFIX = Date.now().toString(36);
const PARENT = `e2e-Browse-${SUFFIX}`;
const CHILD = `e2e-Child-${SUFFIX}`;

test.beforeEach(async ({ page }) => {
  await page.addInitScript((email) => localStorage.setItem("persona-email", email), PERSONA);
});

test("agent renders the MCP-UI browse panel inline, with working drill-in", async ({ page, request }, testInfo) => {
  // Seed a parent → child folder pair as the persona (same identity header the SPA sends).
  const headers = { "X-Goog-Authenticated-User-Email": PERSONA };
  const parentResp = await request.post("/api/folders", { headers, data: { name: PARENT } });
  expect(parentResp.ok()).toBeTruthy();
  const parentId = (await parentResp.json()).folder_id as string;
  const childResp = await request.post("/api/folders", { headers, data: { name: CHILD, parent_id: parentId } });
  expect(childResp.ok()).toBeTruthy();

  await page.goto("/chat");
  await page.getByPlaceholder("Type a message…").fill(PROMPT);
  await page.getByRole("button", { name: "Send" }).click();

  // The panel mounts as a sandboxed iframe titled "Asset browser" once the agent calls
  // `browse`. Cold start + a real LLM turn → be patient.
  const panel = page.locator('iframe[title="Asset browser"]').last();
  await expect(panel).toBeVisible({ timeout: 150_000 });
  await expect(panel).toHaveAttribute("sandbox", "allow-scripts");

  const frame = page.frameLocator('iframe[title="Asset browser"]');
  await expect(frame.getByRole("button", { name: PARENT })).toBeVisible({ timeout: 30_000 });
  await expect(frame.getByRole("button", { name: CHILD })).toBeHidden(); // nested — not at root

  await testInfo.attach("mcpui-browse-panel.png", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });

  // Drill into the parent: the child folder appears (deterministic re-render via /ui/browse).
  await frame.getByRole("button", { name: PARENT }).click();
  await expect(frame.getByRole("button", { name: CHILD })).toBeVisible({ timeout: 30_000 });

  await testInfo.attach("mcpui-browse-drilled-in.png", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
