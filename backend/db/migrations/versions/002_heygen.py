"""add heygen avatar fields to channels

Revision ID: 002
Revises: 001
Create Date: 2025-01-02 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DO $$ BEGIN
          CREATE TYPE avatarmode AS ENUM ('broll', 'heygen');
          EXCEPTION WHEN duplicate_object THEN null;
        END $$;

        ALTER TABLE channels
          ADD COLUMN IF NOT EXISTS avatar_mode      avatarmode  NOT NULL DEFAULT 'broll',
          ADD COLUMN IF NOT EXISTS heygen_avatar_id VARCHAR(255),
          ADD COLUMN IF NOT EXISTS heygen_voice_id  VARCHAR(255),
          ADD COLUMN IF NOT EXISTS heygen_background VARCHAR(20) NOT NULL DEFAULT '#f8f5f0',
          ADD COLUMN IF NOT EXISTS persona_description TEXT;

        -- voice_id was NOT NULL — allow empty string for heygen-only channels
        ALTER TABLE channels ALTER COLUMN voice_id SET DEFAULT '';
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE channels
          DROP COLUMN IF EXISTS avatar_mode,
          DROP COLUMN IF EXISTS heygen_avatar_id,
          DROP COLUMN IF EXISTS heygen_voice_id,
          DROP COLUMN IF EXISTS heygen_background,
          DROP COLUMN IF EXISTS persona_description;
        DROP TYPE IF EXISTS avatarmode;
    """))
