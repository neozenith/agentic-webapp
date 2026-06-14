"""An ADK agent whose ONLY tools are the core API's MCP server — the test harness for
"the agent is just another interface to the core API".

It connects to the backend's `/mcp` over streamable-HTTP and forwards a chosen persona as
the IAP identity header, so the MCP (and the API behind it) apply the SAME RBAC the SPA and
CLI get. Run it to watch a real LLM pick MCP tools and to confirm RBAC shapes what a persona
can do over MCP:

    uv run --directory agent python -m harness.mcp_agent \
        --as nina.analyst@example.com "list my assets and summarise the analytics"

Needs a running backend (`make -C backend dev`) and Vertex/ADC creds for the model — so it
is a manual harness, never part of `make ci`. The construction helpers below are unit-tested
without an LLM or a live server.
"""

from __future__ import annotations

import argparse
import asyncio
import os

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.genai import types

# The IAP identity header the backend trusts in non-prod to simulate "who is signed in"
# (ADR-0004); set via --as so the agent drives the MCP as a given persona.
IAP_USER_HEADER = "X-Goog-Authenticated-User-Email"
DEFAULT_BASE_URL = os.environ.get("AGENTIC_BASE_URL", "http://localhost:8080")
DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")

_INSTRUCTION = """You are a test client for the agentic-webapp core API, reached entirely
through MCP tools (you have no other tools). To answer a request, call the relevant MCP tools
(assets_*, folders_*, admin_*, analytics_*, identity_*) and report what they return. If a tool
is refused with a 403, say so plainly and name the role it requires — do not retry or pretend
it succeeded. Be concise."""


def mcp_connection(base_url: str, as_user: str | None) -> StreamableHTTPConnectionParams:
    """Connection params for the backend's MCP, carrying the persona identity header (or no
    header at all when `as_user` is None → an anonymous caller)."""
    headers = {IAP_USER_HEADER: as_user} if as_user else {}
    return StreamableHTTPConnectionParams(url=f"{base_url.rstrip('/')}/mcp/", headers=headers)


def build_agent(base_url: str, as_user: str | None, *, model: str = DEFAULT_MODEL) -> Agent:
    """An ADK agent whose only toolset is the core API's MCP server, scoped to `as_user`."""
    toolset = McpToolset(connection_params=mcp_connection(base_url, as_user))
    return Agent(
        name="mcp_tester",
        model=model,
        description="Drives the agentic-webapp core API purely through its MCP tools.",
        instruction=_INSTRUCTION,
        tools=[toolset],
    )


async def _run(prompt: str, *, base_url: str, as_user: str | None, model: str) -> None:  # pragma: no cover — needs LLM
    agent = build_agent(base_url, as_user, model=model)
    sessions = InMemorySessionService()
    runner = Runner(app_name="mcp_tester", agent=agent, session_service=sessions)
    user_id = as_user or "anonymous"
    session = await sessions.create_session(app_name="mcp_tester", user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=message):
        for part in event.content.parts if event.content else []:
            if getattr(part, "function_call", None):
                print(f"  → tool: {part.function_call.name}({dict(part.function_call.args or {})})")
            elif getattr(part, "function_response", None):
                print(f"  ← result: {str(part.function_response.response)[:200]}")
            elif getattr(part, "text", None) and event.is_final_response():
                print(f"\n{part.text}")


def main(argv: list[str] | None = None) -> None:  # pragma: no cover — manual entrypoint (needs LLM + server)
    parser = argparse.ArgumentParser(prog="mcp_agent", description="Drive the core API's MCP via an ADK agent.")
    parser.add_argument("prompt", help="what to ask the agent to do")
    parser.add_argument("--as", dest="as_user", metavar="EMAIL", default=None, help="impersonate this persona")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"backend base URL (default {DEFAULT_BASE_URL})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"model id (default {DEFAULT_MODEL})")
    args = parser.parse_args(argv)
    print(f">>> persona={args.as_user or 'anonymous'} model={args.model} mcp={args.base_url}/mcp/")
    asyncio.run(_run(args.prompt, base_url=args.base_url, as_user=args.as_user, model=args.model))


if __name__ == "__main__":  # pragma: no cover
    main()
