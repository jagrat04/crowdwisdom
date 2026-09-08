#!/usr/bin/env python3
"""Record the Hermes Kanban board as the five agents work through it.

Drives a real board through a real run: claim a task, run that agent's stage,
complete it, which promotes the next child from `todo` to `ready` - and captures
the board after every transition. The frames are the actual `hermes kanban list`
output, rendered in a terminal style and muxed to MP4.

    python scripts/record_kanban.py --out output/kanban_board.mp4

Nothing here fakes a state: every frame is read back from kanban.db after the
transition that produced it.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from cwt_ads import kanban, pipeline  # noqa: E402
from cwt_ads.render.openmontage import ffmpeg_path  # noqa: E402

W, H = 1600, 900
BG = (8, 10, 16)
FG = (226, 232, 245)
DIM = (120, 132, 154)
GREEN = (0, 229, 160)
AMBER = (200, 169, 106)
BLUE = (110, 168, 254)

STATUS_COLOUR = {
    "done": GREEN,
    "running": AMBER,
    "ready": BLUE,
    "todo": DIM,
    "blocked": (255, 90, 110),
}


def font(size: int, bold: bool = False):
    for name in (("consolab.ttf", "consola.ttf") if bold else ("consola.ttf",)):
        p = Path("C:/Windows/Fonts") / name
        if p.is_file():
            return ImageFont.truetype(str(p), size)
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",):
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def hermes(*args: str) -> str:
    cli = kanban.hermes_cli()
    if not cli:
        raise SystemExit("hermes CLI not found")
    # text=True decodes with the console codepage (cp1252 on Windows), which
    # chokes on the check marks Hermes prints. Force UTF-8 and never let a
    # decode error kill a capture.
    r = subprocess.run(
        [cli, "kanban", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return (r.stdout or "") + (r.stderr or "")


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def board_rows() -> list[tuple[str, str, str, str]]:
    """Read the live board back: (id, status, assignee, title)."""
    rows = []
    for line in _ANSI.sub("", hermes("list")).splitlines():
        m = re.search(r"(t_[a-f0-9]+)\s+(\w+)\s+(\S+)\s+(.*)$", line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3), m.group(4).strip()))
    return rows


def frame(rows, caption: str, sub: str) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_h1, f_b, f_s = font(34, True), font(21), font(17)

    d.text((60, 46), "HERMES KANBAN", font=f_h1, fill=FG)
    d.text((60, 92), "CrowdWisdom video ads - five agents, one board", font=f_s, fill=DIM)
    d.line([(60, 128), (W - 60, 128)], fill=(38, 44, 58))

    d.text((60, 152), caption, font=f_b, fill=GREEN)
    if sub:
        d.text((60, 182), sub, font=f_s, fill=DIM)

    y = 236
    d.text((60, y), "STATUS", font=f_s, fill=DIM)
    d.text((220, y), "ASSIGNEE", font=f_s, fill=DIM)
    d.text((560, y), "TASK", font=f_s, fill=DIM)
    y += 30
    d.line([(60, y), (W - 60, y)], fill=(30, 36, 48))
    y += 22

    for _id, status, assignee, title in rows:
        colour = STATUS_COLOUR.get(status, DIM)
        d.rectangle([60, y + 6, 66, y + 24], fill=colour)
        d.text((84, y), status.upper(), font=f_b, fill=colour)
        d.text((220, y), assignee, font=f_b, fill=FG if status != "todo" else DIM)
        d.text((560, y), title[:78], font=f_b, fill=FG if status != "todo" else DIM)
        y += 42

    counts: dict[str, int] = {}
    for _i, s, _a, _t in rows:
        counts[s] = counts.get(s, 0) + 1
    tally = "   ".join(
        k + " " + str(v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
    )
    d.line([(60, H - 96), (W - 60, H - 96)], fill=(30, 36, 48))
    d.text((60, H - 74), tally or "board empty", font=f_b, fill=DIM)
    d.text((W - 60 - d.textlength("hermes kanban list", font=f_s), H - 72),
           "hermes kanban list", font=f_s, fill=DIM)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/kanban_board.mp4")
    ap.add_argument("--hold", type=float, default=2.2, help="seconds per frame")
    ap.add_argument("--offline", action="store_true", default=True)
    args = ap.parse_args()

    run_id = pipeline.new_run_id()
    print("run:", run_id)

    # Archive whatever is on the board so the recording starts clean.
    for row in board_rows():
        hermes("archive", row[0])

    ids = kanban.bootstrap(run_id, offline=args.offline, render=True, dry_run=False)
    if not ids:
        raise SystemExit("could not create the board")

    shots: list[tuple[Image.Image, float]] = []

    def capture(caption: str, sub: str = "", hold: float | None = None) -> None:
        shots.append((frame(board_rows(), caption, sub), hold or args.hold))
        print("  frame:", caption)

    capture("Board created - five linked tasks", "each child waits on its parent", 3.4)

    order = ["ads_manager", "insight_agent", "research_agent", "script_agent", "video_agent"]
    for agent_id in order:
        task_id = ids[agent_id]
        stage = kanban.STAGE_FOR_AGENT[agent_id]
        profile = kanban.PROFILES[agent_id]

        hermes("claim", task_id)
        capture(profile + " claimed " + stage, "task -> running")

        cmd = [sys.executable, "-m", "cwt_ads.cli", "stage", stage, "--run", run_id]
        if args.offline:
            cmd.append("--offline")
        env_root = str(Path(__file__).resolve().parents[1])
        subprocess.run(
            cmd,
            cwd=env_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1200,
            env={**os.environ, "PYTHONPATH": env_root + "/src"},
        )

        hermes("complete", task_id, "--result", stage + " artifact written")
        capture(profile + " completed " + stage, "task -> done, next task promoted")

    capture("All five agents done", "artifacts in output/" + run_id, 4.0)

    exe = ffmpeg_path()
    if not exe:
        raise SystemExit("ffmpeg not found")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        listing = []
        for i, (img, hold) in enumerate(shots):
            p = tmpdir / ("f%03d.png" % i)
            img.save(p)
            listing.append("file '" + p.as_posix() + "'\nduration " + str(hold) + "\n")
        listing.append("file '" + (tmpdir / ("f%03d.png" % (len(shots) - 1))).as_posix() + "'\n")
        (tmpdir / "list.txt").write_text("".join(listing), encoding="utf-8")

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [exe, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(tmpdir / "list.txt"),
             "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "20",
             "-movflags", "+faststart", str(out)],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            raise SystemExit("ffmpeg failed: " + (r.stderr or "")[:300])

    print("wrote", out, out.stat().st_size // 1024, "KB,", len(shots), "frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
