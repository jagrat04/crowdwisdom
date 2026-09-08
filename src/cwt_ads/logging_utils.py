"""Console output. Rich when available, plain text when not, ASCII when the
terminal cannot encode anything better - a Windows cp1252 console must not be
able to crash a pipeline run.
"""

from __future__ import annotations

import re
import sys
from typing import Any

# Try to give the console UTF-8; fall back to ASCII glyphs if it refuses.
try:  # pragma: no cover - environment dependent
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass


def _can_encode(text: str) -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


_UNICODE_OK = _can_encode("▍✓✗·→")

G = {
    "bar": "▍" if _UNICODE_OK else "|",
    "ok": "✓" if _UNICODE_OK else "+",
    "fail": "✗" if _UNICODE_OK else "x",
    "dot": "·" if _UNICODE_OK else "-",
    "arrow": "→" if _UNICODE_OK else "->",
}


_SECRET = re.compile(
    r"(apify_api_[A-Za-z0-9]+"
    r"|sk-or-v1-[A-Za-z0-9]+"
    r"|tvly-[A-Za-z0-9\-_]+"
    r"|(?<=token=)[A-Za-z0-9\-_]{12,}"
    r"|(?<=api_key=)[A-Za-z0-9\-_]{12,}"
    r"|(?<=key=)[A-Za-z0-9\-_]{20,})"
)


def redact(text: str) -> str:
    """Strip API keys before anything is printed or stored.

    Provider errors quote the full request URL, which for Apify carries the
    token as a query parameter. That lands in console output and in saved run
    logs, which then get shared. Redact at the boundary rather than trusting
    every call site to remember.
    """
    return _SECRET.sub("<redacted>", text or "")


def ascii_safe(text: str) -> str:
    """Redact secrets, then drop characters this console cannot render."""
    text = redact(text)
    if _UNICODE_OK:
        return text
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _console: Console | None = Console(stderr=False, highlight=False)
except ImportError:  # pragma: no cover - cosmetic fallback
    _console = None
    Console = Panel = Table = None  # type: ignore[assignment]


_AGENT_STYLE = {
    "ads_manager": "bright_cyan",
    "insight_agent": "bright_magenta",
    "research_agent": "bright_yellow",
    "script_agent": "bright_green",
    "video_agent": "bright_blue",
    "pipeline": "white",
}


def _emit(rich_markup: str, plain: str) -> None:
    if _console:
        try:
            _console.print(ascii_safe(rich_markup))
            return
        except UnicodeEncodeError:  # pragma: no cover - belt and braces
            pass
    print(ascii_safe(plain))


def banner(title: str, subtitle: str = "") -> None:
    if _console:
        try:
            _console.print(
                Panel.fit(
                    ascii_safe("[bold]" + title + "[/bold]\n" + subtitle),
                    border_style="bright_black",
                )
            )
            return
        except UnicodeEncodeError:  # pragma: no cover
            pass
    print(ascii_safe("\n=== " + title + " ===\n" + subtitle))


def step(agent: str, message: str) -> None:
    style = _AGENT_STYLE.get(agent, "white")
    _emit(
        "[" + style + "]" + G["bar"] + agent.ljust(15) + "[/" + style + "] " + message,
        G["bar"] + " " + agent.ljust(15) + " " + message,
    )


def warn(message: str) -> None:
    _emit("[yellow]  ! " + message + "[/yellow]", "  ! " + message)


def ok(message: str) -> None:
    _emit(
        "[green]  " + G["ok"] + " " + message + "[/green]",
        "  " + G["ok"] + " " + message,
    )


def fail(message: str) -> None:
    _emit(
        "[red]  " + G["fail"] + " " + message + "[/red]",
        "  " + G["fail"] + " " + message,
    )


def table(title: str, columns: list[str], rows: list[list[Any]]) -> None:
    if _console:
        try:
            tbl = Table(title=ascii_safe(title), title_style="bold", header_style="bright_black")
            for col in columns:
                tbl.add_column(ascii_safe(col), overflow="fold")
            for row in rows:
                tbl.add_row(*[ascii_safe(str(cell)) for cell in row])
            _console.print(tbl)
            return
        except UnicodeEncodeError:  # pragma: no cover
            pass
    print(ascii_safe("\n" + title))
    print(ascii_safe(" | ".join(columns)))
    for row in rows:
        print(ascii_safe(" | ".join(str(cell) for cell in row)))
