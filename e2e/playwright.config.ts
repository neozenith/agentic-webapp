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
  projects: [
    {
      // Desktop evidence suite (chat.spec.ts). Excludes the mobile spec so the
      // agent/cost tests don't run twice.
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /mobile-layout\.spec\.ts/,
    },
    {
      // Mobile layout suite (mobile-layout.spec.ts only). iPhone 11 descriptor =
      // WebKit, 414x715 CSS viewport (screen 414x896), DPR 2, isMobile + hasTouch.
      name: "iphone-11",
      use: { ...devices["iPhone 11"] },
      testMatch: /mobile-layout\.spec\.ts/,
    },
  ],
});
