import { Database, GitBranch, Hammer, History } from "lucide-react";
import { useEffect, useState } from "react";

import { LineageGraph } from "@/components/LineageGraph";
import { RunHistory } from "@/components/RunHistory";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type DbtCommand, type DbtProject, type DbtRunResult, getDbtProject, runDbt } from "../api";

const COMMANDS: DbtCommand[] = ["compile", "run", "test", "build"];

type Tab = "models" | "lineage" | "history";

const TABS: { id: Tab; label: string; icon: typeof Database }[] = [
  { id: "models", label: "Models", icon: Database },
  { id: "lineage", label: "Lineage", icon: GitBranch },
  { id: "history", label: "Run history", icon: History },
];

export function Dbt() {
  const [project, setProject] = useState<DbtProject | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<DbtCommand | null>(null);
  const [result, setResult] = useState<DbtRunResult | null>(null);
  const [tab, setTab] = useState<Tab>("models");

  useEffect(() => {
    getDbtProject()
      .then(setProject)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const exec = async (command: DbtCommand) => {
    setBusy(command);
    setError(null);
    try {
      setResult(await runDbt(command));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!project) return <p className="text-muted-foreground">Loading dbt project…</p>;

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {TABS.map(({ id, label, icon: Icon }) => (
          <Button
            key={id}
            size="sm"
            variant={tab === id ? "default" : "outline"}
            onClick={() => setTab(id)}
            aria-pressed={tab === id}
          >
            <Icon /> {label}
          </Button>
        ))}
      </div>

      {tab === "models" && (
        <>
          <Card className="animate-fade-in-up">
            <CardHeader className="flex-row items-start justify-between gap-2">
              <div className="flex flex-col gap-1">
                <CardTitle className="flex items-center gap-2">
                  <Database className="size-5" /> {project.name}
                </CardTitle>
                <CardDescription>
                  target <span className="font-mono text-foreground">{project.target}</span> · profile{" "}
                  <span className="font-mono text-foreground">{project.profile}</span> · v{project.version}
                </CardDescription>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <Badge variant={project.dbt_cli_available ? "default" : "muted"}>
                    {project.dbt_cli_available ? "dbt CLI available" : "dbt CLI unavailable"}
                  </Badge>
                  <Badge variant="outline">{project.model_count} models</Badge>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {COMMANDS.map((c) => (
                  <Button
                    key={c}
                    size="sm"
                    variant={c === "build" ? "default" : "outline"}
                    disabled={busy !== null}
                    onClick={() => void exec(c)}
                  >
                    <Hammer /> {busy === c ? `${c}…` : c[0].toUpperCase() + c.slice(1)}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>model</TableHead>
                    <TableHead>layer</TableHead>
                    <TableHead>materialized</TableHead>
                    <TableHead>depends on</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {project.models.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-muted-foreground">
                        no models in this project
                      </TableCell>
                    </TableRow>
                  ) : (
                    project.models.map((m) => (
                      <TableRow key={m.name}>
                        <TableCell className="font-medium">{m.name}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{m.db_schema}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{m.materialized}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {m.depends_on.length === 0 ? (
                              <span className="text-muted-foreground">—</span>
                            ) : (
                              m.depends_on.map((d) => (
                                <Badge key={d} variant="outline" className="font-mono">
                                  {d}
                                </Badge>
                              ))
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {result && (
            <Card>
              <CardHeader className="flex-row items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2">
                  <span className="font-mono">dbt {result.command}</span>
                  <Badge
                    variant={result.success ? "default" : "outline"}
                    className={result.success ? "" : "text-destructive border-destructive"}
                  >
                    {result.success ? "success" : "failed"}
                  </Badge>
                  <Badge variant="muted">exit {result.return_code}</Badge>
                </CardTitle>
                <span className="text-sm text-muted-foreground">{result.elapsed_seconds.toFixed(2)}s</span>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {result.stdout && (
                  <div>
                    <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">stdout</h4>
                    <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">{result.stdout}</pre>
                  </div>
                )}
                {result.stderr && (
                  <div>
                    <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">stderr</h4>
                    <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs text-destructive">
                      {result.stderr}
                    </pre>
                  </div>
                )}
                {result.nodes.length > 0 && (
                  <div>
                    <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                      {result.nodes.length} nodes
                    </h4>
                    <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">
                      {JSON.stringify(result.nodes, null, 2)}
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {tab === "lineage" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <GitBranch className="size-5" /> Lineage
            </CardTitle>
            <CardDescription>
              Model dependencies, grouped by layer. Click a node to trace its neighborhood.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LineageGraph models={project.models} />
          </CardContent>
        </Card>
      )}

      {tab === "history" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <History className="size-5" /> Run history
            </CardTitle>
            <CardDescription>Elementary-backed invocation history and per-run timing.</CardDescription>
          </CardHeader>
          <CardContent>
            <RunHistory />
          </CardContent>
        </Card>
      )}
    </section>
  );
}
