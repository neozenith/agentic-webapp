import { expect, test, type Page } from "@playwright/test";

// Evidence suite for the deployed app (see playwright.config.ts for the target URL):
//   1. the chat agent answers a turn through the FastAPI -> ADK sidecar proxy,
//   2. that turn is accounted for in BigQuery and surfaced on the Admin page.
// Screenshots are attached to every test as durable evidence.

const PROMPT = "Reply with exactly the single word: pong";

/** Read the Admin "calls" summary number from its stat card (data-testid="stat-calls"). */
const readAdminCalls = async (page: Page): Promise<number> => {
  await page.goto("/admin");
  const callsText = await page.getByTestId("stat-calls").locator("span").first().textContent();
  return Number.parseInt((callsText ?? "0").trim(), 10);
};

/** Send one chat turn and return the agent's reply text. Reads the assistant bubble by
 *  testid (not the page), so the user's echoed prompt can never be mistaken for the reply. */
const sendChatTurn = async (page: Page, prompt: string): Promise<string> => {
  await page.goto("/chat");
  await page.getByPlaceholder("Type a message…").fill(prompt);
  await page.getByRole("button", { name: "Send" }).click();
  const reply = page.getByTestId("msg-assistant").last();
  await expect(reply).toBeVisible({ timeout: 120_000 });
  await expect(reply).not.toHaveText("");
  return (await reply.textContent())?.trim() ?? "";
};

test("chat agent responds to a message", async ({ page }, testInfo) => {
  const reply = await sendChatTurn(page, PROMPT);

  // The user's message and a non-empty agent reply are both on screen.
  await expect(page.getByTestId("msg-user").last()).toHaveText(PROMPT);
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

  // Real itemised usage, not just a counter: the tokens stat is a positive number too.
  await page.goto("/admin");
  const tokensText = await page.getByTestId("stat-tokens").locator("span").first().textContent();
  expect(Number.parseInt((tokensText ?? "0").replace(/\D/g, ""), 10)).toBeGreaterThan(0);

  await testInfo.attach("admin-usage.png", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
