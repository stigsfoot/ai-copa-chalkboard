"""Runtime configuration, read from the environment.

Every value has a safe default so the Codelab runs out of the box. The API key
is the only thing you MUST supply, and it is read from the environment only —
never hardcoded, never written to a committed file (see .env.example / .gitignore).
"""

from __future__ import annotations

import os

# --- Models -----------------------------------------------------------------
# The Scout needs vision; gemini-3.5-flash is the current cost-efficient
# multimodal Flash model. The Analyst is text-only reasoning over the Scout's
# structured report, so the same Flash model is plenty.
SCOUT_MODEL = os.getenv("GEMINI_SCOUT_MODEL", "gemini-3.5-flash")
ANALYST_MODEL = os.getenv("GEMINI_ANALYST_MODEL", "gemini-3.5-flash")

# --- Validation gate --------------------------------------------------------
# Mirrors the race-condition planner_with_eval gate: pass requires a score at or
# above the threshold AND no critical finding.
GATE_PASS_THRESHOLD = int(os.getenv("COPA_GATE_THRESHOLD", "75"))

# Plausibility bounds the gate uses to sanity-check the Scout's report.
MIN_PLAUSIBLE_PLAYERS = int(os.getenv("COPA_MIN_PLAYERS", "1"))
MAX_PLAUSIBLE_PLAYERS = int(os.getenv("COPA_MAX_PLAYERS", "30"))


def get_api_key() -> str:
    """Return the Gemini API key or raise a clear, actionable error."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your "
            "key, or `export GEMINI_API_KEY=...`. Never hardcode it."
        )
    return key
