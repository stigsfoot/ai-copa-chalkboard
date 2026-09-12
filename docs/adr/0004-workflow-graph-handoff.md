# ADR 0004 — The in-process handoff is an ADK 2.0 `Workflow` graph, not `AgentTool`

- **Status:** Accepted. Supersedes the *mechanism* in ADR 0001 (`AgentTool`
  under a root `LlmAgent`). The *decision* in ADR 0001 — stay in-process — stands.
- **Date:** 2026-09-12

## Context

ADR 0001 implemented the handoff as a root `LlmAgent` calling the Scout and the
Analyst as `AgentTool`s, plus the gate as a function tool. A code review against
the installed SDK found two verified defects in that path:

1. **The frame never reached the Scout.** `AgentTool` exposes a single
   `request: string` parameter and forwards a text-only message into a fresh
   sub-runner session. The root agent had no way to pass the image, so the
   "vision" agent would have scouted a frame it never saw.
2. **Tool-name mismatch.** The root instruction told the model to call
   `validate_scout_report`, but the registered tool was named `_gate_tool`.

The path had no tests and had never been run end to end (the consistency test in
`docs/codelab-verification-findings.md` used `run_pipeline_local`).

Meanwhile ADK moved. Between the pin (`>=2.2.0`, 2026-06-04) and 2.9.0
(2026-09-10), verified against the installed package:

- ADK 2.0 (GA 2026-05-19) introduced a graph **`Workflow`** engine
  (`google.adk.workflow`: `Workflow`, `@node`, `FunctionNode`, `JoinNode`, routed
  edges, `START`, `DEFAULT_ROUTE`).
- `SequentialAgent` and `LoopAgent` now carry `@deprecated("... in favor of
  Workflow and will be removed in a future version")`.
- `AgentTool`'s docstring now says "Direct usage of `AgentTool` is discouraged";
  the recommended way to expose a sub-agent as a tool is `mode='single_turn'`.
- Since 2.2.0, `to_a2a(Workflow)` is supported, so the same graph can later be
  served over the real A2A protocol (the distributed follow-on ADR 0001 promised).

## Decision

The ADK-native pipeline is a `Workflow` graph:

```
START -> match_scout -> validation_gate --pass--> tactical_analyst
                                        --fail--> gate_failed
```

- `match_scout` is the Scout `LlmAgent` with `output_schema=ScoutReport`. As the
  first node it receives the user's message **including the image part**
  (verified with a fake model: the Scout saw an `inline_data` part).
- `validation_gate` is `gate.validate_scout_report` wrapped as a function node.
  ADK coerces the Scout's JSON into the typed `ScoutReport` parameter, so
  `gate.py` stays pure. The node emits a **route**: on `pass` its output is the
  validated report — that output crossing the edge *is* the handoff.
- `tactical_analyst` runs only on the `pass` route and declares
  `input_schema=ScoutReport`, so the contract is enforced on the way in as well
  as the way out.
- `gate_failed` is a terminal function node that reports the issues.

There is **no orchestrator LLM**. Order and gating are code. The run costs two
model calls, not three, and the gate decision is deterministic.

`run_pipeline_adk` runs the graph with the in-memory session service and returns
the same `PipelineResult` as `run_pipeline_local`, so the CLI shows both paths
(`--adk`). `tests/test_adk_workflow.py` runs the real ADK engine offline with a
fake `BaseLlm`; it is skipped when ADK is not installed.

## Consequences

- **Good:** the ADK path now works and is tested; the frame reaches the Scout;
  the Analyst provably never runs on a failed report.
- **Good:** the graph reads like the domain sentence in `CONTEXT.md`. Learners
  see the gate as a routing node, which is what it is.
- **Good:** it is the idiom ADK is moving toward, so the Codelab will not teach
  a deprecated construct.
- **Trade-off:** `Workflow` is a 2.0 API and still moving (2.9.0 changed
  node-resume semantics; nodes should be idempotent — ours are). Pin
  `google-adk>=2.9.0` and re-verify on upgrades.
- **Trade-off:** a `Workflow` cannot yet be a sub-agent of a chat `LlmAgent`. If
  the Codelab later wants a conversational front-end, wrap the graph with
  `mode='single_turn'` sub-agents rather than reaching for `AgentTool`.
- **Gotcha, documented in code:** node functions are defined inside the lazy
  factory. Because `pipeline.py` uses postponed annotations, a return annotation
  naming the lazily imported `Event` breaks ADK's type-hint resolution and the
  gate silently receives a `dict`. The node functions therefore carry parameter
  annotations only.
