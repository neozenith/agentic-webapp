import { defineConfig, devices } from "@playwright/test";

// Target the deployed Test environment by default (no IAP). Override with BASE_URL
// to point at another env. Prod is IAP-locked to a single human account, so it is
// verified manually rather than by this suite (decision recorded with the user).
const BASE_URL = process.env.BASE_URL ?? "https://agentic-webapp-qfe3o66q6q-ts.a.run.app";

export default defineConfig({
  testDir: "./tests",
  // Cloud Run scales from zero and the agent calls a real LLM — be patient.
  timeout: 180_000,
  expect: { timeout: 45_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    baseURL: BASE_URL,
    screenshot: "on",
    trace: "on",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
