import { setupServer } from "msw/node";

// A shared MSW server — a real network-level fake (not an object mock). Tests register
// per-case handlers via `server.use(...)`.
export const server = setupServer();
