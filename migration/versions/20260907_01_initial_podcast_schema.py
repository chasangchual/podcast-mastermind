"""Create podcast ingestion tables.

Revision ID: 20260907_01
Revises:
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    transcript_source = sa.Enum(
        "podcasting20", "publisher", "local_whisper", name="transcript_source"
    )
    processing_status = sa.Enum(
        "pending", "processing", "completed", "failed", name="processing_status"
    )
    op.create_table(
        "podcast_channels",
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("rss_url", sa.String(2000), nullable=False),
        sa.Column("website_url", sa.String(2000)),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("etag", sa.String(500)),
        sa.Column("last_modified", sa.String(500)),
        sa.Column("last_polled_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("rss_url"),
    )
    op.create_index("ix_podcast_channels_slug", "podcast_channels", ["slug"])

    op.create_table(
        "podcast_episodes",
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("external_guid", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("episode_url", sa.String(2000)),
        sa.Column("audio_url", sa.String(2000)),
        sa.Column("audio_path", sa.String(2000)),
        sa.Column("audio_size_bytes", sa.Integer()),
        sa.Column("audio_content_type", sa.String(200)),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("transcript_text", sa.Text()),
        sa.Column("transcript_segments", sa.JSON(), nullable=False),
        sa.Column("transcript_language", sa.String(30)),
        sa.Column("transcript_source", transcript_source),
        sa.Column("transcript_model", sa.String(500)),
        sa.Column("transcript_url", sa.String(2000)),
        sa.Column("transcript_hash", sa.String(64)),
        sa.Column("processing_status", processing_status, server_default="pending", nullable=False),
        sa.Column("failure_details", sa.Text()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["podcast_channels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("channel_id", "external_guid"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("ix_podcast_episodes_public_id", "podcast_episodes", ["public_id"])
    op.create_index("ix_podcast_episodes_published_at", "podcast_episodes", ["published_at"])
    op.create_index("ix_podcast_episodes_transcript_hash", "podcast_episodes", ["transcript_hash"])
    op.create_index("ix_podcast_episodes_processing_status", "podcast_episodes", ["processing_status"])

    op.create_table(
        "podcast_transcript_chunks",
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("overlap_characters", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Float()),
        sa.Column("end_seconds", sa.Float()),
        sa.Column("speaker", sa.String(300)),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["podcast_episodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("episode_id", "chunk_index"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("ix_podcast_transcript_chunks_episode_id", "podcast_transcript_chunks", ["episode_id"])
    op.create_index("ix_podcast_transcript_chunks_public_id", "podcast_transcript_chunks", ["public_id"])
    op.create_index("ix_podcast_transcript_chunks_content_hash", "podcast_transcript_chunks", ["content_hash"])

    op.create_table(
        "podcast_chunk_embeddings",
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("embedding_key", sa.String(700), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(500), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("qdrant_collection", sa.String(500), nullable=False),
        sa.Column("qdrant_point_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["podcast_transcript_chunks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chunk_id", "embedding_key"),
        sa.UniqueConstraint("qdrant_point_id"),
    )
    op.create_index("ix_podcast_chunk_embeddings_chunk_id", "podcast_chunk_embeddings", ["chunk_id"])


def downgrade() -> None:
    op.drop_table("podcast_chunk_embeddings")
    op.drop_table("podcast_transcript_chunks")
    op.drop_table("podcast_episodes")
    op.drop_table("podcast_channels")
    sa.Enum(name="processing_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transcript_source").drop(op.get_bind(), checkfirst=True)
