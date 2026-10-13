import importlib

import pytest

from app.config import app_config
from app.config.app_config import AppConfig


def test_defaults() -> None:
    config = AppConfig(_env_file=None)
    assert config.app_port == 8801
    assert config.qdrant_url == "http://127.0.0.1:6333"
    assert config.langfuse_url is None
    assert config.embedding_key == "openai_compatible:text-embedding-qwen3-embedding-0.6b:1024"


def test_remote_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "192.168.1.161")
    monkeypatch.setenv("QDRANT_HOST", "192.168.1.161")
    monkeypatch.setenv("LANGFUSE_HOST", "192.168.1.161")
    monkeypatch.setenv("LANGFUSE_WEB_PORT", "3100")
    config = AppConfig(_env_file=None)
    assert "@192.168.1.161:" in config.database_url
    assert config.qdrant_url == "http://192.168.1.161:6333"
    assert config.langfuse_url == "http://192.168.1.161:3100"


def test_app_env_file_selects_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.prod"
    env_file.write_text("APP_PORT=9123\nQDRANT_HOST=10.0.0.5\nNEO4J_PASSWORD=ignored\n")
    monkeypatch.setenv("APP_ENV_FILE", str(env_file))
    try:
        module = importlib.reload(app_config)
        config = module.AppConfig()
        assert config.app_port == 9123
        assert config.qdrant_url == "http://10.0.0.5:6333"
    finally:
        monkeypatch.delenv("APP_ENV_FILE")
        importlib.reload(app_config)
