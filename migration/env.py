from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config.app_config import get_config
from app.model import Channel, ChunkEmbedding, Episode, TranscriptChunk  # noqa: F401
from app.model.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_config().database_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    """Keep autogeneration isolated from tables owned by other applications."""
    if type_ == "table":
        return bool(name and name.startswith("podcast_"))
    table_name = parent_names.get("table_name")
    return table_name is None or table_name.startswith("podcast_")


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=True,
        compare_type=True,
        version_table="podcast_alembic_version",
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_server_default=True,
            compare_type=True,
            version_table="podcast_alembic_version",
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
