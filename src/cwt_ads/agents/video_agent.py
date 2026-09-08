"""Agent 5 - Video Director.

Takes the hero storyboard, compiles it into an OpenMontage production package,
and drives the render to a finished MP4.

The cut is locked before this agent starts. Its job is execution: prompts are
already written per shot with the grade baked in, shot boundaries are the edit,
and the deliverable path is fixed. If OpenMontage is not installed the agent
reports exactly what is missing and leaves the playable animatic as the
deliverable rather than pretending a render happened.
"""

from __future__ import annotations

from typing import Any

from ..logging_utils import ok, step, table, warn
from ..render import animatic_video, openmontage
from ..schemas import RenderBrief, StoryboardBundle
from .base import Agent, save_json


class VideoAgent(Agent):
    id = "video_agent"
    role = "Video Director"
    temperature = 0.3

    @property
    def system_prompt(self) -> str:
        return openmontage.DRIVER_SYSTEM

    def run(self, bundle: StoryboardBundle, *, render: bool = True) -> dict[str, Any]:
        script = self._hero(bundle)
        if script is None:
            warn("no script to render")
            return {"rendered": False, "reason": "no scripts in the bundle"}

        cfg = self.cfg.get("video", {})
        out_path = self.run_dir / "ad.mp4"
        brief = openmontage.build_brief(script, out_path, fps=int(cfg.get("fps", 30)))

        save_json(
            self.run_dir / "06_openmontage_brief.json",
            brief,
            {
                "agent": self.id,
                "role": self.role,
                "hero_script": script.id,
                "engine": brief.engine,
                "consumed_by": "https://github.com/calesthio/OpenMontage",
            },
        )
        self._print(brief)

        if not render:
            return {"rendered": False, "reason": "render skipped (--no-render)", "brief": str(brief.output_path)}

        result = openmontage.render(brief, out_path, model=self.model)
        if result.get("rendered"):
            ok("rendered " + str(result.get("output")))
            return result

        warn("OpenMontage did not produce a file: " + str(result.get("reason", "unknown")))

        # Fall back to the ffmpeg animatic. It is not the generated film, and it
        # is labelled as such - but it is the locked cut at the right runtime
        # with the text on the right frames, it needs no keys or credits, and a
        # director can approve pacing from it. Shipping no video at all when
        # ffmpeg is right there would be the worse answer.
        step(self.id, "falling back to the ffmpeg animatic render")
        fallback = animatic_video.render(script, out_path, fps=int(cfg.get("fps", 30)))
        if fallback.get("rendered"):
            fallback["openmontage_reason"] = result.get("reason")
            fallback["note"] = (
                "Animatic render (ffmpeg), not the OpenMontage generated film. "
                "The cut, runtime and on-screen text are final; the imagery is "
                "the storyboard rather than generated footage."
            )
            return fallback

        warn("no MP4 produced: " + str(fallback.get("reason", "unknown")))
        step(self.id, "deliverable for this run is the animatic: 05_storyboard.html")
        return result

    def _hero(self, bundle: StoryboardBundle):
        if not bundle.scripts:
            return None
        for script in bundle.scripts:
            if script.id == bundle.hero_script_id:
                return script
        return bundle.scripts[0]

    @staticmethod
    def _print(brief: RenderBrief) -> None:
        kinds: dict[str, int] = {}
        for asset in brief.assets:
            kinds[asset.kind] = kinds.get(asset.kind, 0) + 1
        table(
            "Render brief - " + brief.title,
            ["Engine", "Runtime", "Aspect", "Shots", "Assets"],
            [
                [
                    brief.engine,
                    str(brief.duration_seconds) + "s @ " + str(brief.fps) + "fps",
                    brief.aspect_ratio,
                    len(brief.timeline),
                    ", ".join(k + ":" + str(v) for k, v in sorted(kinds.items())),
                ]
            ],
        )
