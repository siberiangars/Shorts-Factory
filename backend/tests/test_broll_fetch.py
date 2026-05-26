from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.broll_fetch import fetch_broll
from pipeline.errors import PipelineError


def _pexels_response(video_url="https://example.com/video.mp4"):
    return {
        "videos": [{
            "video_files": [{"quality": "hd", "link": video_url, "duration": 15}],
        }]
    }


def test_fetch_broll_basic(tmp_path):
    with patch("pipeline.broll_fetch.requests.get") as mock_get, \
         patch("pipeline.broll_fetch._download_clip") as mock_dl:

        mock_get.return_value = MagicMock(
            json=lambda: _pexels_response("https://cdn.pexels.com/video1.mp4"),
            raise_for_status=MagicMock(),
        )

        paths, hashes = fetch_broll(
            keywords=["health food", "exercise"],
            target_duration_sec=20.0,
            output_dir=tmp_path / "broll",
            used_video_hashes=set(),
        )

    assert len(paths) > 0
    assert len(hashes) > 0


def test_fetch_broll_deduplication(tmp_path):
    """Clips already in used_video_hashes must be skipped."""
    from utils.hashing import md5_of_string
    existing_url = "https://cdn.pexels.com/already_used.mp4"
    existing_hash = md5_of_string(existing_url)

    def get_side_effect(url, **kwargs):
        resp = MagicMock(raise_for_status=MagicMock())
        resp.json.return_value = _pexels_response(existing_url)
        return resp

    with patch("pipeline.broll_fetch.requests.get", side_effect=get_side_effect), \
         patch("pipeline.broll_fetch._download_clip") as mock_dl:
        with pytest.raises(PipelineError):
            # All returned clips are already used → should fail after exhausting keywords
            fetch_broll(["keyword1"], 10.0, tmp_path / "broll", {existing_hash})


def test_fetch_broll_accumulates_to_required_duration(tmp_path):
    """Should keep fetching until total >= target * 1.3."""
    call_count = 0

    def get_side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock(raise_for_status=MagicMock())
        resp.json.return_value = _pexels_response(f"https://cdn.pexels.com/v{call_count}.mp4")
        return resp

    with patch("pipeline.broll_fetch.requests.get", side_effect=get_side_effect), \
         patch("pipeline.broll_fetch._download_clip"):
        paths, hashes = fetch_broll(
            keywords=["kw1", "kw2", "kw3", "kw4"],
            target_duration_sec=30.0,  # needs ≥39s; each clip is 15s → 3 clips
            output_dir=tmp_path / "broll",
            used_video_hashes=set(),
        )

    assert len(paths) >= 3
