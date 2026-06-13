import "@testing-library/jest-dom/vitest";

import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./src/test/server";

// This jsdom build does not ship a Storage implementation. Install a real in-memory
// one (not a mock — genuine get/set/remove semantics) so localStorage-backed UI is
// exercised for real, matching the project's no-mock testing rule.
if (typeof globalThis.localStorage === "undefined") {
  class MemoryStorage implements Storage {
    private store = new Map<string, string>();
    get length(): number {
      return this.store.size;
    }
    clear(): void {
      this.store.clear();
    }
    getItem(key: string): string | null {
      return this.store.get(key) ?? null;
    }
    key(index: number): string | null {
      return [...this.store.keys()][index] ?? null;
    }
    removeItem(key: string): void {
      this.store.delete(key);
    }
    setItem(key: string, value: string): void {
      this.store.set(key, String(value));
    }
  }
  globalThis.localStorage = new MemoryStorage();
}

// jsdom ships no matchMedia. ThemeProvider reads `prefers-color-scheme` for its initial
// theme, so install a real (non-mock) implementation that reports "no preference"
// (matches=false). Individual tests can replace window.matchMedia to drive the OS-pref
// branch — that's environment control, not mocking app code.
if (typeof globalThis.matchMedia === "undefined") {
  globalThis.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// Start the MSW fake server once; reset handlers between tests; tear down at the end.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
