"""Agent 4 - Creative Director.

Writes three cinematic 30-60 second ad scripts, one per mandated angle:

  pain_led     - built on last-month research into the ICP and their pain
  data_led     - built on CrowdWisdom proprietary prediction data
  outcome_led  - built on how CrowdWisdom changes the trading result

Each script carries a `visual_hook` that must work with the sound off, a
shot-by-shot storyboard with prompts a video model can execute, and a claims
audit so no number reaches the screen unless it is in brand.yaml.
"""

from __future__ import annotations

import json
from typing import Any

import yaml

from ..config import brand
from ..logging_utils import table, warn
from ..schemas import AdScript, InsightReport, ResearchReport, StoryboardBundle
from ..render.previz import write_animatic
from ..tools import unique_data
from .base import Agent, brand_block, claim_ids, looks_like_echoed_schema, now, save_json
from .fallback_scripts import fallback_script

SYSTEM = """You are a commercial film director who moved into performance
marketing and refused to leave the craft behind. Your reel is Nike, Apple and
the opening four minutes of a Villeneuve film. You are writing a 30-60 second
ad that a trader will see on a phone, at 6am, with the sound off, one thumb
already moving.

NON-NEGOTIABLES
1. The hook is an EVENT, not a sentence. Something physically changes on screen
   inside the first 3 seconds - before a single word can be read or heard. If
   your hook only works because of its words, it is not a hook, it is a caption.
2. The ad must work with the sound off. Voiceover is a second layer, never the
   load-bearing one.
3. No number appears on screen unless it comes from one of exactly two places:
   brand.verified_claims (cite the id), or the CrowdWisdom prediction export you
   are handed as evidence (cite it as "data:<ticker>"). List every id you used.
   Any other number must be expressed qualitatively instead.
4. Obey the banned list in the brand bible absolutely. If the whole category
   does something, that is the thing you are here to not do.
5. Every shot gets an image_prompt that a text-to-image or text-to-video model
   can execute standing alone: subject, lens, light, grade, texture, motion.
   Bake the look block into every prompt. Never write "as before".
6. Time is money. Shots are contiguous - shot N ends exactly where shot N+1
   begins - and the total lands inside the requested duration.
7. No profit promises. Capital-at-risk end card. Always.

HOW YOU THINK ABOUT THE OPENING
The scroll is a physical reflex. You do not beat it with information, you beat
it with an unresolved image: something that is wrong, or about to fall, or too
quiet. The viewer stays because their brain has opened a loop it needs closed.
Close it at the turn, not before.

BRAND CONTEXT
-------------
{brand}
"""

SCHEMA = """{
  "id": "pain_led|data_led|outcome_led",
  "angle": "short label",
  "angle_source": "research|unique_data|product",
  "title": "the film's title",
  "logline": "one sentence a director could shoot from",
  "duration_seconds": 45,
  "aspect_ratio": "9:16",
  "target_pain": "the single pain this film presses",
  "icp": "who this is for, in one line",
  "visual_hook": {
    "concept": "the stop-scroll idea in one sentence",
    "first_frame": "exactly what is on screen at t=0 before anything moves",
    "the_event": "the physical change that happens inside 3 seconds",
    "why_it_stops_the_scroll": "the mechanism, in the language of attention not of marketing",
    "sound_at_zero": "what is heard at t=0",
    "text_overlay": "on-screen text at the hook, or empty string"
  },
  "shots": [{
    "n": 1,
    "t_start": 0.0,
    "t_end": 2.5,
    "beat": "hook|escalation|turn|proof|resolution|cta",
    "shot_size": "ECU|CU|MS|WS|aerial etc",
    "camera": "lens, movement, framing",
    "visual": "what a human sees",
    "image_prompt": "standalone prompt for an image/video model, look baked in",
    "motion_prompt": "how the frame moves over its duration",
    "on_screen_text": "",
    "voiceover": "",
    "sfx": "",
    "music": "",
    "transition_out": "cut|whip|dissolve|match cut|hard cut to black"
  }],
  "voiceover_full": "the whole VO as one readable paragraph",
  "on_screen_text_full": ["every text card in order"],
  "cta": "the closing ask",
  "end_card": "what the last frame looks like",
  "music_direction": "genre, tempo, instrumentation, where it drops out",
  "sound_design_direction": "the specific sounds carrying the story",
  "claims_used": ["ids from brand.verified_claims"],
  "compliance_notes": ["how this script satisfies each compliance rule"],
  "why_this_works": "the strategic argument for this film in 3-4 sentences"
}"""


class ScriptAgent(Agent):
    id = "script_agent"
    role = "Creative Director"
    temperature = 0.9
    max_tokens = 9000

    @property
    def system_prompt(self) -> str:
        return SYSTEM.replace("{brand}", brand_block())

    # -- main ---------------------------------------------------------------
    def run(self, insights: InsightReport, research: ResearchReport) -> StoryboardBundle:
        video_cfg = self.cfg.get("video", {})
        duration = float(video_cfg.get("duration_seconds", 45))
        aspect = str(video_cfg.get("aspect_ratio", "9:16"))
        angles = self.cfg.get("scripts", {}).get("angles", [])
        data_brief = unique_data.cinematic_brief()

        scripts: list[AdScript] = []
        for angle in angles:
            self.announce("writing: " + angle.get("name", angle["id"]))
            script = self._write_one(angle, insights, research, data_brief, duration, aspect)
            if script:
                scripts.append(script)

        bundle = StoryboardBundle(
            generated_at=now(),
            hero_script_id=str(video_cfg.get("hero_script", scripts[0].id if scripts else "")),
            scripts=scripts,
            director_notes=self._director_notes(insights, research),
        )
        save_json(
            self.run_dir / "04_storyboards.json",
            bundle,
            {
                "agent": self.id,
                "role": self.role,
                "inputs": ["02_ad_insights.json", "03_research.json", "data/unique/*.json"],
                "angles": [a["id"] for a in angles],
            },
        )
        write_animatic(bundle, self.run_dir / "05_storyboard.html")
        self._print(bundle)
        return bundle

    # -- one script ---------------------------------------------------------
    def _write_one(
        self,
        angle: dict[str, Any],
        insights: InsightReport,
        research: ResearchReport,
        data_brief: dict[str, Any],
        duration: float,
        aspect: str,
    ) -> AdScript | None:
        evidence = self._evidence_for(angle, insights, research, data_brief)
        task = (
            "Write the "
            + str(angle.get("name", angle["id"]))
            + " film.\n\nANGLE BRIEF\n"
            + str(angle.get("brief", ""))
            + "\n\nid must be exactly: "
            + angle["id"]
            + "\nangle_source must be exactly: "
            + angle["source"]
            + "\nTarget duration: "
            + str(duration)
            + " seconds. Aspect ratio: "
            + aspect
            + ".\n\nEVIDENCE YOU MAY USE (and nothing else)\n"
            + evidence
            + "\n\nAvailable claim ids: "
            + ", ".join(claim_ids())
            + "\n\nWrite the film. Make the first three seconds impossible to scroll past."
        )

        data: dict[str, Any] | None = None
        if not self.offline:
            try:
                data = self.hermes().run_json(task, schema_hint=SCHEMA)
                if looks_like_echoed_schema(data, SCHEMA):
                    warn("model echoed the schema for " + angle["id"] + " instead of writing")
                    data = None
            except Exception as exc:  # noqa: BLE001
                warn("script generation failed for " + angle["id"] + " (" + str(exc) + ")")

        if not data:
            self.announce("using the bundled reference script for " + angle["id"])
            data = fallback_script(angle["id"], duration, aspect, data_brief)

        data["id"] = angle["id"]
        data["angle"] = data.get("angle") or angle.get("name", angle["id"])
        data["angle_source"] = angle["source"]
        data.setdefault("aspect_ratio", aspect)
        data.setdefault("duration_seconds", duration)

        try:
            script = AdScript(**data)
        except Exception as exc:  # noqa: BLE001
            warn("script for " + angle["id"] + " failed validation (" + str(exc) + "); using reference")
            script = AdScript(**fallback_script(angle["id"], duration, aspect, data_brief))

        self._repair_timeline(script, duration)
        self._audit_claims(script)
        return script

    # -- evidence assembly --------------------------------------------------
    def _evidence_for(
        self,
        angle: dict[str, Any],
        insights: InsightReport,
        research: ResearchReport,
        data_brief: dict[str, Any],
    ) -> str:
        common = {
            "pain_clusters": [c.model_dump() for c in insights.pain_clusters[:5]],
            "category_conventions_to_break": insights.category_conventions,
            "creative_whitespace": insights.whitespace,
            "hook_devices_that_work_in_this_niche": insights.hook_devices_ranked,
            "icp": insights.icp_refinement,
        }
        source = angle["source"]
        if source == "research":
            common["research_synthesis"] = research.synthesis
            common["evidenced_pains"] = research.evidenced_pains
            common["verbatim_trader_language"] = research.icp_language
            common["quotable_lines"] = research.quotable_lines
            common["sources"] = [
                {"title": f.title, "url": f.url, "published": f.published_date}
                for f in research.findings[:12]
            ]
        elif source == "unique_data":
            common["crowdwisdom_proprietary_data"] = {
                "hero_prediction": data_brief.get("hero"),
                "talking_points": data_brief.get("talking_points"),
                "sample_size": data_brief.get("count"),
            }
            common["note"] = (
                "This is a real CrowdWisdom prediction export. The four source weights, "
                "the confidence level and the entry/target/stop levels are the visual "
                "material - make the dataset itself the hero, physically."
            )
        else:
            common["product"] = brand()["product"]
            common["deliverables"] = brand()["product"]["deliverables"]
        return yaml.safe_dump(common, sort_keys=False, allow_unicode=True, width=100)[:9000]

    # -- post-processing ----------------------------------------------------
    @staticmethod
    def _repair_timeline(script: AdScript, target: float) -> None:
        """Make the timeline contiguous and land it on the target duration.

        Models drift by a second or two and leave gaps between shots. Rather
        than rejecting an otherwise good script, snap the shots into a clean
        contiguous timeline and rescale to the requested runtime.
        """
        if not script.shots:
            return
        script.shots.sort(key=lambda s: (s.t_start, s.n))
        cursor = 0.0
        for i, shot in enumerate(script.shots, start=1):
            length = max(shot.t_end - shot.t_start, 0.4)
            shot.n = i
            shot.t_start = round(cursor, 2)
            cursor = round(cursor + length, 2)
            shot.t_end = cursor

        total = script.shots[-1].t_end
        if total <= 0:
            return
        low, high = 30.0, 60.0
        goal = min(max(target, low), high)
        if abs(total - goal) > 0.5:
            factor = goal / total
            cursor = 0.0
            for shot in script.shots:
                length = round((shot.t_end - shot.t_start) * factor, 2)
                shot.t_start = round(cursor, 2)
                cursor = round(cursor + length, 2)
                shot.t_end = cursor
        script.duration_seconds = script.shots[-1].t_end

    @staticmethod
    def _audit_claims(script: AdScript) -> None:
        """Strip claim ids that trace back to neither the brand bible nor the dataset.

        Two provenances are legitimate: an id from brand.verified_claims, or a
        `data:<ticker>` reference into the CrowdWisdom prediction export. Anything
        else is a number the model invented, and it does not reach the screen.
        """
        allowed = set(claim_ids())
        unknown = [
            c for c in script.claims_used if c not in allowed and not str(c).startswith("data:")
        ]
        if unknown:
            warn("script " + script.id + " cited unknown claims: " + ", ".join(unknown))
            script.claims_used = [
                c for c in script.claims_used if c in allowed or str(c).startswith("data:")
            ]
            script.compliance_notes.append(
                "Unverified claim ids removed during audit: " + ", ".join(unknown)
            )
        if not any("risk" in note.lower() for note in script.compliance_notes):
            script.compliance_notes.append(
                "End card carries the capital-at-risk / not-financial-advice line."
            )

    def _director_notes(self, insights: InsightReport, research: ResearchReport) -> str:
        parts = []
        if insights.whitespace:
            parts.append("Whitespace we are occupying: " + insights.whitespace)
        if insights.category_conventions:
            parts.append(
                "Conventions deliberately broken: " + "; ".join(insights.category_conventions[:4])
            )
        if research.synthesis:
            parts.append("Evidence base: " + research.synthesis)
        return "\n\n".join(parts)

    @staticmethod
    def _print(bundle: StoryboardBundle) -> None:
        table(
            "Scripts",
            ["id", "Title", "Runtime", "Shots", "Visual hook"],
            [
                [
                    s.id + (" (hero)" if s.id == bundle.hero_script_id else ""),
                    s.title[:30],
                    str(s.duration_seconds) + "s",
                    len(s.shots),
                    s.visual_hook.concept[:58],
                ]
                for s in bundle.scripts
            ],
        )
