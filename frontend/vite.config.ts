import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// During `bun dev`, proxy backend + agent paths to the local FastAPI (which itself
// proxies the agent sidecar). In production the SPA is served BY FastAPI, same origin.
const backend = "http://localhost:8080";
const proxied = ["/api", "/run_sse", "/run", "/list-apps", "/apps", "/dev-ui", "/debug"];

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(proxied.map((p) => [p, { target: backend, changeOrigin: true }])),
  },
  build: { outDir: "dist" },
});
