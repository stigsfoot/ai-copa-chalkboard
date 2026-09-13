"""ADK Workflow tests — the real ADK engine, offline, with a fake model.

These prove the ADK-native path does what the plain-Python path does:
the Scout sees the frame, the gate routes, and the Analyst runs only on a
report that passed. Skipped when google-adk is not installed, so `make test`
still needs neither an API key nor ADK.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

import pytest

pytest.importorskip("google.adk")

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.models.base_llm import BaseLlm  # noqa: E402
from google.adk.models.llm_request import LlmRequest  # noqa: E402
from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.genai import types  # noqa: E402

from copa_chalkboard.analyst import ANALYST_AGENT_NAME, ANALYST_SYSTEM  # noqa: E402
from copa_chalkboard.pipeline import GATE_STATE_KEY, make_adk_pipeline, run_pipeline_adk  # noqa: E402
from copa_chalkboard.schemas import AnalystReport, ScoutReport  # noqa: E402
from copa_chalkboard.scout import SCOUT_AGENT_NAME, SCOUT_PROMPT  # noqa: E402

# What each fake model received: (agent name, [part kinds]).
CALLS: list[tuple[str, list[str]]] = []


class FakeLlm(BaseLlm):
    """Returns canned text and records what parts it was shown."""

    canned: str

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        kinds = [
            "image" if p.inline_data else f"text:{p.text or ''}"
            for c in llm_request.contents
            for p in c.parts or []
        ]
        CALLS.append((self.model, kinds))
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=self.canned)]))


GOOD_REPORT = json.dumps(
    {
        "players_detected": 2,
        "player_positions": [
            {"team": "home", "zone": "midfield", "approx_x": 40, "approx_y": 50},
            {"team": "away", "zone": "attacking", "approx_x": 75, "approx_y": 35},
        ],
        "ball_zone": "midfield",
    }
)
BAD_REPORT = json.dumps({"players_detected": 999, "player_positions": [], "ball_zone": "midfield"})
ANALYSIS = json.dumps(
    {
        "summary": "Counter-attack forming.",
        "key_observations": ["Away overloads the right."],
        "recommended_adjustment": "Drop the full-back to cover.",
        "confidence": "high",
    }
)


@pytest.fixture
def fake_agents(monkeypatch):
    """Swap the Gemini-backed agents for fake-model twins with the same contracts."""
    CALLS.clear()

    def make_workflow(scout_json: str):
        monkeypatch.setattr(
            "copa_chalkboard.scout.make_scout_agent",
            lambda: LlmAgent(
                name=SCOUT_AGENT_NAME,
                model=FakeLlm(model=SCOUT_AGENT_NAME, canned=scout_json),
                instruction=SCOUT_PROMPT,
                output_schema=ScoutReport,
            ),
        )
        monkeypatch.setattr(
            "copa_chalkboard.analyst.make_analyst_agent",
            lambda: LlmAgent(
                name=ANALYST_AGENT_NAME,
                model=FakeLlm(model=ANALYST_AGENT_NAME, canned=ANALYSIS),
                instruction=ANALYST_SYSTEM,
                input_schema=ScoutReport,
                output_schema=AnalystReport,
            ),
        )
        return make_adk_pipeline()

    return make_workflow


def test_workflow_graph_has_the_four_nodes(fake_agents):
    wf = fake_agents(GOOD_REPORT)
    names = {n.name for n in wf._build_graph().nodes}
    assert {SCOUT_AGENT_NAME, "validation_gate", ANALYST_AGENT_NAME, "gate_failed"} <= names


def test_scout_receives_the_frame(fake_agents):
    run_pipeline_adk(b"fake-jpeg-bytes", "image/jpeg", workflow=fake_agents(GOOD_REPORT))
    scout_calls = [kinds for name, kinds in CALLS if name == SCOUT_AGENT_NAME]
    assert len(scout_calls) == 1
    assert "image" in scout_calls[0]  # the whole point of ADR-0004


def test_passing_gate_routes_to_analyst(fake_agents):
    result = run_pipeline_adk(b"fake", "image/jpeg", workflow=fake_agents(GOOD_REPORT))
    assert result.gate.passed is True
    assert result.gate.score == 100
    assert result.analysis is not None
    assert result.analysis.confidence == "high"
    assert [name for name, _ in CALLS] == [SCOUT_AGENT_NAME, ANALYST_AGENT_NAME]


def test_analyst_sees_only_the_report_never_the_image(fake_agents):
    run_pipeline_adk(b"fake", "image/jpeg", workflow=fake_agents(GOOD_REPORT))
    (analyst_kinds,) = [kinds for name, kinds in CALLS if name == ANALYST_AGENT_NAME]
    assert "image" not in analyst_kinds
    texts = [k[len("text:") :] for k in analyst_kinds if k.startswith("text:")]
    assert any(ScoutReport.model_validate_json(t).players_detected == 2 for t in texts)


def test_failing_gate_never_calls_analyst(fake_agents):
    result = run_pipeline_adk(b"fake", "image/jpeg", workflow=fake_agents(BAD_REPORT))
    assert result.gate.passed is False
    assert any("plausible range" in i for i in result.gate.issues)
    assert result.analysis is None
    assert [name for name, _ in CALLS] == [SCOUT_AGENT_NAME]  # analyst NEVER ran


def test_gate_verdict_is_recorded_in_session_state(fake_agents):
    # GATE_STATE_KEY is how run_pipeline_adk reads the verdict back out.
    result = run_pipeline_adk(b"fake", "image/jpeg", workflow=fake_agents(BAD_REPORT))
    assert GATE_STATE_KEY == "gate_result"
    assert result.gate.score < 75
