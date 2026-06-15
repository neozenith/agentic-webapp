import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// During `bun dev`, proxy backend + agent paths to the local FastAPI (which itself
// proxies the agent sidecar). In production the SPA is served BY FastAPI, same origin.
const backend = "http://localhost:8080";
const proxied = ["/api", "/ui", "/run_sse", "/run", "/list-apps", "/apps", "/dev-ui", "/debug"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    proxy: Object.fromEntries(proxied.map((p) => [p, { target: backend, changeOrigin: true }])),
  },
  build: { outDir: "dist" },
});
