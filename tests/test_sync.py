import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config.app_config import AppConfig
from app.model.base import Base
from app.model.entities import Channel, ChunkEmbedding, Episode, TranscriptChunk, TranscriptSource
from app.service.rss import FeedEpisode, FeedResult
from app.service.sync import PodcastSyncService
from app.service.transcripts import TranscriptCandidate


class RSSStub:
    def __init__(self, episode: FeedEpisode):
        self.episode = episode

    def fetch(self, url: str, etag: str | None, modified: str | None) -> FeedResult:
        return FeedResult("Test feed", "https://example.com", '"v1"', None, False, [self.episode])


class TranscriptStub:
    def resolve_public(self, links, episode_url) -> TranscriptCandidate:
        return TranscriptCandidate(
            text=("A complete publisher transcript paragraph. " * 20).strip(),
            source=TranscriptSource.publisher,
            url="https://example.com/transcript",
        )


class EmbedderStub:
    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class VectorStub:
    collection_name = "test_collection"

    def upsert(self, chunk: TranscriptChunk, vector: list[float]) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(chunk.public_id))


def test_duplicate_sync_is_idempotent() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    episode = FeedEpisode(
        guid="episode-1",
        title="Episode one",
        description="Description",
        published_at=datetime.now(UTC),
        duration_seconds=600,
        episode_url="https://example.com/episode",
        audio_url="https://example.com/audio.mp3",
        audio_content_type="audio/mpeg",
        transcript_links=[],
    )
    config = AppConfig(
        _env_file=None,
        database_url="sqlite://",
        embedding_dimension=2,
    )
    service = PodcastSyncService(
        config,
        rss=RSSStub(episode),
        transcripts=TranscriptStub(),
        embedder=EmbedderStub(),
        vectors=VectorStub(),
    )

    with Session(engine) as session:
        session.add(
            Channel(
                slug="test",
                title="Test",
                rss_url="https://example.com/feed.xml",
                website_url="https://example.com",
            )
        )
        session.commit()

        first = service.run(session)
        second = service.run(session)

        assert first.episodes_created == 1
        assert first.episodes_processed == 1
        assert second.episodes_created == 0
        assert second.episodes_processed == 0
        assert session.scalar(select(func.count()).select_from(Episode)) == 1
        assert session.scalar(select(func.count()).select_from(TranscriptChunk)) == 1
        assert session.scalar(select(func.count()).select_from(ChunkEmbedding)) == 1


class KeyedVectorStub(VectorStub):
    """Like VectorStore.point_id: the point id depends on the embedding key."""

    def __init__(self, key: str):
        self.key = key

    def upsert(self, chunk: TranscriptChunk, vector: list[float]) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"{self.key}:{chunk.public_id}")


def test_reindex_embeds_chunks_for_new_embedding_model() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    episode = FeedEpisode(
        guid="episode-1",
        title="Episode one",
        description=None,
        published_at=datetime.now(UTC),
        duration_seconds=None,
        episode_url="https://example.com/episode",
        audio_url=None,
        audio_content_type=None,
    )
    stubs = {"rss": RSSStub(episode), "transcripts": TranscriptStub(), "embedder": EmbedderStub()}
    old_config = AppConfig(_env_file=None, embedding_dimension=2)
    new_config = AppConfig(_env_file=None, embedding_dimension=2, embedding_model="other-model")
    old = PodcastSyncService(
        old_config, vectors=KeyedVectorStub(old_config.embedding_key), **stubs
    )
    new = PodcastSyncService(
        new_config, vectors=KeyedVectorStub(new_config.embedding_key), **stubs
    )

    with Session(engine) as session:
        session.add(Channel(slug="test", title="Test", rss_url="https://example.com/feed.xml"))
        session.commit()
        old.run(session)

        assert old.reindex(session) == 0
        assert new.reindex(session) == 1
        assert new.reindex(session) == 0
        assert session.scalar(select(func.count()).select_from(ChunkEmbedding)) == 2
