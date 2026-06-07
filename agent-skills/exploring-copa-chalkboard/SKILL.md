---
name: exploring-copa-chalkboard
description: >
  Tours the Copa Chalkboard codebase — the two-agent (Scout -> Analyst) tactical
  analysis Codelab — and explains where to read first and why each piece exists.
  Use when a learner asks how the system works, wants a walkthrough, or is about
  to make a change.
---

# Exploring Copa Chalkboard

> Drop this folder into `.claude/skills/` (or your agent's skills dir) to make it
> loadable. It mirrors race-condition's `exploring-the-codebase` skill.

A beginner Codelab: a **Match Scout** (vision) hands off to a **Tactical Analyst**
over an in-process A2A pass, guarded by a **validation gate**. Built on Gemini +
Google ADK. Modeled on `GoogleCloudPlatform/race-condition`, shrunk to the
smallest thing that teaches the patterns.

## Where to start (by intent)

| You want to understand... | Read in this order |
|---|---|
| The shared vocabulary | `CONTEXT.md` |
| The contracts between agents | `copa_chalkboard/schemas.py` |
| The vision step | `docs/adr/0002` → `copa_chalkboard/scout.py` → `experiments/scout-smoketest/` |
| The handoff (the lesson) | `docs/adr/0001` → `copa_chalkboard/pipeline.py` |
| The validation gate | `docs/adr/0003` → `copa_chalkboard/gate.py` → `tests/test_gate.py` |
| Why anything is the way it is | `docs/adr/` |
| What was verified vs the reference repo | `docs/codelab-verification-findings.md` |

## The mental model

```
frame ─▶ Match Scout ─▶ ScoutReport ─▶ gate ─(pass)─▶ Tactical Analyst ─▶ AnalystReport
                                          └─(fail)─▶ stop + report issues
```

Two agents, two jobs: the Scout only does vision; the Analyst only reasons over
the (validated) report and never sees the image.

## Patterns worth understanding

1. **In-process A2A.** `pipeline.make_adk_pipeline()` wraps each agent as an ADK
   `AgentTool` and a root `LlmAgent` calls them — all in one process. Same idea
   as the race-condition simulator's `AgentTool(agent=pipeline)`. No gateway,
   no Redis.
2. **The gate is pure.** `gate.py` has no model calls or I/O, so it's instant,
   deterministic, and fully unit-tested. It mirrors `planner_with_eval`'s
   "score ≥ 75 and no critical finding" rule.
3. **Structured output.** The Scout enforces a Pydantic `response_schema` so its
   JSON is reliable (`docs/adr/0002`).
4. **Offline tests.** `make test` passes with no API key and without ADK
   installed, because SDK imports are lazy (inside functions).

## Two implementations of the same flow

- `run_pipeline_local` — plain Python, model steps injected, the tested reference.
- `make_adk_pipeline` — the ADK-native version, for seeing the framework idiom.

## When changing code

Respect `CLAUDE.md`: keep the two jobs separate, keep the gate pure, keep tests
offline, and don't add distributed infra to the core path (that's a deliberate
follow-on, per `docs/adr/0001`).
