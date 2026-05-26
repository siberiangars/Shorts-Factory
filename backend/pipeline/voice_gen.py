import time
from pathlib import Path

import requests
import structlog

from config import get_settings
from pipeline.errors import PipelineError
from utils.cost import elevenlabs_cost_usd

log = structlog.get_logger()

_ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"


def generate_voice(
    text: str,
    voice_id: str,
    voice_settings: dict,
    output_path: Path,
) -> Path:
    """Synthesise speech via ElevenLabs and save to output_path."""
    settings = get_settings()
    url = f"{_ELEVENLABS_BASE}/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": voice_settings.get("stability", 0.5),
            "similarity_boost": voice_settings.get("similarity_boost", 0.75),
            "style": voice_settings.get("style", 0.0),
            "use_speaker_boost": voice_settings.get("use_speaker_boost", True),
        },
    }

    last_exc: Exception | None = None
    for attempt, delay in enumerate([0, 2, 4, 8], start=1):
        if delay:
            time.sleep(delay)
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(resp.content)

            cost = elevenlabs_cost_usd(len(text))
            log.info("voice_generated", chars=len(text), cost_usd=cost, path=str(output_path))
            return output_path

        except requests.HTTPError as exc:
            last_exc = exc
            log.warning("voice_gen_http_error", attempt=attempt, status=exc.response.status_code)
            if exc.response.status_code in (400, 401, 403):
                break  # no point retrying auth/bad-request errors
        except requests.RequestException as exc:
            last_exc = exc
            log.warning("voice_gen_request_error", attempt=attempt, error=str(exc))

    raise PipelineError("voice_gen", f"ElevenLabs request failed after retries: {last_exc}", last_exc)
