"""The validation gate — the heart of the lesson.

A handoff between agents is only as trustworthy as what crosses the boundary.
The gate sits between the Scout and the Analyst and refuses to pass a report
that doesn't make sense. This mirrors the race-condition ``planner_with_eval``
gate: a normalized 0-100 score, a pass threshold, and "no critical finding."

Everything here is a PURE function of a ``ScoutReport`` — no model calls, no I/O —
so it is fast, deterministic, and trivially unit-tested (see tests/test_gate.py).
"""

from __future__ import annotations

from . import config
from .schemas import GateResult, ScoutReport

# Penalty weights (subtracted from a starting score of 100).
_PENALTY_COUNT_MISMATCH = 25  # players_detected != len(player_positions)
_PENALTY_IMPLAUSIBLE_COUNT = 40  # critical: count outside sane bounds
_PENALTY_EMPTY_NOTE = 20
_PENALTY_NO_POSITIONS = 30  # claims players but lists none

# A finding at or above this severity is "critical" and forces a fail
# regardless of the score, exactly like the reference gate's high-severity rule.
_CRITICAL_PENALTY = _PENALTY_IMPLAUSIBLE_COUNT


def validate_scout_report(
    report: ScoutReport,
    *,
    threshold: int | None = None,
) -> GateResult:
    """Score a ScoutReport and decide whether it may cross to the Analyst.

    Args:
        report: the Scout's structured output (already schema-valid).
        threshold: pass mark; defaults to config.GATE_PASS_THRESHOLD.

    Returns:
        GateResult with passed/score/issues.
    """
    threshold = config.GATE_PASS_THRESHOLD if threshold is None else threshold

    score = 100
    issues: list[str] = []
    has_critical = False

    n_claimed = report.players_detected
    n_listed = len(report.player_positions)

    # Critical: an implausible player count means the vision step is unreliable.
    if not (config.MIN_PLAUSIBLE_PLAYERS <= n_claimed <= config.MAX_PLAUSIBLE_PLAYERS):
        score -= _PENALTY_IMPLAUSIBLE_COUNT
        has_critical = True
        issues.append(
            f"players_detected={n_claimed} is outside the plausible range "
            f"[{config.MIN_PLAUSIBLE_PLAYERS}, {config.MAX_PLAUSIBLE_PLAYERS}]."
        )

    # Internal consistency: the count should match the positions listed.
    if n_claimed != n_listed:
        score -= _PENALTY_COUNT_MISMATCH
        issues.append(
            f"players_detected={n_claimed} but {n_listed} positions listed."
        )

    # Claims players but provides no positions for the Analyst to reason over.
    if n_claimed > 0 and n_listed == 0:
        score -= _PENALTY_NO_POSITIONS
        issues.append("players_detected > 0 but player_positions is empty.")

    # A handoff with no tactical note gives the Analyst nothing to anchor on.
    if not report.tactical_note.strip():
        score -= _PENALTY_EMPTY_NOTE
        issues.append("tactical_note is empty.")

    score = max(0, score)
    passed = (score >= threshold) and not has_critical

    return GateResult(passed=passed, score=score, issues=issues)
