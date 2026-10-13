import json

import httpx
import pytest

from app.config.app_config import AppConfig
from app.service.embeddings import (
    EmbeddingError,
    GeminiEmbeddingClient,
    OpenAICompatibleEmbeddingClient,
    create_embedding_client,
)


def test_openai_compatible_order_and_dimension() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [3.0, 4.0]},
                    {"index": 0, "embedding": [1.0, 2.0]},
                ]
            },
        )
    )
    config = AppConfig(_env_file=None, embedding_dimension=2)
    client = OpenAICompatibleEmbeddingClient(config, httpx.Client(transport=transport))
    assert client.embed(["first", "second"]) == [[1.0, 2.0], [3.0, 4.0]]


def test_dimension_mismatch_fails_before_qdrant() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})
    )
    config = AppConfig(_env_file=None, embedding_dimension=2)
    client = OpenAICompatibleEmbeddingClient(config, httpx.Client(transport=transport))
    with pytest.raises(EmbeddingError, match="dimension mismatch"):
        client.embed(["text"])


def test_openai_compatible_sends_dimensions_when_enabled() -> None:
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

    config = AppConfig(_env_file=None, embedding_dimension=2, embedding_send_dimensions=True)
    client = OpenAICompatibleEmbeddingClient(
        config, httpx.Client(transport=httpx.MockTransport(handler))
    )
    client.embed(["text"])
    assert bodies[0]["dimensions"] == 2


def test_gemini_batches_and_task_types() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        count = len(json.loads(request.content)["requests"])
        return httpx.Response(200, json={"embeddings": [{"values": [0.5, 0.5]}] * count})

    config = AppConfig(
        _env_file=None,
        embedding_provider="gemini",
        embedding_model="gemini-embedding-001",
        embedding_dimension=2,
        gemini_api_key="secret",
    )
    client = create_embedding_client(config, httpx.Client(transport=httpx.MockTransport(handler)))
    assert isinstance(client, GeminiEmbeddingClient)

    assert len(client.embed([f"t{i}" for i in range(150)], task="document")) == 150
    assert len(requests) == 2
    first = json.loads(requests[0].content)
    assert requests[0].url.path.endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert requests[0].headers["x-goog-api-key"] == "secret"
    assert len(first["requests"]) == 100
    assert first["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert first["requests"][0]["outputDimensionality"] == 2

    client.embed(["question"], task="query")
    assert json.loads(requests[-1].content)["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_gemini_requires_api_key() -> None:
    config = AppConfig(_env_file=None, embedding_provider="gemini")
    with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
        create_embedding_client(config)


def test_legacy_lmstudio_env_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LMSTUDIO_EMBEDDING_MODEL", "legacy-model")
    monkeypatch.setenv("LMSTUDIO_EMBEDDING_DIMENSION", "768")
    monkeypatch.setenv("EMBEDDING_KEY_PROVIDER", "lmstudio")
    config = AppConfig(_env_file=None)
    assert isinstance(create_embedding_client(config), OpenAICompatibleEmbeddingClient)
    assert config.embedding_key == "lmstudio:legacy-model:768"
