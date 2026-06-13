"""Tests for the web-search grounding wiring — real ADK objects, no mocks.

These assert the structural contract that lets `google_search` coexist with the existing
FunctionTools: a dedicated sub-agent holds google_search alone, and the root agent reaches it
through an AgentTool. The live grounded LLM call itself is never exercised here."""

from __future__ import annotations

from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import GoogleSearchTool

from assistant import search
from assistant.agent import root_agent


def test_search_agent_only_tool_is_google_search():
    # The whole point of the sub-agent: google_search must be ALONE (Gemini rejects it
    # alongside FunctionTools), so the sub-agent's tool list is exactly [google_search].
    assert len(search.search_agent.tools) == 1
    assert isinstance(search.search_agent.tools[0], GoogleSearchTool)
    assert search.search_agent.tools[0] is search.google_search


def test_search_agent_uses_the_shared_model_env_pattern():
    # Reuses the AGENT_MODEL default like agent.py / bookkeeping.py.
    assert search.MODEL == search.search_agent.model
    assert search.search_agent.name == "search_agent"


def test_web_search_is_an_agent_tool_wrapping_the_search_agent():
    assert isinstance(search.web_search, AgentTool)
    assert search.web_search.agent is search.search_agent


def test_root_agent_exposes_web_search_alongside_the_function_tools():
    # web_search is added WITHOUT displacing the existing three FunctionTools.
    assert search.web_search in root_agent.tools
    tool_names = [getattr(t, "name", type(t).__name__) for t in root_agent.tools]
    assert "search_agent" in tool_names  # AgentTool.name derives from the wrapped agent
    # The original function tools are still present (one entry per registered tool).
    assert len(root_agent.tools) == 4


def test_root_instruction_directs_the_model_to_search_for_fresh_info():
    instruction = root_agent.instruction
    assert "web_search" in instruction
    lowered = instruction.lower()
    assert "current events" in lowered
    assert "ground" in lowered
