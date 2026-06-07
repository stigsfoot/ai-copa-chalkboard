# CLAUDE.md — working notes for coding agents

This repo is a **beginner Codelab**. Optimize every change for *readability by a
first-time ADK learner*, not for cleverness.

## Read these first
- `CONTEXT.md` — the ubiquitous language. Use these exact terms.
- `docs/adr/` — why the architecture is the way it is. Don't silently reverse an ADR.
- `README.md` — the learner-facing narrative.

## Ground rules
1. **Two jobs, two agents.** Scout = vision → `ScoutReport`. Analyst = reasoning
   over a validated `ScoutReport` → `AnalystReport`. Never merge them.
2. **The gate is pure.** `gate.py` has no I/O and no model calls. Keep it that way
   so it stays unit-testable.
3. **In-process by default.** The core lesson needs no gateway/Redis/Cloud Run.
   See `docs/adr/0001`. Don't add distributed infra to the core path.
4. **Tests stay offline.** `make test` must pass with no API key and without
   `google-adk` installed. Lazy-import SDKs inside functions (see `scout.py`).
5. **Secrets via env only.** `GEMINI_API_KEY` from the environment. `.env` is
   gitignored. Never hardcode or commit a key.
6. **TDD.** New behavior gets a failing test first (red), then code (green). See
   `tests/`.

## Where things live
- `copa_chalkboard/schemas.py` — the typed contracts (start here).
- `copa_chalkboard/scout.py` / `analyst.py` — the two agents.
- `copa_chalkboard/gate.py` — the validation gate.
- `copa_chalkboard/pipeline.py` — the wiring (plain Python + ADK-native).
- `experiments/scout-smoketest/` — vision-reliability check (delivery risk).
- `docs/codelab-verification-findings.md` — what was verified against the
  `GoogleCloudPlatform/race-condition` reference architecture.
