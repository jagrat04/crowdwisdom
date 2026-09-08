#!/usr/bin/env python3
"""Create the CrowdWisdom board on Hermes Kanban.

    python hermes/kanban/bootstrap.py --dry-run     # print the plan, change nothing
    python hermes/kanban/bootstrap.py               # create profiles + linked tasks
    python hermes/kanban/bootstrap.py --offline     # tasks that need no API keys

Then watch it work:

    hermes kanban watch
    hermes dashboard        # the Kanban tab, drag-and-drop, live over websocket

This is a thin wrapper around `cwt_ads.kanban` so the board can be created
without importing the pipeline package by hand.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from cwt_ads import kanban, pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="run id (default: a new timestamped one)")
    parser.add_argument("--dry-run", action="store_true", help="print commands, change nothing")
    parser.add_argument("--offline", action="store_true", help="tasks run with --offline")
    parser.add_argument("--no-render", action="store_true", help="skip the MP4 render task flag")
    args = parser.parse_args()

    run_id = args.run or pipeline.new_run_id()
    ids = kanban.bootstrap(
        run_id,
        offline=args.offline,
        render=not args.no_render,
        dry_run=args.dry_run,
    )
    return 0 if (ids or args.dry_run) else 1


if __name__ == "__main__":
    sys.exit(main())
