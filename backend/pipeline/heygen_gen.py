"""
HeyGen avatar video generation pipeline step.

Flow:
  1. POST /v2/video/generate  → get video_id
  2. Poll GET /v1/video_status.get every 10s until completed / failed / timeout
  3. Download mp4 to output_path
  4. Return path + duration_sec
"""
import time
from pathlib import Path
from typing import TYPE_CHECKING

import requests
import structlog

from config import get_settings
from pipeline.errors import PipelineError

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

HEYGEN_BASE = "https://api.heygen.com"
POLL_INTERVAL = 10   # seconds between status checks
MAX_POLLS = 72       # 72 × 10s = 12 minutes max wait

# Default background for health/medical content — soft warm white
DEFAULT_BG_COLOR = "#f8f5f0"


def _headers(api_key: str) -> dict:
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def generate_avatar_video(
    script: str,
    avatar_id: str,
    heygen_voice_id: str,
    output_path: Path,
    resolution: tuple[int, int] = (1080, 1920),
    background_color: str = DEFAULT_BG_COLOR,
    avatar_style: str = "normal",
    speed: float = 1.0,
) -> tuple[Path, float]:
    """
    Generate a talking-head avatar video via HeyGen API.

    Returns (output_path, duration_sec).
    Raises PipelineError on any failure.
    """
    settings = get_settings()
    api_key = settings.heygen_api_key
    if not api_key or api_key.startswith("placeholder"):
        raise PipelineError(
            "heygen_gen",
            "HEYGEN_API_KEY is not set. Add it to .env and restart.",
        )

    width, height = resolution

    # ── 1. Create video ───────────────────────────────────────────────────────
    payload = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": avatar_style,
            },
            "voice": {
                "type": "text",
                "input_text": script,
                "voice_id": heygen_voice_id,
                "speed": speed,
            },
            "background": {
                "type": "color",
                "value": background_color,
            },
        }],
        "dimension": {"width": width, "height": height},
        "test": False,
    }

    try:
        resp = requests.post(
            f"{HEYGEN_BASE}/v2/video/generate",
            json=payload,
            headers=_headers(api_key),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise PipelineError("heygen_gen", f"Create video request failed: {exc}", exc)

    if data.get("error"):
        raise PipelineError("heygen_gen", f"HeyGen API error: {data['error']}")

    video_id: str = data["data"]["video_id"]
    log.info("heygen_video_created", video_id=video_id)

    # ── 2. Poll for completion ────────────────────────────────────────────────
    for attempt in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        try:
            st_resp = requests.get(
                f"{HEYGEN_BASE}/v1/video_status.get",
                params={"video_id": video_id},
                headers=_headers(api_key),
                timeout=30,
            )
            st_resp.raise_for_status()
            st_data = st_resp.json()
        except requests.RequestException as exc:
            log.warning("heygen_poll_error", attempt=attempt, error=str(exc))
            continue

        status = st_data["data"]["status"]
        log.info("heygen_poll", video_id=video_id, status=status, attempt=attempt)

        if status == "completed":
            video_url: str = st_data["data"]["video_url"]
            duration: float = float(st_data["data"].get("duration") or 0)
            break
        elif status == "failed":
            msg = st_data["data"].get("error", "unknown error")
            raise PipelineError("heygen_gen", f"HeyGen video failed: {msg}")
    else:
        raise PipelineError(
            "heygen_gen",
            f"HeyGen video {video_id} timed out after {MAX_POLLS * POLL_INTERVAL}s",
        )

    # ── 3. Download mp4 ───────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dl = requests.get(video_url, stream=True, timeout=180)
        dl.raise_for_status()
        with open(output_path, "wb") as fh:
            for chunk in dl.iter_content(chunk_size=65536):
                fh.write(chunk)
    except requests.RequestException as exc:
        raise PipelineError("heygen_gen", f"Download failed: {exc}", exc)

    log.info("heygen_video_downloaded", path=str(output_path), duration=duration)
    return output_path, duration


def list_avatars(api_key: str) -> list[dict]:
    """Helper: list available avatars for the account."""
    resp = requests.get(
        f"{HEYGEN_BASE}/v2/avatars",
        headers=_headers(api_key),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("avatars", [])


def list_voices(api_key: str) -> list[dict]:
    """Helper: list available HeyGen voices."""
    resp = requests.get(
        f"{HEYGEN_BASE}/v2/voices",
        headers=_headers(api_key),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("voices", [])
