import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";

const ALL_AREAS = ["home", "chat", "sessions", "assets", "analytics", "semantic", "dbt", "dashboards", "admin"];

// A shared MSW server — a real network-level fake (not an object mock). Tests register
// per-case handlers via `server.use(...)`, which override the defaults below.
export const server = setupServer(
  // Default identity grants every area, so tests that don't care about RBAC see full nav.
  // RBAC tests override /api/me with a restricted permissions list.
  http.get("/api/me", () =>
    HttpResponse.json({ email: null, user_id: null, environment: "test", roles: ["admin"], permissions: ALL_AREAS }),
  ),
  http.get("/api/auth/personas", () => HttpResponse.json([])),
);
