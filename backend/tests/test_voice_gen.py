from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.voice_gen import generate_voice
from pipeline.errors import PipelineError


def test_generate_voice_success(tmp_path):
    out = tmp_path / "voice.mp3"
    mock_resp = MagicMock()
    mock_resp.content = b"FAKE_MP3_DATA"
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.voice_gen.requests.post", return_value=mock_resp):
        result = generate_voice("Тестовый текст", "voice-id-123", {}, out)

    assert result == out
    assert out.read_bytes() == b"FAKE_MP3_DATA"


def test_generate_voice_retries_on_server_error(tmp_path):
    out = tmp_path / "voice.mp3"
    import requests as req_lib

    # First two calls raise 500, third succeeds
    error_resp = MagicMock()
    error_resp.status_code = 500
    http_error = req_lib.HTTPError(response=error_resp)
    error_resp.raise_for_status.side_effect = http_error

    good_resp = MagicMock()
    good_resp.content = b"OK_MP3"
    good_resp.raise_for_status = MagicMock()

    with patch("pipeline.voice_gen.requests.post", side_effect=[error_resp, error_resp, good_resp]):
        with patch("pipeline.voice_gen.time.sleep"):
            result = generate_voice("text", "vid", {}, out)

    assert result == out


def test_generate_voice_auth_error_no_retry(tmp_path):
    out = tmp_path / "voice.mp3"
    import requests as req_lib

    error_resp = MagicMock()
    error_resp.status_code = 401
    http_error = req_lib.HTTPError(response=error_resp)
    error_resp.raise_for_status.side_effect = http_error

    with patch("pipeline.voice_gen.requests.post", return_value=error_resp):
        with patch("pipeline.voice_gen.time.sleep"):
            with pytest.raises(PipelineError) as exc_info:
                generate_voice("text", "vid", {}, out)
    assert exc_info.value.step_name == "voice_gen"
