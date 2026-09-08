"""Agent 2 - Creative Strategist.

Takes the winning ads and strips the paint off them. The output is not a
summary of the ads; it is the marketing machinery underneath: which pain each
ad presses, what it promises in exchange, the mechanical device used in the
first three seconds, and what proof it offers.

The two fields that matter most downstream are `category_conventions` (what
every ad in this niche does, i.e. the shape of the wallpaper) and `whitespace`
(the angle nobody is running). A cinematic ad earns attention by violating the
first and occupying the second.
"""

from __future__ import annotations

import json

from ..logging_utils import table, warn
from ..schemas import InsightReport, WinningAdsReport
from .base import Agent, brand_block, looks_like_echoed_schema, now, save_json

SYSTEM = """You are a creative strategist who reverse-engineers direct-response
advertising for a living. You have torn down thousands of ads and you refuse to
describe what an ad says. You describe what it DOES to the viewer.

Rules you work by:
- The hook device is a mechanism, not a sentence. "Pattern interrupt: a hand
  covers the lens" is a device. "Attention-grabbing opener" is not.
- A pain is something the viewer already feels at 6am. It is never a feature
  written backwards.
- If an ad is winning for a boring reason (heavy spend, broad targeting), say
  so instead of inventing craft that is not there.
- You are looking for what the whole category does the same way, because that
  is exactly what our ad must not do.

BRAND CONTEXT
-------------
{brand}
"""

SCHEMA = """{
  "teardowns": [{
    "ad_archive_id": "string",
    "advertiser": "string",
    "hook_device": "the mechanism used in the first 3 seconds",
    "hook_transcript": "the opening words, if any",
    "core_pain": "string",
    "pain_intensity": "low|medium|high",
    "promise": "string",
    "proof_type": "track record|testimonial|authority|demo|none",
    "emotional_arc": "start emotion -> end emotion",
    "icp_signals": ["who this ad is aimed at, inferred from language"],
    "why_it_works": "string",
    "transferable_to_crowdwisdom": "the one idea worth stealing",
    "do_not_copy": "the part that would cheapen CrowdWisdom"
  }],
  "pain_clusters": [{
    "id": "snake_case_id",
    "label": "short name",
    "description": "string",
    "frequency": 0,
    "intensity": "low|medium|high",
    "example_phrases": ["verbatim phrases from the ads"],
    "crowdwisdom_answer": "how CrowdWisdom specifically answers this pain"
  }],
  "hook_devices_ranked": ["most effective device first"],
  "icp_refinement": "a sharper ICP statement than we started with",
  "category_conventions": ["what nearly every ad in this niche does"],
  "whitespace": "the angle nobody in the niche is running, and why it is open",
  "search_queries_for_research": ["5-7 web search queries that would verify the top pains with evidence from the last month"]
}"""


class InsightAgent(Agent):
    id = "insight_agent"
    role = "Creative Strategist"
    temperature = 0.6
    max_tokens = 6000

    @property
    def system_prompt(self) -> str:
        return SYSTEM.replace("{brand}", brand_block())

    def run(self, ads_report: WinningAdsReport) -> InsightReport:
        ads = ads_report.ads
        if not ads:
            warn("no ads to analyse; emitting an empty insight report")
            report = InsightReport(generated_at=now(), ads_analysed=0)
            save_json(self.run_dir / "02_ad_insights.json", report, {"agent": self.id})
            return report

        payload = [
            {
                "ad_archive_id": ad.ad_archive_id,
                "advertiser": ad.page_name,
                # 400 chars is the hook, the promise and the CTA - which is all a
                # teardown needs. The tail of a Meta body is disclaimers, and
                # sending it triples the prompt for nothing on a throttled tier.
                "copy": ad.ad_copy[:400],
                "title": ad.title,
                "cta": ad.cta_text,
                "days_running": ad.days_running,
                "variants": ad.variant_count,
                "platforms": ad.publisher_platforms,
                "winner_score": ad.winner_score,
                "why_it_ranked": ad.score_rationale,
            }
            for ad in ads
        ]

        self.announce("tearing down " + str(len(payload)) + " winning ads")
        task = (
            "Here are the ads that have survived longest in this niche over the last 30 days. "
            "Tear each one down, then cluster the pains across all of them.\n\n"
            "Pay particular attention to what the whole set does identically - that is the "
            "convention our cinematic ad has to break.\n\n"
            + json.dumps(payload)[:20000]
        )

        if self.offline:
            self.announce("offline: using the deterministic teardown")
            data = self._offline_report(payload)
        else:
            try:
                data = self.hermes().run_json(task, schema_hint=SCHEMA)
                if looks_like_echoed_schema(data, SCHEMA):
                    raise ValueError(
                        "the model returned the schema template instead of a teardown"
                    )
            except Exception as exc:  # noqa: BLE001
                warn("insight agent failed (" + str(exc) + "); using the offline teardown")
                data = self._offline_report(payload)

        data.setdefault("generated_at", now())
        data["ads_analysed"] = len(payload)
        try:
            report = InsightReport(**data)
        except Exception as exc:  # noqa: BLE001
            # Validation runs after the call, so a schema-shaped response that
            # is still wrong (a model echoing "low|medium|high" back at us) used
            # to escape the try above and kill the run three stages from the end.
            warn("insight report failed validation (" + str(exc)[:200] + "); using the teardown")
            fallback = self._offline_report(payload)
            fallback["generated_at"] = now()
            fallback["ads_analysed"] = len(payload)
            report = InsightReport(**fallback)
        self._rank_pain_frequency(report)

        save_json(
            self.run_dir / "02_ad_insights.json",
            report,
            {"agent": self.id, "role": self.role, "input": "01_winning_ads.json"},
        )
        self._print(report)
        return report

    @staticmethod
    def _rank_pain_frequency(report: InsightReport) -> None:
        """Fill in any frequency the model left at zero by counting teardowns."""
        for cluster in report.pain_clusters:
            if cluster.frequency:
                continue
            words = set(cluster.label.lower().split())
            cluster.frequency = sum(
                1 for t in report.teardowns if words & set(t.core_pain.lower().split())
            )
        report.pain_clusters.sort(key=lambda c: (c.frequency, c.intensity == "high"), reverse=True)

    def _offline_report(self, payload: list[dict]) -> dict:
        """Deterministic teardown so the pipeline still yields a usable artifact."""
        brand_pains = [
            (
                "information_overload",
                "Information overload",
                "Forty voices, zero decisions. Every input adds noise, none add conviction.",
                "high",
                "One weekly consensus distilled from 16,564 tracked traders, instead of "
                "forty feeds to reconcile alone.",
            ),
            (
                "unaccountable_gurus",
                "No scoreboard for gurus",
                "Everyone is confident, nobody publishes a hit rate, so being wrong is free.",
                "high",
                "A public, year-long prediction record with a stated definition of a win - "
                "74.1% of tracked directions hit.",
            ),
            (
                "no_exit_discipline",
                "No entry, stop or target",
                "Positions are opened on a feeling and closed on a feeling.",
                "medium",
                "Every call ships with an entry, two targets and two stops, written before "
                "the trade rather than after it.",
            ),
            (
                "time_poverty",
                "Research competes with life",
                "Hours of scrolling that a job and a family were supposed to have.",
                "medium",
                "100+ hours of weekly research compressed into a 5-minute Monday briefing.",
            ),
        ]
        return {
            "teardowns": [
                {
                    "ad_archive_id": row["ad_archive_id"],
                    "advertiser": row["advertiser"],
                    "hook_device": "direct claim in the opening line",
                    "hook_transcript": (row.get("copy") or "")[:120],
                    "core_pain": "uncertainty about which market opinion to act on",
                    "pain_intensity": "medium",
                    "promise": "clarity and a specific trade",
                    "proof_type": "none",
                    "emotional_arc": "anxiety -> relief",
                    "icp_signals": ["self-directed retail trader"],
                    "why_it_works": "it has run for "
                    + str(row.get("days_running", 0))
                    + " days, which in this niche means it converts.",
                    "transferable_to_crowdwisdom": "specificity beats enthusiasm",
                    "do_not_copy": "unbacked profit claims",
                }
                for row in payload
            ],
            "pain_clusters": [
                {
                    "id": pid,
                    "label": label,
                    "description": desc,
                    "frequency": len(payload) // 2 or 1,
                    "intensity": intensity,
                    "example_phrases": [],
                    "crowdwisdom_answer": answer,
                }
                for pid, label, desc, intensity, answer in brand_pains
            ],
            "hook_devices_ranked": [
                "pattern interrupt on a familiar screen",
                "direct claim in the opening line",
                "on-camera authority",
            ],
            "icp_refinement": "Self-directed active trader, 28-45, over-subscribed and under-decided.",
            "category_conventions": [
                "screen recording of a chart or dashboard",
                "presenter talking straight to camera",
                "green candles and rising arrows",
                "profit screenshots as proof",
            ],
            "whitespace": (
                "Nobody in this niche dramatises the NOISE itself. Every ad sells the "
                "answer; none of them make you feel the question."
            ),
            "search_queries_for_research": [
                "retail traders information overload 2026",
                "why retail traders lose money conflicting advice",
                "trading signal services track record complaints",
                "finfluencer accuracy study",
                "retail trader research time survey",
            ],
        }

    @staticmethod
    def _print(report: InsightReport) -> None:
        if report.pain_clusters:
            table(
                "Pain clusters",
                ["Pain", "Freq", "Intensity", "CrowdWisdom answer"],
                [
                    [c.label, c.frequency, c.intensity, c.crowdwisdom_answer[:60]]
                    for c in report.pain_clusters[:6]
                ],
            )
        if report.whitespace:
            table("Creative whitespace", ["The angle nobody is running"], [[report.whitespace]])
