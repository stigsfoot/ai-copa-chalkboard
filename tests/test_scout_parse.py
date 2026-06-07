"""Scout output parsing tests — the brittle part of any vision step."""

import pytest

from copa_chalkboard.scout import parse_scout_output

GOOD = """{
  "players_detected": 1,
  "player_positions": [
    {"team": "home", "zone": "defensive", "approx_x": 20, "approx_y": 80}
  ],
  "ball_zone": "defensive",
  "tactical_note": "Keeper distributes short."
}"""

FENCED = "```json\n" + GOOD + "\n```"


def test_parses_clean_json():
    r = parse_scout_output(GOOD)
    assert r.players_detected == 1
    assert r.ball_zone == "defensive"


def test_tolerates_code_fence():
    r = parse_scout_output(FENCED)
    assert r.players_detected == 1


def test_raises_on_non_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_scout_output("the image shows a football match")


def test_raises_on_schema_violation():
    with pytest.raises(ValueError, match="did not match the schema"):
        parse_scout_output('{"players_detected": "two", "ball_zone": "midfield"}')
