"""
Subtitles pipeline — transcription via Groq Whisper API (cloud, 3-5 sec)
with fallback to faster-whisper (local CPU, slow).

Groq is 100x faster and uses 0% local CPU.
"""
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from pipeline.errors import PipelineError

log = structlog.get_logger()


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: list[WordTimestamp] = field(default_factory=list)


@dataclass
class SubtitleStyle:
    font: str = "Inter Bold"
    size: int = 64
    color: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    outline_width: int = 4
    y_position: int = 1500
    words_per_line: int = 3


def _format_ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h = cs // 360000
    cs %= 360000
    m = cs // 6000
    cs %= 6000
    s = cs // 100
    cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _transcribe_groq(audio_path: Path, language: str, api_key: str) -> list[Segment]:
    """Transcribe via Groq Whisper API — cloud, ~3-5 seconds."""
    import requests

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    with open(audio_path, "rb") as f:
        resp = requests.post(
            url,
            headers=headers,
            files={"file": (audio_path.name, f, "audio/mpeg")},
            data={
                "model": "whisper-large-v3-turbo",
                "language": language,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            },
            timeout=60,
        )

    resp.raise_for_status()
    data = resp.json()

    segments: list[Segment] = []

    # Build word timestamps from Groq response
    words_raw = data.get("words", [])
    if words_raw:
        # Group words into segments of ~10 words each
        chunk_size = 10
        for i in range(0, len(words_raw), chunk_size):
            chunk = words_raw[i:i + chunk_size]
            wts = [WordTimestamp(
                word=w.get("word", ""),
                start=float(w.get("start", 0)),
                end=float(w.get("end", 0)),
            ) for w in chunk]
            text = " ".join(w.word for w in wts)
            segments.append(Segment(
                text=text,
                start=wts[0].start,
                end=wts[-1].end,
                words=wts,
            ))
    else:
        # Fallback: use segment-level timestamps
        for seg in data.get("segments", []):
            segments.append(Segment(
                text=seg.get("text", ""),
                start=float(seg.get("start", 0)),
                end=float(seg.get("end", 0)),
                words=[],
            ))

    log.info("groq_transcription_done", audio=str(audio_path),
             words=len(words_raw), segments=len(segments))
    return segments


def _transcribe_local(audio_path: Path, language: str) -> list[Segment]:
    """Fallback: local faster-whisper (slow, uses CPU)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise PipelineError("transcribe", "faster-whisper not installed", exc)

    model = WhisperModel("medium", device="cpu", compute_type="int8")
    raw_segments, _ = model.transcribe(
        str(audio_path), language=language, word_timestamps=True
    )
    segments: list[Segment] = []
    for seg in raw_segments:
        words = [WordTimestamp(word=w.word, start=w.start, end=w.end)
                 for w in (seg.words or [])]
        segments.append(Segment(text=seg.text, start=seg.start, end=seg.end, words=words))
    log.info("local_transcription_done", audio=str(audio_path), segments=len(segments))
    return segments


def transcribe_with_timestamps(audio_path: Path, language: str = "ru") -> list[Segment]:
    """
    Transcribe audio to word-level timestamps.
    Uses Groq API if configured (fast), falls back to local Whisper (slow).
    """
    from config import get_settings
    settings = get_settings()
    groq_key = getattr(settings, "groq_api_key", "")

    if groq_key and not groq_key.startswith("placeholder"):
        try:
            log.info("transcribe_via_groq", audio=str(audio_path))
            return _transcribe_groq(audio_path, language, groq_key)
        except Exception as exc:
            log.warning("groq_transcription_failed_falling_back",
                        error=str(exc)[:100])
            # Fall through to local

    log.info("transcribe_via_local_whisper", audio=str(audio_path))
    try:
        return _transcribe_local(audio_path, language)
    except Exception as exc:
        raise PipelineError("transcribe", f"Transcription failed: {exc}", exc)


def generate_ass_subtitles(
    segments: list[Segment],
    output_path: Path,
    style: SubtitleStyle | None = None,
) -> Path:
    if style is None:
        style = SubtitleStyle()

    all_words: list[WordTimestamp] = []
    for seg in segments:
        if seg.words:
            all_words.extend(seg.words)
        else:
            all_words.append(WordTimestamp(
                word=seg.text.strip(), start=seg.start, end=seg.end
            ))

    lines: list[tuple[float, float, str]] = []
    n = style.words_per_line
    for i in range(0, len(all_words), n):
        chunk = all_words[i:i + n]
        start = chunk[0].start
        end = chunk[-1].end
        text = " ".join(w.word.strip() for w in chunk)
        lines.append((start, end, text))

    ass_header = f"""\
[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{style.size},{style.color},&H000000FF,{style.outline_color},&H64000000,-1,0,0,0,100,100,0,0,1,{style.outline_width},0,2,10,10,{style.y_position},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue_lines = []
    for start, end, text in lines:
        t_start = _format_ass_time(start)
        t_end = _format_ass_time(end)
        escaped = text.replace("{", "{{").replace("}", "}}")
        dialogue_lines.append(
            f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{{\\fad(80,0)}}{escaped}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        ass_header + "\n".join(dialogue_lines) + "\n", encoding="utf-8"
    )
    log.info("subtitles_generated", path=str(output_path), lines=len(dialogue_lines))
    return output_path
