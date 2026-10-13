import re
import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from app.config.app_config import AppConfig
from app.model.entities import TranscriptChunk

POINT_NAMESPACE = uuid.UUID("c23c3b53-a761-4ab1-88a9-c51ad3461d13")


class VectorStore:
    def __init__(self, config: AppConfig, client: QdrantClient | None = None):
        self.config = config
        self.client = client or QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key)

    @property
    def collection_name(self) -> str:
        safe_model = re.sub(r"[^a-zA-Z0-9_-]+", "_", self.config.embedding_model)
        return f"podcast_chunks_{safe_model}_{self.config.embedding_dimension}"[:255]

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.config.embedding_dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            return
        info = self.client.get_collection(self.collection_name)
        vector_config = info.config.params.vectors
        size = getattr(vector_config, "size", None)
        if size != self.config.embedding_dimension:
            raise RuntimeError(
                f"Qdrant collection {self.collection_name} has dimension {size}; "
                f"expected {self.config.embedding_dimension}"
            )

    def point_id(self, chunk: TranscriptChunk) -> uuid.UUID:
        return uuid.uuid5(POINT_NAMESPACE, f"{self.config.embedding_key}:{chunk.public_id}")

    def upsert(self, chunk: TranscriptChunk, vector: list[float]) -> uuid.UUID:
        self.ensure_collection()
        episode = chunk.episode
        point_id = self.point_id(chunk)
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=str(point_id),
                    vector=vector,
                    payload={
                        "chunk_id": str(chunk.public_id),
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        "episode_id": str(episode.public_id),
                        "episode_title": episode.title,
                        "published_at": episode.published_at.isoformat(),
                        "participants": episode.participants,
                        "transcript_source": episode.transcript_source.value,
                        "channel": episode.channel.slug,
                        "start_seconds": chunk.start_seconds,
                        "end_seconds": chunk.end_seconds,
                    },
                )
            ],
            wait=True,
        )
        return point_id

    def search(
        self, vector: list[float], limit: int, channel: str | None = None
    ) -> list[dict[str, Any]]:
        query_filter = None
        if channel:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="channel", match=models.MatchValue(value=channel))]
            )
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [{"score": point.score, **(point.payload or {})} for point in result.points]

