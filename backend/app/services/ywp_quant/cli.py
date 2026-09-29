"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import analyze_document


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze a market ticket with the YWP quantitative gate"
    )
    parser.add_argument("input", type=Path, help="JSON input document")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    result = analyze_document(json.loads(args.input.read_text(encoding="utf-8")))
    rendered = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
