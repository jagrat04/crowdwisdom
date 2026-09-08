"""Time-boxed web research via Tavily and Exa.

Both providers are used when both keys are present: Tavily is better at
answer-shaped recall, Exa at finding the odd forum thread where a real trader
says the quiet part out loud. Every query is constrained to the last N days,
per the assignment.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from ..config import env
from ..logging_utils import step, warn

TAVILY_URL = "https://api.tavily.com/search"
EXA_URL = "https://api.exa.ai/search"


def available_providers() -> list[str]:
    providers = []
    if env("TAVILY_API_KEY"):
        providers.append("tavily")
    if env("EXA_API_KEY"):
        providers.append("exa")
    return providers


def _window_start(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def tavily_search(query: str, *, days: int = 30, max_results: int = 8) -> list[dict[str, Any]]:
    key = env("TAVILY_API_KEY")
    if not key:
        return []
    payload = {
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "days": days,
        "time_range": "month" if days <= 31 else "year",
        "include_answer": False,
        "include_raw_content": False,
        "topic": "general",
    }
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key}
    try:
        resp = requests.post(TAVILY_URL, json={**payload, "api_key": key}, headers=headers, timeout=90)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        warn("tavily failed for '" + query + "': " + str(exc))
        return []

    out = []
    for hit in data.get("results", []) or []:
        out.append(
            {
                "query": query,
                "provider": "tavily",
                "title": hit.get("title", "")[:300],
                "url": hit.get("url", ""),
                "published_date": hit.get("published_date"),
                "snippet": (hit.get("content") or "")[:1200],
                "relevance": float(hit.get("score") or 0.0),
            }
        )
    step("research_agent", "tavily: " + query + " -> " + str(len(out)) + " hits")
    return out


def exa_search(query: str, *, days: int = 30, max_results: int = 8) -> list[dict[str, Any]]:
    key = env("EXA_API_KEY")
    if not key:
        return []
    payload = {
        "query": query,
        "numResults": max_results,
        "type": "auto",
        "startPublishedDate": _window_start(days).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "contents": {"text": {"maxCharacters": 1200}, "highlights": {"numSentences": 2}},
    }
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    try:
        resp = requests.post(EXA_URL, json=payload, headers=headers, timeout=90)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        warn("exa failed for '" + query + "': " + str(exc))
        return []

    out = []
    for hit in data.get("results", []) or []:
        highlights = hit.get("highlights") or []
        snippet = " ".join(highlights) if highlights else (hit.get("text") or "")
        out.append(
            {
                "query": query,
                "provider": "exa",
                "title": (hit.get("title") or "")[:300],
                "url": hit.get("url", ""),
                "published_date": hit.get("publishedDate"),
                "snippet": snippet[:1200],
                "relevance": float(hit.get("score") or 0.0),
            }
        )
    step("research_agent", "exa: " + query + " -> " + str(len(out)) + " hits")
    return out


def search_all(
    queries: list[str], *, days: int = 30, max_results: int = 8
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run every query against every configured provider, de-duplicated by URL."""
    providers = available_providers()
    if not providers:
        return [], []

    seen: set[str] = set()
    findings: list[dict[str, Any]] = []
    for query in queries:
        for provider in providers:
            fn = tavily_search if provider == "tavily" else exa_search
            for hit in fn(query, days=days, max_results=max_results):
                url = hit.get("url") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                findings.append(hit)
    return findings, providers
