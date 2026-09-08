"""The distributed path: this team on the Hermes Kanban board.

The local pipeline runs the five agents in one process. This module runs the
same five agents as five independent Hermes profiles claiming tasks off the
shared board at ~/.hermes/kanban.db, with real parent/child dependencies so the
dispatcher only starts an agent once its inputs exist.

That is what the board recording in the submission shows: five named agents,
work moving through triage -> ready -> running -> done, each handoff a row
anybody can read.

Everything here shells out to the `hermes` CLI. With `--dry-run` it prints the
exact commands instead of running them, so the plan is reviewable (and the repo
is useful) on a machine without Hermes installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import ROOT, pipeline
from .logging_utils import fail, ok, step, table, warn

PROFILES = {
    "ads_manager": "cwt_ads_manager",
    "insight_agent": "cwt_insight_miner",
    "research_agent": "cwt_market_researcher",
    "script_agent": "cwt_script_writer",
    "video_agent": "cwt_video_director",
}

STAGE_FOR_AGENT = {
    "ads_manager": "mine",
    "insight_agent": "insight",
    "research_agent": "research",
    "script_agent": "script",
    "video_agent": "video",
}


def hermes_cli() -> str | None:
    return shutil.which("hermes")


def _run(cmd: list[str], *, dry_run: bool, capture: bool = True) -> str:
    printable = " ".join(('"' + c + '"') if " " in c else c for c in cmd)
    if dry_run:
        print("  $ " + printable)
        return ""
    step("pipeline", printable)
    result = subprocess.run(cmd, capture_output=capture, text=True, timeout=180)
    if result.returncode != 0:
        warn((result.stderr or result.stdout or "").strip()[:400])
    return (result.stdout or "").strip()


def _task_body(agent_id: str, run_id: str, offline: bool, render: bool) -> str:
    stage = STAGE_FOR_AGENT[agent_id]
    cfg = next((a for a in pipeline()["agents"] if a["id"] == agent_id), {})
    flags = " --run " + run_id
    if offline:
        flags += " --offline"
    if stage == "video" and not render:
        flags += " --no-render"
    outputs = ", ".join(cfg.get("outputs", []))
    return "\n".join(
        [
            "CHARTER",
            (cfg.get("charter") or "").strip(),
            "",
            "HOW TO EXECUTE",
            "Run this from the repository root (" + ROOT.as_posix() + "):",
            "",
            "    python -m cwt_ads.cli stage " + stage + flags,
            "",
            "The stage reads the artifacts of its parent tasks out of",
            "output/" + run_id + "/ and writes its own there. Do not re-derive",
            "upstream work - if an input is missing, block the task rather than",
            "inventing the input.",
            "",
            "DONE WHEN",
            "output/" + run_id + "/ contains: " + (outputs or "the stage artifact"),
            "",
            "Then call kanban_complete() with the artifact paths in metadata.",
        ]
    )


def plan(run_id: str, *, offline: bool = False, render: bool = True) -> list[dict[str, Any]]:
    """The task graph, in dependency order."""
    tasks = []
    for cfg in pipeline()["agents"]:
        agent_id = cfg["id"]
        tasks.append(
            {
                "agent": agent_id,
                "profile": PROFILES[agent_id],
                "title": "[" + run_id + "] " + cfg["role"] + " - " + STAGE_FOR_AGENT[agent_id],
                "depends_on": [d for d in cfg.get("depends_on", [])],
                "body": _task_body(agent_id, run_id, offline, render),
                "outputs": cfg.get("outputs", []),
            }
        )
    return tasks


def ensure_profiles(*, dry_run: bool = False) -> None:
    """Create one Hermes profile per agent, pointed at this repo."""
    profiles_dir = ROOT / "hermes" / "profiles"
    for agent_id, profile in PROFILES.items():
        cfg = next((a for a in pipeline()["agents"] if a["id"] == agent_id), {})
        _run(
            [
                "hermes",
                "profile",
                "create",
                profile,
                "--description",
                cfg.get("role", agent_id) + " for CrowdWisdom video ads",
            ],
            dry_run=dry_run,
        )
    if not dry_run:
        ok(
            "profiles created. Reference config for each lives in "
            + profiles_dir.as_posix()
        )


def bootstrap(run_id: str, *, offline: bool = False, render: bool = True, dry_run: bool = False) -> dict[str, str]:
    """Create the board and the five linked tasks. Returns agent id -> task id."""
    cli = hermes_cli()
    if cli is None and not dry_run:
        fail(
            "`hermes` is not on PATH. Install it (see hermes/README.md) or re-run "
            "with --dry-run to print the plan."
        )
        return {}

    _run(["hermes", "kanban", "init"], dry_run=dry_run)
    ensure_profiles(dry_run=dry_run)

    ids: dict[str, str] = {}
    for task in plan(run_id, offline=offline, render=render):
        cmd = [
            "hermes",
            "kanban",
            "create",
            task["title"],
            "--assignee",
            task["profile"],
            "--body",
            task["body"],
            "--workspace",
            "dir:" + ROOT.as_posix(),
            "--idempotency-key",
            run_id + ":" + task["agent"],
            "--json",
        ]
        for dep in task["depends_on"]:
            if dep in ids:
                cmd += ["--parent", ids[dep]]
        out = _run(cmd, dry_run=dry_run)
        task_id = _extract_task_id(out) or ("t_" + task["agent"])
        ids[task["agent"]] = task_id

    _print_board(run_id, ids, dry_run)
    return ids


def _extract_task_id(stdout: str) -> str | None:
    import json as _json
    import re

    try:
        data = _json.loads(stdout)
        for key in ("id", "task_id"):
            if isinstance(data, dict) and data.get(key):
                return str(data[key])
    except (ValueError, TypeError):
        pass
    match = re.search(r"\bt_[A-Za-z0-9]+\b", stdout or "")
    return match.group(0) if match else None


def _print_board(run_id: str, ids: dict[str, str], dry_run: bool) -> None:
    table(
        ("PLANNED " if dry_run else "") + "Hermes Kanban board - " + run_id,
        ["Task", "Assignee profile", "Waits for", "Produces"],
        [
            [
                ids.get(t["agent"], "-"),
                t["profile"],
                ", ".join(ids.get(d, d) for d in t["depends_on"]) or "-",
                ", ".join(t["outputs"]),
            ]
            for t in plan(run_id)
        ],
    )
    if not dry_run:
        ok("watch it live:  hermes kanban watch      |      board UI:  hermes dashboard")


def watch() -> None:
    if hermes_cli() is None:
        fail("`hermes` is not on PATH")
        return
    subprocess.run(["hermes", "kanban", "watch"], check=False)
