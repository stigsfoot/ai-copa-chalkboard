"""End-to-end wiring tests with fake model steps (no API key, no network).

This proves the lesson's core behavior: a failing gate stops the handoff, and a
passing gate lets the Analyst run.
"""

from copa_chalkboard.pipeline import run_pipeline_local
from copa_chalkboard.schemas import AnalystReport, PlayerPosition, ScoutReport


def _good_report():
    return ScoutReport(
        players_detected=2,
        player_positions=[
            PlayerPosition(team="home", zone="midfield", approx_x=40, approx_y=50),
            PlayerPosition(team="away", zone="attacking", approx_x=75, approx_y=35),
        ],
        ball_zone="midfield",
        tactical_note="Away team springs a counter.",
    )


def _bad_report():
    # implausible count -> critical -> gate fails
    return ScoutReport(
        players_detected=999, player_positions=[], ball_zone="midfield", tactical_note="?"
    )


def _fake_analyst(report):
    return AnalystReport(
        summary="Counter-attack forming.",
        key_observations=["Away overloads the right."],
        recommended_adjustment="Drop the full-back to cover.",
        confidence="high",
    )


def test_passing_gate_invokes_analyst():
    analyst_calls = []

    def analyst(report):
        analyst_calls.append(report)
        return _fake_analyst(report)

    result = run_pipeline_local(
        b"fake", "image/jpeg",
        scout_fn=lambda b, m: _good_report(),
        analyst_fn=analyst,
    )
    assert result.gate.passed is True
    assert result.analysis is not None
    assert len(analyst_calls) == 1  # analyst ran exactly once


def test_failing_gate_blocks_analyst():
    analyst_calls = []

    def analyst(report):
        analyst_calls.append(report)
        return _fake_analyst(report)

    result = run_pipeline_local(
        b"fake", "image/jpeg",
        scout_fn=lambda b, m: _bad_report(),
        analyst_fn=analyst,
    )
    assert result.gate.passed is False
    assert result.analysis is None
    assert analyst_calls == []  # analyst NEVER ran on a bad report
