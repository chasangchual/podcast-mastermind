"""Remove indexes duplicated by unique constraints.

Revision ID: 20260907_02
Revises: 20260907_01
Create Date: 2026-09-07
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260907_02"
down_revision: str | Sequence[str] | None = "20260907_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_podcast_channels_slug", table_name="podcast_channels")
    op.drop_index("ix_podcast_episodes_public_id", table_name="podcast_episodes")
    op.drop_index(
        "ix_podcast_transcript_chunks_public_id", table_name="podcast_transcript_chunks"
    )


def downgrade() -> None:
    op.create_index("ix_podcast_channels_slug", "podcast_channels", ["slug"])
    op.create_index("ix_podcast_episodes_public_id", "podcast_episodes", ["public_id"])
    op.create_index(
        "ix_podcast_transcript_chunks_public_id",
        "podcast_transcript_chunks",
        ["public_id"],
    )
