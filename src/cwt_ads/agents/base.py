"""Shared machinery for every agent: prompts, artifacts, Hermes wiring."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from .. import hermes_runtime
from ..config import brand, env, pipeline
from ..logging_utils import ok, redact, step


def now() -> datetime:
    return datetime.now(timezone.utc)


def brand_block() -> str:
    """The brand bible, rendered for a prompt. Agents get facts, not vibes."""
    return yaml.safe_dump(brand(), sort_keys=False, allow_unicode=True, width=100)


def claim_ids() -> list[str]:
    return [c["id"] for c in brand()["product"]["verified_claims"]]


_QUOTED = re.compile(r'"([^"\n]{3,})"')
_UNIVERSAL_PLACEHOLDERS = {
    "string",
    "str",
    "text",
    "0",
    "",
    "<one sentence>",
    "snake_case_id",
    "short name",
}


def _walk_strings(node: Any):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_strings(value)


def looks_like_echoed_schema(data: Any, schema_text: str, threshold: float = 0.30) -> bool:
    """True when the model returned the schema hint instead of an answer.

    A weak model handed a JSON template will sometimes fill nothing in and
    return the template: `"advertiser": "string"`, `"whitespace": "the angle
    nobody in the niche is running"`. That parses, and with lenient enum
    coercion it also *validates* - so it sails past every type-level guard and
    silently poisons every downstream agent with placeholder prose. The only
    way to catch it is to compare the content against the hint we sent.
    """
    placeholders = {p.strip().lower() for p in _QUOTED.findall(schema_text)}
    placeholders |= _UNIVERSAL_PLACEHOLDERS

    values = [v.strip().lower() for v in _walk_strings(data) if v and v.strip()]
    if not values:
        return True
    echoed = sum(1 for v in values if v in placeholders)
    return echoed / len(values) >= threshold


def save_json(path: Path, payload: Any, meta: dict[str, Any] | None = None) -> Path:
    """Write a human-readable artifact with a provenance header."""
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    if isinstance(data, dict):
        data = {"_meta": _meta(meta), **data}
    else:
        data = {"_meta": _meta(meta), "items": data}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Provider errors quoted into notes can carry a token in a URL.
    body = redact(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    path.write_text(body, encoding="utf-8")
    ok("wrote " + path.name + "  (" + str(path.stat().st_size // 1024) + " KB)")
    return path


def _meta(extra: dict[str, Any] | None) -> dict[str, Any]:
    meta = {
        "project": "CrowdWisdom Video Ads Agent",
        "generated_at": now().isoformat(),
        "llm_transport": hermes_runtime.transport(),
        "schema": "see src/cwt_ads/schemas.py",
    }
    if extra:
        meta.update(extra)
    return meta


class Agent:
    """One member of the team.

    Subclasses declare `id`, `role`, `charter` and `system_prompt`, then
    implement `run()`. The base class hands them a configured Hermes agent.
    """

    id: str = "agent"
    role: str = "Agent"
    charter: str = ""
    temperature: float = 0.7
    max_tokens: int = 8000

    def __init__(self, run_dir: Path, *, offline: bool = False) -> None:
        self.run_dir = run_dir
        self.offline = offline
        self.cfg = pipeline()
        self._agent_cfg = next(
            (a for a in self.cfg.get("agents", []) if a.get("id") == self.id), {}
        )
        if self._agent_cfg.get("charter"):
            self.charter = self._agent_cfg["charter"]

    # ── prompt surface ─────────────────────────────────────────────────────
    @property
    def system_prompt(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    @property
    def model(self) -> str | None:
        """Resolve the model for this agent.

        Precedence: an explicit per-agent model in pipeline.yaml (a deliberate
        creative choice) > CWT_MODEL in the environment (deployment reality:
        which models this machine can actually afford) > the pipeline default.
        Environment beating the file default is what lets a zero-balance account
        switch every agent onto a free model with one line in .env.
        """
        return (
            self._agent_cfg.get("model")
            or env("CWT_MODEL")
            or self.cfg.get("defaults", {}).get("model")
        )

    def hermes(self, **overrides: Any) -> hermes_runtime.HermesAgent:
        kwargs: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "charter": self.charter,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "transcript_dir": self.run_dir / "hermes_transcripts",
        }
        kwargs.update(overrides)
        return hermes_runtime.HermesAgent(**kwargs)

    # ── lifecycle ──────────────────────────────────────────────────────────
    def announce(self, message: str) -> None:
        step(self.id, message)

    def run(self, **kwargs: Any) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError
