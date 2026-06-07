"""Validation gate tests — the boundary guard between Scout and Analyst."""

from copa_chalkboard.gate import validate_scout_report
from copa_chalkboard.schemas import PlayerPosition, ScoutReport


def _report(n, positions, ball="midfield"):
    return ScoutReport(
        players_detected=n,
        player_positions=positions,
        ball_zone=ball,
    )


def _pos(team="home", zone="midfield", x=50, y=50):
    return PlayerPosition(team=team, zone=zone, approx_x=x, approx_y=y)


def test_clean_report_passes_with_full_score():
    r = _report(2, [_pos(), _pos(team="away", zone="attacking")])
    g = validate_scout_report(r)
    assert g.passed is True
    assert g.score == 100
    assert g.issues == []


def test_count_mismatch_penalized_but_may_still_pass():
    # 3 claimed, 2 listed: -25 -> score 75, no critical -> passes at default threshold 75.
    r = _report(3, [_pos(), _pos()])
    g = validate_scout_report(r)
    assert g.score == 75
    assert g.passed is True
    assert any("positions listed" in i for i in g.issues)


def test_implausible_count_is_critical_and_fails():
    r = _report(999, [])
    g = validate_scout_report(r)
    assert g.passed is False  # critical finding forces fail
    assert any("plausible range" in i for i in g.issues)


def test_players_claimed_but_none_listed_fails():
    # 5 claimed, 0 listed: -25 (mismatch) -30 (no positions) = 45 < 75.
    r = _report(5, [])
    g = validate_scout_report(r)
    assert g.passed is False
    assert g.score == 45


def test_custom_threshold_is_respected():
    r = _report(3, [_pos(), _pos()])  # score 75
    assert validate_scout_report(r, threshold=80).passed is False
    assert validate_scout_report(r, threshold=70).passed is True
