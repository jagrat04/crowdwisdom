"""Meta Ad Library mining through Apify.

Uses the canonical Ad Library actor (apify/facebook-ads-scraper).

A note on why this module has two search modes, because it is the single most
important thing about the ad data and it is not obvious until you look at a
real payload:

  * **Keyword search** (`?q=...&search_type=keyword_unordered`) is what you
    reach for first, and its dates are useless. Every row comes back with
    `startDate == endDate == today` and a `totalActiveTime` measured in hours,
    because the keyword view returns *today's delivery record* rather than the
    ad's life. `collationCount` is almost always 1. So longevity - the whole
    reason we can infer what is working - is simply absent.

  * **Page search** (a Facebook page URL, or `?view_all_page_id=...`) returns
    the real thing: per-ad `startDate` spanning months, honest `endDate`, and
    meaningful `collationCount`.

So the Ads Manager discovers advertisers by keyword and then measures them by
page. `longevity_known` records which of the two produced a given row, and the
scorer refuses to credit longevity it did not actually observe.

Field names in the live payload are camelCase (`ctaText`, `videoHdUrl`,
`startDateFormatted`); several older/aliased spellings also appear. The
normaliser reads all of them.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from ..config import env
from ..logging_utils import step, warn

APIFY_BASE = "https://api.apify.com/v2"
DEFAULT_ACTOR = "apify/facebook-ads-scraper"
AD_LIBRARY = "https://www.facebook.com/ads/library/"


class ApifyUnavailable(RuntimeError):
    pass


class ApifyOutOfCredit(ApifyUnavailable):
    """The account has no usage credit left this cycle."""


def actor_id() -> str:
    return (env("APIFY_ADS_ACTOR") or DEFAULT_ACTOR).replace("/", "~")


# -- URL builders ------------------------------------------------------------
def build_search_url(
    query: str,
    *,
    country: str = "US",
    media_type: str = "video",
    active_status: str = "active",
    ad_type: str = "all",
) -> str:
    """Keyword search. Good for discovering advertisers, bad for dates."""
    params = {
        "active_status": active_status,
        "ad_type": ad_type,
        "country": country,
        "q": query,
        "search_type": "keyword_unordered",
        "media_type": media_type,
        "sort_data[direction]": "desc",
        "sort_data[mode]": "relevancy_monthly_grouped",
    }
    return AD_LIBRARY + "?" + urlencode(params)


def build_page_url(
    page_id: str,
    *,
    country: str = "US",
    media_type: str = "video",
    active_status: str = "active",
    ad_type: str = "all",
) -> str:
    """Page view. This is the one with real start dates."""
    params = {
        "active_status": active_status,
        "ad_type": ad_type,
        "country": country,
        "view_all_page_id": page_id,
        "search_type": "page",
        "media_type": media_type,
    }
    return AD_LIBRARY + "?" + urlencode(params)


# -- running the actor -------------------------------------------------------
def _run(payload: dict[str, Any], *, timeout: int) -> list[dict[str, Any]]:
    token = env("APIFY_TOKEN")
    if not token:
        raise ApifyUnavailable(
            "APIFY_TOKEN is not set. Get a free token at "
            "https://console.apify.com/settings/integrations, or run with --offline."
        )
    resp = requests.post(
        APIFY_BASE + "/acts/" + actor_id() + "/run-sync-get-dataset-items",
        params={"token": token, "timeout": timeout, "format": "json"},
        json=payload,
        timeout=timeout + 30,
    )
    if resp.status_code in (401, 402, 403):
        # Apify answers an exhausted free plan with a bare 403 on the run
        # endpoint. Whatever the wording, none of these are worth retrying
        # against eleven more queries - stop the whole phase now.
        raise ApifyOutOfCredit(
            "Apify refused the run (HTTP "
            + str(resp.status_code)
            + "). Usual cause is an exhausted free-plan credit for this billing "
            "cycle; it can also be a bad or revoked token. Check "
            "https://console.apify.com/billing. Falling back to the bundled fixture."
        )
    resp.raise_for_status()
    batch = resp.json()
    return batch if isinstance(batch, list) else []


def discover_pages(
    queries: list[str],
    *,
    country: str = "US",
    media_type: str = "video",
    active_status: str = "active",
    results_per_query: int = 30,
    timeout: int = 900,
) -> dict[str, str]:
    """Keyword-search the library to find *who* is advertising in the niche.

    Returns page_id -> page_name. The ads themselves are discarded: their dates
    cannot be trusted, and we are only here for the advertiser list.
    """
    pages: dict[str, str] = {}
    for query in queries:
        url = build_search_url(
            query, country=country, media_type=media_type, active_status=active_status
        )
        step("ads_manager", "apify discovery: " + query)
        try:
            batch = _run(
                {
                    "startUrls": [{"url": url}],
                    "resultsLimit": results_per_query,
                    "activeStatus": active_status,
                    "isDetailsPerAd": False,
                },
                timeout=timeout,
            )
        except ApifyOutOfCredit:
            raise
        except Exception as exc:  # noqa: BLE001 - one bad query must not kill the mine
            warn("apify discovery failed for " + query + ": " + str(exc))
            continue
        found = 0
        for item in batch:
            pid = str(_first(item, "pageId", "pageID", "page_id", default="") or "")
            name = str(_first(item, "pageName", "page_name", default="") or "")
            if pid and pid not in pages:
                pages[pid] = name
                found += 1
        step("ads_manager", "   -> " + str(len(batch)) + " ads, " + str(found) + " new advertisers")
    return pages


def scrape_pages(
    page_urls: list[str],
    *,
    results_limit: int = 20,
    active_status: str = "active",
    timeout: int = 900,
    label: str = "",
) -> list[dict[str, Any]]:
    """Scrape advertiser pages. These rows carry real lifetimes."""
    items: list[dict[str, Any]] = []
    for url in page_urls:
        step("ads_manager", "apify page: " + url[:90])
        try:
            batch = _run(
                {
                    "startUrls": [{"url": url}],
                    "resultsLimit": results_limit,
                    "activeStatus": active_status,
                    "isDetailsPerAd": False,
                },
                timeout=timeout,
            )
        except ApifyOutOfCredit:
            raise
        except Exception as exc:  # noqa: BLE001
            warn("apify page scrape failed for " + url[:70] + ": " + str(exc))
            continue
        for item in batch:
            if isinstance(item, dict):
                item["_cwt_query"] = label or url
                item["_cwt_source"] = "page"
                items.append(item)
        step("ads_manager", "   -> " + str(len(batch)) + " ads")
    return items


def run_ad_search(
    queries: list[str],
    *,
    country: str = "US",
    media_type: str = "video",
    active_status: str = "active",
    results_per_query: int = 40,
    timeout: int = 900,
) -> list[dict[str, Any]]:
    """Keyword-only mining. Kept for discovery and for callers that want it.

    Prefer `discover_pages` + `scrape_pages`: these rows have no usable dates.
    """
    items: list[dict[str, Any]] = []
    for query in queries:
        url = build_search_url(
            query, country=country, media_type=media_type, active_status=active_status
        )
        step("ads_manager", "apify keyword: " + query)
        try:
            batch = _run(
                {
                    "startUrls": [{"url": url}],
                    "resultsLimit": results_per_query,
                    "activeStatus": active_status,
                    "isDetailsPerAd": False,
                },
                timeout=timeout,
            )
        except ApifyOutOfCredit:
            raise
        except Exception as exc:  # noqa: BLE001
            warn("apify run failed for " + query + ": " + str(exc))
            continue
        for item in batch:
            if isinstance(item, dict):
                item["_cwt_query"] = query
                item["_cwt_source"] = "keyword"
                items.append(item)
        step("ads_manager", "   -> " + str(len(batch)) + " ads")
    return items


# -- normalisation -----------------------------------------------------------
def _first(d: dict[str, Any], *paths: str, default: Any = None) -> Any:
    """Fetch the first present value from a list of dotted paths."""
    for path in paths:
        node: Any = d
        for part in path.split("."):
            if isinstance(node, list) and part.isdigit():
                idx = int(part)
                node = node[idx] if idx < len(node) else None
            elif isinstance(node, dict):
                node = node.get(part)
            else:
                node = None
            if node is None:
                break
        if node not in (None, "", [], {}):
            return node
    return default


def _to_date(value: Any) -> str | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    for fmt in ("%b %d, %Y", "%d %b %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# Live payload uses camelCase; older exports use snake_case. Read both.
_VIDEO_KEYS = ("videoHdUrl", "videoSdUrl", "video_hd_url", "video_sd_url", "videoUrl")
_IMAGE_KEYS = (
    "originalImageUrl",
    "resizedImageUrl",
    "original_image_url",
    "resized_image_url",
    "imageUrl",
)


def _collect_urls(node: Any, keys: tuple[str, ...], out: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in keys and isinstance(value, str) and value.startswith("http"):
                out.append(value)
            else:
                _collect_urls(value, keys, out)
    elif isinstance(node, list):
        for value in node:
            _collect_urls(value, keys, out)


def normalise(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten one raw Apify/Meta ad record into WinningAd fields."""
    snapshot = item.get("snapshot") or {}

    ad_id = str(
        _first(item, "adArchiveID", "adArchiveId", "ad_archive_id", "adId", "id", default="") or ""
    )

    body = _first(
        item,
        "snapshot.body.text",
        "snapshot.body.markup.__html",
        "snapshot.caption",
        "ad_creative_bodies.0",
        "adCreativeBodies.0",
        "body",
        "text",
        default="",
    )
    body = re.sub(r"<[^>]+>", " ", str(body))
    body = re.sub(r"\s+", " ", body).strip()

    videos: list[str] = []
    images: list[str] = []
    _collect_urls(snapshot or item, _VIDEO_KEYS, videos)
    _collect_urls(snapshot or item, _IMAGE_KEYS, images)

    # displayFormat is Meta's own answer and beats guessing from media arrays.
    display = str(_first(item, "snapshot.displayFormat", "displayFormat", default="") or "").lower()
    if display in ("video", "image"):
        media_type = display
    elif videos:
        media_type = "video"
    elif images:
        media_type = "image"
    else:
        media_type = "unknown"

    start = _to_date(
        _first(item, "startDateFormatted", "startDate", "start_date", "ad_delivery_start_time")
    )
    end = _to_date(
        _first(item, "endDateFormatted", "endDate", "end_date", "ad_delivery_stop_time")
    )

    # Keyword-search rows report start == end == the day of the scrape. That is
    # a snapshot artefact, not a one-day ad, and it must not be scored as one.
    today = datetime.now(timezone.utc).date().isoformat()
    longevity_known = bool(start) and not (start == end == today)

    days_running = 0
    if longevity_known and start:
        stop = date.fromisoformat(end) if end else datetime.now(timezone.utc).date()
        days_running = max((stop - date.fromisoformat(start)).days, 0)

    platforms = _first(
        item, "publisherPlatform", "publisher_platform", "publisher_platforms", default=[]
    )
    if isinstance(platforms, str):
        platforms = [platforms]

    impressions = item.get("impressionsWithIndex") or {}

    return {
        "ad_archive_id": ad_id,
        "page_name": str(
            _first(item, "pageName", "page_name", "snapshot.pageName", default="unknown")
        ),
        "page_id": _first(item, "pageId", "pageID", "page_id", default=None),
        "ad_copy": body,
        "title": _first(item, "snapshot.title", "snapshot.cards.0.title", "title", default=None),
        "cta_text": _first(
            item,
            "snapshot.ctaText",
            "snapshot.cta_text",
            "snapshot.cards.0.ctaText",
            "ctaText",
            default=None,
        ),
        "link_url": _first(
            item,
            "snapshot.linkUrl",
            "snapshot.link_url",
            "snapshot.cards.0.linkUrl",
            "linkUrl",
            default=None,
        ),
        "media_type": media_type,
        "video_urls": list(dict.fromkeys(videos))[:3],
        "image_urls": list(dict.fromkeys(images))[:3],
        "publisher_platforms": [str(p).lower() for p in platforms]
        if isinstance(platforms, list)
        else [],
        "start_date": start,
        "end_date": end,
        "days_running": days_running,
        "longevity_known": longevity_known,
        "variant_count": int(
            _first(item, "collationCount", "collation_count", "total", default=1) or 1
        ),
        "is_active": bool(_first(item, "isActive", "is_active", default=True)),
        "impressions_text": impressions.get("impressionsText"),
        "matched_query": item.get("_cwt_query", ""),
        "discovery_source": item.get("_cwt_source", "unknown"),
        "ad_library_url": (AD_LIBRARY + "?id=" + ad_id) if ad_id else None,
    }


def within_window(ad: dict[str, Any], window_days: int) -> bool:
    """True if the ad was live at any point inside the last window_days."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=window_days)
    end = ad.get("end_date")
    start = ad.get("start_date")
    if end:
        return date.fromisoformat(end) >= cutoff
    if ad.get("is_active"):
        return True
    if start:
        return date.fromisoformat(start) >= cutoff
    return False
