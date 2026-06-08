"""The default ADK agent. Kept minimal for now — PR3 adds the bookkeeping callback
(token/cost accounting → BigQuery via agentic-core).

Model defaults to the cheapest Gemini (2.5 Flash-Lite); override via AGENT_MODEL.
Auth is keyless via Vertex AI (GOOGLE_GENAI_USE_VERTEXAI=True + project/location),
using the dedicated agent service account.
"""

import os

from google.adk.agents import Agent

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")

root_agent = Agent(
    name="assistant",
    model=MODEL,
    description="General-purpose assistant for agentic-webapp.",
    instruction="You are a helpful, concise assistant.",
)
