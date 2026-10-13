from typing import Any, Literal, Protocol

import httpx

from app.config.app_config import AppConfig

EmbeddingTask = Literal["document", "query"]


class EmbeddingError(RuntimeError):
    pass


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str], task: EmbeddingTask = "document") -> list[list[float]]: ...

    def health(self) -> dict[str, Any]: ...


def validate_vectors(
    config: AppConfig, texts: list[str], vectors: list[list[float]]
) -> list[list[float]]:
    if len(vectors) != len(texts):
        raise EmbeddingError("Embedding provider returned a different number of vectors")
    dimensions = {len(vector) for vector in vectors}
    if dimensions != {config.embedding_dimension}:
        raise EmbeddingError(
            "Embedding dimension mismatch: "
            f"expected {config.embedding_dimension}, got {sorted(dimensions)}"
        )
    return vectors


class OpenAICompatibleEmbeddingClient:
    """LM Studio, Ollama, vLLM, TEI, Infinity, OpenAI: any POST {base}/embeddings API."""

    def __init__(self, config: AppConfig, client: httpx.Client | None = None):
        self.config = config
        self.client = client or httpx.Client(timeout=120)

    @property
    def headers(self) -> dict[str, str]:
        if not self.config.embedding_api_key:
            return {}
        return {"Authorization": f"Bearer {self.config.embedding_api_key}"}

    def embed(self, texts: list[str], task: EmbeddingTask = "document") -> list[list[float]]:
        if not texts:
            return []
        body: dict[str, Any] = {"model": self.config.embedding_model, "input": texts}
        if self.config.embedding_send_dimensions:
            body["dimensions"] = self.config.embedding_dimension
        response = self.client.post(
            f"{self.config.embedding_base_url.rstrip('/')}/embeddings",
            headers=self.headers,
            json=body,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Embedding request failed: {exc}") from exc
        payload: dict[str, Any] = response.json()
        ordered = sorted(payload.get("data", []), key=lambda item: item["index"])
        return validate_vectors(self.config, texts, [item["embedding"] for item in ordered])

    def health(self) -> dict[str, Any]:
        response = self.client.get(
            f"{self.config.embedding_base_url.rstrip('/')}/models",
            headers=self.headers,
            timeout=5,
        )
        response.raise_for_status()
        models = [model.get("id") for model in response.json().get("data", [])]
        return {
            "status": "ok",
            "provider": self.config.embedding_provider,
            "embedding_model": self.config.embedding_model,
            "model_available": self.config.embedding_model in models,
        }


class GeminiEmbeddingClient:
    """Google Gemini embeddings through the Generative Language REST API."""

    base_url = "https://generativelanguage.googleapis.com/v1beta"
    batch_size = 100
    task_types = {"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY"}

    def __init__(self, config: AppConfig, client: httpx.Client | None = None):
        if not config.gemini_api_key:
            raise EmbeddingError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY")
        self.config = config
        self.client = client or httpx.Client(timeout=120)

    @property
    def model_path(self) -> str:
        model = self.config.embedding_model
        return model if model.startswith("models/") else f"models/{model}"

    @property
    def headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.config.gemini_api_key or ""}

    def embed(self, texts: list[str], task: EmbeddingTask = "document") -> list[list[float]]:
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset : offset + self.batch_size]
            response = self.client.post(
                f"{self.base_url}/{self.model_path}:batchEmbedContents",
                headers=self.headers,
                json={
                    "requests": [
                        {
                            "model": self.model_path,
                            "content": {"parts": [{"text": text}]},
                            "taskType": self.task_types[task],
                            "outputDimensionality": self.config.embedding_dimension,
                        }
                        for text in batch
                    ]
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise EmbeddingError(f"Gemini embedding request failed: {exc}") from exc
            vectors.extend(item["values"] for item in response.json().get("embeddings", []))
        return validate_vectors(self.config, texts, vectors)

    def health(self) -> dict[str, Any]:
        response = self.client.get(
            f"{self.base_url}/{self.model_path}", headers=self.headers, timeout=5
        )
        response.raise_for_status()
        return {
            "status": "ok",
            "provider": "gemini",
            "embedding_model": self.config.embedding_model,
            "model_available": True,
        }


def create_embedding_client(
    config: AppConfig, client: httpx.Client | None = None
) -> EmbeddingClient:
    if config.embedding_provider == "gemini":
        return GeminiEmbeddingClient(config, client)
    return OpenAICompatibleEmbeddingClient(config, client)
