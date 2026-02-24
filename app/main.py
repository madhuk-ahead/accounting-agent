"""FastAPI app: static frontend and WebSocket chat page."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from core.config import get_settings


def _create_sub_app(settings, templates, root_path: str) -> FastAPI:
    """Sub-app with health, root, app page, and static. Mount at root_path for ALB path prefix."""
    sub = FastAPI()
    sub.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    @sub.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @sub.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok", "service": "agent-template-frontend"}

    @sub.get("/app", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        ws_url = os.getenv("AGENT_WS_URL", "ws://localhost:8000/ws")
        return templates.TemplateResponse(
            "base.html",
            {"request": request, "ws_url": ws_url, "root_path": root_path},
        )
    return sub


def create_app() -> FastAPI:
    settings = get_settings()
    root_path = (os.getenv("APP_ROOT_PATH") or "").strip()
    templates_dir = settings.templates_dir
    static_dir = settings.static_dir
    templates_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)
    templates = Jinja2Templates(directory=str(templates_dir))

    app = FastAPI(title="Agent Template", version="0.1.0", docs_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    sub = _create_sub_app(settings, templates, root_path)
    if root_path:
        app.mount(root_path, sub)
    else:
        app.mount("/", sub)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
