import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.config.app_config import AppConfig
from app.model.entities import (
    Channel,
    ChunkEmbedding,
    Episode,
    ProcessingStatus,
    TranscriptChunk,
)
from app.routers.schemas import SyncStats
from app.service.chunking import chunk_transcript
from app.service.embeddings import EmbeddingClient, create_embedding_client
from app.service.rss import FeedEpisode, RSSClient
from app.service.transcription import LocalTranscriber
from app.service.transcripts import TranscriptCandidate, TranscriptResolver
from app.service.vector_store import VectorStore

logger = logging.getLogger(__name__)


def normalized_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class PodcastSyncService:
    def __init__(
        self,
        config: AppConfig,
        rss: RSSClient | None = None,
        transcripts: TranscriptResolver | None = None,
        transcriber: LocalTranscriber | None = None,
        embedder: EmbeddingClient | None = None,
        vectors: VectorStore | None = None,
        http: httpx.Client | None = None,
    ):
        self.config = config
        self.rss = rss or RSSClient(config.http_user_agent)
        self.transcripts = transcripts or TranscriptResolver(config)
        self.transcriber = transcriber or LocalTranscriber(config)
        self.embedder = embedder or create_embedding_client(config)
        self.vectors = vectors or VectorStore(config)
        self.http = http or httpx.Client(
            follow_redirects=True,
            timeout=120,
            headers={"User-Agent": config.http_user_agent},
        )

    def run(self, session: Session, years: int = 2, slugs: list[str] | None = None) -> SyncStats:
        stats = SyncStats()
        cutoff = datetime.now(UTC).replace(microsecond=0)
        try:
            cutoff = cutoff.replace(year=cutoff.year - years)
        except ValueError:
            cutoff = cutoff.replace(year=cutoff.year - years, day=28)
        query = select(Channel).where(Channel.active.is_(True)).order_by(Channel.slug)
        if slugs:
            query = query.where(Channel.slug.in_(slugs))
        channels = list(session.scalars(query))
        for channel in channels:
            stats.channels_polled += 1
            self._sync_channel(session, channel, cutoff, stats)
        return stats

    def reindex(self, session: Session, slugs: list[str] | None = None) -> int:
        """Embed chunks that lack a vector for the current embedding configuration."""
        query = (
            select(Episode.id)
            .join(Episode.channel)
            .where(Episode.processing_status == ProcessingStatus.completed)
            .where(
                Episode.chunks.any(
                    ~TranscriptChunk.embeddings.any(
                        ChunkEmbedding.embedding_key == self.config.embedding_key
                    )
                )
            )
            .order_by(Episode.published_at)
        )
        if slugs:
            query = query.where(Channel.slug.in_(slugs))
        episode_ids = list(session.scalars(query))
        for episode_id in episode_ids:
            self._embed_missing(session, session.get(Episode, episode_id))
        return len(episode_ids)

    def _sync_channel(
        self, session: Session, channel: Channel, cutoff: datetime, stats: SyncStats
    ) -> None:
        channel.last_polled_at = datetime.now(UTC)
        try:
            feed = self.rss.fetch(channel.rss_url, channel.etag, channel.last_modified)
            if feed.not_modified:
                channel.last_success_at = datetime.now(UTC)
                channel.last_error = None
                session.commit()
                return
            channel.etag = feed.etag
            channel.last_modified = feed.last_modified
            channel.title = feed.title or channel.title
            channel.website_url = feed.website_url or channel.website_url
            for item in feed.episodes:
                if item.published_at < cutoff:
                    continue
                stats.episodes_seen += 1
                episode, created, changed = self._upsert_episode(session, channel, item)
                stats.episodes_created += int(created)
                if created or changed or episode.processing_status != ProcessingStatus.completed:
                    self._process_episode(session, episode, item, stats)
            channel.last_success_at = datetime.now(UTC)
            channel.last_error = None
            session.commit()
        except Exception as exc:
            session.rollback()
            channel = session.merge(channel)
            channel.last_polled_at = datetime.now(UTC)
            channel.last_error = str(exc)[:4000]
            session.commit()
            logger.exception("Failed to sync channel %s", channel.slug)

    def _upsert_episode(
        self, session: Session, channel: Channel, item: FeedEpisode
    ) -> tuple[Episode, bool, bool]:
        episode = session.scalar(
            select(Episode).where(
                Episode.channel_id == channel.id, Episode.external_guid == item.guid
            )
        )
        created = episode is None
        if episode is None:
            episode = Episode(
                channel=channel,
                external_guid=item.guid,
                title=item.title,
                description=item.description,
                published_at=item.published_at,
                duration_seconds=item.duration_seconds,
                episode_url=item.episode_url,
                audio_url=item.audio_url,
                audio_content_type=item.audio_content_type,
                participants=item.participants,
                source_metadata={**item.metadata, "transcript_links": item.transcript_links},
            )
            session.add(episode)
            session.flush()
            return episode, True, True
        comparison = (
            episode.title,
            episode.description,
            normalized_utc(episode.published_at),
            episode.duration_seconds,
            episode.episode_url,
            episode.audio_url,
            episode.participants,
            episode.source_metadata,
        )
        updated = (
            item.title,
            item.description,
            normalized_utc(item.published_at),
            item.duration_seconds,
            item.episode_url,
            item.audio_url,
            item.participants,
            {**item.metadata, "transcript_links": item.transcript_links},
        )
        changed = comparison != updated
        if changed:
            (
                episode.title,
                episode.description,
                episode.published_at,
                episode.duration_seconds,
                episode.episode_url,
                episode.audio_url,
                episode.participants,
                episode.source_metadata,
            ) = updated
        return episode, created, changed

    def _process_episode(
        self, session: Session, episode: Episode, item: FeedEpisode, stats: SyncStats
    ) -> None:
        episode.processing_status = ProcessingStatus.processing
        episode.failure_details = None
        session.commit()
        try:
            candidate = self.transcripts.resolve_public(item.transcript_links, item.episode_url)
            if candidate is None:
                audio_path = self._download_audio(episode)
                candidate = self.transcriber.transcribe(audio_path)
            self._store_transcript(session, episode, candidate)
            self._embed_missing(session, episode)
            episode.processing_status = ProcessingStatus.completed
            episode.failure_details = None
            episode.processed_at = datetime.now(UTC)
            session.commit()
            stats.episodes_processed += 1
        except Exception as exc:
            session.rollback()
            episode = session.get(Episode, episode.id)
            if episode:
                episode.processing_status = ProcessingStatus.failed
                episode.failure_details = str(exc)[:8000]
                session.commit()
            stats.episodes_failed += 1
            logger.exception("Failed to process episode %s", episode.id if episode else "unknown")

    def _download_audio(self, episode: Episode) -> Path:
        if not episode.audio_url:
            raise RuntimeError("Episode has no audio enclosure and no complete public transcript")
        extension = Path(urlparse(episode.audio_url).path).suffix or ".audio"
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", episode.external_guid)[-160:]
        target = (
            self.config.podcast_data_path
            / "audio"
            / episode.channel.slug
            / str(episode.published_at.year)
            / f"{safe_id}{extension}"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with self.http.stream("GET", episode.audio_url) as response:
                response.raise_for_status()
                with target.open("wb") as output:
                    for block in response.iter_bytes():
                        output.write(block)
        episode.audio_path = str(target)
        episode.audio_size_bytes = target.stat().st_size
        return target

    def _store_transcript(
        self, session: Session, episode: Episode, candidate: TranscriptCandidate
    ) -> None:
        transcript_hash = hashlib.sha256(candidate.text.encode()).hexdigest()
        if transcript_hash == episode.transcript_hash and episode.chunks:
            return
        session.execute(delete(TranscriptChunk).where(TranscriptChunk.episode_id == episode.id))
        episode.transcript_text = candidate.text
        episode.transcript_segments = candidate.segments
        episode.transcript_language = candidate.language
        episode.transcript_source = candidate.source
        episode.transcript_model = (
            self.config.whisper_model if candidate.source.value == "local_whisper" else None
        )
        episode.transcript_url = candidate.url
        episode.transcript_hash = transcript_hash
        session.flush()
        for chunk in chunk_transcript(candidate.text):
            session.add(
                TranscriptChunk(
                    episode=episode,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    content_hash=chunk.content_hash,
                    character_count=len(chunk.text),
                    overlap_characters=chunk.overlap_characters,
                )
            )
        session.flush()

    def _embed_missing(self, session: Session, episode: Episode) -> None:
        episode = session.scalar(
            select(Episode)
            .options(joinedload(Episode.channel), joinedload(Episode.chunks))
            .where(Episode.id == episode.id)
        )
        if episode is None:
            raise RuntimeError("Episode disappeared during processing")
        existing = set(
            session.scalars(
                select(ChunkEmbedding.chunk_id).where(
                    ChunkEmbedding.embedding_key == self.config.embedding_key,
                    ChunkEmbedding.chunk_id.in_([chunk.id for chunk in episode.chunks]),
                )
            )
        )
        missing = [chunk for chunk in episode.chunks if chunk.id not in existing]
        for offset in range(0, len(missing), 16):
            batch = missing[offset : offset + 16]
            vectors = self.embedder.embed([chunk.text for chunk in batch], task="document")
            for chunk, vector in zip(batch, vectors, strict=True):
                point_id = self.vectors.upsert(chunk, vector)
                session.add(
                    ChunkEmbedding(
                        chunk=chunk,
                        embedding_key=self.config.embedding_key,
                        provider=self.config.embedding_provider,
                        model=self.config.embedding_model,
                        dimension=self.config.embedding_dimension,
                        qdrant_collection=self.vectors.collection_name,
                        qdrant_point_id=point_id,
                        completed_at=datetime.now(UTC),
                    )
                )
            session.commit()
