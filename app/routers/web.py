from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
web_router = APIRouter()


@web_router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"page": "dashboard"})


@web_router.get("/episodes/{episode_id}", response_class=HTMLResponse)
def episode_page(request: Request, episode_id: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "episode.html", {"page": "episodes", "episode_id": episode_id}
    )

