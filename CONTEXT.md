# CONTEXT — the ubiquitous language of Copa Chalkboard

> A shared vocabulary so humans and agents name the same thing the same way.
> (Borrowed from Matt Pocock's `grill-with-docs` / `CONTEXT.md` practice and
> Eric Evans' Domain-Driven Design.) When you add code, reuse these terms.

## The system in one sentence

A **Match Scout** looks at one match **frame**, emits a **ScoutReport**, a
**validation gate** decides whether that report is trustworthy, and if so a
**Tactical Analyst** turns it into an **AnalystReport** — all in one process.

## Domain terms

| Term | Means |
|---|---|
| **Frame** | A single still image of a football (soccer) match. The only raw input. |
| **Match Scout** (Scout) | The multimodal agent. Vision in, structured `ScoutReport` out. Does NOT analyze tactics. |
| **ScoutReport** | The typed contract the Scout emits: `players_detected`, `player_positions[]`, `ball_zone`, `tactical_note`. |
| **Zone** | A third of the pitch: `defensive` \| `midfield` \| `attacking`. |
| **Validation gate** (the gate) | A pure function that scores a `ScoutReport` 0–100 and returns pass/fail. Guards the handoff. |
| **Critical finding** | A gate issue severe enough to force a fail regardless of score (e.g. an implausible player count). |
| **Handoff** | The in-process pass of a *validated* `ScoutReport` from Scout to Analyst. This is the "A2A" moment. |
| **Tactical Analyst** (Analyst) | The reasoning agent. Reads the `ScoutReport` only (never the image), emits an `AnalystReport`. |
| **AnalystReport** | `summary`, `key_observations[]`, `recommended_adjustment`, `confidence`. |
| **In-process A2A** | One agent invoking another inside a single Python process (ADK `AgentTool` / `SequentialAgent`) — no network, no gateway. |
| **Distributed A2A** | The other style: agents as separate services, discovered via `/.well-known/agent-card.json`, talking over HTTP/JSON-RPC. Not needed here. |

## Naming rules

- Code identifiers use these exact words: `ScoutReport`, not `vision_result`;
  `gate`, not `validator2`; `handoff`, not `transfer`.
- The Scout never reasons about tactics; the Analyst never touches pixels. If a
  change blurs that line, it's probably wrong.
