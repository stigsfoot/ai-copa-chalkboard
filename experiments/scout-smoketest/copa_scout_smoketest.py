#!/usr/bin/env python3
"""
Copa Chalkboard — Match Scout multimodal smoke-test (Workstream 3).

Purpose
-------
Decide whether the Match Scout's vision step is reliable enough for a BEGINNER
Codelab, or whether the Codelab should fall back to text match-logs.

What it does
------------
1. Loads ONE openly-licensed sports image (configurable; verified before use).
2. Sends the SAME image + SAME prompt to gemini-3.5-flash exactly 5 times,
   asking for ONLY valid JSON matching a fixed schema.
3. Scores each run: parseable JSON? players_detected count? schema honored?
4. If ANY of the 5 runs failed validity/schema, runs ONE more call (the 6th and
   final) WITH response_mime_type="application/json" + an enforced response
   schema, to test the structured-output fallback.
5. Prints a scoring table, a GO/NO-GO recommendation, and the raw outputs for
   manual plausibility review.

HARD COST CAPS (enforced in code, not just by convention)
---------------------------------------------------------
* Maximum 5 free-form calls.
* Plus at most 1 structured-output fallback call.
* Absolute maximum: 6 Gemini API calls. The script will refuse to exceed this.

Safety
------
* API key is read from the GEMINI_API_KEY environment variable. It is NEVER
  hardcoded, logged, or written to any file.
* The image is loaded from a configurable, openly-licensed source and verified
  (HTTP 200 + image content-type) BEFORE any paid API call, so a bad image URL
  fails fast and wastes zero calls.

Usage
-----
    export GEMINI_API_KEY="...your key..."
    # Optional: override the default image with any CC-licensed sports photo
    export IMAGE_URL="https://upload.wikimedia.org/.../some-football-match.jpg"
    pip install google-genai requests
    python copa_scout_smoketest.py

The script writes nothing except stdout and an optional JSON results dump
(copa_scout_results.json) in the current directory.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from typing import Any

import requests

try:
    from google import genai
    from google.genai import types
except ImportError:
    sys.exit(
        "google-genai is not installed. Run:  pip install google-genai requests"
    )

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

MODEL = "gemini-3.5-flash"

# Hard caps. The script will not exceed these no matter what.
MAX_FREEFORM_CALLS = 5
MAX_TOTAL_CALLS = 6  # 5 free-form + at most 1 structured-output fallback

# Default image: an openly-licensed football (soccer) match photo with multiple
# players visible. Override with the IMAGE_URL env var if you prefer another
# CC-licensed source. The exact source URL is printed at runtime for the record.
#
# NOTE: This default points at Wikimedia Commons via the canonical Special:
# FilePath redirect, which resolves to the current file bytes. If it ever fails
# to resolve, set IMAGE_URL to any CC-licensed match photo and re-run.
DEFAULT_IMAGE_URL = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "Israel_-_Belgium%2C_2018_FIFA_World_Cup_qualification.jpg"
)

PROMPT = """\
You are a football (soccer) Match Scout analyzing a single still frame.
Return ONLY valid JSON. No markdown, no code fences, no commentary.
The JSON MUST match this exact schema:

{
  "players_detected": 0,
  "player_positions": [
    {"team": "home|away", "zone": "defensive|midfield|attacking",
     "approx_x": 0, "approx_y": 0}
  ],
  "ball_zone": "defensive|midfield|attacking"
}

Rules:
- players_detected is an integer count of players you can see.
- player_positions has one entry per detected player.
- team is "home" or "away" (your best guess from kit color).
- zone and ball_zone are one of: defensive, midfield, attacking.
- approx_x and approx_y are integers 0-100 (percent of image width/height).
Output the JSON object and nothing else."""

# Response schema for the structured-output fallback (step 3.4).
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "players_detected": {"type": "integer"},
        "player_positions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "team": {"type": "string", "enum": ["home", "away"]},
                    "zone": {
                        "type": "string",
                        "enum": ["defensive", "midfield", "attacking"],
                    },
                    "approx_x": {"type": "integer"},
                    "approx_y": {"type": "integer"},
                },
                "required": ["team", "zone", "approx_x", "approx_y"],
            },
        },
        "ball_zone": {
            "type": "string",
            "enum": ["defensive", "midfield", "attacking"],
        },
    },
    "required": [
        "players_detected",
        "player_positions",
        "ball_zone",
    ],
}

REQUIRED_TOP_KEYS = {
    "players_detected",
    "player_positions",
    "ball_zone",
}
VALID_ZONES = {"defensive", "midfield", "attacking"}
VALID_TEAMS = {"home", "away"}


# --------------------------------------------------------------------------- #
# Result bookkeeping
# --------------------------------------------------------------------------- #


@dataclass
class RunResult:
    run: int
    mode: str  # "freeform" or "structured"
    valid_json: bool
    players_detected: int | None
    schema_honored: bool
    schema_problems: list[str] = field(default_factory=list)
    raw_output: str = ""


def validate_schema(obj: Any) -> tuple[bool, list[str], int | None]:
    """Check the parsed object against the Scout schema.

    Returns (schema_honored, problems, players_detected).
    """
    problems: list[str] = []
    players_detected: int | None = None

    if not isinstance(obj, dict):
        return False, ["Top-level value is not a JSON object."], None

    missing = REQUIRED_TOP_KEYS - obj.keys()
    if missing:
        problems.append(f"Missing keys: {sorted(missing)}")
    extra = obj.keys() - REQUIRED_TOP_KEYS
    if extra:
        problems.append(f"Unexpected keys: {sorted(extra)}")

    pd = obj.get("players_detected")
    if isinstance(pd, bool) or not isinstance(pd, int):
        problems.append("players_detected is not an integer.")
    else:
        players_detected = pd

    if obj.get("ball_zone") not in VALID_ZONES:
        problems.append(f"ball_zone not in {sorted(VALID_ZONES)}: {obj.get('ball_zone')!r}")

    positions = obj.get("player_positions")
    if not isinstance(positions, list):
        problems.append("player_positions is not a list.")
    else:
        for i, p in enumerate(positions):
            if not isinstance(p, dict):
                problems.append(f"player_positions[{i}] is not an object.")
                continue
            if p.get("team") not in VALID_TEAMS:
                problems.append(f"player_positions[{i}].team invalid: {p.get('team')!r}")
            if p.get("zone") not in VALID_ZONES:
                problems.append(f"player_positions[{i}].zone invalid: {p.get('zone')!r}")
            for axis in ("approx_x", "approx_y"):
                v = p.get(axis)
                if isinstance(v, bool) or not isinstance(v, int):
                    problems.append(f"player_positions[{i}].{axis} not an integer: {v!r}")

    return (len(problems) == 0), problems, players_detected


def parse_and_score(run: int, mode: str, text: str) -> RunResult:
    """Parse raw model text as JSON and score it."""
    cleaned = text.strip()
    # Be tolerant of accidental code fences when scoring "valid JSON?" leniently,
    # but record the RAW output untouched for the record.
    fenced = cleaned
    if fenced.startswith("```"):
        fenced = fenced.split("```", 2)[1] if "```" in fenced[3:] else fenced
        fenced = fenced.replace("json", "", 1).strip("`").strip()

    valid_json = False
    schema_honored = False
    problems: list[str] = []
    players: int | None = None

    for candidate in (cleaned, fenced):
        try:
            obj = json.loads(candidate)
            valid_json = True
            schema_honored, problems, players = validate_schema(obj)
            break
        except (json.JSONDecodeError, TypeError):
            continue
    if not valid_json:
        problems = ["Output was not parseable as JSON."]

    return RunResult(
        run=run,
        mode=mode,
        valid_json=valid_json,
        players_detected=players,
        schema_honored=schema_honored,
        schema_problems=problems,
        raw_output=text,
    )


# --------------------------------------------------------------------------- #
# Image loading (verified before any paid call)
# --------------------------------------------------------------------------- #


def load_image(url: str) -> tuple[bytes, str]:
    """Download and verify the test image. Fails fast on any problem."""
    print(f"[image] Source URL: {url}")
    resp = requests.get(url, timeout=30, headers={"User-Agent": "copa-scout-smoketest/1.0"})
    resp.raise_for_status()
    ctype = resp.headers.get("Content-Type", "")
    if not ctype.startswith("image/"):
        raise RuntimeError(
            f"URL did not return an image (Content-Type={ctype!r}). "
            "Set IMAGE_URL to a direct CC-licensed image link and re-run."
        )
    data = resp.content
    print(f"[image] OK — {len(data):,} bytes, content-type={ctype}")
    return data, ctype


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set. Export it and re-run. (Never hardcode it.)")

    image_url = os.environ.get("IMAGE_URL", DEFAULT_IMAGE_URL)

    try:
        image_bytes, ctype = load_image(image_url)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[image] FAILED to load test image: {e}")

    client = genai.Client(api_key=api_key)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=ctype)

    results: list[RunResult] = []
    calls_made = 0

    print(f"\n=== Free-form consistency test ({MAX_FREEFORM_CALLS} calls, model={MODEL}) ===")
    for i in range(1, MAX_FREEFORM_CALLS + 1):
        if calls_made >= MAX_TOTAL_CALLS:
            print("[cap] Absolute call cap reached; stopping.")
            break
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=[image_part, PROMPT],
            )
            calls_made += 1
            text = resp.text or ""
        except Exception as e:  # noqa: BLE001
            calls_made += 1
            text = f"<API ERROR: {e}>"
        r = parse_and_score(i, "freeform", text)
        results.append(r)
        status = "valid+schema" if (r.valid_json and r.schema_honored) else (
            "valid/bad-schema" if r.valid_json else "INVALID JSON"
        )
        print(f"  Run {i}: {status}  players_detected={r.players_detected}")
        time.sleep(0.5)

    # Step 3.4 — structured-output fallback, only if needed and within cap.
    any_bad = any((not r.valid_json) or (not r.schema_honored) for r in results)
    fallback: RunResult | None = None
    if any_bad and calls_made < MAX_TOTAL_CALLS:
        print("\n=== Structured-output fallback (1 call, response_schema enforced) ===")
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=[image_part, PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                ),
            )
            calls_made += 1
            text = resp.text or ""
        except Exception as e:  # noqa: BLE001
            calls_made += 1
            text = f"<API ERROR: {e}>"
        fallback = parse_and_score(6, "structured", text)
        ok = fallback.valid_json and fallback.schema_honored
        print(f"  Fallback: {'FIXED (valid+schema)' if ok else 'still broken'}  "
              f"players_detected={fallback.players_detected}")
    elif any_bad:
        print("\n[cap] Free-form runs had issues but call cap is reached; skipping fallback.")
    else:
        print("\n[info] All 5 free-form runs valid + schema-honoring; fallback not needed.")

    # ----------------------------------------------------------------------- #
    # Report
    # ----------------------------------------------------------------------- #
    print("\n" + "=" * 64)
    print(f"SCORING TABLE  (total API calls made: {calls_made} / cap {MAX_TOTAL_CALLS})")
    print("=" * 64)
    print(f"{'Run':<5}{'Mode':<12}{'Valid JSON?':<13}{'players':<9}{'schema?':<9}")
    for r in results + ([fallback] if fallback else []):
        print(f"{r.run:<5}{r.mode:<12}{str(r.valid_json):<13}"
              f"{str(r.players_detected):<9}{str(r.schema_honored):<9}")

    valid_schema_count = sum(1 for r in results if r.valid_json and r.schema_honored)
    counts = [r.players_detected for r in results if r.players_detected is not None]
    spread = (max(counts) - min(counts)) if counts else None

    print("\n--- Aggregate (free-form runs only) ---")
    print(f"  valid + schema-honoring: {valid_schema_count}/{len(results)}")
    print(f"  players_detected values: {counts}")
    print(f"  count spread (max-min):  {spread}")

    # GO / NO-GO heuristic from the plan.
    go = valid_schema_count >= 4 and (spread is not None and spread <= 1)
    print("\n--- RECOMMENDATION ---")
    if go:
        print("  GO (keep imagery): >=4/5 valid+schema and counts stable (+/-1).")
    else:
        reasons = []
        if valid_schema_count < 4:
            reasons.append(f"only {valid_schema_count}/5 valid+schema")
        if spread is None or spread > 1:
            reasons.append(f"count spread = {spread} (unstable)")
        print(f"  NO-GO (fall back to text match-logs): {', '.join(reasons)}.")
        if fallback and fallback.valid_json and fallback.schema_honored:
            print("  NOTE: structured-output fallback FIXED validity — if you keep "
                  "imagery, the Codelab MUST use enforced response_schema.")
    print("\n  Reminder: the A2A handoff lesson is identical for imagery vs text. "
          "The vision step is garnish, not the core lesson.")

    # ----------------------------------------------------------------------- #
    # Raw outputs for manual plausibility review (human check)
    # ----------------------------------------------------------------------- #
    print("\n" + "=" * 64)
    print("RAW OUTPUTS (eyeball tactical-zone plausibility yourself — the script")
    print("CANNOT verify whether zones match the actual image).")
    print("=" * 64)
    for r in results + ([fallback] if fallback else []):
        print(f"\n----- Run {r.run} ({r.mode}) -----\n{r.raw_output}")

    # Dump machine-readable results too.
    out = {
        "model": MODEL,
        "image_url": image_url,
        "total_calls": calls_made,
        "runs": [asdict(r) for r in results + ([fallback] if fallback else [])],
        "valid_schema_count": valid_schema_count,
        "count_spread": spread,
        "recommendation": "GO" if go else "NO-GO",
    }
    with open("copa_scout_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n[done] Wrote copa_scout_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
