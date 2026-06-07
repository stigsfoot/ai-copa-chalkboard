"""The Tactical Analyst — the second agent.

The Analyst never sees the image. It reasons purely over the Scout's *validated*
``ScoutReport`` and returns an ``AnalystReport``. That separation is the whole
point of the Codelab: a clean, typed message crosses the boundary, and each
agent does one job well.
"""

from __future__ import annotations

import json

from . import config
from .schemas import AnalystReport, ScoutReport

ANALYST_SYSTEM = """\
You are a Tactical Analyst. You receive a structured scouting report (JSON) about
one frame of a football match. You do NOT see the image. Reason only over the
report. Return ONLY a JSON object with:
  summary: one or two sentences on the tactical picture,
  key_observations: a list of short strings,
  recommended_adjustment: one concrete coaching adjustment,
  confidence: "low" | "medium" | "high".
"""


def build_analyst_prompt(report: ScoutReport) -> str:
    """Render the Scout's report into the Analyst's input prompt."""
    return (
        ANALYST_SYSTEM
        + "\n\nSCOUT REPORT:\n"
        + report.model_dump_json(indent=2)
    )


def parse_analyst_output(text: str) -> AnalystReport:
    """Parse raw model text into a validated AnalystReport."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Analyst output was not valid JSON: {e}") from e
    try:
        return AnalystReport.model_validate(data)
    except Exception as e:
        raise ValueError(f"Analyst output did not match the schema: {e}") from e


def analyst_with_genai(report: ScoutReport) -> AnalystReport:
    """Run the Analyst against a validated report using google-genai."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.get_api_key())
    resp = client.models.generate_content(
        model=config.ANALYST_MODEL,
        contents=build_analyst_prompt(report),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AnalystReport,
            temperature=0.3,
        ),
    )
    return parse_analyst_output(resp.text or "")


def make_analyst_agent():
    """Build the Analyst as a Google ADK ``LlmAgent`` (ADK-native path)."""
    from google.adk.agents import LlmAgent
    from google.genai import types

    return LlmAgent(
        name="tactical_analyst",
        model=config.ANALYST_MODEL,
        description="Reasons over a validated ScoutReport and returns an AnalystReport.",
        instruction=ANALYST_SYSTEM,
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AnalystReport,
            temperature=0.3,
        ),
    )
