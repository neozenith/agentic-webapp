import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import dagre from "cytoscape-dagre";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import type { DbtModelInfo } from "../api";

// Register the dagre layout extension exactly once (module scope). Safe under the test's
// vi.mock("cytoscape") because the mocked default still exposes a no-op `use`.
cytoscape.use(dagre);

const LAYER_PREFIX = "layer:";
const SOURCES_LAYER = `${LAYER_PREFIX}sources`;

/** Derive the dbt layer from a model path: the first segment after `models/`
 * (`models/staging/consulting/x.sql` → `staging`). Falls back to "other". */
export const layerOf = (path: string): string => {
  const marker = "models/";
  const idx = path.indexOf(marker);
  const rel = idx >= 0 ? path.slice(idx + marker.length) : path;
  return rel.includes("/") ? rel.split("/")[0] : "other";
};

/** Pure element builder so the graph shape is unit-testable without a real cytoscape:
 * one node per model (classed table/view), one source node per dotted depends_on entry,
 * one edge per dependency, and a compound boundary parent per layer (+ a sources boundary). */
export const buildElements = (models: DbtModelInfo[]): ElementDefinition[] => {
  const elements: ElementDefinition[] = [];
  const layers = new Set<string>();
  const nodeIds = new Set<string>();
  let hasSources = false;

  for (const m of models) {
    const layer = layerOf(m.path);
    layers.add(layer);
    nodeIds.add(m.name);
    elements.push({
      data: { id: m.name, label: m.name, parent: `${LAYER_PREFIX}${layer}` },
      classes: `model ${m.materialized === "table" ? "table" : "view"}`,
    });
  }

  for (const m of models) {
    for (const dep of m.depends_on) {
      if (dep.includes(".") && !nodeIds.has(dep)) {
        nodeIds.add(dep);
        hasSources = true;
        elements.push({ data: { id: dep, label: dep, parent: SOURCES_LAYER }, classes: "source" });
      }
    }
  }

  for (const layer of layers) {
    elements.push({ data: { id: `${LAYER_PREFIX}${layer}`, label: layer }, classes: "boundary" });
  }
  if (hasSources) elements.push({ data: { id: SOURCES_LAYER, label: "sources" }, classes: "boundary" });

  for (const m of models) {
    for (const dep of m.depends_on) {
      elements.push({ data: { id: `${dep}->${m.name}`, source: dep, target: m.name }, classes: "edge" });
    }
  }

  return elements;
};

const STYLE: cytoscape.StylesheetStyle[] = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "font-size": 11,
      color: "#e5e7eb",
      "text-valign": "center",
      "text-halign": "center",
      "text-outline-color": "#111827",
      "text-outline-width": 2,
      width: "label",
      height: 28,
      padding: "8px",
      shape: "round-rectangle",
    },
  },
  { selector: "node.model", style: { "background-color": "#3b82f6" } },
  { selector: "node.model.table", style: { "background-color": "#1d4ed8" } },
  { selector: "node.source", style: { "background-color": "#6b7280", shape: "diamond", height: 36 } },
  {
    selector: "node.boundary",
    style: {
      "background-color": "#A5C84D",
      "background-opacity": 0.08,
      "border-color": "#A5C84D",
      "border-width": 2,
      shape: "round-rectangle",
      "text-valign": "top",
      "text-halign": "center",
      color: "#A5C84D",
      "font-size": 12,
      padding: "16px",
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#6b7280",
      "target-arrow-color": "#6b7280",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
    },
  },
  {
    selector: ".highlighted",
    style: { "border-color": "#10b981", "border-width": 3, "line-color": "#10b981", "target-arrow-color": "#10b981" },
  },
  { selector: ".dimmed", style: { opacity: 0.25 } },
];

/** Interactive dbt lineage graph: dagre LR layout, compound layer boundaries, and
 * click-to-highlight a node's neighborhood (incomers + outgoers). */
export function LineageGraph({ models }: { models: DbtModelInfo[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElements(models),
      style: STYLE,
      layout: { name: "dagre", rankDir: "LR" } as unknown as cytoscape.LayoutOptions,
    });
    cyRef.current = cy;

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      const related = node.incomers().union(node.outgoers()).union(node);
      cy.elements().addClass("dimmed");
      cy.elements().removeClass("highlighted");
      related.removeClass("dimmed").addClass("highlighted");
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) cy.elements().removeClass("dimmed").removeClass("highlighted");
    });

    return () => cy.destroy();
  }, [models]);

  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button variant="outline" size="sm" onClick={() => cyRef.current?.fit(undefined, 24)}>
          Fit
        </Button>
      </div>
      <div
        ref={containerRef}
        data-testid="lineage-canvas"
        className="h-[480px] w-full rounded-md border border-border bg-card"
      />
    </div>
  );
}
