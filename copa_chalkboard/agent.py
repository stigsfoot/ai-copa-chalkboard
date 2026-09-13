"""``adk web`` / ``adk run`` entry point: the Workflow graph as ``root_agent``.

    export GEMINI_API_KEY=...
    adk web .            # from the repo root; pick "copa_chalkboard" in the UI

Importing this module imports google-adk, so nothing else in the package
imports it (rule: tests stay importable without ADK).
"""

from .pipeline import make_adk_pipeline

root_agent = make_adk_pipeline()
