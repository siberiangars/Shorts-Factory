import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _write_client_secret(path: Path):
    path.write_text(json.dumps({
        "installed": {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }))


def _mock_channel(has_token=True):
    from utils.crypto import encrypt
    ch = MagicMock()
    ch.id = 1
    ch.refresh_token_encrypted = encrypt("fake-refresh-token") if has_token else None
    ch.access_token_encrypted = encrypt("fake-access-token") if has_token else None
    return ch


def test_upload_short_adds_shorts_tag():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        tmp_path = Path(tf.name)
    _write_client_secret(tmp_path)

    with patch("pipeline.youtube_upload.get_settings") as mock_settings, \
         patch("pipeline.youtube_upload.Credentials") as mock_creds_cls, \
         patch("pipeline.youtube_upload.build") as mock_build:

        mock_settings.return_value.youtube_client_secrets_file = str(tmp_path)
        mock_creds = MagicMock(valid=True)
        mock_creds_cls.return_value = mock_creds

        mock_yt = MagicMock()
        mock_build.return_value = mock_yt
        mock_yt.videos.return_value.insert.return_value.next_chunk.return_value = (
            None, {"id": "abc123"}
        )

        from pipeline.youtube_upload import upload_short
        result = upload_short(
            channel=_mock_channel(),
            video_path=Path("/fake/video.mp4"),
            title="Польза магния",  # no #Shorts
            description="Описание",
            tags=["здоровье"],
        )

    assert result["youtube_video_id"] == "abc123"
    assert "shorts" in result["youtube_url"].lower() or "abc123" in result["youtube_url"]
    # Verify #Shorts was added in the insert call
    call_kwargs = mock_yt.videos.return_value.insert.call_args[1]
    assert "#Shorts" in call_kwargs["body"]["snippet"]["title"]


def test_upload_short_no_token_raises():
    from pipeline.youtube_upload import upload_short
    from pipeline.errors import PipelineError
    with pytest.raises(PipelineError) as exc_info:
        upload_short(
            channel=_mock_channel(has_token=False),
            video_path=Path("/fake/video.mp4"),
            title="Title",
            description="Desc",
            tags=[],
        )
    assert exc_info.value.step_name == "youtube_upload"
