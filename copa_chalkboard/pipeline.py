"""Wiring: Scout -> Gate -> Analyst, in-process.

This module is the lesson. It shows the same Scout -> Gate -> Analyst flow two ways:

1. ``run_pipeline_local`` — a plain, readable Python orchestrator. The two model
   steps are *injected*, so the whole flow is unit-tested offline with fakes
   (tests/test_pipeline_wiring.py). This is the "what is actually happening" view.

2. ``make_adk_pipeline`` — the Google ADK-native version: the same three steps
   as an ADK 2.0 ``Workflow`` graph. The Scout and Analyst are ``LlmAgent``
   nodes, the gate is a plain function node that *routes*, and everything runs
   IN-PROCESS — no gateway, no Redis, no Cloud Run. ``run_pipeline_adk`` runs
   that graph and returns the same ``PipelineResult`` as the plain path.
   See docs/adr/0001 (why in-process) and docs/adr/0004 (why a Workflow graph).
"""

from __future__ import annotations

from typing import Callable

from .analyst import analyst_with_genai
from .gate import validate_scout_report
from .schemas import AnalystReport, GateResult, PipelineResult, ScoutReport
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
# ADK-native pipeline: the same flow as an ADK 2.0 Workflow graph (ADR-0004)
# --------------------------------------------------------------------------- #

# Session-state key under which the gate node records its verdict.
GATE_STATE_KEY = "gate_result"

# Text that accompanies the frame in the user message. The Scout's real
# instructions live in scout.SCOUT_PROMPT (its LlmAgent ``instruction``).
FRAME_MESSAGE = "Scout this match frame."


def make_adk_pipeline():
    """Build the ADK-native pipeline as a ``Workflow`` graph (lazy-imports ADK).

    The graph::

        START -> match_scout -> validation_gate --pass--> tactical_analyst
                                                --fail--> gate_failed

    - ``match_scout`` is the Scout ``LlmAgent``. As the first node it receives
      the user's message directly — image part included.
    - ``validation_gate`` is the pure gate wrapped as a function node. ADK
      coerces the Scout's JSON into the typed ``ScoutReport`` parameter, the
      node calls ``validate_scout_report``, and emits a *route*. On ``pass`` its
      output is the validated report — that output crossing the edge IS the
      handoff.
    - ``tactical_analyst`` runs only on the ``pass`` route and, via its
      ``input_schema``, only ever sees a ``ScoutReport``.
    - ``gate_failed`` ends the run with the gate's issues. The Analyst is never
      invoked on a bad report.

    There is no orchestrator LLM: the order and the gate decision are code.
    Requires the [adk] extra: ``pip install "copa-chalkboard[adk]"``.
    """
    from google.adk import Event, Workflow

    from .analyst import make_analyst_agent
    from .scout import make_scout_agent

    # No return annotations on the node functions: this module uses postponed
    # annotations, and ADK resolves a node's type hints to coerce its input
    # (JSON -> ScoutReport). ``Event`` is lazily imported, so annotating with it
    # would make that resolution fail and the gate would receive a plain dict.
    def validation_gate(node_input: ScoutReport):
        """Score the ScoutReport; route to the Analyst only if it passes."""
        gate = validate_scout_report(node_input)
        return Event(
            output=node_input if gate.passed else gate,
            route="pass" if gate.passed else "fail",
            state={GATE_STATE_KEY: gate.model_dump()},
        )

    def gate_failed(node_input: GateResult):
        """Terminal node for the fail route: report the issues, no Analyst."""
        return Event(
            message="Gate did NOT pass — Analyst was not invoked. Issues: "
            + "; ".join(node_input.issues)
        )

    return Workflow(
        name="copa_chalkboard",
        description="Match Scout -> validation gate -> Tactical Analyst.",
        edges=[
            ("START", make_scout_agent(), validation_gate),
            (validation_gate, {"pass": make_analyst_agent(), "fail": gate_failed}),
        ],
    )


async def run_pipeline_adk_async(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    workflow=None,
) -> PipelineResult:
    """Run the ADK ``Workflow`` on one frame and collect a ``PipelineResult``.

    Same contract as ``run_pipeline_local`` so the CLI can show both paths side
    by side. Pass ``workflow`` to run a graph whose agents use a fake model
    (tests/test_adk_workflow.py does exactly that — the real ADK engine, offline).

    In a notebook with a running event loop, ``await`` this directly.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from .analyst import ANALYST_AGENT_NAME, parse_analyst_output
    from .scout import SCOUT_AGENT_NAME, parse_scout_output

    runner = Runner(
        node=workflow or make_adk_pipeline(),
        session_service=InMemorySessionService(),
    )
    session = await runner.session_service.create_session(
        app_name=runner.app_name, user_id="learner"
    )
    message = types.Content(
        role="user",
        parts=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part(text=FRAME_MESSAGE),
        ],
    )

    # Each LlmAgent node emits one final event whose text is its JSON output.
    outputs: dict[str, str] = {}
    async for event in runner.run_async(
        user_id="learner", session_id=session.id, new_message=message
    ):
        if event.partial or not event.content or not event.content.parts:
            continue
        text = "".join(p.text or "" for p in event.content.parts if not p.thought)
        if text and event.author in (SCOUT_AGENT_NAME, ANALYST_AGENT_NAME):
            outputs[event.author] = text

    session = await runner.session_service.get_session(
        app_name=runner.app_name, user_id="learner", session_id=session.id
    )
    report = parse_scout_output(outputs[SCOUT_AGENT_NAME])
    gate = GateResult.model_validate(session.state[GATE_STATE_KEY])
    analysis = (
        parse_analyst_output(outputs[ANALYST_AGENT_NAME]) if ANALYST_AGENT_NAME in outputs else None
    )
    return PipelineResult(report=report, gate=gate, analysis=analysis)


def run_pipeline_adk(
    image_bytes: bytes, mime_type: str = "image/jpeg", *, workflow=None
) -> PipelineResult:
    """Synchronous wrapper around ``run_pipeline_adk_async`` (CLI and tests)."""
    import asyncio

    return asyncio.run(run_pipeline_adk_async(image_bytes, mime_type, workflow=workflow))
