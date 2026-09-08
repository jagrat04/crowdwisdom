"""OpenMontage integration.

OpenMontage (https://github.com/calesthio/OpenMontage) is instruction-driven:
the intelligence lives in its pipeline manifests and stage-director skills, and
an AI assistant drives them. Its own contract - Rule Zero in AGENT_GUIDE.md - is
that production goes through a pipeline and never through ad-hoc scripts calling
its tools directly.

So this module does not try to be a second orchestrator. It does two things:

1. Compiles our storyboard into a production package that OpenMontage's
   `cinematic` pipeline can consume: a natural-language brief plus a structured
   shot list with per-shot prompts.
2. Hands that package to a Hermes agent with terminal access, working inside the
   OpenMontage checkout - which is exactly the "AI coding assistant" that
   AGENT_GUIDE.md expects to be driving it.

If no checkout is configured, `render()` reports that cleanly and the pipeline
falls back to the animatic in `previz.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import re
import subprocess
from pathlib import Path
from typing import Any

from ..config import brand, env
from ..hermes_runtime import HermesAgent
from ..logging_utils import step, warn
from ..schemas import AdScript, RenderAsset, RenderBrief
from ..agents.base import now

PIPELINE = "cinematic"


def home() -> Path | None:
    raw = env("OPENMONTAGE_HOME")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if (path / "pipeline_defs" / (PIPELINE + ".yaml")).is_file() else None


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "crowdwisdom-ad"


# ── brief compilation ───────────────────────────────────────────────────────
def build_brief(script: AdScript, output_path: Path, fps: int = 30) -> RenderBrief:
    look = brand()["look"]
    assets: list[RenderAsset] = []
    for shot in script.shots:
        assets.append(
            RenderAsset(
                shot=shot.n,
                kind="video" if shot.motion_prompt else "image",
                prompt=shot.image_prompt,
                duration=shot.duration,
                provider_hint="generated visual; stock only if it can match the grade",
            )
        )
        if shot.voiceover:
            assets.append(
                RenderAsset(shot=shot.n, kind="voiceover", prompt=shot.voiceover, duration=shot.duration)
            )
        if shot.sfx:
            assets.append(RenderAsset(shot=shot.n, kind="sfx", prompt=shot.sfx, duration=shot.duration))

    return RenderBrief(
        generated_at=now(),
        script_id=script.id,
        title=script.title,
        duration_seconds=script.duration_seconds,
        aspect_ratio=script.aspect_ratio,
        fps=fps,
        engine="openmontage:" + PIPELINE,
        look=look,
        timeline=script.shots,
        assets=assets,
        narration_script=script.voiceover_full,
        output_path=str(output_path),
        instructions=_instructions(script, output_path),
    )


def _instructions(script: AdScript, output_path: Path) -> str:
    look = brand()["look"]
    return "\n".join(
        [
            "Pipeline: " + PIPELINE + " (pipeline_defs/" + PIPELINE + ".yaml)",
            "Composition mode: atelier - this is hero marketing work, not batch output.",
            "Aspect: " + script.aspect_ratio + " | Duration: " + str(script.duration_seconds) + "s",
            "Grade: " + str(look.get("grade", "")),
            "Lens: " + str(look.get("lens", "")),
            "Motion: " + str(look.get("motion", "")),
            "Texture: " + str(look.get("texture", "")),
            "Palette: " + json.dumps(look.get("palette", {})),
            "Every shot already carries a standalone image_prompt with the look baked in - "
            "use them as written rather than re-deriving prompts.",
            "The cut is locked. Shot boundaries in the timeline are the edit; do not re-time.",
            "Deliver the final MP4 to: " + str(output_path),
        ]
    )


def write_production(brief: RenderBrief, om_home: Path) -> Path:
    """Write the production package into the OpenMontage checkout."""
    name = slug(brief.title)
    project = om_home / "productions" / ("crowdwisdom-" + name)
    project.mkdir(parents=True, exist_ok=True)

    (project / "shotlist.json").write_text(
        json.dumps(brief.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (project / "BRIEF.md").write_text(_brief_markdown(brief), encoding="utf-8")
    step("video_agent", "production package -> " + str(project))
    return project


def _brief_markdown(brief: RenderBrief) -> str:
    lines = [
        "# " + brief.title,
        "",
        "A " + str(brief.duration_seconds) + "-second cinematic ad for CrowdWisdom Trading.",
        "",
        "## Delivery",
        "",
        "- Aspect ratio: " + brief.aspect_ratio,
        "- Frame rate: " + str(brief.fps),
        "- Output: `" + brief.output_path + "`",
        "",
        "## Direction",
        "",
        brief.instructions,
        "",
        "## Narration",
        "",
        brief.narration_script or "_No voiceover._",
        "",
        "## Shot list",
        "",
    ]
    for shot in brief.timeline:
        lines += [
            "### Shot " + str(shot.n) + " - " + shot.beat
            + "  (" + str(shot.t_start) + "s to " + str(shot.t_end) + "s)",
            "",
            "- **Framing:** " + (shot.shot_size or "-") + " / " + (shot.camera or "-"),
            "- **Visual:** " + shot.visual,
            "- **Image prompt:** " + shot.image_prompt,
            "- **Motion:** " + (shot.motion_prompt or "-"),
            "- **On-screen text:** " + (shot.on_screen_text.replace("\n", " / ") or "-"),
            "- **VO:** " + (shot.voiceover or "-"),
            "- **SFX:** " + (shot.sfx or "-"),
            "- **Music:** " + (shot.music or "-"),
            "- **Out:** " + shot.transition_out,
            "",
        ]
    return "\n".join(lines)


# ── driving the render ──────────────────────────────────────────────────────
DRIVER_SYSTEM = """You are driving OpenMontage, an instruction-driven video
production system, from inside its own checkout.

Follow its contract exactly:
- Read AGENT_GUIDE.md first. Rule Zero: all production goes through a pipeline.
- Use the `cinematic` pipeline. Read pipeline_defs/cinematic.yaml.
- Read each stage director skill before doing that stage's work.
- Never write ad-hoc Python that calls OpenMontage tools directly.
- Announce provider and model choices before any paid generation call.
- Prefer providers that need no paid key when a free one can hold the grade.

The creative work is already done and locked. The brief and shot list are the
input, not a starting point: the cut is locked, the prompts are written, and the
grade is specified. Your job is execution and delivery, not reinterpretation.
"""


def render(brief: RenderBrief, output_path: Path, *, model: str | None = None) -> dict[str, Any]:
    """Drive an OpenMontage render. Returns a status dict; never raises."""
    om_home = home()
    if om_home is None:
        return {
            "rendered": False,
            "reason": (
                "OPENMONTAGE_HOME is not set to a valid OpenMontage checkout. "
                "Clone https://github.com/calesthio/OpenMontage, run `make setup`, "
                "and point OPENMONTAGE_HOME at it."
            ),
        }

    project = write_production(brief, om_home)
    task = (
        "Produce the video described in " + str(project / "BRIEF.md") + ".\n"
        "The machine-readable shot list is " + str(project / "shotlist.json") + ".\n\n"
        "Run the cinematic pipeline end to end and deliver the final MP4 to "
        + brief.output_path
        + ".\n\nWhen you are finished, reply with the absolute path of the rendered file "
        "on the first line and nothing else on that line."
    )

    agent = HermesAgent(
        id="video_agent",
        role="Video Director",
        charter="Drive OpenMontage to deliver the locked cut.",
        system_prompt=DRIVER_SYSTEM,
        model=model,
        enabled_toolsets=["terminal", "files", "web"],
        temperature=0.3,
        max_tokens=16000,
    )
    step("video_agent", "handing the locked cut to OpenMontage (" + str(om_home) + ")")
    try:
        reply = agent.run(task)
    except Exception as exc:  # noqa: BLE001
        warn("OpenMontage run failed: " + str(exc))
        return {"rendered": False, "reason": str(exc), "production_dir": str(project)}

    produced = output_path if output_path.exists() else _find_output(reply)
    return {
        "rendered": bool(produced and Path(produced).exists()),
        "output": str(produced) if produced else None,
        "production_dir": str(project),
        "agent_reply": reply[-4000:],
    }


def _find_output(reply: str) -> Path | None:
    for line in (reply or "").splitlines():
        candidate = line.strip().strip("`\"'")
        if candidate.lower().endswith(".mp4") and Path(candidate).exists():
            return Path(candidate)
    return None


def ffmpeg_path() -> str | None:
    """Locate ffmpeg, tolerating a PATH that has not been refreshed yet.

    A Windows installer updates the user PATH, but every shell already running
    keeps the old copy - so a freshly installed ffmpeg looks missing until the
    terminal is restarted. Fall back to the standard install locations rather
    than reporting a component as absent when it is sitting right there.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found

    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        winget = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if winget.is_dir():
            candidates += list(winget.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"))
        candidates.append(Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
    for extra in ("/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"):
        candidates.append(Path(extra))

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def ffmpeg_available() -> bool:
    exe = ffmpeg_path()
    if not exe:
        return False
    try:
        subprocess.run([exe, "-version"], capture_output=True, check=True, timeout=20)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
