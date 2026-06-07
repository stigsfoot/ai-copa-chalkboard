"""The Match Scout — the multimodal (vision) agent.

The Scout looks at one still frame and emits a structured ``ScoutReport``.

Design split (Pocock-style deep module, simple surface):
- Pure, testable helpers at module level: the prompt, and ``parse_scout_output``.
- Side-effecting model calls behind small functions that lazy-import the SDKs,
  so importing this module (and running the tests) needs no API key and no ADK.

Why structured output? See docs/adr/0002 — vision models are inconsistent about
JSON unless you enforce a response schema, so the Scout always requests one.
"""

from __future__ import annotations

import json

from . import config
from .schemas import ScoutReport

SCOUT_PROMPT = """\
You are a football (soccer) Match Scout analyzing a single still frame.
Return ONLY a JSON object matching the required schema. No prose, no code fences.

- players_detected: integer count of players you can see.
- player_positions: one entry per detected player, each with:
    team ("home" or "away", from kit color),
    zone ("defensive" | "midfield" | "attacking"),
    approx_x and approx_y (integers 0-100, percent of width/height).
- ball_zone: "defensive" | "midfield" | "attacking".
- tactical_note: a single short sentence.
"""


def parse_scout_output(text: str) -> ScoutReport:
    """Parse raw model text into a validated ScoutReport.

    Tolerates an accidental ```json fence but otherwise expects clean JSON.
    Raises ValueError on unparseable or schema-invalid output so callers (and
    the gate) get a clear failure rather than a silent bad report.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # drop the first fence line and any trailing fence
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Scout output was not valid JSON: {e}") from e
    try:
        return ScoutReport.model_validate(data)
    except Exception as e:  # pydantic.ValidationError
        raise ValueError(f"Scout output did not match the schema: {e}") from e


def scout_with_genai(image_bytes: bytes, mime_type: str = "image/jpeg") -> ScoutReport:
    """Run the Scout against an image using google-genai with enforced schema.

    This is the simple, beginner path. Lazy-imports the SDK so the rest of the
    package stays import-clean.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.get_api_key())
    resp = client.models.generate_content(
        model=config.SCOUT_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            SCOUT_PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ScoutReport,  # enforce the contract (ADR-0002)
        ),
    )
    return parse_scout_output(resp.text or "")


def make_scout_agent():
    """Build the Scout as a Google ADK ``LlmAgent`` (the ADK-native path).

    Used by the ADK pipeline (pipeline.make_adk_pipeline). Lazy-imports ADK so
    `pip install copa-chalkboard` without the [adk] extra still works.
    """
    from google.adk.agents import LlmAgent
    from google.genai import types

    return LlmAgent(
        name="match_scout",
        model=config.SCOUT_MODEL,
        description="Looks at one match frame and returns a structured ScoutReport.",
        instruction=SCOUT_PROMPT,
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ScoutReport,
            temperature=0.1,
        ),
    )
