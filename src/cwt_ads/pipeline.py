"""The local pipeline: five agents, one run folder, six artifacts.

This is the single-process path. The same five agents can instead be run as
independent Hermes profiles claiming tasks off the Hermes Kanban board - see
`cwt_ads.kanban` and `hermes/kanban/` - which is what the board recording in the
submission shows. Both paths call the same agent classes and write the same
artifacts.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import hermes_runtime
from .agents.ads_manager import AdsManagerAgent
from .agents.insight_agent import InsightAgent
from .agents.research_agent import ResearchAgent
from .agents.script_agent import ScriptAgent
from .agents.video_agent import VideoAgent
from .config import OUTPUT_DIR, run_dir
from .logging_utils import banner, ok, step, table, warn
from .schemas import InsightReport, ResearchReport, StoryboardBundle, WinningAdsReport

STAGES = ("mine", "insight", "research", "script", "video")

_ARTIFACTS = {
    "ads": ("01_winning_ads.json", WinningAdsReport),
    "insights": ("02_ad_insights.json", InsightReport),
    "research": ("03_research.json", ResearchReport),
    "bundle": ("04_storyboards.json", StoryboardBundle),
}


def load_artifact(out: Path, key: str):
    """Read a previous stage's artifact off disk.

    Stages are run in one process locally, but as separate Hermes Kanban
    workers in the distributed path - where the only handoff between agents is
    the run folder. Loading from disk is what makes both paths identical.
    """
    name, model = _ARTIFACTS[key]
    path = out / name
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("_meta", None)
    try:
        return model(**payload)
    except Exception as exc:  # noqa: BLE001
        warn("could not load " + name + ": " + str(exc))
        return None


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


def _point_latest_at(path: Path) -> None:
    """Leave a `output/latest` pointer. Symlink where allowed, file where not."""
    latest = OUTPUT_DIR / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            if latest.is_dir() and not latest.is_symlink():
                shutil.rmtree(latest, ignore_errors=True)
            else:
                latest.unlink()
        latest.symlink_to(path, target_is_directory=True)
    except (OSError, NotImplementedError):
        (OUTPUT_DIR / "LATEST_RUN.txt").write_text(path.name, encoding="utf-8")


def run(
    *,
    offline: bool = False,
    render: bool = True,
    run_id: str | None = None,
    stages: tuple[str, ...] = STAGES,
) -> dict[str, Any]:
    run_id = run_id or new_run_id()
    out = run_dir(run_id)

    banner(
        "CrowdWisdom Video Ads Agent",
        "run " + run_id + ("  offline" if offline else "  live") + "\n" + out.as_posix(),
    )
    hermes_runtime.log_runtime()

    results: dict[str, Any] = {"run_id": run_id, "output_dir": str(out), "offline": offline}

    ads = insights = research = bundle = None

    if "mine" in stages:
        step("pipeline", "stage 1/5 - Ads Manager")
        ads = AdsManagerAgent(out, offline=offline).run()
        results["winning_ads"] = len(ads.ads)

    if "insight" in stages:
        step("pipeline", "stage 2/5 - Creative Strategist")
        ads = ads or load_artifact(out, "ads")
        if ads is None:
            warn("insight stage needs 01_winning_ads.json; skipping")
        else:
            insights = InsightAgent(out, offline=offline).run(ads)
            results["pain_clusters"] = len(insights.pain_clusters)

    if "research" in stages:
        step("pipeline", "stage 3/5 - Market Researcher")
        insights = insights or load_artifact(out, "insights")
        if insights is None:
            warn("research stage needs 02_ad_insights.json; skipping")
        else:
            research = ResearchAgent(out, offline=offline).run(insights)
            results["research_findings"] = len(research.findings)

    if "script" in stages:
        step("pipeline", "stage 4/5 - Creative Director")
        insights = insights or load_artifact(out, "insights")
        research = research or load_artifact(out, "research")
        if insights is None or research is None:
            warn("script stage needs 02_ad_insights.json + 03_research.json; skipping")
        else:
            bundle = ScriptAgent(out, offline=offline).run(insights, research)
            results["scripts"] = [s.id for s in bundle.scripts]
            results["hero_script"] = bundle.hero_script_id

    if "video" in stages:
        step("pipeline", "stage 5/5 - Video Director")
        bundle = bundle or load_artifact(out, "bundle")
        if bundle is None:
            warn("video stage needs 04_storyboards.json; skipping")
        else:
            results["video"] = VideoAgent(out, offline=offline).run(bundle, render=render)

    _write_summary(out, results)
    _point_latest_at(out)
    _print_manifest(out)
    return results


def _write_summary(out: Path, results: dict[str, Any]) -> None:
    summary = {
        "run": results.get("run_id"),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "llm_transport": hermes_runtime.transport(),
        "results": results,
        "artifacts": sorted(p.name for p in out.iterdir() if p.is_file()),
    }
    (out / "00_run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )


def _print_manifest(out: Path) -> None:
    rows = []
    labels = {
        "00_run_summary.json": "Run manifest",
        "01_winning_ads.json": "Winning Meta ads, last 30 days",
        "02_ad_insights.json": "Marketing teardown + pain clusters",
        "03_research.json": "Tavily/Exa evidence, last 30 days",
        "04_storyboards.json": "Three cinematic scripts + storyboards",
        "05_storyboard.html": "Playable animatic - open in a browser",
        "06_openmontage_brief.json": "OpenMontage production brief",
        "ad.mp4": "Final render",
    }
    for name, label in labels.items():
        path = out / name
        if path.exists():
            rows.append([name, label, str(path.stat().st_size // 1024) + " KB"])
    if rows:
        table("Artifacts - " + out.as_posix(), ["File", "What it is", "Size"], rows)
    ok("done")
