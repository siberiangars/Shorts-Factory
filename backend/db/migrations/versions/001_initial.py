"""initial

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Pure-SQL migration avoids SQLAlchemy auto-emitting duplicate CREATE TYPE
_DDL = """
DO $$ BEGIN
  CREATE TYPE topicstatus AS ENUM ('pending','in_progress','done','failed','skipped');
  EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE videostatus AS ENUM
    ('pending','generating_script','generating_voice','fetching_broll',
     'transcribing','assembling','uploading','done','failed');
  EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE logstatus AS ENUM ('start','success','failed');
  EXCEPTION WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS channels (
    id                           SERIAL PRIMARY KEY,
    name                         VARCHAR(255) NOT NULL,
    niche                        VARCHAR(255) NOT NULL,
    language                     VARCHAR(10)  NOT NULL DEFAULT 'ru',
    voice_id                     VARCHAR(255) NOT NULL,
    voice_settings_json          JSONB        NOT NULL DEFAULT '{}',
    google_cloud_project_id      VARCHAR(255),
    youtube_channel_id           VARCHAR(255),
    refresh_token_encrypted      TEXT,
    access_token_encrypted       TEXT,
    token_expires_at             TIMESTAMPTZ,
    default_tags                 JSONB        NOT NULL DEFAULT '[]',
    description_template         TEXT,
    script_prompt_template       TEXT,
    auto_publish_public          BOOLEAN      NOT NULL DEFAULT FALSE,
    daily_upload_count           INTEGER      NOT NULL DEFAULT 0,
    daily_upload_count_reset_at  TIMESTAMPTZ,
    created_at                   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topics (
    id            SERIAL PRIMARY KEY,
    channel_id    INTEGER      NOT NULL REFERENCES channels(id),
    title         VARCHAR(512) NOT NULL,
    brief         TEXT,
    status        topicstatus  NOT NULL DEFAULT 'pending',
    priority      INTEGER      NOT NULL DEFAULT 0,
    scheduled_at  TIMESTAMPTZ,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    retry_count   INTEGER      NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_topics_channel_id   ON topics(channel_id);
CREATE INDEX IF NOT EXISTS ix_topics_status        ON topics(status);
CREATE INDEX IF NOT EXISTS ix_topics_scheduled_at  ON topics(scheduled_at);

CREATE TABLE IF NOT EXISTS videos (
    id                   SERIAL PRIMARY KEY,
    topic_id             INTEGER      NOT NULL UNIQUE REFERENCES topics(id),
    channel_id           INTEGER      NOT NULL REFERENCES channels(id),
    script_text          TEXT,
    script_title         VARCHAR(512),
    script_tags          JSONB        NOT NULL DEFAULT '[]',
    script_description   TEXT,
    broll_keywords       JSONB        NOT NULL DEFAULT '[]',
    broll_video_hashes   JSONB        NOT NULL DEFAULT '[]',
    voice_audio_path     TEXT,
    broll_dir            TEXT,
    subtitles_path       TEXT,
    final_video_path     TEXT,
    duration_sec         FLOAT,
    youtube_video_id     VARCHAR(255),
    youtube_url          TEXT,
    status               videostatus  NOT NULL DEFAULT 'pending',
    generation_cost_usd  NUMERIC(10,4),
    error_message        TEXT,
    published_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_videos_topic_id         ON videos(topic_id);
CREATE INDEX IF NOT EXISTS ix_videos_channel_id       ON videos(channel_id);
CREATE INDEX IF NOT EXISTS ix_videos_status           ON videos(status);
CREATE INDEX IF NOT EXISTS ix_videos_youtube_video_id ON videos(youtube_video_id);

CREATE TABLE IF NOT EXISTS generation_logs (
    id           SERIAL PRIMARY KEY,
    video_id     INTEGER      NOT NULL REFERENCES videos(id),
    step_name    VARCHAR(100) NOT NULL,
    status       logstatus    NOT NULL,
    duration_ms  INTEGER,
    cost_usd     NUMERIC(10,4),
    payload_json JSONB,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_generation_logs_video_id ON generation_logs(video_id);
"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(_DDL))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DROP TABLE IF EXISTS generation_logs CASCADE;
        DROP TABLE IF EXISTS videos CASCADE;
        DROP TABLE IF EXISTS topics CASCADE;
        DROP TABLE IF EXISTS channels CASCADE;
        DROP TYPE IF EXISTS logstatus;
        DROP TYPE IF EXISTS videostatus;
        DROP TYPE IF EXISTS topicstatus;
    """))
