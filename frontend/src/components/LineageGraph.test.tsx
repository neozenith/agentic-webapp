import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

// Stub the 3rd-party cytoscape lib: a real graph engine needs a layout-capable DOM that
// jsdom doesn't provide. The factory is a vi.fn so we can inspect the elements the
// component hands it, and `.use` is a no-op for the dagre registration at module load.
vi.mock("cytoscape", () => {
  const chain = () => {
    const c = {
      union: () => c,
      addClass: () => c,
      removeClass: () => c,
      incomers: () => c,
      outgoers: () => c,
    };
    return c;
  };
  const cy = { on: vi.fn(), fit: vi.fn(), destroy: vi.fn(), elements: () => chain() };
  const factory = Object.assign(
    vi.fn(() => cy),
    { use: vi.fn() },
  );
  return { default: factory };
});

import cytoscape from "cytoscape";
import type { DbtModelInfo } from "../api";
import { buildElements, LineageGraph, layerOf } from "./LineageGraph";

const model = (over: Partial<DbtModelInfo>): DbtModelInfo => ({
  name: "m",
  resource_type: "model",
  db_schema: "staging",
  materialized: "view",
  description: "",
  depends_on: [],
  tags: [],
  path: "models/staging/m.sql",
  ...over,
});

const MODELS: DbtModelInfo[] = [
  model({ name: "stg_orders", depends_on: ["raw.orders"], path: "models/staging/stg_orders.sql" }),
  model({
    name: "stg_customers",
    depends_on: ["raw.customers"],
    path: "models/staging/consulting/stg_customers.sql",
  }),
  model({
    name: "fct_orders",
    materialized: "table",
    db_schema: "marts",
    depends_on: ["stg_orders", "stg_customers"],
    path: "models/marts/fct_orders.sql",
  }),
];

interface ElementLike {
  data: { id: string; source?: string; target?: string };
  classes?: string;
}

describe("buildElements", () => {
  it("derives the layer from the segment after models/", () => {
    expect(layerOf("models/staging/stg_orders.sql")).toBe("staging");
    expect(layerOf("models/staging/consulting/x.sql")).toBe("staging");
    expect(layerOf("models/marts/fct.sql")).toBe("marts");
    expect(layerOf("top_level.sql")).toBe("other");
  });

  it("builds one node per model, a source per dotted dep, layer boundaries, and edges", () => {
    const els = buildElements(MODELS) as unknown as ElementLike[];
    const byClass = (c: string) => els.filter((e) => e.classes === c || e.classes?.startsWith(`${c} `));
    expect(byClass("model").length).toBe(3); // "model view" / "model table"
    expect(els.filter((e) => e.classes === "source").length).toBe(2); // raw.orders, raw.customers
    expect(els.filter((e) => e.classes === "boundary").length).toBe(3); // staging, marts, sources
    expect(els.filter((e) => e.data.source).length).toBe(4); // 1 + 1 + 2 dependency edges
    // the table-materialized model is classed darker
    expect(els.find((e) => e.data.id === "fct_orders")?.classes).toContain("table");
  });
});

describe("LineageGraph", () => {
  it("hands the built elements to cytoscape and wires interactivity", async () => {
    render(<LineageGraph models={MODELS} />);
    expect(screen.getByTestId("lineage-canvas")).toBeInTheDocument();

    const factory = cytoscape as unknown as ReturnType<typeof vi.fn>;
    const cfg = factory.mock.calls[0][0] as { elements: ElementLike[] };
    // 3 models + 2 sources + 3 boundaries + 4 edges = 12 elements.
    expect(cfg.elements.length).toBe(12);

    const cy = factory.mock.results[0].value as {
      on: ReturnType<typeof vi.fn>;
      fit: ReturnType<typeof vi.fn>;
    };
    const calls = cy.on.mock.calls as unknown[][];
    const nodeHandler = calls.find((c) => c.length === 3)?.[2] as (e: unknown) => void;
    const bgHandler = calls.find((c) => c.length === 2)?.[1] as (e: unknown) => void;
    expect(nodeHandler).toBeTypeOf("function");
    expect(bgHandler).toBeTypeOf("function");

    const fakeNode = {
      union: () => fakeNode,
      addClass: () => fakeNode,
      removeClass: () => fakeNode,
      incomers: () => fakeNode,
      outgoers: () => fakeNode,
    };
    // Exercise both interactivity branches.
    nodeHandler({ target: fakeNode });
    bgHandler({ target: cy }); // background tap → reset
    bgHandler({ target: fakeNode }); // tap on a node, not background → no reset

    await userEvent.click(screen.getByRole("button", { name: /fit/i }));
    expect(cy.fit).toHaveBeenCalled();
  });
});
