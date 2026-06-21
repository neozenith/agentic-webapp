import { expect, test, type TestInfo } from "@playwright/test";
import {
  type ElementBox,
  findElementsBeyondRightEdge,
  findElementsWiderThanViewport,
  findSmallTapTargets,
  hasReachableNav,
  measureHorizontalOverflow,
  settleRoute,
  type TapTarget,
} from "./helpers/mobile";

// Mobile layout suite. Runs ONLY under the "iphone-11" Playwright project
// (devices["iPhone 11"]: WebKit, 414x715 CSS viewport, screen 414x896, DPR 2,
// isMobile + hasTouch) — see playwright.config.ts. The goal is to *detect mobile
// layout failures*, not to exercise the agent, so these tests never send a chat
// turn (no LLM cost): they navigate the public Test env and measure the DOM.
//
// Each route runs every check with `expect.soft` so a single violation does not
// abort the rest — one run yields a complete report of every mobile issue on the
// page, with offender selectors attached as evidence.

const ROUTES = [
  { path: "/", name: "home" },
  { path: "/chat", name: "chat" },
  { path: "/assets", name: "assets" },
  { path: "/admin", name: "admin" },
  { path: "/semantic", name: "semantic" },
  { path: "/dbt", name: "dbt" },
  { path: "/dashboards", name: "dashboards" },
] as const;

// Sub-pixel rounding (DPR 2) can leave a fractional px; allow a tiny slack so we
// flag real overflow, not 0.5px rounding noise.
const OVERFLOW_TOLERANCE = 2;

// Tap-target thresholds encode the two WCAG conformance levels rather than a
// single arbitrary number:
//   FLOOR (24px) = WCAG 2.5.8 Target Size (Minimum), Level AA — a genuine
//                  conformance failure, so it is *asserted* (fails the suite).
//   GOAL  (44px) = WCAG 2.5.5 Target Size (Enhanced, AAA) + Apple HIG — the
//                  recommended size; every control under it is *reported* as
//                  evidence (annotation + JSON) but does not, on its own, fail a
//                  build, which would otherwise leave the suite permanently red
//                  on legitimate small icon buttons.
const TAP_TARGET_FLOOR = 24;
const TAP_TARGET_GOAL = 44;

const fmtBoxes = (boxes: ElementBox[]): string =>
  boxes.length === 0
    ? "none"
    : boxes.map((b) => `\n    • ${b.selector} (w=${b.width}, right=${b.right}, +${b.overflowBy}px)`).join("");

const fmtTargets = (targets: TapTarget[]): string =>
  targets.length === 0
    ? "none"
    : targets.map((t) => `\n    • ${t.selector} (${t.width}x${t.height}) "${t.label}"`).join("");

const attachJson = async (testInfo: TestInfo, name: string, data: unknown): Promise<void> => {
  await testInfo.attach(name, {
    body: JSON.stringify(data, null, 2),
    contentType: "application/json",
  });
};

for (const route of ROUTES) {
  test(`mobile layout is sound on ${route.name} (${route.path})`, async ({ page }, testInfo) => {
    await settleRoute(page, route.path);

    // ── Check 1: no page-level horizontal overflow ──────────────────────────
    // WHY: documentElement.scrollWidth > window.innerWidth means the page scrolls
    // sideways on a phone — the #1 mobile layout failure. When it trips, name the
    // elements reaching past the right edge so the failure is actionable.
    const overflow = await measureHorizontalOverflow(page);
    const culprits =
      overflow.overflowBy > OVERFLOW_TOLERANCE
        ? await findElementsBeyondRightEdge(page, OVERFLOW_TOLERANCE)
        : [];
    if (culprits.length > 0) await attachJson(testInfo, `${route.name}-overflow-culprits.json`, culprits);
    expect
      .soft(
        overflow.overflowBy,
        `Horizontal overflow on ${route.path}: content scrollWidth=${overflow.scrollWidth} > ` +
          `viewport=${overflow.innerWidth} (+${overflow.overflowBy}px). Likely culprits:${fmtBoxes(culprits)}`,
      )
      .toBeLessThanOrEqual(OVERFLOW_TOLERANCE);

    // ── Check 2: no element wider than the viewport ─────────────────────────
    // WHY: a box wider than the screen (hard-coded px width, unwrapped <pre>/long
    // URL, table, image without max-width:100%) physically cannot fit a phone and
    // is almost always a real bug — high signal, low false-positive.
    const tooWide = await findElementsWiderThanViewport(page, OVERFLOW_TOLERANCE);
    if (tooWide.length > 0) await attachJson(testInfo, `${route.name}-elements-too-wide.json`, tooWide);
    expect
      .soft(
        tooWide,
        `Elements wider than the ${overflow.innerWidth}px viewport on ${route.path}:${fmtBoxes(tooWide)}`,
      )
      .toEqual([]);

    // ── Check 3: tap-target size (WCAG 2.5.8 AA floor + 2.5.5 AAA goal) ──────
    // WHY: fingertips are imprecise; controls below ~44px cause mis-taps. We
    // assert the 24px AA floor and report everything under the 44px AAA/HIG goal.
    const underGoal = await findSmallTapTargets(page, TAP_TARGET_GOAL);
    const underFloor = underGoal.filter(
      (t) => t.width < TAP_TARGET_FLOOR || t.height < TAP_TARGET_FLOOR,
    );
    if (underGoal.length > 0) {
      await attachJson(testInfo, `${route.name}-tap-targets-under-44.json`, underGoal);
      testInfo.annotations.push({
        type: "tap-targets < 44px (WCAG 2.5.5 AAA / Apple HIG)",
        description: `${underGoal.length} control(s) on ${route.path} below the 44px enhanced target.`,
      });
    }
    expect
      .soft(
        underFloor,
        `Tap targets below the WCAG 2.5.8 (AA) 24px minimum on ${route.path}:${fmtTargets(underFloor)}`,
      )
      .toEqual([]);

    // ── Check 4: navigation is reachable at mobile width ────────────────────
    // WHY: a common responsive failure is the desktop sidebar going display:none
    // with no hamburger replacement, stranding the user. Accept visible route
    // links OR a visible menu/hamburger toggle as proof the app stays navigable.
    expect
      .soft(
        await hasReachableNav(page),
        `No navigation affordance (nav links or hamburger/menu toggle) is visible on ${route.path} ` +
          `at the 414px mobile width — the user may be stranded on this screen.`,
      )
      .toBe(true);

    // ── Evidence: full-page mobile screenshot (matches chat.spec.ts) ────────
    await testInfo.attach(`${route.name}-mobile.png`, {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });
  });
}

// Visual regression baselines at the mobile viewport. WHY: pixel snapshots catch
// layout regressions the structural checks above can't name in advance (a shifted
// header, an overlapping card). On the FIRST run Playwright writes the baseline
// PNGs (committed under mobile-layout.spec.ts-snapshots/) and reports them as
// "added" — review them, then subsequent runs diff against them. Animations are
// disabled and a small per-pixel diff ratio absorbs the app's live theming.
test.describe("visual snapshots @ iPhone 11", () => {
  for (const route of ROUTES) {
    test(`${route.name} matches mobile baseline`, async ({ page }) => {
      await settleRoute(page, route.path);
      await expect
        .soft(page)
        .toHaveScreenshot(`${route.name}-iphone11.png`, {
          fullPage: true,
          animations: "disabled",
          // Live theming (brandpack) + dynamic session cards shift a few pixels
          // between deploys; tolerate a small ratio so only real layout breaks fail.
          maxDiffPixelRatio: 0.1,
        });
    });
  }
});
