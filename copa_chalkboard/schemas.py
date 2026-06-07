"""The contract between the two agents.

The Scout produces a ``ScoutReport``. The validation gate checks it. The Analyst
consumes a *validated* ``ScoutReport`` and produces an ``AnalystReport``. Keeping
these as Pydantic models gives us three things at once:

1. A single source of truth for the JSON the Scout must emit.
2. Free structured-output enforcement (Gemini accepts a Pydantic schema).
3. Parse-time validation we can unit-test offline.

This is the "ubiquitous language" of the system in code form — see CONTEXT.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Team = Literal["home", "away"]
Zone = Literal["defensive", "midfield", "attacking"]


class PlayerPosition(BaseModel):
    """One detected player and where they are on the pitch."""

    team: Team
    zone: Zone
    approx_x: int = Field(ge=0, le=100, description="Percent of image width, 0-100.")
    approx_y: int = Field(ge=0, le=100, description="Percent of image height, 0-100.")


class ScoutReport(BaseModel):
    """The Match Scout's structured read of a single still frame."""

    players_detected: int = Field(ge=0)
    player_positions: list[PlayerPosition] = Field(default_factory=list)
    ball_zone: Zone
    tactical_note: str = Field(min_length=1)


class GateResult(BaseModel):
    """The validation gate's verdict on a ScoutReport."""

    passed: bool
    score: int = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)


class AnalystReport(BaseModel):
    """The Tactical Analyst's read on a validated ScoutReport."""

    summary: str = Field(min_length=1)
    key_observations: list[str] = Field(default_factory=list)
    recommended_adjustment: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"] = "medium"


class PipelineResult(BaseModel):
    """The end-to-end result: what the gate decided and, if it passed, the analysis."""

    report: ScoutReport
    gate: GateResult
    analysis: AnalystReport | None = None
