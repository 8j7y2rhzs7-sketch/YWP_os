"""Attach YWP OS to the existing DECISION ENGINE product on Whop.

Does not create a product or plan. Requires WHOP_API_KEY and
NEXT_PUBLIC_WHOP_APP_ID from Whop Dashboard → Developer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.whop_experience import link_decision_engine_experience  # noqa: E402


def main() -> int:
    try:
        result = link_decision_engine_experience()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
