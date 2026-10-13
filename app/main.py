from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config.app_config import get_config
from app.routers.api import api_router
from app.routers.web import web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config = get_config()
    yield


config = get_config()
app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description="Private podcast transcript ingestion and semantic search",
    lifespan=lifespan,
)
app.mount(
    "/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static"
)
app.include_router(api_router)
app.include_router(web_router)

