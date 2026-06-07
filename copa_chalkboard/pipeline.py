"""Wiring: Scout -> Gate -> Analyst, in-process.

This module is the lesson. It shows the same Scout -> Gate -> Analyst flow two ways:

1. ``run_pipeline_local`` — a plain, readable Python orchestrator. The two model
   steps are *injected*, so the whole flow is unit-tested offline with fakes
   (tests/test_pipeline_wiring.py). This is the "what is actually happening" view.

2. ``make_adk_pipeline`` — the Google ADK-native version. A root ``LlmAgent``
   invokes the Scout and Analyst as ``AgentTool``s and calls the gate as a
   function tool — all IN-PROCESS, no gateway, no Redis, no Cloud Run. This is
   the exact in-process pattern the race-condition simulator uses (AgentTool +
   sub-agent composition). See docs/adr/0001.
"""

from __future__ import annotations

from typing import Callable

from .analyst import analyst_with_genai
from .gate import validate_scout_report
from .schemas import AnalystReport, PipelineResult, ScoutReport
from .scout import scout_with_genai

# Type aliases for the injectable model steps.
ScoutFn = Callable[[bytes, str], ScoutReport]
AnalystFn = Callable[[ScoutReport], AnalystReport]


def run_pipeline_local(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    scout_fn: ScoutFn | None = None,
    analyst_fn: AnalystFn | None = None,
    gate_threshold: int | None = None,
) -> PipelineResult:
    """Run Scout -> Gate -> Analyst in plain Python.

    The Analyst only runs if the gate passes. Inject ``scout_fn``/``analyst_fn``
    in tests to avoid any network or API key.
    """
    _scout: ScoutFn = scout_fn or (lambda b, m: scout_with_genai(b, m))
    _analyst: AnalystFn = analyst_fn or analyst_with_genai

    report = _scout(image_bytes, mime_type)
    gate = validate_scout_report(report, threshold=gate_threshold)
    analysis = _analyst(report) if gate.passed else None

    return PipelineResult(report=report, gate=gate, analysis=analysis)


# --------------------------------------------------------------------------- #
# ADK-native pipeline (the in-process A2A pattern, faithful to race-condition)
# --------------------------------------------------------------------------- #


def _gate_tool(scout_report_json: str) -> dict:
    """ADK function tool: validate a Scout report JSON and return the verdict.

    Args:
        scout_report_json: the Scout's JSON output (a ScoutReport).

    Returns:
        dict with passed/score/issues. The root agent uses ``passed`` to decide
        whether to call the Analyst.
    """
    report = ScoutReport.model_validate_json(scout_report_json)
    return validate_scout_report(report).model_dump()


ROOT_INSTRUCTION = """\
You orchestrate a two-agent tactical analysis, in this exact order:
1. Call the `match_scout` tool with the match frame to get a ScoutReport (JSON).
2. Call `validate_scout_report` with that JSON. Read the `passed` field.
3. If passed is true, call the `tactical_analyst` tool with the ScoutReport JSON
   and return its AnalystReport. If passed is false, STOP and report the gate's
   issues — do NOT call the analyst on an invalid report.
Call each tool at most once.
"""


def make_adk_pipeline():
    """Build the ADK-native root orchestrator (lazy-imports ADK).

    Demonstrates in-process agent-to-agent invocation: the Scout and Analyst are
    wrapped as ``AgentTool``s and called by a root ``LlmAgent`` within one
    process. Requires the [adk] extra: `pip install "copa-chalkboard[adk]"`.
    """
    from google.adk.agents import LlmAgent
    from google.adk.tools.agent_tool import AgentTool

    from .analyst import make_analyst_agent
    from .scout import make_scout_agent

    scout_agent = make_scout_agent()
    analyst_agent = make_analyst_agent()

    return LlmAgent(
        name="copa_chalkboard_root",
        model="gemini-3.5-flash",
        description="Orchestrates Match Scout -> validation gate -> Tactical Analyst.",
        instruction=ROOT_INSTRUCTION,
        tools=[
            AgentTool(agent=scout_agent),
            _gate_tool,
            AgentTool(agent=analyst_agent),
        ],
    )
