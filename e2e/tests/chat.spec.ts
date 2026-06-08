import { expect, test, type Page } from "@playwright/test";

// Evidence suite for the deployed app (see playwright.config.ts for the target URL):
//   1. the chat agent answers a turn through the FastAPI -> ADK sidecar proxy,
//   2. that turn is accounted for in BigQuery and surfaced on the Admin page.
// Screenshots are attached to every test as durable evidence.

const PROMPT = "Reply with exactly the single word: pong";

/** Read the three Admin summary numbers (calls, tokens) from the .stats card. */
const readAdminCalls = async (page: Page): Promise<number> => {
  await page.goto("/admin");
  const callsText = await page.locator(".stats .big").first().textContent();
  return Number.parseInt((callsText ?? "0").trim(), 10);
};

/** Send one chat turn and return the agent's reply text (skips the "…thinking" bubble). */
const sendChatTurn = async (page: Page, prompt: string): Promise<string> => {
  await page.goto("/chat");
  await page.locator(".composer input").fill(prompt);
  await page.getByRole("button", { name: "Send" }).click();
  const reply = page.locator(".msg.assistant .bubble:not(.muted)").last();
  await expect(reply).toBeVisible();
  await expect(reply).not.toHaveText("");
  return (await reply.textContent())?.trim() ?? "";
};

test("chat agent responds to a message", async ({ page }, testInfo) => {
  const reply = await sendChatTurn(page, PROMPT);

  // The user's message and a non-empty agent reply are both on screen.
  await expect(page.locator(".msg.user .bubble")).toHaveText(PROMPT);
  expect(reply.length).toBeGreaterThan(0);

  await testInfo.attach("chat-conversation.png", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});

test("agent usage is accounted into BigQuery and shown on Admin", async ({ page }, testInfo) => {
  const before = await readAdminCalls(page);

  await sendChatTurn(page, PROMPT);

  // The Admin page reads BigQuery, whose streaming inserts are eventually
  // consistent — poll (reloading /admin) until the call count rises.
  await expect
    .poll(async () => readAdminCalls(page), {
      message: "Admin call count should increase after a chat turn",
      timeout: 90_000,
      intervals: [2_000, 3_000, 5_000],
    })
    .toBeGreaterThan(before);

  // The cheapest model is the one billed, and the by-model table proves itemisation.
  await page.goto("/admin");
  await expect(page.getByText("gemini-2.5-flash-lite")).toBeVisible();

  await testInfo.attach("admin-usage.png", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
