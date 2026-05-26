"""add instagram fields

Revision ID: 003
Revises: 002
Create Date: 2025-01-03 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE channels
          ADD COLUMN IF NOT EXISTS instagram_user_id              VARCHAR(255),
          ADD COLUMN IF NOT EXISTS instagram_access_token_encrypted TEXT,
          ADD COLUMN IF NOT EXISTS auto_post_instagram            BOOLEAN NOT NULL DEFAULT FALSE;

        ALTER TABLE videos
          ADD COLUMN IF NOT EXISTS instagram_media_id        VARCHAR(255),
          ADD COLUMN IF NOT EXISTS instagram_url             TEXT,
          ADD COLUMN IF NOT EXISTS instagram_published_at    TIMESTAMPTZ;
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE channels
          DROP COLUMN IF EXISTS instagram_user_id,
          DROP COLUMN IF EXISTS instagram_access_token_encrypted,
          DROP COLUMN IF EXISTS auto_post_instagram;

        ALTER TABLE videos
          DROP COLUMN IF EXISTS instagram_media_id,
          DROP COLUMN IF EXISTS instagram_url,
          DROP COLUMN IF EXISTS instagram_published_at;
    """))
