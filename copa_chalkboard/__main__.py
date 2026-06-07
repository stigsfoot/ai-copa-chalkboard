"""CLI entry point: run the full Scout -> Gate -> Analyst pipeline on one image.

Usage:
    export GEMINI_API_KEY=...
    python -m copa_chalkboard --image https://.../match-frame.jpg
    # or a local file:
    python -m copa_chalkboard --image ./assets/frame.jpg

This uses the plain-Python pipeline (run_pipeline_local) with the real
google-genai model steps. The ADK-native pipeline lives in pipeline.make_adk_pipeline.
"""

from __future__ import annotations

import argparse
import sys

from .pipeline import run_pipeline_local


def _load_image(source: str) -> tuple[bytes, str]:
    """Load image bytes from a URL or local path. Returns (bytes, mime_type)."""
    if source.startswith(("http://", "https://")):
        import requests

        resp = requests.get(
            source, timeout=30, headers={"User-Agent": "copa-chalkboard/0.1"}
        )
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "image/jpeg")
        if not ctype.startswith("image/"):
            raise SystemExit(f"URL did not return an image (Content-Type={ctype!r}).")
        return resp.content, ctype
    with open(source, "rb") as f:
        data = f.read()
    mime = "image/png" if source.lower().endswith(".png") else "image/jpeg"
    return data, mime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copa Chalkboard two-agent pipeline.")
    parser.add_argument("--image", required=True, help="Image URL or local path.")
    args = parser.parse_args(argv)

    image_bytes, mime = _load_image(args.image)
    result = run_pipeline_local(image_bytes, mime)

    print("=== ScoutReport ===")
    print(result.report.model_dump_json(indent=2))
    print("\n=== Gate ===")
    print(result.gate.model_dump_json(indent=2))
    if result.analysis is None:
        print("\nGate did NOT pass — Analyst was not invoked.")
        return 1
    print("\n=== AnalystReport ===")
    print(result.analysis.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
