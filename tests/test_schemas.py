"""Schema contract tests — the typed boundary between the two agents."""

import pytest
from pydantic import ValidationError

from copa_chalkboard.schemas import AnalystReport, PlayerPosition, ScoutReport


def test_valid_scout_report():
    r = ScoutReport(
        players_detected=2,
        player_positions=[
            PlayerPosition(team="home", zone="midfield", approx_x=40, approx_y=55),
            PlayerPosition(team="away", zone="attacking", approx_x=70, approx_y=30),
        ],
        ball_zone="midfield",
        tactical_note="Home side compresses the midfield.",
    )
    assert r.players_detected == 2
    assert len(r.player_positions) == 2


def test_rejects_bad_zone():
    with pytest.raises(ValidationError):
        ScoutReport(
            players_detected=0,
            player_positions=[],
            ball_zone="penalty-box",  # not a valid Zone
            tactical_note="x",
        )


def test_rejects_out_of_range_coordinates():
    with pytest.raises(ValidationError):
        PlayerPosition(team="home", zone="midfield", approx_x=150, approx_y=10)


def test_rejects_empty_tactical_note():
    with pytest.raises(ValidationError):
        ScoutReport(
            players_detected=0, player_positions=[], ball_zone="midfield", tactical_note=""
        )


def test_analyst_report_defaults_confidence_medium():
    a = AnalystReport(
        summary="s", key_observations=["a"], recommended_adjustment="press higher"
    )
    assert a.confidence == "medium"
