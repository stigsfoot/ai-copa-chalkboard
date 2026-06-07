# ADR 0002 — Force structured output for the Scout's vision step

- **Status:** Accepted
- **Date:** 2026-06-07

## Context

The Match Scout is a multimodal call: image in, JSON out. Vision models are
inconsistent about returning *clean, schema-valid* JSON when merely asked to in
the prompt — they wrap it in prose, add code fences, or drift from the schema.
For a beginner Codelab, a flaky parse step is a terrible first experience.

The `google-genai` SDK supports `response_mime_type="application/json"` plus a
`response_schema` (a Pydantic model), which makes the model emit conformant JSON.

> The reliability of free-form JSON vs enforced structured output is exactly what
> `experiments/scout-smoketest/` measures. This ADR will be confirmed or revised
> by that test's GO/NO-GO result.

## Decision

The Scout always requests **structured output** with the `ScoutReport` Pydantic
model as the response schema. The parser (`parse_scout_output`) still tolerates a
stray code fence as a belt-and-braces fallback.

## Consequences

- **Good:** near-deterministic, schema-valid Scout output; the gate and Analyst
  can rely on the contract.
- **Good:** the Pydantic model is the single source of truth, reused for the
  schema, validation, and the typed handoff.
- **Trade-off:** if a chosen model/region doesn't support `response_schema`, fall
  back to prompt-only JSON + the tolerant parser. If the smoke-test returns
  NO-GO on imagery, swap the Scout's input to text match-logs — the rest of the
  pipeline is unchanged.
