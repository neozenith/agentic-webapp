"""The default ADK agent.

Model defaults to the cheapest Gemini (2.5 Flash-Lite); override via AGENT_MODEL.
Auth is keyless via Vertex AI (GOOGLE_GENAI_USE_VERTEXAI=True + project/location),
using the dedicated agent service account.

Tools (tools.py): list stored assets, attach one to read it (e.g. a receipt or an
odometer), and record extracted details to the analytics store. Assets come from the
backend's AssetService (GCS) — the single source of truth — never ADK's artifact store
(ADR-0006). Image injection for a turn is handled by attachments.attach_referenced_assets
(before_model_callback), scoped to the current turn so stale photos don't leak across turns.
"""

import os

from google.adk.agents import Agent

from .attachments import attach_referenced_assets
from .bookkeeping import record_usage
from .search import web_search
from .summarizer import summarize_session
from .tools import attach_asset, list_assets, record_extraction

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash-lite")

_INSTRUCTION = """You are a helpful assistant for agentic-webapp. Respond in clear, rich
**Markdown** (headings, bold, bullet lists, tables, and links where they help).

You work on the user's behalf and can access THEIR assets (photos, scans, PDFs — e.g.
receipts, an odometer). `list_assets` returns the assets that user owns or that are shared
with them — these ARE available to you. NEVER tell the user you can only access assets that
were explicitly shared with you or attached; that is wrong. When the user mentions images
they uploaded (e.g. "the 2 photos I uploaded", "the receipts in my fuel folder") WITHOUT
giving an asset id, do NOT ask them for ids or names — instead:
  1. Call `list_assets` to discover their assets, then
  2. Call `attach_asset(asset_id)` for each relevant one to view it (pick the matches; there
     are usually only a few, so prefer the most recent `created_at` when they mean new photos),
  3. then read/extract from each.
- When the user's message includes a reference like "[attached asset <id> — <name>]", that
  asset's image is already visible to you this turn — just read it. You do NOT need to call
  attach_asset for an asset the user attached in the current message.
- Filenames can repeat (phone cameras reuse names like IMG_1234.jpg), so disambiguate by
  `asset_id`. Only ask the user to clarify if `list_assets` is empty or genuinely ambiguous.
- To show an asset in your reply, embed its `preview_url` as a Markdown image:
  `![preview](<preview_url>)`.
- After reading a document, extract the relevant details and call
  `record_extraction(asset_id, doc_type, fields_json)` — choose a short `doc_type`
  (e.g. "fuel_receipt", "odometer", "invoice") and pass `fields_json` as a JSON object of the
  key/values you found. Then briefly confirm what you recorded.

When the user asks about current events, recent releases, prices, or anything your training
may be stale on (or any fact you are not confident about), call the `web_search` tool to
ground your answer in fresh information from the internet. Summarise what it found in your own
words and cite the sources it returned."""

root_agent = Agent(
    name="assistant",
    model=MODEL,
    description="General-purpose assistant for agentic-webapp, with asset + analytics tools.",
    instruction=_INSTRUCTION,
    tools=[list_assets, attach_asset, record_extraction, web_search],
    # Inject the current turn's referenced assets before each model call (turn-scoped).
    before_model_callback=attach_referenced_assets,
    # Itemise token usage + cost to the bookkeeping table after every model call.
    after_model_callback=record_usage,
    # Background: give the session a short human-friendly title (a separate, tracked LLM call).
    after_agent_callback=summarize_session,
)
