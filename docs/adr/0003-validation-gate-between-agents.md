# ADR 0003 — A pure validation gate between Scout and Analyst

- **Status:** Accepted
- **Date:** 2026-06-07

## Context

A handoff is only as trustworthy as what crosses it. If the Scout hallucinates
(e.g. "999 players") and we pass that straight to the Analyst, we get confident
nonsense. The race-condition `planner_with_eval` agent solves the analogous
problem with an **LLM-as-Judge** gate: a normalized 0–100 score, a pass threshold
(≥ 75), and an automatic fail on any high-severity finding.

We want the same *shape* of gate, but for a beginner Codelab a deterministic,
instant, free, unit-testable gate teaches the concept better than a second LLM
call. (An LLM-as-Judge variant is an easy, well-motivated extension.)

## Decision

`gate.py` is a **pure function** of a `ScoutReport`: no I/O, no model calls. It
returns a `GateResult(passed, score, issues)`. Pass requires `score >= threshold`
(default 75) **and** no critical finding — mirroring the reference gate's rule.
The Analyst runs only if the gate passes.

Checks: player-count plausibility (critical), count-vs-positions consistency,
non-empty positions when players are claimed.

## Consequences

- **Good:** deterministic and instant; `tests/test_gate.py` covers it fully with
  no API key; the pass/block behavior is visible and obvious to learners.
- **Good:** clean extension point — students can replace/augment the pure gate
  with an LLM-as-Judge call and compare cost vs robustness, exactly the lesson
  `planner_with_eval` embodies.
- **Trade-off:** a deterministic gate can't judge *semantic* quality (are the
  tactical zones actually right?). That stays a human/LLM-judge concern and is
  called out as such.

## Known Limitations

- **Syntactic vs. Grounded Validation:** The validation gate evaluates structural, internal, and syntactic consistency (e.g., verifying that player coordinates are within bounds, enums are valid, and counts are consistent). It **cannot** verify whether the Scout's observations are externally grounded in the actual image.
- **Score-100-on-Fabrication:** During 5-run consistency testing on the *Sulley Muntari* transition image, the Scout successfully emitted 5/5 reports that scored 100/100 on the gate. However, the gate had no way to verify whether the specific player kit details or coordinate positions in the `tactical_note` were factually accurate or partially fabricated by the vision model.
- **Future Work:** A future ADR (e.g., LLM-as-Judge / Grounding-Aware Gate) could define a secondary gate utilizing a reasoning model with visual context to cross-reference the structured report against the original frame.
