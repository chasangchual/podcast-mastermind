from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.db import get_session
from app.main import app
from app.model.base import Base

ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SESSION = sessionmaker(bind=ENGINE, expire_on_commit=False)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    Base.metadata.create_all(ENGINE)

    def override_session() -> Generator[Session, None, None]:
        with SESSION() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(ENGINE)


def test_channel_api_and_frontend(client: TestClient) -> None:
    response = client.post(
        "/api/v1/channels",
        json={
            "slug": "example",
            "title": "Example Podcast",
            "rss_url": "https://example.com/feed.xml",
        },
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "example"

    listing = client.get("/api/v1/channels")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    page = client.get("/")
    assert page.status_code == 200
    assert "Podcast Mastermind" in page.text
