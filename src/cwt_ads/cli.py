"""Command line entry point.

    python -m cwt_ads.cli run                 # the whole team, end to end
    python -m cwt_ads.cli run --offline       # no keys needed, fixtures + reference scripts
    python -m cwt_ads.cli stage script --run run_20260907_120000
    python -m cwt_ads.cli kanban bootstrap    # same team, on the Hermes Kanban board
    python -m cwt_ads.cli doctor              # what is configured, what is missing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import hermes_runtime, kanban, pipeline
from .config import OUTPUT_DIR, env, load_env
from .logging_utils import banner, fail, ok, table, warn
from .render import openmontage
from .tools import search

STAGE_KEYS = {
    "mine": "mine",
    "insight": "insight",
    "research": "research",
    "script": "script",
    "video": "video",
}


def _latest_run() -> str | None:
    pointer = OUTPUT_DIR / "LATEST_RUN.txt"
    if pointer.exists():
        return pointer.read_text(encoding="utf-8").strip()
    runs = sorted(p.name for p in OUTPUT_DIR.glob("run_*") if p.is_dir())
    return runs[-1] if runs else None


def cmd_run(args: argparse.Namespace) -> int:
    pipeline.run(offline=args.offline, render=not args.no_render, run_id=args.run)
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    run_id = args.run or _latest_run()
    if not run_id:
        fail("no run id given and no previous run found. Start one with: cwt_ads.cli run")
        return 1
    pipeline.run(
        offline=args.offline,
        render=not args.no_render,
        run_id=run_id,
        stages=(STAGE_KEYS[args.name],),
    )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    load_env()
    banner("Doctor", "what this machine can currently do")

    def state(value: object, good: str, bad: str) -> str:
        return good if value else bad

    rows = [
        [
            "LLM",
            state(env("OPENROUTER_API_KEY") or env("NVIDIA_API_KEY"), "ready", "MISSING"),
            "OPENROUTER_API_KEY or NVIDIA_API_KEY",
        ],
        [
            "Hermes runtime",
            state(hermes_runtime.hermes_home(), "in-process AIAgent", "direct transport"),
            hermes_runtime.describe_runtime(),
        ],
        [
            "Hermes CLI",
            state(kanban.hermes_cli(), "ready", "not installed"),
            "needed only for the Kanban board path",
        ],
        [
            "Apify",
            state(env("APIFY_TOKEN"), "ready", "MISSING"),
            "APIFY_TOKEN - Meta Ad Library mining",
        ],
        [
            "Tavily",
            state(env("TAVILY_API_KEY"), "ready", "missing"),
            "TAVILY_API_KEY - last-month research",
        ],
        [
            "Exa",
            state(env("EXA_API_KEY"), "ready", "missing"),
            "EXA_API_KEY - last-month research",
        ],
        [
            "OpenMontage",
            state(openmontage.home(), "ready", "not configured"),
            "OPENMONTAGE_HOME - final MP4 render",
        ],
        [
            "ffmpeg",
            state(openmontage.ffmpeg_available(), "ready", "not on PATH"),
            "required by OpenMontage composition",
        ],
    ]
    table("Configuration", ["Component", "Status", "Notes"], rows)

    providers = search.available_providers()
    if not providers:
        warn("no research provider configured - the Market Researcher will run unsourced")
    if not (env("OPENROUTER_API_KEY") or env("NVIDIA_API_KEY")):
        warn("no LLM key - use `run --offline` to exercise the full pipeline on fixtures")
    ok("doctor complete")
    return 0


def cmd_kanban(args: argparse.Namespace) -> int:
    if args.action == "watch":
        kanban.watch()
        return 0
    run_id = args.run or pipeline.new_run_id()
    banner("Hermes Kanban", "run " + run_id)
    kanban.bootstrap(
        run_id,
        offline=args.offline,
        render=not args.no_render,
        dry_run=(args.action == "plan"),
    )
    return 0


def cmd_setup_hermes(args: argparse.Namespace) -> int:
    """Clone hermes-agent into vendor/ so AIAgent can be imported in-process."""
    import subprocess

    from .config import ROOT

    target = Path(args.path) if args.path else ROOT / "vendor" / "hermes-agent"
    if (target / "run_agent.py").is_file():
        ok("hermes-agent already present at " + target.as_posix())
        print("Add this to your .env:  CWT_HERMES_CHECKOUT=" + target.as_posix())
        return 0

    print("This will clone https://github.com/NousResearch/hermes-agent into:")
    print("  " + target.as_posix())
    print("and then you will need to run `uv sync` inside it.")
    if not args.yes:
        reply = input("Proceed? [y/N] ").strip().lower()
        if reply != "y":
            print("aborted")
            return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/NousResearch/hermes-agent.git", str(target)],
        check=False,
    )
    if result.returncode != 0:
        fail("clone failed")
        return 1
    ok("cloned. Now run:  cd " + target.as_posix() + " && uv sync")
    print("Then add to .env:  CWT_HERMES_CHECKOUT=" + target.as_posix())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cwt_ads",
        description="CrowdWisdom Trading - cinematic video ads agent team (Hermes)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--offline", action="store_true", help="no network: fixtures + reference scripts")
        p.add_argument("--no-render", action="store_true", help="write the render brief but do not render")
        p.add_argument("--run", help="run id (defaults to a new timestamped run)")

    p_run = sub.add_parser("run", help="run the full five-agent pipeline")
    add_common(p_run)
    p_run.set_defaults(func=cmd_run)

    p_stage = sub.add_parser("stage", help="run a single stage against an existing run")
    p_stage.add_argument("name", choices=sorted(STAGE_KEYS))
    add_common(p_stage)
    p_stage.set_defaults(func=cmd_stage)

    p_doc = sub.add_parser("doctor", help="report what is configured and what is missing")
    p_doc.set_defaults(func=cmd_doctor)

    p_kan = sub.add_parser("kanban", help="run the team on the Hermes Kanban board")
    p_kan.add_argument("action", choices=["bootstrap", "plan", "watch"])
    add_common(p_kan)
    p_kan.set_defaults(func=cmd_kanban)

    p_setup = sub.add_parser("setup-hermes", help="clone hermes-agent for the in-process runtime")
    p_setup.add_argument("--path", help="where to clone (default: vendor/hermes-agent)")
    p_setup.add_argument("--yes", action="store_true", help="do not prompt")
    p_setup.set_defaults(func=cmd_setup_hermes)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        warn("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
