"""Direct LLM access (OpenRouter / NVIDIA build) + tolerant JSON extraction.

This is the *fallback* transport. The preferred path is the Hermes AIAgent
runtime in `hermes_runtime.py`, which uses this module only when a Hermes
checkout is not available.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

from .config import env
from .logging_utils import warn

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


class LLMError(RuntimeError):
    pass


class LLMUnavailable(LLMError):
    """No provider key configured."""


class LLMCredit(LLMError):
    """Provider refused on auth or balance. Not transient, so never retried."""


class LLMTimeout(LLMError):
    """Deadline exceeded. Retried at most once - a model that cannot finish the
    prompt in the budget will not finish it on the third attempt either."""


def _provider() -> tuple[str, str, str]:
    """Return (name, url, api_key) for the first configured provider."""
    key = env("OPENROUTER_API_KEY")
    if key:
        return "openrouter", OPENROUTER_URL, key
    key = env("NVIDIA_API_KEY")
    if key:
        return "nvidia", NVIDIA_URL, key
    raise LLMUnavailable(
        "No LLM key found. Set OPENROUTER_API_KEY (or NVIDIA_API_KEY) in .env, "
        "or run the pipeline with --offline to use bundled fixtures."
    )


def default_model() -> str:
    return env("CWT_MODEL") or "anthropic/claude-sonnet-4.6"


def _post_with_deadline(
    url: str, headers: dict[str, str], payload: dict[str, Any], deadline: float
) -> requests.Response:
    """POST with a hard wall-clock limit on the whole response.

    `requests`' own `timeout` is per socket operation, not per request: a
    provider that trickles bytes resets it on every chunk and the call hangs
    indefinitely. Stream the body and enforce a real deadline on top.

    Every way the provider can go quiet - refusing to answer, accepting and
    then stalling, or dribbling past the deadline - is raised as `LLMTimeout`,
    because all three mean the same thing operationally and none of them are
    worth three retries with backoff.
    """
    started = time.monotonic()

    try:
        resp = requests.post(
            url, headers=headers, json=payload, timeout=(15, 60), stream=True
        )
    except requests.exceptions.Timeout as exc:
        raise LLMTimeout("provider did not respond: " + str(exc)[:160]) from exc

    if resp.status_code >= 400:
        resp.content  # materialise the error body so the caller can read it
        return resp

    chunks: list[bytes] = []
    try:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
            if time.monotonic() - started > deadline:
                resp.close()
                raise LLMTimeout(
                    "provider exceeded the "
                    + str(int(deadline))
                    + "s deadline while streaming (received "
                    + str(sum(len(c) for c in chunks))
                    + " bytes). Free tiers throttle hard under load; raise "
                    "CWT_LLM_DEADLINE or use a faster model."
                )
    except requests.exceptions.RequestException as exc:
        resp.close()
        raise LLMTimeout(
            "provider stalled after "
            + str(int(time.monotonic() - started))
            + "s: "
            + str(exc)[:160]
        ) from exc

    resp._content = b"".join(chunks)  # noqa: SLF001 - fill the cached body
    resp._content_consumed = True  # noqa: SLF001
    return resp


def chat(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 8000,
    json_mode: bool = False,
    retries: int = 3,
) -> str:
    name, url, api_key = _provider()
    model = model or default_model()
    if name == "nvidia" and "/" in model and model.startswith("anthropic/"):
        model = "meta/llama-3.3-70b-instruct"  # anthropic ids do not exist on NVIDIA NIM

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if name == "openrouter":
        headers["HTTP-Referer"] = "https://crowdwisdomtrading.com"
        headers["X-Title"] = "CrowdWisdom Video Ads Agent"

    # requests' `timeout` is per socket read, not per request: a provider that
    # trickles bytes slowly (free tiers do, under load) resets it on every
    # chunk and the call hangs indefinitely. Stream the response and enforce a
    # real wall-clock deadline on top.
    deadline = float(env("CWT_LLM_DEADLINE") or 240)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = _post_with_deadline(url, headers, payload, deadline)
            if resp.status_code in (401, 402, 403):
                # Not transient. OpenRouter reserves against max_tokens up
                # front, so a zero-balance account fails a big call while a
                # tiny probe succeeds - which makes this look flaky when it is
                # not. Fail loudly and immediately with the actual fix.
                raise LLMCredit(
                    "Provider refused the request (HTTP "
                    + str(resp.status_code)
                    + "): "
                    + resp.text[:200]
                    + "\nOpenRouter reserves credit against max_tokens ("
                    + str(max_tokens)
                    + " here), so a paid model needs a funded balance even for a "
                    "short reply. Either add credit, or set a free model in .env, "
                    "e.g. CWT_MODEL=nvidia/nemotron-3.5-lightning:free"
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise LLMError(f"{resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"] or ""
        except LLMCredit:
            raise
        except Exception as exc:  # noqa: BLE001 - retried below
            last_error = exc
            # A timeout gets one attempt, not `retries`: if the provider could
            # not finish inside the deadline it will not finish inside the same
            # deadline twice more, and burning 3x the budget on it delays the
            # fallback that was always going to run.
            budget = 1 if isinstance(exc, LLMTimeout) else retries
            if attempt >= budget:
                break
            backoff = 2**attempt
            warn(f"LLM call failed ({exc}); retrying in {backoff}s")
            time.sleep(backoff)
    raise LLMError(f"LLM call gave up after {attempt} attempt(s): {last_error}")


# ── JSON extraction ─────────────────────────────────────────────────────────
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Pull the first JSON value out of a model response.

    Models wrap JSON in prose or fences even when told not to, so try, in
    order: the raw string, any fenced block, then the widest balanced
    ``{...}``/``[...]`` span in the text.
    """
    text = (text or "").strip()
    if not text:
        raise LLMError("empty model response")

    for candidate in _candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise LLMError(f"could not parse JSON from model response: {text[:400]}")


def _candidates(text: str):
    yield text
    for block in _FENCE.findall(text):
        yield block.strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            yield text[start : end + 1]


def chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 8000,
    retries: int = 2,
) -> Any:
    """Ask for JSON and keep asking until it parses."""
    prompt = user
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        raw = chat(
            system,
            prompt,
            model=model,
            temperature=temperature if attempt == 0 else min(temperature, 0.3),
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            return extract_json(raw)
        except LLMError as exc:
            last_error = exc
            prompt = (
                f"{user}\n\n---\nYour previous reply was not valid JSON ({exc}). "
                "Reply with the JSON object ONLY. No prose, no code fences."
            )
    raise LLMError(f"model never returned valid JSON: {last_error}")
