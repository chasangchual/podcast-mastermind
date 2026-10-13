from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from qdrant_client import QdrantClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.config.app_config import AppConfig, get_config
from app.config.db import DbSession
from app.model.entities import Channel, Episode
from app.routers.schemas import (
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
    EpisodeResponse,
    EpisodeSummary,
    HealthResponse,
    SearchRequest,
    SearchResult,
    SyncRequest,
    SyncStats,
)
from app.service.embeddings import create_embedding_client
from app.service.sync import PodcastSyncService
from app.service.vector_store import VectorStore

api_router = APIRouter(prefix="/api/v1")
Config = Annotated[AppConfig, Depends(get_config)]


def langfuse_health(config: AppConfig) -> dict[str, object]:
    if not config.langfuse_url:
        return {"status": "disabled"}
    try:
        response = httpx.get(f"{config.langfuse_url}/api/public/health", timeout=3)
        response.raise_for_status()
        return {"status": "ok", "url": config.langfuse_url}
    except Exception as exc:
        return {"status": "error", "url": config.langfuse_url, "detail": str(exc)}


@api_router.get("/health", response_model=HealthResponse)
def health(session: DbSession, config: Config) -> HealthResponse:
    services: dict[str, object] = {}
    try:
        session.execute(text("SELECT 1"))
        services["postgres"] = {"status": "ok"}
    except Exception as exc:
        services["postgres"] = {"status": "error", "detail": str(exc)}
        session.rollback()
    try:
        client = QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key, timeout=3)
        client.get_collections()
        services["qdrant"] = {"status": "ok"}
    except Exception as exc:
        services["qdrant"] = {"status": "error", "detail": str(exc)}
    try:
        services["embeddings"] = create_embedding_client(config).health()
    except Exception as exc:
        services["embeddings"] = {"status": "error", "detail": str(exc)}
    services["langfuse"] = langfuse_health(config)
    overall = (
        "ok"
        if all(item.get("status") in ("ok", "disabled") for item in services.values())
        else "degraded"
    )
    return HealthResponse(status=overall, services=services)


@api_router.get("/channels", response_model=list[ChannelResponse])
def list_channels(session: DbSession) -> list[Channel]:
    return list(session.scalars(select(Channel).order_by(Channel.title)))


@api_router.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(payload: ChannelCreate, session: DbSession) -> Channel:
    channel = Channel(
        slug=payload.slug,
        title=payload.title,
        rss_url=str(payload.rss_url),
        website_url=str(payload.website_url) if payload.website_url else None,
        active=payload.active,
    )
    session.add(channel)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Channel slug or RSS URL already exists"
        ) from exc
    session.refresh(channel)
    return channel


@api_router.patch("/channels/{slug}", response_model=ChannelResponse)
def update_channel(slug: str, payload: ChannelUpdate, session: DbSession) -> Channel:
    channel = session.scalar(select(Channel).where(Channel.slug == slug))
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        normalized = str(value) if field.endswith("_url") and value is not None else value
        setattr(channel, field, normalized)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="RSS URL already exists") from exc
    session.refresh(channel)
    return channel


@api_router.get("/episodes", response_model=list[EpisodeSummary])
def list_episodes(
    session: DbSession,
    channel: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Episode]:
    query = select(Episode).join(Episode.channel).order_by(Episode.published_at.desc())
    if channel:
        query = query.where(Channel.slug == channel)
    return list(session.scalars(query.offset(offset).limit(limit)))


@api_router.get("/episodes/{public_id}", response_model=EpisodeResponse)
def get_episode(public_id: UUID, session: DbSession) -> Episode:
    episode = session.scalar(select(Episode).where(Episode.public_id == public_id))
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@api_router.post("/sync", response_model=SyncStats)
def sync_podcasts(payload: SyncRequest, session: DbSession, config: Config) -> SyncStats:
    return PodcastSyncService(config).run(session, years=payload.years, slugs=payload.channels)


@api_router.post("/search", response_model=list[SearchResult])
def search(payload: SearchRequest, config: Config) -> list[SearchResult]:
    vector = create_embedding_client(config).embed([payload.query], task="query")[0]
    results = VectorStore(config).search(vector, payload.limit, payload.channel)
    return [SearchResult.model_validate(result) for result in results]


@api_router.get("/stats")
def stats(session: DbSession) -> dict[str, int]:
    return {
        "channels": session.scalar(select(func.count()).select_from(Channel)) or 0,
        "episodes": session.scalar(select(func.count()).select_from(Episode)) or 0,
    }
