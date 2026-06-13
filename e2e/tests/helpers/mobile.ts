import type { Page } from "@playwright/test";

// Reusable in-page scans for detecting mobile layout failures. Each function runs
// a single page.evaluate() so the DOM measurements happen in one frame (no
// round-trips per element) and the spec stays readable: the spec asserts, these
// helpers measure. The WHY of each check is documented at its call site and below.

/** Page-level horizontal overflow — the classic mobile bug. */
export interface OverflowReport {
  /** Widest scrollable content width of the document. */
  scrollWidth: number;
  /** The mobile viewport's CSS width (no scrollbar on mobile webkit). */
  innerWidth: number;
  /** scrollWidth - innerWidth; > tolerance means the user can scroll sideways. */
  overflowBy: number;
}

/** One offending element, with a best-effort CSS selector for triage. */
export interface ElementBox {
  selector: string;
  /** getBoundingClientRect().right (px from the left of the viewport). */
  right: number;
  /** getBoundingClientRect().width. */
  width: number;
  /** How far past the right viewport edge this element reaches (right - innerWidth). */
  overflowBy: number;
}

export interface TapTarget {
  selector: string;
  width: number;
  height: number;
  /** Trimmed, truncated accessible-ish label to make the report human-readable. */
  label: string;
}

/**
 * Measure document-level horizontal overflow.
 *
 * WHY: On a phone the layout viewport width === window.innerWidth (there is no
 * desktop scrollbar to subtract). If documentElement.scrollWidth exceeds that,
 * the page scrolls sideways — the single most common and most jarring mobile
 * layout failure (off-screen content, a fixed-width element, an image or table
 * that won't shrink). Comparing scrollWidth vs innerWidth is the canonical
 * detection (see Playwright responsive-testing guidance).
 */
export const measureHorizontalOverflow = (page: Page): Promise<OverflowReport> =>
  page.evaluate(() => {
    const innerWidth = window.innerWidth;
    const scrollWidth = Math.max(
      document.documentElement.scrollWidth,
      document.body?.scrollWidth ?? 0,
    );
    return { scrollWidth, innerWidth, overflowBy: scrollWidth - innerWidth };
  });

// Builds a short, stable-ish CSS selector for an element so a failure report
// points at *which* node overflowed, not just "something did". Defined as a
// string and injected so it is available inside the page context.
const CSS_PATH_FN = `
function cssPath(el) {
  if (el.id) return el.tagName.toLowerCase() + '#' + el.id;
  const cls = (el.getAttribute('class') || '')
    .trim().split(/\\s+/).filter(Boolean).slice(0, 3).join('.');
  let sel = el.tagName.toLowerCase() + (cls ? '.' + cls : '');
  const parent = el.parentElement;
  if (parent && parent !== document.body && parent !== document.documentElement) {
    const pcls = (parent.getAttribute('class') || '')
      .trim().split(/\\s+/).filter(Boolean).slice(0, 2).join('.');
    sel = parent.tagName.toLowerCase() + (pcls ? '.' + pcls : '') + ' > ' + sel;
  }
  return sel;
}
`;

const VISIBLE_FN = `
function isVisible(el) {
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return false;
  const s = getComputedStyle(el);
  if (s.visibility === 'hidden' || s.display === 'none' || s.opacity === '0') return false;
  return true;
}
`;

/**
 * Find visible elements that are themselves WIDER than the viewport.
 *
 * WHY: An element whose own border-box is wider than the screen is almost always
 * a genuine bug — a hard-coded `width: 600px`, an unwrapped <pre>/<code> or long
 * URL, a table, or an image missing `max-width: 100%`. Unlike a raw "right edge
 * past the viewport" scan (which false-positives on legitimately off-canvas
 * drawers), `rect.width > innerWidth` is a high-signal, low-false-positive check
 * for content that physically cannot fit the phone.
 */
export const findElementsWiderThanViewport = (page: Page, tolerance = 1): Promise<ElementBox[]> =>
  page.evaluate(
    ({ tol, cssPathSrc, visibleSrc }) => {
      eval(cssPathSrc);
      eval(visibleSrc);
      const vw = window.innerWidth;
      const out: ElementBox[] = [];
      for (const el of Array.from(document.querySelectorAll<HTMLElement>("*"))) {
        if (el === document.body || el === document.documentElement) continue;
        // @ts-expect-error injected via eval
        if (!isVisible(el)) continue;
        const r = el.getBoundingClientRect();
        if (r.width > vw + tol) {
          out.push({
            // @ts-expect-error injected via eval
            selector: cssPath(el),
            right: Math.round(r.right),
            width: Math.round(r.width),
            overflowBy: Math.round(r.width - vw),
          });
        }
      }
      // Dedupe by selector, widest first, cap the report.
      const seen = new Set<string>();
      return out
        .sort((a, b) => b.overflowBy - a.overflowBy)
        .filter((e) => (seen.has(e.selector) ? false : (seen.add(e.selector), true)))
        .slice(0, 20);
    },
    { tol: tolerance, cssPathSrc: CSS_PATH_FN, visibleSrc: VISIBLE_FN },
  );

/**
 * Find visible elements whose right edge extends past the viewport.
 *
 * WHY: Used to *explain* a page-level overflow failure (name the culprits that
 * push the scroll width out). Reported as diagnostic context, not asserted on
 * directly, because off-canvas menu drawers legitimately sit past the right edge.
 */
export const findElementsBeyondRightEdge = (page: Page, tolerance = 1): Promise<ElementBox[]> =>
  page.evaluate(
    ({ tol, cssPathSrc, visibleSrc }) => {
      eval(cssPathSrc);
      eval(visibleSrc);
      const vw = window.innerWidth;
      const out: ElementBox[] = [];
      for (const el of Array.from(document.querySelectorAll<HTMLElement>("*"))) {
        if (el === document.body || el === document.documentElement) continue;
        // @ts-expect-error injected via eval
        if (!isVisible(el)) continue;
        const r = el.getBoundingClientRect();
        if (r.right > vw + tol) {
          out.push({
            // @ts-expect-error injected via eval
            selector: cssPath(el),
            right: Math.round(r.right),
            width: Math.round(r.width),
            overflowBy: Math.round(r.right - vw),
          });
        }
      }
      const seen = new Set<string>();
      return out
        .sort((a, b) => b.overflowBy - a.overflowBy)
        .filter((e) => (seen.has(e.selector) ? false : (seen.add(e.selector), true)))
        .slice(0, 20);
    },
    { tol: tolerance, cssPathSrc: CSS_PATH_FN, visibleSrc: VISIBLE_FN },
  );

/**
 * Find interactive controls smaller than `minPx` square.
 *
 * WHY: Fingertips are imprecise. WCAG 2.5.8 Target Size (Minimum, Level AA)
 * requires >= 24x24 CSS px; WCAG 2.5.5 (Enhanced, AAA) and Apple's HIG both call
 * for >= 44x44. Controls below the bar cause mis-taps on a phone. We apply the
 * standard's documented exceptions so the check is principled, not noisy:
 *   - inline links inside running text are exempt (WCAG "inline" exception);
 *   - hidden/zero-size controls are skipped.
 */
export const findSmallTapTargets = (page: Page, minPx = 44): Promise<TapTarget[]> =>
  page.evaluate(
    ({ min, cssPathSrc, visibleSrc }) => {
      eval(cssPathSrc);
      eval(visibleSrc);
      const SELECTOR = [
        "a[href]",
        "button",
        "input:not([type=hidden])",
        "select",
        "textarea",
        '[role="button"]',
        '[role="link"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[role="switch"]',
        '[role="checkbox"]',
        "[onclick]",
      ].join(",");

      const isInlineTextLink = (el: HTMLElement): boolean => {
        if (el.tagName !== "A") return false;
        if (getComputedStyle(el).display !== "inline") return false;
        // Sits inside a text-bearing block (paragraph, list item, etc.).
        const parentText = (el.parentElement?.textContent ?? "").trim();
        const ownText = (el.textContent ?? "").trim();
        return parentText.length > ownText.length;
      };

      const out: TapTarget[] = [];
      const seen = new Set<string>();
      for (const el of Array.from(document.querySelectorAll<HTMLElement>(SELECTOR))) {
        // @ts-expect-error injected via eval
        if (!isVisible(el)) continue;
        if ((el as HTMLButtonElement).disabled) continue;
        if (isInlineTextLink(el)) continue;
        const r = el.getBoundingClientRect();
        if (r.width < min || r.height < min) {
          // @ts-expect-error injected via eval
          const selector = cssPath(el);
          if (seen.has(selector)) continue;
          seen.add(selector);
          const label =
            (el.getAttribute("aria-label") || el.textContent || el.getAttribute("title") || "")
              .trim()
              .replace(/\s+/g, " ")
              .slice(0, 40);
          out.push({
            selector,
            width: Math.round(r.width),
            height: Math.round(r.height),
            label,
          });
        }
      }
      return out;
    },
    { min: minPx, cssPathSrc: CSS_PATH_FN, visibleSrc: VISIBLE_FN },
  );

/**
 * Is some navigation affordance reachable at the current (mobile) width?
 *
 * WHY: A frequent responsive failure is the desktop sidebar/nav being `display:
 * none` at mobile width with no hamburger to replace it — the user is stranded
 * on one screen. We accept either visible cross-route links OR a visible menu /
 * hamburger toggle as proof the app remains navigable on a phone.
 */
export const hasReachableNav = (page: Page): Promise<boolean> =>
  page.evaluate(() => {
    const visible = (el: Element): boolean => {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return false;
      const s = getComputedStyle(el);
      return s.visibility !== "hidden" && s.display !== "none";
    };
    // 1) A visible <nav> / role=navigation with at least one visible link.
    const navs = Array.from(document.querySelectorAll('nav, [role="navigation"]'));
    for (const nav of navs) {
      if (visible(nav) && Array.from(nav.querySelectorAll("a,button")).some(visible)) return true;
    }
    // 2) Any visible link that points at another in-app route.
    const routeLinks = Array.from(document.querySelectorAll<HTMLAnchorElement>("a[href]")).filter(
      (a) => visible(a) && /^\/(chat|assets|admin)?$/.test(a.getAttribute("href") ?? ""),
    );
    if (routeLinks.length > 0) return true;
    // 3) A visible hamburger / menu toggle (icon buttons rarely have text, so
    //    match aria-label / title / class too).
    const toggles = Array.from(
      document.querySelectorAll<HTMLElement>('button,[role="button"],[aria-haspopup]'),
    );
    return toggles.some((b) => {
      if (!visible(b)) return false;
      const hay = `${b.getAttribute("aria-label") ?? ""} ${b.getAttribute("title") ?? ""} ${
        b.className
      } ${b.textContent ?? ""}`.toLowerCase();
      return /menu|nav|hamburger|☰|≡|drawer|sidebar/.test(hay);
    });
  });

/** Settle a freshly-navigated route: wait for load + a brief paint/layout settle. */
export const settleRoute = async (page: Page, route: string): Promise<void> => {
  await page.goto(route, { waitUntil: "load" });
  // The app streams/hydrates after load (theming, session cards); give layout a
  // moment so overflow/measurement reflects the settled DOM, not a mid-render frame.
  await page.waitForTimeout(1500);
};
