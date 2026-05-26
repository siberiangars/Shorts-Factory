from pathlib import Path

import pytest

from pipeline.subtitles import (
    Segment, SubtitleStyle, WordTimestamp,
    _format_ass_time, generate_ass_subtitles,
)


def _make_segments() -> list[Segment]:
    words = [
        WordTimestamp(word="Привет", start=0.0, end=0.5),
        WordTimestamp(word="мир", start=0.6, end=1.0),
        WordTimestamp(word="как", start=1.1, end=1.4),
        WordTimestamp(word="дела", start=1.5, end=2.0),
        WordTimestamp(word="всё", start=2.1, end=2.5),
        WordTimestamp(word="отлично", start=2.6, end=3.2),
    ]
    return [Segment(text="Привет мир как дела всё отлично", start=0.0, end=3.2, words=words)]


def test_format_ass_time():
    assert _format_ass_time(0.0) == "0:00:00.00"
    assert _format_ass_time(61.5) == "0:01:01.50"
    assert _format_ass_time(3661.99) == "1:01:01.99"


def test_generate_ass_creates_file(tmp_path):
    out = tmp_path / "subs.ass"
    generate_ass_subtitles(_make_segments(), out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "Dialogue:" in content


def test_generate_ass_word_grouping(tmp_path):
    out = tmp_path / "subs.ass"
    style = SubtitleStyle(words_per_line=2)
    generate_ass_subtitles(_make_segments(), out, style)
    content = out.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    # 6 words / 2 per line = 3 dialogue lines
    assert len(lines) == 3


def test_generate_ass_pop_in_animation(tmp_path):
    out = tmp_path / "subs.ass"
    generate_ass_subtitles(_make_segments(), out)
    content = out.read_text(encoding="utf-8")
    assert r"\fad(80,0)" in content


def test_generate_ass_style_override(tmp_path):
    out = tmp_path / "subs.ass"
    style = SubtitleStyle(font="Arial", size=48, y_position=1200)
    generate_ass_subtitles(_make_segments(), out, style)
    content = out.read_text(encoding="utf-8")
    assert "Arial" in content
    assert "48" in content
    assert "1200" in content
