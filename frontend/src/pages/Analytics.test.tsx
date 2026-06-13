import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { Analytics } from "./Analytics";

describe("Analytics page", () => {
  it("shows the per-doc_type schema and recent extractions", async () => {
    server.use(
      http.get("/api/analytics/summary", () =>
        HttpResponse.json({
          total: 2,
          by_doc_type: [{ doc_type: "fuel_receipt", count: 2, fields: ["vendor", "total"] }],
        }),
      ),
      http.get("/api/analytics/extractions", () =>
        HttpResponse.json([
          {
            extraction_id: "e1",
            asset_id: "a1",
            doc_type: "fuel_receipt",
            user_id: "alice@example.com",
            session_id: "s1",
            fields: { vendor: "Shell", total: "82.50" },
            model_id: "gemini-2.5-flash-lite",
            created_at: "2026-06-12T00:00:00Z",
          },
        ]),
      ),
    );
    render(<Analytics />);
    // semantic layer: doc_type appears in the schema section and the records table
    expect((await screen.findAllByText("fuel_receipt")).length).toBeGreaterThan(0);
    expect(screen.getByText("vendor")).toBeInTheDocument(); // discovered field key
    // a record row shows a fields preview
    expect(screen.getByText(/vendor=Shell/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no extractions", async () => {
    server.use(
      http.get("/api/analytics/summary", () => HttpResponse.json({ total: 0, by_doc_type: [] })),
      http.get("/api/analytics/extractions", () => HttpResponse.json([])),
    );
    render(<Analytics />);
    expect(await screen.findByText(/No analytics records yet/i)).toBeInTheDocument();
  });

  it("surfaces an error", async () => {
    server.use(
      http.get("/api/analytics/summary", () => new HttpResponse(null, { status: 500 })),
      http.get("/api/analytics/extractions", () => HttpResponse.json([])),
    );
    render(<Analytics />);
    expect(await screen.findByText(/analytics error 500/i)).toBeInTheDocument();
  });
});
