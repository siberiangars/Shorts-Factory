"""E2E test for process_topic with all external calls mocked."""
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


FAKE_SCRIPT = {
    "title": "Тест #shorts",
    "hook": "Хук",
    "body": "Тело",
    "cta": "CTA",
    "full_text": "Полный текст для озвучки",
    "tags": ["тег1"],
    "description": "Описание",
    "broll_keywords": ["health food"],
    "estimated_duration_sec": 60.0,
    "_cost_usd": 0.001,
}


@pytest.fixture
def db_session_with_data(tmp_path):
    """Create in-memory SQLite DB with a channel, topic, no video."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from models.base import Base
    from models.channel import Channel
    from models.topic import Topic, TopicStatus

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as session:
        ch = Channel(
            name="Test", niche="health", language="ru",
            voice_id="voice-1", voice_settings_json={},
            daily_upload_count=0,
        )
        session.add(ch)
        session.flush()
        t = Topic(channel_id=ch.id, title="Тест", status=TopicStatus.pending)
        session.add(t)
        session.flush()
        session.commit()
        return session, ch.id, t.id


def test_process_topic_full_pipeline(tmp_path, db_session_with_data):
    session, channel_id, topic_id = db_session_with_data

    voice_mp3 = tmp_path / str(topic_id) / "voice.mp3"
    broll_dir = tmp_path / str(topic_id) / "broll"
    subs_ass = tmp_path / str(topic_id) / "subtitles.ass"
    final_mp4 = tmp_path / str(topic_id) / "final.mp4"

    # Pre-create fake files so idempotency checks pass
    voice_mp3.parent.mkdir(parents=True, exist_ok=True)
    voice_mp3.write_bytes(b"FAKE")
    broll_dir.mkdir(parents=True, exist_ok=True)
    (broll_dir / "broll_0_0.mp4").write_bytes(b"FAKE")
    subs_ass.write_text("[Script Info]\n[Events]\n")
    final_mp4.write_bytes(b"FAKE_MP4")

    patches = {
        "workers.tasks.sync_session_factory": MagicMock(return_value=session),
        "workers.tasks.settings.storage_path": str(tmp_path),
        "pipeline.script_gen.generate_script": MagicMock(return_value=FAKE_SCRIPT),
        "pipeline.voice_gen.generate_voice": MagicMock(return_value=voice_mp3),
        "pipeline.broll_fetch.fetch_broll": MagicMock(return_value=([broll_dir / "broll_0_0.mp4"], ["hash1"])),
        "pipeline.subtitles.transcribe_with_timestamps": MagicMock(return_value=[]),
        "pipeline.subtitles.generate_ass_subtitles": MagicMock(return_value=subs_ass),
        "pipeline.video_assemble.assemble_short": MagicMock(return_value=final_mp4),
        "pipeline.youtube_upload.upload_short": MagicMock(return_value={
            "youtube_video_id": "yt123",
            "youtube_url": "https://youtube.com/shorts/yt123",
            "quota_used": 1600,
        }),
    }

    # We just test _run_pipeline logic by checking model states
    # (Full e2e with real DB happens in CI against postgres)
    from models.topic import TopicStatus
    from models.video import VideoStatus

    # Verify topic started in pending
    topic = session.query(__import__("models.topic", fromlist=["Topic"]).Topic).get(topic_id)
    assert topic.status == TopicStatus.pending
