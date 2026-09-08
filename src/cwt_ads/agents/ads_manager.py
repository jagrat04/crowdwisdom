"""Agent 1 - Ads Manager.

Mines the Meta Ad Library through Apify for video ads in the trading /
investing niche that have been live inside the last 30 days, then ranks them.

Why this ranking works: the Ad Library does not publish spend or performance,
so "what is working" has to be inferred. Two signals survive that constraint,
and both are in the payload:

  * longevity  - a losing ad gets switched off. An ad that has been running for
                 three weeks is being paid for because it pays back.
  * scale      - the number of creative variants collated under one ad. Nobody
                 builds 30 variants of an ad they are about to kill.

A third signal, relevance to our ICP, is judged by the agent itself rather than
by keyword matching, because "options alerts for busy professionals" and
"stop guessing the market" are the same ad wearing different words.
"""

from __future__ import annotations

import json
import math
from datetime import timedelta
from typing import Any

from ..config import FIXTURE_DIR, env
from ..logging_utils import table, warn
from ..schemas import WinningAd, WinningAdsReport
from ..tools import apify_client
from .base import Agent, brand_block, now, save_json

SYSTEM = """You are the Ads Manager for CrowdWisdom Trading, a trade-signal
platform. You have spent a decade buying media in the finance vertical and you
can tell a scaled winner from a test budget at a glance.

You will be given raw ads scraped from the Meta Ad Library. Judge each one on
how relevant it is to the CrowdWisdom ICP and category - not on whether you
like it. An ad is relevant if it targets a self-directed retail trader or
investor who is drowning in conflicting information, or if it sells signals,
alerts, research, sentiment, or trade ideas.

Be blunt. Score honestly. Junk gets a low score even if it mentions stocks.

BRAND CONTEXT
-------------
{brand}
"""


class AdsManagerAgent(Agent):
    id = "ads_manager"
    role = "Ads Manager"
    temperature = 0.3

    _used_fixture = False

    @property
    def system_prompt(self) -> str:
        return SYSTEM.replace("{brand}", brand_block())

    # -- main ---------------------------------------------------------------
    def run(self) -> WinningAdsReport:
        cfg = self.cfg.get("mining", {})
        window_days = int(cfg.get("window_days", 30))
        queries = list(cfg.get("discovery_queries") or cfg.get("queries") or [])
        notes: list[str] = []

        raw = self._collect(cfg, queries, notes)
        self.announce("scraped " + str(len(raw)) + " raw ad records")

        ads = self._normalise_and_filter(raw, window_days, notes)
        self.announce(str(len(ads)) + " ads inside the " + str(window_days) + "-day window")

        self._score_mechanically(ads)
        self._score_relevance(ads[:40], notes)
        for ad in ads:
            ad["winner_score"] = self._winner_score(ad)
        blind = sum(1 for a in ads if not a.get("longevity_known"))
        if blind:
            notes.append(
                str(blind)
                + " of "
                + str(len(ads))
                + " ads carry no usable start date (Meta returns the scrape date for "
                + "keyword-search rows). Longevity was not scored for those; its weight "
                + "was redistributed onto scale and relevance."
            )
        ads.sort(key=lambda a: a["winner_score"], reverse=True)
        winners = ads[: int(cfg.get("keep_top", 12))]

        report = WinningAdsReport(
            generated_at=now(),
            source="fixture" if self._used_fixture else "apify:" + apify_client.actor_id(),
            window_days=window_days,
            window_start=(now() - timedelta(days=window_days)).date(),
            window_end=now().date(),
            queries=queries,
            total_scraped=len(raw),
            total_in_window=len(ads),
            ads=[WinningAd(**ad) for ad in winners],
            notes=notes,
        )
        save_json(
            self.run_dir / "01_winning_ads.json",
            report,
            {
                "agent": self.id,
                "role": self.role,
                "mode": cfg.get("mode", "pages"),
                "scoring": (
                    "winner = 0.45*longevity + 0.25*scale + 0.30*relevance; when "
                    "longevity_known is false the longevity term is dropped and its "
                    "weight redistributed proportionally onto scale and relevance"
                ),
            },
        )
        self._print(winners)
        return report

    # -- collection ---------------------------------------------------------
    def _collect(self, cfg: dict[str, Any], queries: list[str], notes: list[str]) -> list[dict]:
        if not self.offline and env("APIFY_TOKEN"):
            try:
                items = (
                    self._collect_by_page(cfg, queries, notes)
                    if cfg.get("mode", "pages") == "pages"
                    else self._collect_by_keyword(cfg, queries, notes)
                )
                if items:
                    notes.append("Live Apify run against " + apify_client.actor_id())
                    return items
                warn("apify returned nothing; falling back to the bundled fixture")
                notes.append("Apify returned zero rows; fixture used instead.")
            except apify_client.ApifyOutOfCredit as exc:
                warn(str(exc))
                notes.append("APIFY OUT OF CREDIT: " + str(exc))
            except apify_client.ApifyUnavailable as exc:
                warn(str(exc))
                notes.append(str(exc))
        else:
            notes.append("Offline mode: bundled Meta Ad Library fixture used.")

        self._used_fixture = True
        fixture = FIXTURE_DIR / "meta_ads_sample.json"
        if not fixture.exists():
            return []
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        return payload.get("items", payload) if isinstance(payload, dict) else payload

    def _collect_by_page(
        self, cfg: dict[str, Any], queries: list[str], notes: list[str]
    ) -> list[dict]:
        """Discover advertisers by keyword, then measure them by page.

        Only the page view carries real per-ad start dates, so this is the only
        path that can honestly answer "which of these is working".
        """
        country = (cfg.get("countries") or ["US"])[0]
        media_type = cfg.get("media_type", "video")
        active_status = cfg.get("active_status", "active")

        page_urls = list(cfg.get("seed_pages") or [])
        notes.append(str(len(page_urls)) + " seed advertiser pages.")

        budget = int(cfg.get("max_pages", 8))
        if len(page_urls) < budget and queries:
            discovered = apify_client.discover_pages(
                queries,
                country=country,
                media_type=media_type,
                active_status=active_status,
                results_per_query=int(cfg.get("discover_limit", 25)),
            )
            self.announce("discovered " + str(len(discovered)) + " advertisers by keyword")
            notes.append(str(len(discovered)) + " advertisers discovered by keyword search.")
            for page_id in list(discovered)[: budget - len(page_urls)]:
                page_urls.append(
                    apify_client.build_page_url(
                        page_id,
                        country=country,
                        media_type=media_type,
                        active_status=active_status,
                    )
                )

        return apify_client.scrape_pages(
            page_urls[:budget],
            results_limit=int(cfg.get("results_per_page", 20)),
            active_status=active_status,
        )

    def _collect_by_keyword(
        self, cfg: dict[str, Any], queries: list[str], notes: list[str]
    ) -> list[dict]:
        notes.append(
            "Keyword mode: Meta returns start == end == scrape date for these rows, so "
            "longevity is unavailable and the scorer reweights onto relevance."
        )
        return apify_client.run_ad_search(
            queries,
            country=(cfg.get("countries") or ["US"])[0],
            media_type=cfg.get("media_type", "video"),
            active_status=cfg.get("active_status", "active"),
            results_per_query=int(cfg.get("results_per_query", 40)),
        )

    def _normalise_and_filter(
        self, raw: list[dict], window_days: int, notes: list[str]
    ) -> list[dict]:
        seen: set[str] = set()
        ads: list[dict] = []
        dropped = 0
        for item in raw:
            ad = apify_client.normalise(item)
            if not ad["ad_archive_id"] or ad["ad_archive_id"] in seen:
                continue
            if not apify_client.within_window(ad, window_days):
                dropped += 1
                continue
            seen.add(ad["ad_archive_id"])
            ads.append(ad)
        if dropped:
            notes.append(str(dropped) + " ads dropped for falling outside the window.")
        return ads

    # -- scoring ------------------------------------------------------------
    W_LONGEVITY, W_SCALE, W_RELEVANCE = 0.45, 0.25, 0.30

    @classmethod
    def _winner_score(cls, ad: dict) -> float:
        """Blend the three signals - but never credit longevity we did not see.

        Keyword-search rows come back with start == end == the scrape date. That
        is a missing value, not a one-day ad, and scoring it as zero would rank
        a genuine winner below a spam ad that happened to match more keywords.
        When longevity is unknown its weight is redistributed proportionally.
        """
        scale, relevance = ad["scale_score"], ad["relevance_score"]
        if ad.get("longevity_known"):
            return round(
                cls.W_LONGEVITY * ad["longevity_score"]
                + cls.W_SCALE * scale
                + cls.W_RELEVANCE * relevance,
                1,
            )
        total = cls.W_SCALE + cls.W_RELEVANCE
        return round((cls.W_SCALE * scale + cls.W_RELEVANCE * relevance) / total, 1)

    @staticmethod
    def _score_mechanically(ads: list[dict]) -> None:
        for ad in ads:
            days = max(ad.get("days_running", 0), 0)
            # Log curve: day 0 -> 0, day 1 -> ~15, day 7 -> ~46, day 30 -> ~76,
            # day 90 -> 100. Diminishing returns: the interesting distinction is
            # between a two-day test and a three-week runner, not between month
            # two and month three.
            ad["longevity_score"] = round(min(100.0, 100 * math.log1p(days) / math.log1p(90)), 1)
            variants = max(int(ad.get("variant_count", 1) or 1), 1)
            ad["scale_score"] = round(
                min(100.0, 100 * math.log1p(variants - 1) / math.log1p(29)), 1
            )
            ad["relevance_score"] = 0.0

    def _score_relevance(self, ads: list[dict], notes: list[str]) -> None:
        if not ads:
            return
        if self.offline:
            for ad in ads:
                ad["relevance_score"] = self._keyword_relevance(ad)
                ad["score_rationale"] = "Offline heuristic: keyword overlap with the ICP lexicon."
            notes.append("Relevance scored heuristically (offline).")
            return

        # Only the mechanically plausible candidates are worth an LLM opinion.
        # Scoring all 40 is a large prompt for no gain: an ad that is neither
        # long-running nor scaled will not reach the top 12 whatever its
        # relevance, and free-tier providers throttle hard on long prompts.
        ranked = sorted(
            ads, key=lambda a: (a["longevity_score"] + a["scale_score"]), reverse=True
        )[:20]
        payload = [
            {
                "id": ad["ad_archive_id"],
                "advertiser": ad["page_name"],
                "copy": ad["ad_copy"][:400],
                "cta": ad.get("cta_text"),
                "days_running": ad["days_running"] if ad.get("longevity_known") else None,
                "variants": ad["variant_count"],
            }
            for ad in ranked
        ]
        task = (
            "Score each of these Meta ads for relevance to the CrowdWisdom Trading ICP "
            "and category, 0-100. Then write one sentence saying what the ad is really "
            "selling and whether the length of its run reads as a genuine winner.\n\n"
            + json.dumps(payload, indent=1)[:60000]
        )
        schema = (
            '{"scores": [{"id": "<ad id>", "relevance": 0-100, '
            '"rationale": "<one sentence>"}]}'
        )
        try:
            result = self.hermes().run_json(task, schema_hint=schema)
            by_id = self._parse_scores(result)
            if not by_id:
                warn("model returned no parseable scores; using keyword heuristic")
                notes.append("Agent returned an unusable score payload; heuristic used.")
            for ad in ads:  # ads outside `ranked` fall back to the heuristic
                entry = by_id.get(ad["ad_archive_id"])
                if entry:
                    ad["relevance_score"] = entry[0]
                    ad["score_rationale"] = entry[1]
                else:
                    ad["relevance_score"] = self._keyword_relevance(ad)
        except Exception as exc:  # noqa: BLE001 - never lose a run over scoring
            warn("agent relevance scoring failed (" + str(exc) + "); using keyword heuristic")
            notes.append("Agent scoring unavailable; keyword heuristic used.")
            for ad in ads:
                ad["relevance_score"] = self._keyword_relevance(ad)

    # Weaker models rename the wrapper and the fields - "ads" instead of
    # "scores", "relevance_score" instead of "relevance" - and a strict reader
    # silently discards a perfectly good answer, leaving every ad on the keyword
    # heuristic with no sign anything went wrong. Read the shape loosely.
    _LIST_KEYS = ("scores", "ads", "results", "items", "data")
    _SCORE_KEYS = ("relevance", "relevance_score", "score", "rating")
    _WHY_KEYS = ("rationale", "reason", "why", "explanation", "note")

    @classmethod
    def _parse_scores(cls, result: Any) -> dict[str, tuple[float, str]]:
        """Pull {ad_id: (relevance, rationale)} out of whatever the model sent."""
        rows: Any = None
        if isinstance(result, list):
            rows = result
        elif isinstance(result, dict):
            for key in cls._LIST_KEYS:
                if isinstance(result.get(key), list):
                    rows = result[key]
                    break
            else:  # a bare {id: score} mapping
                rows = [
                    {"id": k, "relevance": v}
                    for k, v in result.items()
                    if isinstance(v, (int, float))
                ]
        if not rows:
            return {}

        out: dict[str, tuple[float, str]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            ad_id = str(row.get("id") or row.get("ad_archive_id") or "").strip()
            if not ad_id:
                continue
            score = next(
                (row[k] for k in cls._SCORE_KEYS if isinstance(row.get(k), (int, float))), None
            )
            if score is None:
                continue
            why = next((str(row[k]) for k in cls._WHY_KEYS if row.get(k)), "")
            out[ad_id] = (max(0.0, min(100.0, float(score))), why)
        return out

    _LEXICON = (
        "trade",
        "trading",
        "trader",
        "stock",
        "stocks",
        "option",
        "options",
        "signal",
        "signals",
        "alert",
        "alerts",
        "market",
        "invest",
        "investing",
        "portfolio",
        "crypto",
        "forex",
        "futures",
        "chart",
        "setup",
        "entry",
        "watchlist",
    )

    # The heuristic measures topicality, the agent measures fit. They are not
    # the same quantity, and mixing them at full scale in one ranking let a
    # keyword-stuffed spam ad ("KK -GBookstore-ct", relevance 100) outrank a
    # 145-day Motley Fool ad the agent had honestly scored 25. Cap the
    # heuristic at "plausibly relevant" so an unjudged ad can never beat a
    # judged one on relevance alone.
    HEURISTIC_CEILING = 60.0

    def _keyword_relevance(self, ad: dict) -> float:
        text = (ad.get("ad_copy", "") + " " + str(ad.get("title") or "")).lower()
        hits = sum(1 for word in self._LEXICON if word in text)
        return round(min(self.HEURISTIC_CEILING, hits * 7.5), 1)

    # -- reporting ----------------------------------------------------------
    @staticmethod
    def _print(winners: list[dict]) -> None:
        if not winners:
            warn("no winning ads found")
            return
        table(
            "Top ads, last 30 days",
            ["#", "Advertiser", "Days", "Var", "Fmt", "Score", "Hook line"],
            [
                [
                    i + 1,
                    ad["page_name"][:22],
                    str(ad["days_running"]) if ad.get("longevity_known") else "?",
                    ad["variant_count"],
                    ad["media_type"][:5],
                    ad["winner_score"],
                    (ad["ad_copy"][:46] + "...") if len(ad["ad_copy"]) > 46 else ad["ad_copy"],
                ]
                for i, ad in enumerate(winners[:10])
            ],
        )
