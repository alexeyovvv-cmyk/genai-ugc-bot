#!/usr/bin/env python3
"""
Thin CLI wrapper around the Shotstack renderer.

Example:
    SHOTSTACK_API_KEY=... python assemble.py talking_head_overlay.json
"""
from __future__ import annotations

import argparse
import json

from render.shotstack import ShotstackError, render_from_spec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a Shotstack video from a JSON specification.")
    parser.add_argument("spec", help="Path to JSON spec file.")
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit render and exit immediately without polling status.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        result = render_from_spec(args.spec, wait=not args.no_wait)
    except ShotstackError as exc:
        print(f"[ASSEMBLE] ❌ Shotstack error: {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # pragma: no cover
        print(f"[ASSEMBLE] ❌ Unexpected error: {exc}")
        raise SystemExit(1) from exc

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
