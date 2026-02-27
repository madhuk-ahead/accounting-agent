"""FastAPI app: static frontend and WebSocket chat page."""

import json
import os
import uuid

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import get_settings


def _create_sub_app(settings, templates, root_path: str) -> FastAPI:
    """Sub-app with health, root, app page, static, and local WebSocket. Mount at root_path for ALB path prefix."""
    sub = FastAPI()
    sub.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    @sub.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Local WebSocket for development; mimics Lambda chat flow."""
        await websocket.accept()
        session_id = str(uuid.uuid4())
        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            from core.agent import get_agent_manager
            agent_manager = get_agent_manager()
            loop = asyncio.get_event_loop()

            def stream_cb(msg: str, msg_type: str = "status") -> None:
                fut = asyncio.run_coroutine_threadsafe(
                    websocket.send_json({"type": msg_type, "content": msg}),
                    loop,
                )
                try:
                    fut.result(timeout=5)
                except Exception:
                    pass

            while True:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    payload = {}
                user_text = (payload.get("text") or "").strip()
                conversation = (payload.get("conversation") or "").strip()
                form_data = payload.get("form_data") or {}
                if not conversation and user_text:
                    conversation = f"USER: {user_text}"

                executor = ThreadPoolExecutor(max_workers=1)

                def run_agent():
                    return agent_manager.run(
                        conversation_id=session_id,
                        user_text=user_text,
                        transcript=conversation,
                        on_stream_message=stream_cb,
                        form_data=form_data,
                    )

                result = await loop.run_in_executor(executor, run_agent)
                final = {
                    "type": "final",
                    "content": result.message,
                    "buttons": getattr(result, "buttons", []),
                    "conversation_id": result.conversation_id,
                    "file_content": getattr(result, "file_content", None),
                }
                await websocket.send_json(final)
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "content": str(e)})
            except Exception:
                pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

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
