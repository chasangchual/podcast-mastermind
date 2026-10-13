import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.base import AuditableMixin, Base


class ProcessingStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TranscriptSource(enum.StrEnum):
    podcasting20 = "podcasting20"
    publisher = "publisher"
    local_whisper = "local_whisper"


class Channel(AuditableMixin, Base):
    __tablename__ = "podcast_channels"

    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    rss_url: Mapped[str] = mapped_column(String(2000), unique=True)
    website_url: Mapped[str | None] = mapped_column(String(2000))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class Episode(AuditableMixin, Base):
    __tablename__ = "podcast_episodes"
    __table_args__ = (UniqueConstraint("channel_id", "external_guid"),)

    public_id: Mapped[UUID] = mapped_column(default=uuid4, unique=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("podcast_channels.id", ondelete="CASCADE"))
    external_guid: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    episode_url: Mapped[str | None] = mapped_column(String(2000))
    audio_url: Mapped[str | None] = mapped_column(String(2000))
    audio_path: Mapped[str | None] = mapped_column(String(2000))
    audio_size_bytes: Mapped[int | None] = mapped_column(Integer)
    audio_content_type: Mapped[str | None] = mapped_column(String(200))
    participants: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    transcript_text: Mapped[str | None] = mapped_column(Text)
    transcript_segments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    transcript_language: Mapped[str | None] = mapped_column(String(30))
    transcript_source: Mapped[TranscriptSource | None] = mapped_column(
        Enum(TranscriptSource, name="transcript_source")
    )
    transcript_model: Mapped[str | None] = mapped_column(String(500))
    transcript_url: Mapped[str | None] = mapped_column(String(2000))
    transcript_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.pending,
        server_default=ProcessingStatus.pending.value,
        index=True,
    )
    failure_details: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    channel: Mapped[Channel] = relationship(back_populates="episodes")
    chunks: Mapped[list["TranscriptChunk"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="TranscriptChunk.chunk_index",
    )


class TranscriptChunk(AuditableMixin, Base):
    __tablename__ = "podcast_transcript_chunks"
    __table_args__ = (UniqueConstraint("episode_id", "chunk_index"),)

    public_id: Mapped[UUID] = mapped_column(default=uuid4, unique=True)
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("podcast_episodes.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    character_count: Mapped[int] = mapped_column(Integer)
    overlap_characters: Mapped[int] = mapped_column(Integer, default=0)
    start_seconds: Mapped[float | None] = mapped_column(Float)
    end_seconds: Mapped[float | None] = mapped_column(Float)
    speaker: Mapped[str | None] = mapped_column(String(300))

    episode: Mapped[Episode] = relationship(back_populates="chunks")
    embeddings: Mapped[list["ChunkEmbedding"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class ChunkEmbedding(AuditableMixin, Base):
    __tablename__ = "podcast_chunk_embeddings"
    __table_args__ = (UniqueConstraint("chunk_id", "embedding_key"),)

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("podcast_transcript_chunks.id", ondelete="CASCADE"), index=True
    )
    embedding_key: Mapped[str] = mapped_column(String(700))
    provider: Mapped[str] = mapped_column(String(100), default="lmstudio")
    model: Mapped[str] = mapped_column(String(500))
    dimension: Mapped[int] = mapped_column(Integer)
    qdrant_collection: Mapped[str] = mapped_column(String(500))
    qdrant_point_id: Mapped[UUID] = mapped_column(unique=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    chunk: Mapped[TranscriptChunk] = relationship(back_populates="embeddings")
