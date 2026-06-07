# Copa Chalkboard ⚽🧠

A beginner Codelab: build a **two-agent tactical-analysis system** on Gemini +
[Google ADK](https://google.github.io/adk-docs/). A **Match Scout** looks at one
match frame and a **Tactical Analyst** turns its read into coaching advice — with
a **validation gate** guarding the handoff between them.

> The whole thing runs **in a single process** (one Colab notebook). No gateway,
> no Redis, no Cloud Run. The agent-to-agent handoff *is* the lesson.

This project mirrors the patterns in Google's
[`GoogleCloudPlatform/race-condition`](https://github.com/GoogleCloudPlatform/race-condition)
reference architecture (from the Google Cloud Next '26 Developer Keynote),
distilled to the smallest thing that teaches them. See
[`docs/codelab-verification-findings.md`](docs/codelab-verification-findings.md)
for exactly what was verified against that repo.

## What you'll learn

1. A **multimodal agent** (the Scout) that returns reliable structured JSON.
2. An **in-process A2A handoff** — one agent invoking another via ADK `AgentTool`.
3. A **validation gate** that refuses to pass a bad report downstream
   (the same idea as race-condition's LLM-as-Judge `planner_with_eval`).

## The flow

```
   frame ──▶ Match Scout ──▶ ScoutReport ──▶ [ validation gate ]
                                                   │ passed?
                                          no ◀─────┴─────▶ yes
                                       (stop, report      Tactical Analyst
                                        the issues)         │
                                                            ▼
                                                       AnalystReport
```

## Quickstart

```bash
# 1. Install (uv recommended)
make install            # or: pip install -e ".[dev,adk]"

# 2. Run the tests — no API key needed, fully offline
make test

# 3. Add your key (https://aistudio.google.com/apikey)
cp .env.example .env    # then edit .env  (it's gitignored)
export GEMINI_API_KEY=...          # or rely on .env

# 4. Run the two-agent pipeline on a match image
make run IMAGE=https://commons.wikimedia.org/wiki/Special:FilePath/Example_match.jpg
#   or: python -m copa_chalkboard --image ./assets/frame.jpg
```

## Layout

```
copa_chalkboard/
  schemas.py     # the typed contracts between agents (start here)
  scout.py       # Match Scout — vision -> ScoutReport (genai + ADK paths)
  gate.py        # validation gate — a PURE, tested function
  analyst.py     # Tactical Analyst — ScoutReport -> AnalystReport
  pipeline.py    # wiring: plain-Python orchestrator + ADK-native (AgentTool)
  __main__.py    # CLI: python -m copa_chalkboard --image ...
tests/           # offline unit tests (TDD; no key, no network)
docs/adr/        # why the architecture is the way it is
experiments/scout-smoketest/   # is the vision step reliable enough? (delivery risk)
CONTEXT.md       # the ubiquitous language — read before contributing
CLAUDE.md        # ground rules for coding agents
```

## Two ways to see the handoff

- **`run_pipeline_local`** (`pipeline.py`) — plain, readable Python. The model
  steps are injected, so the flow is unit-tested with fakes. This is the
  "what's actually happening" view.
- **`make_adk_pipeline`** (`pipeline.py`) — the ADK-native version: a root
  `LlmAgent` calls the Scout and Analyst as `AgentTool`s, in-process. Requires
  `pip install "copa-chalkboard[adk]"`.

## Engineering practices

Adapted from [Matt Pocock's skills](https://github.com/mattpocock/skills):
a `CONTEXT.md` shared language, `docs/adr/` decision records, a green-by-default
TDD harness, deep modules with simple surfaces, and secrets via env only.

## License

Apache-2.0.
