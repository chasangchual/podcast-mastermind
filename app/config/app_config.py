import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


def env_file_path() -> Path:
    """Resolve the env file from APP_ENV_FILE (default: .env), relative to the project root."""
    path = Path(os.environ.get("APP_ENV_FILE", ".env"))
    return path if path.is_absolute() else ROOT_DIR / path


class AppConfig(BaseSettings):
    app_name: str = "Podcast Mastermind"
    app_version: str = "0.1.0"
    app_env: str = Field(default="local", validation_alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", validation_alias="APP_HOST")
    app_port: int = Field(default=8801, validation_alias="APP_PORT")

    postgres_host: str = Field(default="127.0.0.1", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="podcast_mastermind", validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(
        default="podcast-mastermind", validation_alias="POSTGRES_PASSWORD"
    )
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")

    qdrant_url_override: str | None = Field(default=None, validation_alias="QDRANT_URL")
    qdrant_host: str = Field(default="127.0.0.1", validation_alias="QDRANT_HOST")
    qdrant_rest_port: int = Field(default=6333, validation_alias="QDRANT_REST_PORT")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")

    langfuse_host: str | None = Field(default=None, validation_alias="LANGFUSE_HOST")
    langfuse_web_port: int = Field(default=3000, validation_alias="LANGFUSE_WEB_PORT")
    langfuse_public_key: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")

    embedding_provider: Literal["openai_compatible", "gemini"] = Field(
        default="openai_compatible", validation_alias="EMBEDDING_PROVIDER"
    )
    embedding_key_provider: str | None = Field(
        default=None, validation_alias="EMBEDDING_KEY_PROVIDER"
    )
    embedding_base_url: str = Field(
        default="http://127.0.0.1:1234/v1",
        validation_alias=AliasChoices("EMBEDDING_BASE_URL", "LMSTUDIO_BASE_URL"),
    )
    embedding_api_key: str | None = Field(
        default="lm-studio",
        validation_alias=AliasChoices("EMBEDDING_API_KEY", "LMSTUDIO_API_KEY"),
    )
    embedding_model: str = Field(
        default="text-embedding-qwen3-embedding-0.6b",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "LMSTUDIO_EMBEDDING_MODEL"),
    )
    embedding_dimension: int = Field(
        default=1024,
        validation_alias=AliasChoices("EMBEDDING_DIMENSION", "LMSTUDIO_EMBEDDING_DIMENSION"),
    )
    embedding_send_dimensions: bool = Field(
        default=False, validation_alias="EMBEDDING_SEND_DIMENSIONS"
    )
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")

    transcription_backend: Literal["faster_whisper", "mlx"] = Field(
        default="faster_whisper", validation_alias="TRANSCRIPTION_BACKEND"
    )
    whisper_model: str = Field(default="large-v3-turbo", validation_alias="WHISPER_MODEL")
    whisper_device: str = Field(default="cpu", validation_alias="WHISPER_DEVICE")
    whisper_compute_type: str = Field(default="int8", validation_alias="WHISPER_COMPUTE_TYPE")
    whisper_cpu_threads: int = Field(default=0, validation_alias="WHISPER_CPU_THREADS")
    whisper_beam_size: int = Field(default=1, validation_alias="WHISPER_BEAM_SIZE")
    diarization_enabled: bool = Field(default=False, validation_alias="DIARIZATION_ENABLED")
    diarization_model: str = Field(
        default="pyannote/speaker-diarization-community-1",
        validation_alias="DIARIZATION_MODEL",
    )
    huggingface_token: str | None = Field(default=None, validation_alias="HUGGINGFACE_TOKEN")
    podcast_data_path: Path = Field(default=ROOT_DIR / "data", validation_alias="PODCAST_DATA_PATH")
    http_user_agent: str = Field(
        default="podcast-mastermind/0.1 (+private local transcript index)",
        validation_alias="HTTP_USER_AGENT",
    )
    transcript_min_words: int = Field(default=150, validation_alias="TRANSCRIPT_MIN_WORDS")

    model_config = SettingsConfigDict(
        env_file=env_file_path(), env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg://{user}:{password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def embedding_key(self) -> str:
        provider = self.embedding_key_provider or self.embedding_provider
        return f"{provider}:{self.embedding_model}:{self.embedding_dimension}"

    @property
    def qdrant_url(self) -> str:
        return self.qdrant_url_override or f"http://{self.qdrant_host}:{self.qdrant_rest_port}"

    @property
    def langfuse_url(self) -> str | None:
        if not self.langfuse_host:
            return None
        if self.langfuse_host.startswith(("http://", "https://")):
            return self.langfuse_host.rstrip("/")
        return f"http://{self.langfuse_host}:{self.langfuse_web_port}"


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()
