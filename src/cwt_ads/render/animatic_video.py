"""Render the storyboard to a real MP4 animatic.

This is not the finished film - the finished film is generated shot by shot by
OpenMontage. This is the *animatic*: the locked cut, at the right runtime, with
the on-screen text landing on the right frames, in the brand palette, with a
slow push on every shot so the pacing can actually be judged.

It exists because an animatic is what a director signs off before anyone spends
money on generation, and because it needs nothing but ffmpeg and Pillow - no
API keys, no credits, no model. Whatever else fails, this produces a video.
"""

from __future__ import annotations

import random
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import brand
from ..logging_utils import ok, step, warn
from ..schemas import AdScript
from .openmontage import ffmpeg_path

W, H = 1080, 1920  # 9:16

_FONT_DIRS = ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts")
_DISPLAY = ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf")
_BODY = ("arial.ttf", "DejaVuSans.ttf", "Arial.ttf")
_MONO = ("consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc")


def _font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for directory in _FONT_DIRS:
        for name in names:
            path = Path(directory) / name
            if path.is_file():
                try:
                    return ImageFont.truetype(str(path), size)
                except OSError:
                    continue
    return ImageFont.load_default()


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# Each beat gets its own ground, so the emotional shape of the cut is legible
# even in a still: chaos is red and busy, the turn is green and empty.
_BEAT_TINT = {
    "hook": ("paper", 0.16),
    "escalation": ("noise", 0.22),
    "turn": ("signal", 0.14),
    "proof": ("brass", 0.12),
    "resolution": ("paper", 0.10),
    "cta": ("signal", 0.10),
}


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in (text or "").split("\n"):
        if not para.strip():
            lines.append("")
            continue
        words, cur = para.split(), ""
        for word in words:
            trial = (cur + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def _frame(shot, script: AdScript, palette: dict, rng: random.Random) -> Image.Image:
    ink = _rgb(palette["ink"])
    paper = _rgb(palette["paper"])
    signal = _rgb(palette["signal"])
    dim = tuple(int(c * 0.55) for c in paper)

    img = Image.new("RGB", (W, H), ink)
    draw = ImageDraw.Draw(img)

    # Ground: a soft vertical wash tinted by the beat.
    key, strength = _BEAT_TINT.get(shot.beat, ("paper", 0.10))
    tint = _rgb(palette[key])
    for y in range(H):
        # brightest around the optical centre, falling off top and bottom
        d = abs(y - H * 0.42) / (H * 0.58)
        k = max(0.0, 1.0 - d * d) * strength
        draw.line(
            [(0, y), (W, y)],
            fill=tuple(int(ink[i] + (tint[i] - ink[i]) * k) for i in range(3)),
        )

    if shot.beat == "escalation":  # busy, unresolved
        noise = _rgb(palette["noise"])
        for i in range(0, H, 14):
            if rng.random() < 0.5:
                draw.line([(0, i), (W, i)], fill=tuple(int(c * 0.30) for c in noise))
    if shot.beat == "proof":  # measured grid
        brass = tuple(int(c * 0.28) for c in _rgb(palette["brass"]))
        for x in range(0, W, 90):
            draw.line([(x, 0), (x, H)], fill=brass)
        for y in range(0, H, 90):
            draw.line([(0, y), (W, y)], fill=brass)

    f_mono_s = _font(_MONO, 26)
    f_display = _font(_DISPLAY, 76)
    f_fine = _font(_MONO, 24)
    f_body = _font(_BODY, 30)
    f_vo = _font(_MONO, 28)

    # Header: beat + timecode
    draw.text((70, 90), shot.beat.upper(), font=f_mono_s, fill=signal)
    tc = "SHOT %02d   %04.1f-%04.1fs" % (shot.n, shot.t_start, shot.t_end)
    draw.text((W - 70 - draw.textlength(tc, font=f_mono_s), 90), tc, font=f_mono_s, fill=dim)

    # On-screen text: the big type, with legal-ish lines rendered small.
    y = 620
    for raw in (shot.on_screen_text or "").split("\n"):
        line = raw.strip()
        if not line:
            y += 24
            continue
        small = line[:1].islower() or line.lower().startswith(
            ("win =", "not financial", "capital at risk")
        )
        font = f_fine if small else f_display
        colour = dim if small else paper
        for piece in _wrap(draw, line if small else line.upper(), font, W - 200):
            draw.text(
                ((W - draw.textlength(piece, font=font)) / 2, y), piece, font=font, fill=colour
            )
            y += (font.size + 14) if not small else (font.size + 8)
        y += 10

    # What the camera sees
    vy = max(y + 60, 1180)
    for piece in _wrap(draw, shot.visual, f_body, W - 260)[:5]:
        draw.text(((W - draw.textlength(piece, font=f_body)) / 2, vy), piece, font=f_body, fill=dim)
        vy += f_body.size + 12

    # Voiceover, bottom, with the signal-green rule
    if shot.voiceover:
        lines = _wrap(draw, shot.voiceover, f_vo, W - 220)[:4]
        by = H - 300 - len(lines) * (f_vo.size + 10)
        draw.rectangle([70, by - 6, 74, by + len(lines) * (f_vo.size + 10)], fill=signal)
        for piece in lines:
            draw.text((100, by), piece, font=f_vo, fill=paper)
            by += f_vo.size + 10

    # Footer
    draw.text((70, H - 150), "CROWDWISDOM TRADING", font=f_mono_s, fill=dim)
    legal = "Not financial advice. Capital at risk."
    draw.text(
        (W - 70 - draw.textlength(legal, font=f_fine), H - 148), legal, font=f_fine, fill=dim
    )

    # Grain, so it does not read as a slide
    px = img.load()
    for _ in range(24000):
        x, yy = rng.randrange(W), rng.randrange(H)
        r, g, b = px[x, yy]
        n = rng.randint(-12, 12)
        px[x, yy] = (
            max(0, min(255, r + n)),
            max(0, min(255, g + n)),
            max(0, min(255, b + n)),
        )
    return img


def render(script: AdScript, out_path: Path, *, fps: int = 30) -> dict:
    """Render `script` to an MP4. Returns a status dict; never raises."""
    exe = ffmpeg_path()
    if not exe:
        return {"rendered": False, "reason": "ffmpeg not found"}
    if not script.shots:
        return {"rendered": False, "reason": "script has no shots"}

    palette = brand()["look"]["palette"]
    rng = random.Random(7)  # deterministic grain, so reruns are byte-comparable
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        clips: list[Path] = []
        step("video_agent", "rendering " + str(len(script.shots)) + " shots at %dx%d" % (W, H))

        for shot in script.shots:
            still = tmpdir / ("shot_%02d.png" % shot.n)
            _frame(shot, script, palette, rng).save(still)

            clip = tmpdir / ("shot_%02d.mp4" % shot.n)
            dur = max(shot.duration, 0.5)
            frames = max(int(dur * fps), 2)
            # Slow push in: 1.00 -> 1.06 across the shot. Cheap, but it is the
            # difference between an animatic and a slideshow.
            zoom = "zoompan=z='1+0.06*on/%d':d=%d:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=%dx%d:fps=%d" % (
                frames,
                frames,
                W,
                H,
                fps,
            )
            cmd = [
                exe, "-y", "-loglevel", "error",
                "-loop", "1", "-i", str(still),
                "-t", "%.2f" % dur,
                "-vf", zoom + ",fade=t=in:st=0:d=0.18",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                str(clip),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                warn("ffmpeg failed on shot %d: %s" % (shot.n, (result.stderr or "")[:200]))
                return {"rendered": False, "reason": "ffmpeg failed on shot %d" % shot.n}
            clips.append(clip)

        listing = tmpdir / "clips.txt"
        listing.write_text(
            "".join("file '" + c.as_posix() + "'\n" for c in clips), encoding="utf-8"
        )
        concat = [
            exe, "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            # a silent stereo track, so the file behaves like a real ad everywhere
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
            "-c:a", "aac", "-movflags", "+faststart",
            str(out_path),
        ]
        result = subprocess.run(concat, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            warn("ffmpeg concat failed: " + (result.stderr or "")[:250])
            return {"rendered": False, "reason": "concat failed"}

    size_kb = out_path.stat().st_size // 1024
    ok("rendered " + out_path.name + "  (" + str(size_kb) + " KB)")
    return {
        "rendered": True,
        "output": str(out_path),
        "engine": "ffmpeg-animatic",
        "shots": len(script.shots),
        "duration_seconds": script.total_shot_time,
        "size_kb": size_kb,
    }
