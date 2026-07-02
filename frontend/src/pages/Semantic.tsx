import { Boxes, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  listSemanticModels,
  runSemanticQuery,
  type SemanticEntity,
  type SemanticModel,
  type SemanticQuery,
  type SemanticQueryResult,
} from "../api";

const TIME_GRAINS = ["day", "week", "month", "quarter", "year"] as const;

/** A list of named-thing checkboxes (measures or dimensions) for the query runner. */
function CheckList({
  legend,
  options,
  selected,
  onToggle,
}: {
  legend: string;
  options: string[];
  selected: Set<string>;
  onToggle: (name: string) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="text-sm font-medium">{legend}</legend>
      {options.length === 0 ? (
        <span className="text-xs text-muted-foreground">none</span>
      ) : (
        <div className="flex flex-wrap gap-3">
          {options.map((name) => (
            <label key={name} className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={selected.has(name)} onChange={() => onToggle(name)} />
              <span className="font-mono">{name}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

/** Read-only view of one entity: its dimensions and measures as tables. */
function EntityCard({ entity }: { entity: SemanticEntity }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{entity.name}</span>
        <Badge variant="outline" className="font-mono">
          {entity.table}
        </Badge>
        {entity.time_dimension && <Badge variant="muted">time: {entity.time_dimension}</Badge>}
      </div>
      {entity.description && <p className="mt-1 text-sm text-muted-foreground">{entity.description}</p>}
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Dimensions</h4>
          <div className="flex flex-wrap gap-1">
            {entity.dimensions.map((d) => (
              <Badge key={d.name} variant="secondary" className="font-mono" title={d.description}>
                {d.name}
              </Badge>
            ))}
          </div>
        </div>
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Measures</h4>
          <div className="flex flex-wrap gap-1">
            {entity.measures.map((m) => (
              <Badge key={m.name} variant="default" className="font-mono" title={m.description}>
                {m.name} ({m.agg})
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Interactive query builder + runner for one entity of the selected model. */
function QueryRunner({ model, entity }: { model: SemanticModel; entity: SemanticEntity }) {
  const [measures, setMeasures] = useState<Set<string>>(new Set());
  const [dimensions, setDimensions] = useState<Set<string>>(new Set());
  const [timeGrain, setTimeGrain] = useState<string>("");
  const [result, setResult] = useState<SemanticQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, name: string) => {
    const next = new Set(set);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setter(next);
  };

  const run = async () => {
    setBusy(true);
    setError(null);
    const query: SemanticQuery = {
      entity: entity.name,
      measures: [...measures],
      dimensions: [...dimensions],
      filters: [],
      time_grain: timeGrain || null,
      order_by: null,
      descending: false,
      limit: 100,
    };
    try {
      setResult(await runSemanticQuery(model.model_id, query));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <CheckList
        legend="Measures"
        options={entity.measures.map((m) => m.name)}
        selected={measures}
        onToggle={(n) => toggle(measures, setMeasures, n)}
      />
      <CheckList
        legend="Dimensions"
        options={entity.dimensions.map((d) => d.name)}
        selected={dimensions}
        onToggle={(n) => toggle(dimensions, setDimensions, n)}
      />
      <label className="flex items-center gap-2 text-sm">
        <span className="font-medium">Time grain</span>
        <select
          aria-label="Time grain"
          value={timeGrain}
          onChange={(e) => setTimeGrain(e.target.value)}
          className="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
        >
          <option value="">none</option>
          {TIME_GRAINS.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      </label>
      <div>
        <Button size="sm" disabled={busy} onClick={() => void run()}>
          <Play /> {busy ? "Running…" : "Run"}
        </Button>
      </div>

      {error && <p className="text-destructive">⚠️ {error}</p>}
      {result && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">{result.row_count} rows</p>
          <Table>
            <TableHeader>
              <TableRow>
                {result.columns.map((c) => (
                  <TableHead key={c}>{c}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={Math.max(result.columns.length, 1)} className="text-muted-foreground">
                    no rows
                  </TableCell>
                </TableRow>
              ) : (
                result.rows.map((row, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: query result rows have no stable id
                  <TableRow key={i}>
                    {result.columns.map((c) => (
                      <TableCell key={c}>{String(row[c] ?? "")}</TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{result.sql}</pre>
        </div>
      )}
    </div>
  );
}

export function Semantic() {
  const [models, setModels] = useState<SemanticModel[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [entityName, setEntityName] = useState<string | null>(null);

  useEffect(() => {
    listSemanticModels()
      .then(setModels)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const selected = useMemo(() => models?.find((m) => m.model_id === selectedId) ?? null, [models, selectedId]);
  const activeEntity = useMemo(
    () => selected?.entities.find((e) => e.name === entityName) ?? selected?.entities[0] ?? null,
    [selected, entityName],
  );

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!models) return <p className="text-muted-foreground">Loading semantic models…</p>;

  return (
    <section className="flex flex-col gap-4">
      <Card className="animate-fade-in-up">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Boxes className="size-5" /> Semantic models
          </CardTitle>
          <CardDescription>
            The semantic layer: entities with their dimensions and measures. Pick a model to explore it and run queries.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {models.length === 0 ? (
            <p className="text-muted-foreground">No semantic models defined yet.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {models.map((m) => (
                <button
                  key={m.model_id}
                  type="button"
                  onClick={() => {
                    setSelectedId(m.model_id);
                    setEntityName(null);
                  }}
                  className={`flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors hover:bg-accent ${
                    m.model_id === selectedId ? "border-primary bg-accent" : "border-border"
                  }`}
                >
                  <span className="font-medium">{m.name}</span>
                  <span className="text-sm text-muted-foreground">{m.description}</span>
                  <Badge variant="muted">{m.entities.length} entities</Badge>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {selected && (
        <Card>
          <CardHeader>
            <CardTitle>{selected.name}</CardTitle>
            <CardDescription>{selected.description}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {selected.entities.map((e) => (
              <EntityCard key={e.name} entity={e} />
            ))}
          </CardContent>
        </Card>
      )}

      {selected && activeEntity && (
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2">
            <CardTitle>Query runner</CardTitle>
            <select
              aria-label="Entity"
              value={activeEntity.name}
              onChange={(e) => setEntityName(e.target.value)}
              className="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
            >
              {selected.entities.map((e) => (
                <option key={e.name} value={e.name}>
                  {e.name}
                </option>
              ))}
            </select>
          </CardHeader>
          <CardContent>
            <QueryRunner key={activeEntity.name} model={selected} entity={activeEntity} />
          </CardContent>
        </Card>
      )}
    </section>
  );
}
