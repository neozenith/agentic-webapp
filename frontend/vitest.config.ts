import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Unit/component tests run in jsdom. The HTTP boundary is faked with MSW (a real
// network-level fake server — not object mocks), per the project no-mock rule.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
      // main.tsx is the createRoot bootstrap (no logic to unit-test); styles + types
      // excluded; components/ui/** are vendored shadcn primitives (not app logic).
      exclude: [
        "src/main.tsx",
        "src/vite-env.d.ts",
        "src/test/**",
        "src/components/ui/**",
        "src/**/*.test.{ts,tsx}",
        "**/*.css",
        "**/*.d.ts",
      ],
      reporter: ["text", "text-summary"],
      thresholds: { statements: 90, lines: 90, functions: 90, branches: 80 },
    },
  },
});
