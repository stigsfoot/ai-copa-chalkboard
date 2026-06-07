# Scout vision-reliability smoke-test

**Question this answers:** is the Match Scout's vision step reliable enough for a
beginner Codelab, or should the Codelab fall back to text match-logs? This is the
single biggest delivery-risk decision (see `docs/adr/0002`).

## What it does

Sends the **same image + same prompt** to `gemini-3.5-flash` **5 times**, asking
for only schema-valid JSON, and scores each run. If any run is invalid, it makes
**one** more call with enforced structured output to see if that fixes it.

- **Hard cap: 6 Gemini API calls**, enforced in code.
- API key from `GEMINI_API_KEY` only — never hardcoded or committed.
- The image is verified (HTTP 200 + image content-type) **before** any paid call,
  so a bad URL wastes zero calls.

## Run it

```bash
export GEMINI_API_KEY=...
pip install google-genai requests
# optional: override the default CC-licensed image
export IMAGE_URL="https://commons.wikimedia.org/wiki/Special:FilePath/Your_match.jpg"
python copa_scout_smoketest.py
```

## Reading the result

- **GO (keep imagery):** ≥ 4/5 runs valid + schema-honoring, counts stable (±1).
- **NO-GO (use text match-logs):** unreliable JSON, wild count swings, or obvious
  hallucination.

Either way, **the A2A handoff lesson is identical for imagery vs text** — the
vision step is garnish. The script also dumps all raw outputs so you can eyeball
whether the tactical zones are plausible (a human check the script can't make).
