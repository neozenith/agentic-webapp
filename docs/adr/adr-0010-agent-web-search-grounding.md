# ADR-0010: Agent web-search grounding via an AgentTool sub-agent

**Status:** Accepted · implemented

## Context

The assistant agent needs to ground answers in current information from the public
internet (recent events, releases, prices — anything the model is stale on). Gemini
offers a built-in `google_search` grounding tool. The agent already carries custom
`FunctionTool`s (`list_assets`, `attach_asset`, `record_extraction`).

The forcing constraint (ADK 2.2.0 / Gemini): a built-in grounding tool like
`google_search` **cannot coexist with custom function declarations in the same agent's
tool list** — the API rejects the mixed configuration.

## Decision

Isolate `google_search` in a dedicated **search sub-agent** whose only tool is
`google_search`, and expose it to the root agent as
`AgentTool(agent=search_agent)`. The root agent then invokes web search as just another
function tool, so the existing asset/analytics `FunctionTool`s remain untouched on the
root agent. The instruction tells the model when to reach for search and to summarise +
cite what it finds.

Import paths that satisfy the strict typecheck gate (runtime re-exports differ):
`from google.adk.tools.google_search_tool import google_search` and
`from google.adk.tools.agent_tool import AgentTool`.

## Consequences

- The two tool families (built-in grounding vs. custom functions) stay on separate agents
  and compose through the `AgentTool` boundary — no API rejection.
- One extra agent hop per search (the root delegates to the sub-agent); acceptable for the
  grounding benefit.
- `google_search` is imported at module top level, so a renamed/missing import crashes
  loudly at load (no silent no-op fallback). The live grounded call is `# pragma: no cover`;
  the wiring is unit-tested.

## Lens

When two capabilities are individually supported but **mutually exclusive in one container**
(here, built-in vs. function tools in one agent), don't drop one — **wrap one as a callable
boundary** so both compose. Pin import paths against the **strict typecheck**, not just
runtime success: a module that imports fine at runtime can still fail `mypy --strict` when
the package doesn't explicitly re-export it.
