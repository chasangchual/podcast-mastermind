import json
from typing import Annotated

import typer

from app.config.app_config import get_config
from app.config.db import SessionLocal
from app.model.entities import Channel
from app.service.sync import PodcastSyncService

app = typer.Typer(help="Ingest and index podcast transcripts.")


@app.command()
def sync(
    years: Annotated[
        int, typer.Option(min=1, max=20, help="Number of years to scan.")
    ] = 2,
    channel: Annotated[
        list[str] | None, typer.Option(help="Channel slug; repeat to select several.")
    ] = None,
) -> None:
    """Fetch configured RSS feeds and process new, changed, or failed episodes."""
    with SessionLocal() as session:
        stats = PodcastSyncService(get_config()).run(session, years=years, slugs=channel)
    typer.echo(json.dumps(stats.model_dump(), indent=2))
    if stats.episodes_failed:
        raise typer.Exit(code=1)


@app.command()
def reindex(
    channel: Annotated[
        list[str] | None, typer.Option(help="Channel slug; repeat to select several.")
    ] = None,
) -> None:
    """Embed stored chunks missing from the current embedding model's Qdrant collection."""
    with SessionLocal() as session:
        count = PodcastSyncService(get_config()).reindex(session, slugs=channel)
    typer.echo(f"Re-embedded {count} episodes")


@app.command("add-channel")
def add_channel(slug: str, title: str, rss_url: str, website_url: str | None = None) -> None:
    """Add a podcast RSS feed to the channel catalog."""
    with SessionLocal() as session:
        session.add(Channel(slug=slug, title=title, rss_url=rss_url, website_url=website_url))
        session.commit()
    typer.echo(f"Added {slug}")


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Bind address (default: APP_HOST).")] = None,
    port: Annotated[int | None, typer.Option(help="Port (default: APP_PORT, 8801).")] = None,
    reload: Annotated[bool, typer.Option(help="Reload on code changes.")] = False,
) -> None:
    """Start the web UI and REST API."""
    import uvicorn

    config = get_config()
    uvicorn.run(
        "app.main:app",
        host=host or config.app_host,
        port=port or config.app_port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
