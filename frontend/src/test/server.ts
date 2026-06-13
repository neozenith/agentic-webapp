import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";

// A shared MSW server — a real network-level fake (not an object mock). Tests register
// per-case handlers via `server.use(...)`, which override the defaults below.
export const server = setupServer(
  // Default identity so the global Header renders in any test that mounts <App>.
  http.get("/api/me", () => HttpResponse.json({ email: null, user_id: null, environment: "test" })),
);
