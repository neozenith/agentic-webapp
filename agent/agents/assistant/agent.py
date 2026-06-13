"""The default ADK agent.

Model defaults to the cheapest Gemini (2.5 Flash-Lite); override via AGENT_MODEL.
Auth is keyless via Vertex AI (GOOGLE_GENAI_USE_VERTEXAI=True + project/location),
using the dedicated agent service account.

Tools (see tools.py): the agent can list stored assets, attach one inline to read it
(e.g. a receipt photo), and record the extracted details to the analytics store. Assets
come from the backend's AssetService (GCS) — the single source of truth — never ADK's
artifact store (ADR-0006), so the agent stays stateless / scale-to-zero safe.
"""

import os

from google.adk.agents import Agent

from .bookkeeping import record_usage
from .tools import AttachAssetTool, list_assets, record_extraction

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")

_INSTRUCTION = """You are a helpful, concise assistant for agentic-webapp.

You can work with the user's uploaded assets (photos, scans, PDFs — e.g. receipts):
- Use `list_assets` to see what assets exist (id, filename, type) when the user refers to
  one without an id.
- Use `attach_asset(asset_id)` to load an asset so you can SEE it. The user's message may
  already include an attached asset reference like "[attached asset <id> — <name>]"; pass
  that <id> to attach_asset, then read the image.
- After reading a document, extract the relevant details and call
  `record_extraction(asset_id, doc_type, fields_json)` to save them. Choose a short
  `doc_type` (e.g. "fuel_receipt", "invoice") and pass `fields_json` as a JSON object of
  the key/values you found, e.g.
  {"vendor":"Shell","total":"82.50","currency":"AUD","date":"2026-06-10","litres":"45.2"}.
  Then briefly confirm what you recorded."""

root_agent = Agent(
    name="assistant",
    model=MODEL,
    description="General-purpose assistant for agentic-webapp, with asset + extraction tools.",
    instruction=_INSTRUCTION,
    tools=[list_assets, AttachAssetTool(), record_extraction],
    # Itemise token usage + cost to the bookkeeping table after every model call.
    after_model_callback=record_usage,
)
