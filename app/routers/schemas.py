from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.model.entities import ProcessingStatus, TranscriptSource


class ChannelCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    title: str = Field(min_length=1, max_length=300)
    rss_url: HttpUrl
    website_url: HttpUrl | None = None
    active: bool = True


class ChannelUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    rss_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    active: bool | None = None


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    rss_url: str
    website_url: str | None
    active: bool
    last_polled_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None


class EpisodeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    title: str
    published_at: datetime
    duration_seconds: int | None
    participants: list[str]
    transcript_source: TranscriptSource | None
    processing_status: ProcessingStatus


class EpisodeResponse(EpisodeSummary):
    description: str | None
    episode_url: str | None
    audio_url: str | None
    transcript_text: str | None
    transcript_language: str | None
    transcript_model: str | None
    failure_details: str | None


class SyncRequest(BaseModel):
    years: int = Field(default=2, ge=1, le=20)
    channels: list[str] = Field(default_factory=list)


class SyncStats(BaseModel):
    channels_polled: int = 0
    episodes_seen: int = 0
    episodes_created: int = 0
    episodes_processed: int = 0
    episodes_failed: int = 0


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    limit: int = Field(default=10, ge=1, le=50)
    channel: str | None = None


class SearchResult(BaseModel):
    score: float
    text: str
    channel: str
    episode_id: UUID
    episode_title: str
    published_at: datetime
    participants: list[str]
    transcript_source: str
    chunk_index: int
    start_seconds: float | None = None
    end_seconds: float | None = None


class HealthResponse(BaseModel):
    status: str
    services: dict[str, Any]

