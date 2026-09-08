"""Hermes Agent runtime integration.

Every agent in this project is a Hermes agent. There are two ways this repo
talks to Hermes, and both are first-class:

1. **In-process** — `AIAgent` imported from a local `hermes-agent` checkout
   (`https://github.com/NousResearch/hermes-agent`). This is what
   `HermesAgent.run_json()` uses and what the local pipeline runs on.
2. **Distributed** — the Hermes Kanban board, where each agent is a named
   profile that claims tasks off a shared SQLite board. See
   `src/cwt_ads/kanban.py` and `hermes/kanban/`.

If no Hermes checkout is present the runtime degrades to a direct OpenRouter
call with the identical system prompt, so the pipeline still produces the same
artifacts on a bare machine. The transport actually used is recorded in every
artifact's `_meta` block, so a reviewer can always tell which path ran.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import llm
from .config import ROOT, env, env_flag
from .logging_utils import step, warn

_CANDIDATE_HOMES = (
    "HERMES_HOME",
)


@lru_cache(maxsize=1)
def hermes_home() -> Path | None:
    """Locate a hermes-agent checkout, if there is one."""
    explicit = env("HERMES_HOME")
    candidates = [Path(explicit)] if explicit else []
    candidates += [
        ROOT / "vendor" / "hermes-agent",
        Path.home() / ".hermes" / "hermes-agent",
        Path("/usr/local/lib/hermes-agent"),
    ]
    for path in candidates:
        try:
            if (path / "run_agent.py").is_file():
                return path
        except OSError:
            continue
    return None


@lru_cache(maxsize=1)
def _import_aiagent():
    """Import `AIAgent` from the Hermes checkout, or return None."""
    if not env_flag("CWT_USE_HERMES", True):
        return None
    home = hermes_home()
    if home is None:
        return None
    home_str = str(home)
    if home_str not in sys.path:
        sys.path.insert(0, home_str)
    try:
        from run_agent import AIAgent  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 - a broken checkout must not kill the run
        warn(f"Hermes checkout at {home} could not be imported ({exc}); using direct LLM transport")
        return None
    return AIAgent


def transport() -> str:
    return "hermes.AIAgent" if _import_aiagent() is not None else "openrouter.direct"


@dataclass
class HermesAgent:
    """One named member of the marketing team.

    Mirrors a Hermes *profile*: an id, a charter, a model and a toolset
    allow-list. `hermes/profiles/<id>/config.yaml` holds the same values for
    when the agent is run by the Hermes gateway instead of in-process.
    """

    id: str
    role: str
    charter: str
    system_prompt: str
    model: str | None = None
    enabled_toolsets: list[str] | None = None
    disabled_toolsets: list[str] = field(default_factory=lambda: ["terminal", "browser"])
    temperature: float = 0.7
    max_tokens: int = 8000
    transcript_dir: Path | None = None

    # ── public API ─────────────────────────────────────────────────────────
    def run(self, task: str) -> str:
        agent_cls = _import_aiagent()
        if agent_cls is None:
            return llm.chat(
                self.system_prompt,
                task,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        return self._run_hermes(agent_cls, task)

    def run_json(self, task: str, *, schema_hint: str = "") -> Any:
        """Run the agent and return parsed JSON."""
        instruction = task
        if schema_hint:
            instruction = (
                f"{task}\n\n"
                f"Return a single JSON object matching this shape exactly:\n{schema_hint}\n\n"
                "Output JSON only — no prose, no markdown fences."
            )

        agent_cls = _import_aiagent()
        if agent_cls is None:
            return llm.chat_json(
                self.system_prompt,
                instruction,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        raw = self._run_hermes(agent_cls, instruction)
        try:
            return llm.extract_json(raw)
        except llm.LLMError:
            retry = (
                f"{instruction}\n\n---\nYour previous reply was not valid JSON. "
                "Reply with the JSON object ONLY."
            )
            return llm.extract_json(self._run_hermes(agent_cls, retry))

    # ── internals ──────────────────────────────────────────────────────────
    def _run_hermes(self, agent_cls: Any, task: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model or llm.default_model(),
            "quiet_mode": True,      # never let CLI spinners leak into our stdout
            "skip_memory": True,     # agents are stateless; the board carries state
            "skip_context_files": True,
            "ephemeral_system_prompt": self.system_prompt,
        }
        if self.enabled_toolsets is not None:
            kwargs["enabled_toolsets"] = self.enabled_toolsets
        elif self.disabled_toolsets:
            kwargs["disabled_toolsets"] = self.disabled_toolsets

        # A fresh instance per call: AIAgent carries per-conversation state and
        # is explicitly documented as not thread-safe to share.
        agent = agent_cls(**kwargs)
        result = agent.run_conversation(user_message=task, task_id=f"cwt-{self.id}")
        final = result.get("final_response", "") if isinstance(result, dict) else str(result)
        self._save_transcript(task, result)
        return final

    def _save_transcript(self, task: str, result: Any) -> None:
        if not self.transcript_dir:
            return
        try:
            self.transcript_dir.mkdir(parents=True, exist_ok=True)
            path = self.transcript_dir / f"{self.id}.json"
            messages = result.get("messages", []) if isinstance(result, dict) else []
            path.write_text(
                json.dumps(
                    {
                        "agent": self.id,
                        "role": self.role,
                        "model": self.model or llm.default_model(),
                        "task": task,
                        "messages": messages,
                    },
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )
        except OSError as exc:  # transcripts are a nicety, never a blocker
            warn(f"could not write transcript for {self.id}: {exc}")


def describe_runtime() -> str:
    home = hermes_home()
    if home:
        return f"Hermes AIAgent (checkout: {home})"
    return "direct OpenRouter transport (no hermes-agent checkout found — set HERMES_HOME)"


def log_runtime() -> None:
    step("pipeline", "LLM runtime: " + describe_runtime())
    if hermes_home() is None:
        warn(
            "For the full Hermes experience run `python -m cwt_ads.cli setup-hermes`, "
            "or clone https://github.com/NousResearch/hermes-agent and set HERMES_HOME."
        )
