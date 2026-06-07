# Ubiquitous Language Rules

You must use the following terms precisely in comments, schemas, and code implementations:

- **Frame**: A single still image of a football match. Do not refer to it as "pixels" or "input_image" in contracts.
- **Match Scout**: The vision agent. Vision in, structured `ScoutReport` out. Do NOT perform tactical analysis here.
- **ScoutReport**: The typed contract emitted by the Match Scout.
- **Zone**: One of `defensive`, `midfield`, or `attacking`.
- **Validation Gate**: The pure Python function guarding the handoff.
- **Tactical Analyst**: The reasoning agent. Consumes only the `ScoutReport` (never the image) and outputs the `AnalystReport`.
- **AnalystReport**: The typed contract emitted by the Tactical Analyst.
- **Handoff**: The process of passing the validated `ScoutReport` to the Tactical Analyst.

Never merge the Match Scout and Tactical Analyst roles. Ensure that filenames and classes match these rules.
