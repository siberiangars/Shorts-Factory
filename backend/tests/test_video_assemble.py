"""
Requires ffmpeg installed locally. Skips if not available.
Uses a tiny synthetic audio + blank video clip.
"""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0,
    reason="ffmpeg not installed",
)


def _create_test_audio(path: Path, duration: float = 3.0) -> Path:
    """Generate a silent mp3 using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono",
         "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", str(path)],
        check=True, capture_output=True,
    )
    return path


def _create_test_video(path: Path, duration: float = 5.0) -> Path:
    """Generate a black 1080x1920 mp4 using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=black:size=1080x1920:rate=30",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
         "-t", str(duration), "-c:v", "libx264", "-c:a", "aac", str(path)],
        check=True, capture_output=True,
    )
    return path


def _create_test_subtitles(path: Path) -> Path:
    path.write_text(
        "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,36,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
        "0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Test\n",
        encoding="utf-8",
    )
    return path


def test_assemble_short_produces_mp4(tmp_path):
    from pipeline.video_assemble import assemble_short

    voice = _create_test_audio(tmp_path / "voice.mp3", 3.0)
    broll = _create_test_video(tmp_path / "broll.mp4", 5.0)
    subs = _create_test_subtitles(tmp_path / "subs.ass")
    out = tmp_path / "final.mp4"

    result = assemble_short(
        voice_path=voice,
        broll_paths=[broll],
        subtitles_path=subs,
        music_path=None,
        output_path=out,
        resolution=(1080, 1920),
        fps=30,
    )

    assert result == out
    assert out.exists()
    assert out.stat().st_size > 1000  # not empty
