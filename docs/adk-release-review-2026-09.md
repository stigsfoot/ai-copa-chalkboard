# google-adk release review — what changed since our pin, and what we did about it

**Date:** 2026-09-12
**Baseline:** `pyproject.toml` pinned `google-adk>=2.2.0` (released 2026-06-04).
**Latest:** 2.9.0 (released 2026-09-10). Seven minor releases in between.
**Method:** installed 2.9.0 in a clean sandbox and introspected the package;
read `CHANGELOG.md` from `google/adk-python@main` and the graph-workflow pages
from `google/adk-docs@main`. The rendered docs site was not reachable from the
sandbox, so every claim below marked **[VERIFIED]** was checked against the
installed source, not a web page. Nothing here was run against a live model.

## TL;DR

1. **The construct our ADK path was built on is now the wrong one.** ADK 2.0
   (GA 2026-05-19) shipped a graph `Workflow` engine. In 2.9.0,
   `SequentialAgent` and `LoopAgent` are decorated `@deprecated(... in favor of
   Workflow ...)`, and `AgentTool`'s docstring says direct use "is discouraged".
   **[VERIFIED]** We rewrote the ADK path as a `Workflow` (ADR 0004).
2. **The old path also had a real bug** independent of deprecation: `AgentTool`
   forwards a text-only `request` string, so the Scout never received the frame.
   **[VERIFIED]** Fixed by the same rewrite; the first graph node gets the
   user's full message.
3. **Pin bumped to `google-adk>=2.9.0`.** The graph API and the
   input-schema-on-nodes behaviour we rely on landed across 2.4–2.5 and were
   corrected in 2.6–2.9; 2.9.0 is the first release we have verified end to end.

## Release-by-release: what matters for Copa Chalkboard

| Version (date) | What landed | Relevance here | Action |
|---|---|---|---|
| 2.0.0 (05-19) | Graph `Workflow` engine: `Workflow`, `@node`, `FunctionNode`, `JoinNode`, routed edges, `START`, `DEFAULT_ROUTE`. Task/single-turn agent modes. | The whole ADK path. | **Adopted.** |
| 2.2.0 (06-04) | `to_a2a(Workflow)` supported; a2a-sdk constraint widened. | The distributed follow-on can serve *our exact graph* over the real A2A protocol. | Follow-on (see below). |
| 2.4.0 (07-07) | "Workflow as Tool"; `ToolNode` accepts JSON or `Content`; misleading workflow-agent deprecation messages corrected. | Confirms direction: graphs are the primary orchestration idiom. | Noted. |
| 2.5.0 (07-16) | Strict `input_schema` validation for `LlmAgent` workflow nodes; "validate that no old orchestrators are used inside Workflow graphs"; `AgentTool` docstring now recommends `mode='single_turn'`; context caching (`ContextCacheConfig`); tool confirmation / HITL; `output_schema` inferred from function return types. | `input_schema=ScoutReport` on the Analyst is now enforced by the framework, not just by our prompt. | **Adopted** (`input_schema` on the Analyst). |
| 2.6.0 (07-29) | `ReflectAndRetryModelPlugin`; plugin `on_agent_error_callback`; resumability checkpoints from graph nodes. **Breaking:** artifacts namespaced by app. | Self-healing on malformed Scout output is a one-line plugin. | Follow-on. |
| 2.7.0 (08-13) | Tools can return media; Jinja2 instruction templates (`use_jinja2=True`); models declare capabilities (output schema + tools pairing); native task mode on root `LlmAgent`; faster import. | Media-returning tools matter only if a future gate needs the image. | Noted. |
| 2.8.0 (08-25) | `FallbackModel` (automatic failover between models); Model Armor guardrail plugin; per-workflow token/inference telemetry; `RemoteA2aAgent` task mode + auth. | `FallbackModel` is the cheapest reliability win for the Scout. | Follow-on. |
| 2.9.0 (09-10) | Graph workflows loadable from YAML; MCP SDK 2.x; LiveKit runner. **Breaking:** a failed node re-runs on resume (make node bodies idempotent); `InMemorySessionService` raises on unknown session. | Our nodes are pure/idempotent; we never append to an unknown session. | Verified compatible. |

Dates are PyPI upload dates. **[VERIFIED]** via the PyPI JSON API.

## What we adopted now

- **`Workflow` graph for the handoff** — `copa_chalkboard/pipeline.py`,
  `make_adk_pipeline`. Scout node → gate node (routes `pass`/`fail`) → Analyst
  node. No orchestrator LLM. Rationale and diagram in `docs/adr/0004`.
- **`input_schema=ScoutReport` on the Analyst** — the contract is enforced on
  the way in as well as the way out.
- **`run_pipeline_adk` + `--adk` CLI flag + `copa_chalkboard/agent.py`** — the
  ADK path is now runnable (`python -m copa_chalkboard --image … --adk`,
  `adk web .`) and returns the same `PipelineResult` as the plain path.
- **Offline ADK tests** — `tests/test_adk_workflow.py` drives the real ADK
  engine with a fake `BaseLlm`. They prove the Scout receives the image part
  and the Analyst never runs on a failed report. Skipped when ADK is absent.
- **Pin** — `google-adk>=2.9.0`.

## Worth a follow-on (ranked by value to the Codelab)

1. **LLM-as-Judge gate via `google.adk.evaluation`.** ADR 0003 promised an
   LLM-judge extension and named the grounding gap (a fabricated but
   internally consistent report scores 100). ADK now ships
   `llm_as_judge`, `rubric_based_evaluator`, `hallucinations_v1` and
   `safety_evaluator` under `google.adk.evaluation`, plus `adk eval` with
   eval-set files and CSV export. **[VERIFIED: modules present]** A second
   lesson could add a rubric-based judge node on the `pass` route and compare
   cost vs robustness — exactly the `planner_with_eval` lesson the reference
   architecture embodies.
2. **`FallbackModel` on the Scout (2.8).** `model=FallbackModel(models=[...])`
   fails over to a backup model on retriable status codes. One line, and it
   is the honest answer to "what happens when Flash is overloaded mid-demo?".
3. **`ReflectAndRetryModelPlugin` (2.6).** A runner plugin that feeds a
   model-side error back to the model and retries. Pairs with structured
   output for the rare malformed Scout response.
4. **The distributed variant = real A2A.** ADR 0001 deferred distributed A2A.
   ADK now supports `to_a2a(Workflow)` (2.2) and `RemoteA2aAgent` with task
   mode and auth (2.8), behind the `[a2a]` extra (`a2a-sdk[http-server]`).
   The follow-on lesson can serve the Scout as an A2A service and have the
   graph call it via `RemoteA2aAgent`, which is where the term "A2A" should
   be introduced. `CONTEXT.md` now distinguishes the in-process handoff from
   the A2A protocol for this reason.
5. **YAML graph configs (2.9).** The same graph as a declarative file is a
   nice "look, no code" moment for beginners. Not adopted: it adds a second
   source of truth to keep in sync with `pipeline.py`.

## Not adopting, and why

- **Context caching (`ContextCacheConfig` on `App`).** Single image, two short
  calls; nothing to cache. Revisit only if the Codelab moves to video frames.
- **Jinja2 instruction templates.** Our prompts have no conditionals.
- **Task mode / `mode='task'`, LiveKit, MCP 2.x, Model Armor.** Out of scope for
  a two-agent beginner lesson; none of them touch the handoff.

## Things a reader of the older docs should know

- `docs/codelab-verification-findings.md` §2 recommends `AgentTool` and
  `SequentialAgent`. That was accurate for ADK 1.x and the reference repo at
  the time; it is now superseded by ADR 0004. The findings doc is kept as the
  historical record and not edited.
- The ADK default model is now `gemini-3-flash-preview` (changelog, 2.x). We
  always set the model explicitly from `config.py`, so this does not affect us.
- The `[adk]` extra still does **not** pull in `a2a-sdk`. Real A2A needs
  `pip install "google-adk[a2a]"`.
