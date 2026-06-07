# Architecture Guidelines

You must respect the following architectural decisions when modifying the codebase:

1.  **In-Process Handoff**: Keep agent communication in-process by default (using `AgentTool` inside a single process). Do not add distributed infrastructure (e.g. gateways, pub/sub, HTTP routing) to the core pipeline.
2.  **Pure Validation Gate**: The validation gate (`gate.py`) must remain a pure function of `ScoutReport`. Do not introduce I/O, network requests, or model calls inside `gate.py`.
3.  **Offline-Capable Tests**: Ensure `python -m pytest` runs fully offline and does not require an API key or having `google-adk` installed.
4.  **Lazy Imports**: Lazy-import SDKs (like `google.genai` and `google.adk`) inside the functions that use them to prevent import-time side effects and keep tests offline-capable.
