"""CrowdWisdom proprietary prediction data.

The two sample records in data/unique/ are the real CrowdWisdom export format
(the files linked in the assignment brief). Drop any number of additional
exports into that folder and they are picked up automatically.

Beyond loading, this module does the thing an ad needs: it turns a prediction
row into *cinematic facts* - risk/reward, the spread between the four listening
channels, how lopsided the consensus is - because "youtube 10 / x 30 / reddit 0
/ groq 60" is a picture, and "confidence 46" is a dial that can move on screen.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import UNIQUE_DIR
from ..logging_utils import warn

CHANNEL_LABELS = {
    "youtube": "YouTube",
    "x": "X / Twitter",
    "reddit": "Reddit",
    "groq": "News + LLM synthesis",
}


def _num(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def load_predictions(directory: Path | None = None) -> list[dict[str, Any]]:
    directory = directory or UNIQUE_DIR
    records: list[dict[str, Any]] = []
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            warn("could not read unique data file " + path.name + ": " + str(exc))
            continue
        for record in raw if isinstance(raw, list) else [raw]:
            if isinstance(record, dict):
                record["_source_file"] = path.name
                records.append(record)
    return records


def enrich(record: dict[str, Any]) -> dict[str, Any]:
    """Add the derived numbers an ad can actually dramatise."""
    price = _num(record.get("current price"))
    t1 = _num(record.get("target 1"))
    t2 = _num(record.get("target 2"))
    s1 = _num(record.get("stop 1"))
    confidence = _num(record.get("confidence level")) or 0.0

    upside_pct = round((t1 - price) / price * 100, 2) if price and t1 else None
    stretch_pct = round((t2 - price) / price * 100, 2) if price and t2 else None
    risk_pct = round((price - s1) / price * 100, 2) if price and s1 else None
    rr = round(abs(upside_pct / risk_pct), 2) if upside_pct and risk_pct else None

    weights = record.get("sources weights") or {}
    weights = {k: float(v) for k, v in weights.items() if _num(v) is not None}
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    dominant = ranked[0] if ranked else None
    silent = [CHANNEL_LABELS.get(k, k) for k, v in weights.items() if v == 0]

    return {
        "ticker": record.get("ticker", "?"),
        "date": record.get("date"),
        "title": record.get("title", ""),
        "direction": record.get("direction", ""),
        "confidence": confidence,
        "confidence_band": _band(confidence),
        "confidence_reasoning": record.get("confidence reasoning", ""),
        "price": price,
        "target_1": t1,
        "target_2": t2,
        "stop_1": s1,
        "stop_2": _num(record.get("stop 2")),
        "upside_pct": upside_pct,
        "stretch_pct": stretch_pct,
        "risk_pct": risk_pct,
        "risk_reward": rr,
        "target_method": record.get("target method", ""),
        "source_weights": weights,
        "source_weights_labelled": {CHANNEL_LABELS.get(k, k): v for k, v in weights.items()},
        "dominant_channel": CHANNEL_LABELS.get(dominant[0], dominant[0]) if dominant else None,
        "dominant_channel_weight": dominant[1] if dominant else None,
        "silent_channels": silent,
        "consensus_narrative": record.get("Wisdom of Professional Traders", ""),
        "key_insights": record.get("Key Insights", ""),
        "recent_performance": record.get("Recent Performance", ""),
        "expert_analysis": record.get("Expert Analysis", ""),
        "news_impact": record.get("News Impact", ""),
        "recommendation": record.get("Trading Recommendation", ""),
        "source_file": record.get("_source_file"),
    }


def _band(confidence: float) -> str:
    if confidence >= 75:
        return "high conviction - the crowd agrees"
    if confidence >= 50:
        return "moderate - the crowd leans"
    return "low - thin evidence, stated as such"


def dataset() -> list[dict[str, Any]]:
    return [enrich(r) for r in load_predictions()]


def cinematic_brief(limit: int = 4) -> dict[str, Any]:
    """The compact, ad-ready view handed to the Script Agent.

    Picks the record with the widest channel spread, because an ad needs one
    number that visibly disagrees with another number.
    """
    rows = dataset()
    if not rows:
        return {"available": False, "predictions": [], "hero": None, "talking_points": []}

    def spread(row: dict[str, Any]) -> float:
        weights = list(row.get("source_weights", {}).values())
        return (max(weights) - min(weights)) if weights else 0.0

    hero = max(rows, key=spread)
    points = [
        "Every prediction publishes its own confidence level, not just a direction "
        "(this one is " + str(int(hero["confidence"])) + "/100, and says why).",
        "The weighting across the four listening channels is disclosed per call: "
        + ", ".join(str(k) + " " + str(int(v)) for k, v in hero["source_weights_labelled"].items())
        + ".",
        "Every call ships with entry, two targets and two stops - the discipline "
        "most retail traders never write down.",
    ]
    if hero.get("silent_channels"):
        points.append(
            "Channels that had nothing to say are shown as zero rather than padded: "
            + ", ".join(hero["silent_channels"])
            + " contributed nothing to this call."
        )
    if hero.get("risk_reward"):
        points.append(
            "The published risk/reward on this call is "
            + str(hero["risk_reward"])
            + ":1, computed from the levels above."
        )

    return {
        "available": True,
        "count": len(rows),
        "hero": hero,
        "predictions": rows[:limit],
        "talking_points": points,
    }
