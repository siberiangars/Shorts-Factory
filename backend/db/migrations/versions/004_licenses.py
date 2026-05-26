"""add licenses table

Revision ID: 004
Revises: 003
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'licenses',
        sa.Column('id',         sa.Integer(),     primary_key=True),
        sa.Column('key',        sa.String(32),    nullable=False, unique=True, index=True),
        sa.Column('note',       sa.String(255),   nullable=True),
        sa.Column('activated_by_email', sa.String(255), nullable=True, index=True),
        sa.Column('activated_by_name',  sa.String(255), nullable=True),
        sa.Column('is_active',  sa.Boolean(),     nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('licenses')
