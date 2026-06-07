# ADR 0001 — In-process A2A via ADK `AgentTool`, not distributed services

- **Status:** Accepted
- **Date:** 2026-06-07

## Context

The Codelab teaches an agent-to-agent (A2A) handoff. The `GoogleCloudPlatform/
race-condition` reference architecture (Google Cloud Next '26) implements A2A in
two ways:

1. **Distributed** — agents run as separate services, discover each other via
   `/.well-known/agent-card.json`, and talk over HTTP / A2A JSON-RPC through a Go
   gateway, with Redis, Memorystore, Cloud SQL and Cloud NAT behind it
   (~$91/month standing cost).
2. **In-process** — a root `LlmAgent` invokes other agents *inside one Python
   process* using `AgentTool`, and composes them with `SequentialAgent` /
   `LoopAgent`. The simulator does exactly this:
   `AgentTool(agent=simulation_pipeline)` where the pipeline is a
   `SequentialAgent([pre_race, race_engine, post_race])`.

Verification confirmed in-process composition is fully supported by ADK and is
the *dominant* pattern in the reference repo. (See
`docs/codelab-verification-findings.md`, §2.)

## Decision

The core Codelab uses **in-process A2A**: the root orchestrator calls the Scout
and Analyst as `AgentTool`s within a single process. No gateway, no Redis, no
agent cards, no Cloud Run. The whole thing runs in one Colab notebook.

## Consequences

- **Good:** zero standing infrastructure cost; a learner can run it in minutes;
  the handoff is observable as plain function calls.
- **Good:** the lesson is identical whether the Scout's input is an image or a
  text match-log — the handoff is the lesson, the vision step is garnish.
- **Trade-off:** does not teach service discovery / horizontal scale. That is a
  deliberate follow-on, not a gap. A `distributed variant` can be added later
  (mirroring race-condition's gateway) for learners who want production scale.
