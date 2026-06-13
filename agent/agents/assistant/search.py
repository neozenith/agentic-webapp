"""Internet web-search / grounding capability, exposed as a tool the root agent can call.

Gemini rejects mixing the built-in `google_search` grounding tool with custom FunctionTools
in the SAME agent's tool list (the Vertex API 400s the request). The idiomatic ADK workaround
is a dedicated sub-agent whose ONLY tool is `google_search`, surfaced to the root agent via
`AgentTool` — the root agent then calls it like an ordinary function, so the existing
list_assets/attach_asset/record_extraction FunctionTools are preserved unchanged.

`web_search` is the AgentTool the root agent registers. Its name/description tell the model to
reach for it whenever the answer depends on current events, recent releases, prices, or any
fact the model may be stale on.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import google_search

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")

_SEARCH_INSTRUCTION = """You are a web-search grounding assistant. Use the `google_search`
tool to find current, factual information on the internet for the topic or question you are
given. Prefer recent, authoritative sources. Return a concise, factual summary of what you
found, and include the source URLs you relied on so the caller can cite them."""

# A sub-agent whose ONLY tool is the built-in google_search grounding tool. Keeping it alone
# in this agent's tool list is what satisfies Gemini's "no built-in tool alongside function
# tools" constraint.
search_agent = Agent(
    name="search_agent",
    model=MODEL,
    description="Searches the public internet (Google Search) for current, factual grounding.",
    instruction=_SEARCH_INSTRUCTION,
    tools=[google_search],
)

# Surface the search sub-agent to the root agent as a callable tool. The clear name +
# description steer the model to use it for current events / latest info / facts it isn't
# sure about.
web_search = AgentTool(agent=search_agent)
