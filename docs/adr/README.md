# Architecture Decision Records

Short, dated records of *why* — not *how*. Each ADR captures one decision, its
context, and its consequences, so a future reader (human or agent) doesn't
re-litigate a settled choice or accidentally reverse it.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-in-process-a2a-via-agenttool.md) | Stay in-process, not distributed services | Accepted (mechanism superseded by 0004) |
| [0002](0002-scout-structured-output.md) | Force structured output for the Scout's vision step | Accepted |
| [0003](0003-validation-gate-between-agents.md) | Put a pure validation gate between Scout and Analyst | Accepted |
| [0004](0004-workflow-graph-handoff.md) | Implement the handoff as an ADK 2.0 `Workflow` graph, not `AgentTool` | Accepted |

Format: Context → Decision → Consequences. Keep them short.
