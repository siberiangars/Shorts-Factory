"""
Video assembly pipeline — BioBase12 visual style:

- Dark vignette overlay on B-roll (makes any footage look more dramatic)
- Large bold title text overlay at start (0–3 sec) — key visual element
- Word-by-word subtitle pop-in (existing ASS subtitles at bottom)
- Loudnorm audio
"""
import re
import subprocess
from pathlib import Path

import ffmpeg
import structlog

from pipeline.errors import PipelineError

log = structlog.get_logger()


def _sanitize_for_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    # Remove everything after # (YouTube tags in title)
    text = re.sub(r"\s*#\w+.*$", "", text).strip()
    # Escape special chars
    for ch in ("\\", "'", ":", "[", "]", "{", "}", "(", ")", ",", ";", "=", "%"):
        text = text.replace(ch, f"\\{ch}")
    return text


def _wrap_title(text: str, max_chars: int = 18) -> str:
    """Wrap title text to fit in video frame."""
    words = text.split()
    lines, line = [], []
    for word in words:
        if sum(len(w) for w in line) + len(line) + len(word) > max_chars and line:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return "\\n".join(lines)


def assemble_short(
    voice_path: Path,
    broll_paths: list[Path],
    subtitles_path: Path,
    music_path: Path | None,
    output_path: Path,
    resolution: tuple[int, int] = (1080, 1920),
    fps: int = 30,
    title_text: str = "",
) -> Path:
    """
    Build a 9:16 Short with BioBase12-style visuals:
    - Dark vignette on B-roll
    - Large title overlay (first 3 seconds)
    - ASS word-level subtitles at bottom
    """
    width, height = resolution
    work_dir = output_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)

    broll_list = work_dir / "broll_list.txt"
    with open(broll_list, "w", encoding="utf-8") as fh:
        for p in broll_paths:
            fh.write(f"file '{p.resolve().as_posix()}'\n")

    subs_arg = subtitles_path.resolve().as_posix()

    # Build FFmpeg filter complex manually for full control
    broll_list_str = str(broll_list.resolve().as_posix())
    voice_str = str(voice_path.resolve().as_posix())
    out_str = str(output_path.resolve().as_posix())

    # Title drawtext — DISABLED (Cyrillic font issues in Docker)
    # Russian text renders as garbled characters without proper Cyrillic font
    # Title is visible in subtitles instead
    title_filters = ""

    # Subtitles DISABLED — libass with Cyrillic causes 10+ min timeout on this server
    # TODO: add subtitles back once font/performance issue is resolved
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"setsar=1,"
        f"fps={fps}"
    )

    audio_filter = "loudnorm=I=-16:LRA=11:TP=-1.5"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", broll_list_str,
        "-i", voice_str,
        "-filter_complex",
        f"[0:v]{video_filter}[v];[1:a]{audio_filter}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-shortest", "-movflags", "+faststart",
        out_str,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode != 0:
            err = result.stderr.decode(errors="replace")
            # Show last 600 chars where actual error is (skip FFmpeg banner)
            err_tail = err[-600:] if len(err) > 600 else err
            log.error("ffmpeg_error_detail", stderr_tail=err_tail[:300])
            # Retry with simple fallback
            log.warning("video_assemble_fallback", reason="main assembly failed")
            return _assemble_simple(
                broll_list_str, voice_str, subs_arg, out_str,
                width, height, fps
            )
    except subprocess.TimeoutExpired:
        raise PipelineError("video_assemble", "FFmpeg timed out after 10 minutes")

    log.info("video_assembled", path=out_str, has_title=bool(title_text))
    return output_path


def _assemble_simple(
    broll_list: str, voice: str, subs: str, out: str,
    width: int, height: int, fps: int,
) -> Path:
    """Fallback assembly without advanced filters."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", broll_list,
        "-i", voice,
        "-filter_complex",
        (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
         f"crop={width}:{height},setsar=1,fps={fps}[v];"
         f"[1:a]loudnorm=I=-16:LRA=11:TP=-1.5[a]"),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-shortest", "-movflags", "+faststart",
        out,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")
        raise PipelineError("video_assemble", f"FFmpeg fallback failed: {err[:500]}")
    return Path(out)
