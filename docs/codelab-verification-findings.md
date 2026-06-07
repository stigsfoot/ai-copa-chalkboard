# Copa Chalkboard — Codelab Pre-Proposal Verification Findings

**Prepared for:** Noble Ackerson
**Date:** 2026-06-07
**Reference repo:** `GoogleCloudPlatform/race-condition` @ `33c1ff8` (cloned & read locally)
**Scope:** Read-only verification only. No cloud deploy, no `terraform apply`, zero live LLM
runs executed. Cost-incurring steps are gated pending your go-ahead.

> **Confidence convention:** **[VERIFIED]** = I read the file or ran the command.
> **[INFERRED]** = reasoned from verified evidence but not directly executed.
> **[DRIFT]** = differs from the stated anchor fact; flagged for you.

---

## 1. Fact-check results

| Anchor fact | Status | Evidence |
|---|---|---|
| Repo `GoogleCloudPlatform/race-condition` exists | **[VERIFIED]** | `git clone` succeeded; HEAD `33c1ff8`. GitHub repo description + web search corroborate. |
| Open-sourced from **Google Cloud Next '26 Developer Keynote** (NOT I/O) | **[VERIFIED]** | `README.md` L23/27: "Originally demoed at the Google Cloud Next '26 Developer Keynote." GitHub one-liner says the same. No doc says I/O. (Easter egg: frontend port `9119` = Las Vegas ZIP 89119, Michelob Ultra Arena, the Next '26 venue.) |
| Three planner variants: `planner`, `planner_with_eval`, `planner_with_memory` | **[VERIFIED]** | `agents/` listing shows all three. README demo table: `Ctrl+1` base, `Ctrl+2` eval, `Ctrl+3` memory. |
| `planner_with_eval` = LLM-as-Judge gating | **[VERIFIED]** | `agents/planner_with_eval/agent.py` docstring + README: 7-criteria eval, 6 judged by an LLM via Vertex AI Eval API, 1 deterministic. |
| `planner_with_memory` = AlloyDB persistence | **[VERIFIED]** | README: "Planner backed by AlloyDB route memory." Skill doc confirms pgvector/AlloyDB. |
| Hub session pattern in `internal/hub/` (Go gateway, WebSocket, A2A routing, anti-thundering-herd batching) | **[VERIFIED]** | `internal/hub/{hub.go, switchboard.go, subscription.go}` + README. Batching = spawn-queue sharding (8 shards, FNV-1a) + `BatchEnqueueOrchestration` (N→1 round-trips). |
| A2A client + discovery in `internal/agent/`; `/.well-known/agent-card.json` | **[VERIFIED]** | `internal/agent/catalog.go` + README. Standard agents: `/.well-known/agent-card.json`. Agent Engine: `/a2a/v1/card`. |
| Default **runner** model `gemini-3.1-flash-lite-preview` | **[VERIFIED, with nuance]** | `.env.example` L148: `# RUNNER_MODEL=gemini-3.1-flash-lite-preview  # Default (Vertex AI)`. Nuance: it's the **runner** default, set via `RUNNER_MODEL`, and the line is **commented** (active default comes from config/code). |
| Local free option `ollama_chat/gemma4:e2b` | **[VERIFIED]** | `.env.example` L148, same line ("For local Ollama: ollama_chat/gemma4:e2b"). |
| Production `openai/gemma-4-E4B-it` on vLLM | **[VERIFIED]** | `.env.example` L161 (vLLM on GKE / Gemma 4), with `VLLM_API_URL`. |
| Simulator = `SequentialAgent`: pre-race → race engine (`LoopAgent`, ≤200 ticks) → post-race | **[VERIFIED]** | `agents/simulator/agent.py`: `SequentialAgent(sub_agents=[pre_race_agent, race_engine, post_race_agent])`; `race_engine = LoopAgent(max_iterations=200, ...)`. README L354 + skill doc agree. |
| WS3 model `gemini-3.5-flash` is a real, current model | **[VERIFIED]** | Web search: Gemini 3.5 Flash = newest Flash generation (May 2026). |

### Drift / inconsistencies to be aware of

- **[DRIFT — minor, internal to the repo]** The `planner_with_eval` README says the judge is a
  **"Gemini 3 Pro judge model,"** but `.env.example` sets `EVALUATOR_MODEL=gemini-3-flash-preview`.
  The repo's own doc and config disagree on the judge model. Decide which to cite; don't claim "Pro"
  on the strength of the README alone.
- **[NUANCE]** "Default runner model" ≠ "default model everywhere." The simulator's sub-agents
  hardcode `gemini-flash-lite-latest`; shared utils default to `gemini-3-flash-preview`. Phrase any
  proposal claim as "the *runner* default is `gemini-3.1-flash-lite-preview`," not "the system runs
  on `gemini-3.1-flash-lite-preview`."
- **[DRIFT — wording]** The in-repo skill (`exploring-the-codebase`) says the gateway "routes by
  declared skill." The actual Go code routes by **agent type/name + dispatch mode** (capability
  extension `n26:dispatch/1.0`) and, at the hub, by **session/simulation ID** — not by matching the
  card's advertised `AgentSkill`s. Cards *do* declare skills, but skills aren't the routing key.
  See §3.

---

## 2. The runtime answer (Step 1.4 — the question that drives your Codelab)

**Answer: BOTH are supported. In-process is the dominant pattern in the reference repo, and it is
exactly what your beginner Codelab should use. Distributed A2A is a scale/deployment concern, not a
requirement for one agent to invoke another.**

### In-process (same Python process, function-boundary handoff) — **[VERIFIED]**

ADK constructs, all used in `agents/simulator/agent.py`:

- **`AgentTool`** (`google.adk.tools.agent_tool.AgentTool`) — wraps a whole agent as a callable tool.
  The root simulator `LlmAgent` invokes its pipeline with
  `AgentTool(agent=pipeline, skip_summarization=True)`. **This is the literal "invoke one agent from
  another in-process" mechanism you asked about.**
- **`SequentialAgent`** (`google.adk.agents`) — composes sub-agents in order, in-process:
  `simulation_pipeline = SequentialAgent(sub_agents=[pre_race_agent, race_engine, post_race_agent])`.
- **`LoopAgent`** (`google.adk.agents`) — in-process iteration:
  `race_engine = LoopAgent(max_iterations=200, sub_agents=[tick_agent])`.

None of these require Redis, a gateway, agent cards, or HTTP. They run in one process and can run in
a single Colab notebook.

### Distributed A2A (separate deployments + agent-card-over-HTTP discovery + gateway routing) — **[VERIFIED]**

- Cross-process handoffs (e.g. **planner → simulator**) go over A2A. The single entry point is
  `call_agent(tool_context, agent_name, message)` in `agents/utils/communication.py`.
- Agents are deployed via `create_a2a_deployment(...)`, which publishes an agent card; the Go gateway
  discovers cards (`internal/agent/catalog.go`) and dispatches via HTTP poke (`/orchestration`) or
  A2A `message/send` JSON-RPC depending on the agent's declared dispatch mode.
- This layer exists to fan out to **thousands of WebSocket clients and hundreds of runner agents
  across multiple gateway instances** — i.e., the keynote's scale problem.

### What this means for Copa Chalkboard

Your **Match Scout → Tactical Analyst handoff + validation gate can be 100% in-process** using
`AgentTool` (or a `SequentialAgent` of `[scout, gate, analyst]`). You do **not** need the gateway,
Redis, Memorystore, Cloud SQL, NAT, agent cards, or Cloud Run for the core lesson. That keeps the
Codelab in a single Colab with zero standing infra cost.

> **[INFERRED]** I verified this from the repo's own usage of standard ADK constructs, not by
> executing the ADK docs. To cite authoritatively in the proposal, link the ADK multi-agent docs for
> `AgentTool` / `SequentialAgent` (see §6).

---

## 3. Hub / A2A delta table (Workstream 1 deliverable)

| Mechanism | How race-condition does it | In-process possible for a Colab? | Notes |
|---|---|---|---|
| **Message routing** | Protobuf `gateway.Wrapper` envelope routed by the Go hub in 3 phases: global observers (`session_id==""`), targeted `destination[]`/`session_id`, then `simulation_id` subscribers (O(1) reverse index). Cross-instance via Redis Pub/Sub "Switchboard." | **Yes — trivially.** In-process, a handoff is a function return value; no envelope or router needed. | `Wrapper` fields: `timestamp, type, request_id, session_id, payload(bytes), origin{type,id,session_id}, destination[], status, event, metadata(bytes), simulation_id`. |
| **Agent discovery** | HTTP fetch of `/.well-known/agent-card.json` (Agent Engine: `/a2a/v1/card`) from `AGENT_URLS`, cached 30 s with double-checked locking (anti-thundering-herd). | **N/A — not needed.** In-process you hold a direct Python reference to the agent object. | Card carries typed `Name/URL/BaseURL/Version` + raw JSON passthrough; dispatch mode via `n26:dispatch/1.0` extension. |
| **Scout→Analyst-style handoff** | Cross-process via `call_agent(tool_context, agent_name, message)` → A2A `message/send` JSON-RPC. In-process via `AgentTool(agent=...)` and `SequentialAgent`/`LoopAgent` sub-agents. | **Yes.** Use `AgentTool` or `SequentialAgent([scout, gate, analyst])`. | App-level A2A message between planner→simulator is JSON: `{action: "verify"|"execute", narrative, route(GeoJSON), simulation_config{duration_seconds, tick_interval_seconds, runner_count, runner_type}}`. |
| **Eval / validation gate** | `planner_with_eval`: `evaluate_plan` tool scores a plan on **7 criteria** (6 LLM-judged in one Vertex AI Eval API call + 1 deterministic distance check), normalizes to 0–100. **Pass = overall ≥ 75 AND no high-severity finding (<40)**; heuristic keyword fallback if the API is down. | **Yes.** The gate is just a tool/function inside one agent; replicate as an in-process "LLM-as-Judge" tool that returns pass/fail + score. | This is the closest analog to your Quality Gate. The gate runs in-process; only the subsequent planner→simulator step is A2A. |
| **Session / state management** | Redis-backed `DistributedRegistry` (session→agent-type, session→simulation) with TTLs + lazy `Reap()`; `InMemorySessionService` for local/dev. ADK session state carries data across sub-agents (`callback_context.state[...]`). | **Yes.** Use ADK in-memory session state (`tool_context.state` / `callback_context.state`) — no Redis. | Repo's own "pragmatic shortcuts" note: `InMemorySessionService` locally, `VertexAiSessionService` in cloud — both intentional. |

---

## 4. Reference-app status (Workstream 2)

### Prerequisites — **[VERIFIED]**

`Makefile`: `PREREQS := go node uv docker`. README requirements: Go (badge), **Python 3.13**
(`.python-version` = `3.13`), **uv** (latest), **Node.js 24+**, **Docker + Compose**.

### Why I did **not** run `make init` / `make start`

My shell is a **separate, ephemeral Linux sandbox — not your Windows machine.** Running the 13-process
app there would (a) not give *you* the 3D frontend you need to see, and (b) fails prereqs anyway:

| Tool | Sandbox has | Required | OK? |
|---|---|---|---|
| Go | **missing** | 1.25+ | ❌ |
| Docker | **missing** | latest | ❌ |
| Python | 3.10.12 | 3.13 | ❌ |
| Node | 22.x | 24+ | ❌ |
| uv | 0.11.2 | latest | ✅ |

So Workstream 2 is set up + handed off rather than executed. **You must run it locally or in Cloud
Shell.** Good news for guardrail #5: **`.env` IS gitignored** (`.gitignore` L38–40), so creating a
local `.env` from `.env.example` is safe.

### What the commands do (read from the Makefile)

- `make check-prereqs` → checks `go node uv docker`.
- `make init` → `cp .env.example .env` (if absent) → `uv sync` → `npm install` (frontend + admin +
  tester) → `docker compose up -d` (Redis, Pub/Sub emulator, Postgres) → build Go services.
- `make start` → launches all services via Honcho. Ports: **frontend `9119`**, **admin dashboard
  `9100`**, **agent debug console `9111`**.

### HUMAN-HANDOFF CHECKLIST — Cached mode (free), do this on your machine

- [ ] `make check-prereqs`, then `make init`, then `make start`.
- [ ] Open `http://localhost:9119`; confirm it boots in **Cached** mode (no LLM cost).
- [ ] `Ctrl+2` — "Creating multi-agent systems" = `planner_with_eval` (LLM-as-Judge). Watch the eval
      gate. **[VERIFIED this hotkey↔variant mapping against the README.]**
- [ ] `Ctrl+1` — base planner alone, for contrast. **[VERIFIED]**
- [ ] Open agent debug console `http://localhost:9111`; screenshot the A2A message flow.
- [ ] Note: does the eval gate visibly reject/revise any output?
- [ ] Admin health: `http://localhost:9100`.

### Live run (Step 2.5) — **GATED, ~$3–4**

Not actionable until the app is running locally (I cannot toggle `Ctrl+L` in your frontend). When you
run it: toggle Live with `Ctrl+L`, then tell me and I'll parse `logs/simulation.log` for the real A2A
message sequence, model calls, and errors — **one run only**.

---

## 5. Multimodal smoke-test (Workstream 3) — set up, **GATED on cost**

- Script written and self-verified: `experiments/scout-smoketest/copa_scout_smoketest.py`.
  - `gemini-3.5-flash`; key read from `GEMINI_API_KEY` (never hardcoded/committed).
  - **Hard caps enforced in code:** 5 free-form calls + at most 1 structured-output fallback =
    **6 absolute max**; the loop refuses to exceed it.
  - Image is **verified (HTTP 200 + image content-type) before any paid call**, so a bad URL wastes
    zero calls. Default = a CC-licensed Wikimedia Commons football match photo via the canonical
    `Special:FilePath` redirect; override with `IMAGE_URL`.
  - Offline-tested: JSON parser + schema validator behave correctly on good/bad inputs.
- **No recommendation yet** — I have not made any API call. After it runs I'll deliver the scoring
  table (`Run | Valid JSON? | players_detected | schema honored?`), the GO/NO-GO, and all raw outputs
  for your manual zone-plausibility check.

---

## 6. Open questions / things only you can do

1. **Run the local app + the Cached-mode walkthrough** (checklist in §4). I can't see the 3D frontend.
2. **Eyeball tactical-zone plausibility** on the 5 raw Scout outputs (after the smoke-test runs) — I
   can't verify zones against an image I can't independently judge.
3. **Decide the live run** (~$3–4, one run) — and run `Ctrl+L` yourself when ready.
4. **Confirm the smoke-test image** resolves (or set `IMAGE_URL` to a CC photo you prefer).
5. **Cite the ADK in-process constructs authoritatively** — read the ADK multi-agent docs for
   `AgentTool` / `SequentialAgent` and link them in the proposal (Google PMs will expect a doc cite,
   not just a repo cite). Repo evidence is solid; doc cite makes it bulletproof.
6. **Pick the evaluator model to cite** given the repo's own Pro-vs-flash inconsistency (§1).

---

## 7. Proposal-ready claims (verified-only, phrased conservatively)

Safe to put in front of Google:

- The `race-condition` reference architecture was open-sourced from the **Google Cloud Next '26
  Developer Keynote** and ships **three planner variants** (`planner`, `planner_with_eval`,
  `planner_with_memory`), where `planner_with_eval` implements an **LLM-as-Judge** evaluation gate
  (7 criteria; pass threshold ≥ 75/100 with no high-severity finding). **[VERIFIED]**
- The simulator is an **ADK `SequentialAgent` pipeline** (pre-race → `LoopAgent` race engine, ≤ 200
  ticks → post-race), and the root agent invokes that pipeline **in-process via `AgentTool`**.
  **[VERIFIED]**
- **ADK supports in-process, function-boundary agent-to-agent composition** (`AgentTool`,
  `SequentialAgent`, `LoopAgent`). A two-agent Scout→Analyst handoff with a validation gate can run
  entirely **in a single process / Colab with no gateway, no Redis, and no Cloud Run**. **[VERIFIED
  from repo usage; INFERRED as a general ADK guarantee — confirm with ADK docs.]**
- Agents in the distributed deployment discover each other via **`/.well-known/agent-card.json`** and
  communicate over **A2A `message/send` JSON-RPC**; the Go gateway/hub adds **anti-thundering-herd
  batching** (spawn-queue sharding + pipelined enqueues) for keynote-scale fan-out. **[VERIFIED]**
- The reference app's distributed infrastructure (Memorystore, Cloud SQL, Cloud NAT) is a
  **scale/deployment concern, separable from the agent-communication lesson**. **[VERIFIED from repo
  structure + the repo's own "pragmatic shortcuts" notes.]**

Do **NOT** yet claim (unverified):

- Any claim that the system "runs on `gemini-3.1-flash-lite-preview`" generally — that's the *runner*
  default only. **[DRIFT]**
- That the eval judge is "Gemini 3 Pro" — the repo's config says `gemini-3-flash-preview`. **[DRIFT]**
- Any reliability claim about the Scout vision step — pending the smoke-test run.
- Anything about the live on-stage behavior or visual UX — pending your local walkthrough.
