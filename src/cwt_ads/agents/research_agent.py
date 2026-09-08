"""Agent 3 - Market Researcher.

Takes the pain clusters the strategist inferred from competitor ads and tests
them against the open web from the last 30 days, using Tavily and Exa. The
point is not more reading; it is to come back with the words real traders used
this month, so the script can quote a human instead of a persona.
"""

from __future__ import annotations

import json
from datetime import timedelta

from ..logging_utils import table, warn
from ..schemas import InsightReport, ResearchFinding, ResearchReport
from ..tools import search
from .base import Agent, brand_block, looks_like_echoed_schema, now, save_json

SYSTEM = """You are a market researcher for a trading-signals company. You are
allergic to marketing language and you never write a sentence that a source
does not support.

You will receive real search results from the last 30 days. Your job:
1. Decide which of our hypothesised pains the evidence actually supports, and
   say plainly which ones it does not.
2. Extract verbatim phrases traders used. Ugly, specific, first-person language
   is worth more than a well-written summary.
3. Surface anything that changes the creative brief - a new pain, a shift in
   sentiment, a fresh source of anxiety this month.

Never invent a quote. If the evidence is thin, say the evidence is thin.

BRAND CONTEXT
-------------
{brand}
"""

SCHEMA = """{
  "synthesis": "3-5 sentences on what the last month of evidence actually shows",
  "evidenced_pains": ["pains the sources support, most supported first"],
  "quotable_lines": ["short lines usable as on-screen text or voiceover, grounded in the sources"],
  "icp_language": ["verbatim phrases real traders used, in their own words"]
}"""


class ResearchAgent(Agent):
    id = "research_agent"
    role = "Market Researcher"
    temperature = 0.4

    @property
    def system_prompt(self) -> str:
        return SYSTEM.replace("{brand}", brand_block())

    def run(self, insights: InsightReport) -> ResearchReport:
        cfg = self.cfg.get("research", {})
        window_days = int(cfg.get("window_days", 30))
        queries = insights.search_queries_for_research or self._fallback_queries()

        findings, providers = [], []
        if not self.offline:
            raw, providers = search.search_all(
                queries,
                days=window_days,
                max_results=int(cfg.get("max_results_per_query", 8)),
            )
            findings = [ResearchFinding(**hit) for hit in raw]
            if not providers:
                warn("no TAVILY_API_KEY or EXA_API_KEY set; research will be unsourced")
        else:
            self.announce("offline: skipping live search")

        self.announce(
            str(len(findings)) + " findings from " + (", ".join(providers) or "no provider")
        )

        synthesis = self._synthesise(insights, findings, window_days)
        base = dict(
            generated_at=now(),
            window_days=window_days,
            window_start=(now() - timedelta(days=window_days)).date(),
            providers_used=providers,
            findings=findings,
        )
        try:
            report = ResearchReport(**base, **synthesis)
        except Exception as exc:  # noqa: BLE001
            # The sources are real and already paid for; do not lose them just
            # because the model returned a list where a string was expected.
            warn("research synthesis failed validation (" + str(exc)[:160] + ")")
            report = ResearchReport(
                **base,
                synthesis="Synthesis discarded: the model returned an invalid shape. "
                "The findings below are unaffected and were retrieved live.",
                evidenced_pains=[c.label for c in insights.pain_clusters[:4]],
            )
        save_json(
            self.run_dir / "03_research.json",
            report,
            {
                "agent": self.id,
                "role": self.role,
                "queries": queries,
                "time_window": "last " + str(window_days) + " days",
            },
        )
        self._print(report)
        return report

    def _synthesise(
        self, insights: InsightReport, findings: list[ResearchFinding], window_days: int
    ) -> dict:
        if not findings or self.offline:
            return {
                "synthesis": (
                    "No live sources were retrieved for this run, so the brief falls back to "
                    "the pains inferred from the competitor teardown. Treat every line below "
                    "as a hypothesis, not evidence."
                ),
                "evidenced_pains": [c.label for c in insights.pain_clusters[:4]],
                "quotable_lines": [],
                "icp_language": [],
            }

        payload = [
            {
                "title": f.title,
                "url": f.url,
                "published": f.published_date,
                "provider": f.provider,
                "snippet": f.snippet[:300],
            }
            for f in findings[:30]
        ]
        hypotheses = [
            {"label": c.label, "description": c.description} for c in insights.pain_clusters
        ]
        task = (
            "Our hypothesised pains, inferred from competitor ads:\n"
            + json.dumps(hypotheses, indent=1)
            + "\n\nSearch results from the last "
            + str(window_days)
            + " days:\n"
            + json.dumps(payload)[:18000]
            + "\n\nTest the hypotheses against the evidence."
        )
        try:
            out = self.hermes().run_json(task, schema_hint=SCHEMA)
            if looks_like_echoed_schema(out, SCHEMA):
                raise ValueError("the model returned the schema template, not a synthesis")
            return out
        except Exception as exc:  # noqa: BLE001
            warn("research synthesis failed (" + str(exc) + ")")
            return {
                "synthesis": "Synthesis unavailable: " + str(exc),
                "evidenced_pains": [c.label for c in insights.pain_clusters[:4]],
                "quotable_lines": [],
                "icp_language": [],
            }

    def _fallback_queries(self) -> list[str]:
        icp = self.cfg.get("research", {}).get("queries")
        if icp:
            return list(icp)
        return [
            "retail traders overwhelmed conflicting advice",
            "trading signals service accuracy track record",
            "finfluencer wrong calls accountability",
            "how much time retail traders spend on research",
            "retail trader stop loss discipline problem",
        ]

    @staticmethod
    def _print(report: ResearchReport) -> None:
        if report.findings:
            table(
                "Sources, last " + str(report.window_days) + " days",
                ["Provider", "Published", "Title"],
                [
                    [f.provider, f.published_date or "-", f.title[:66]]
                    for f in report.findings[:8]
                ],
            )
        if report.icp_language:
            table(
                "Words traders actually used",
                ["Verbatim"],
                [[line[:90]] for line in report.icp_language[:6]],
            )
