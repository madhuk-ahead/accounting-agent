"""FastAPI app: static frontend and WebSocket chat page."""

import json
import logging
import os
import uuid
from pathlib import Path

# Load .env for local development (OPENAI_API_KEY, S3_AP_BUCKET, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging so MOCK DATA warnings from tools are visible
logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")

from fastapi import FastAPI, File, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import get_settings
from core.telemetry import get_meter, get_tracer, init_telemetry


def _create_sub_app(settings, templates, root_path: str) -> FastAPI:
    """Sub-app with health, root, app page, static, and local WebSocket. Mount at root_path for ALB path prefix."""
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    sub = FastAPI()
    sub.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    ws_tracer = get_tracer("app.websocket")
    ws_meter = get_meter("app.websocket")
    ws_sessions_counter = ws_meter.create_counter(
        "ws.sessions.total",
        description="Total WebSocket sessions",
    )
    ws_turns_counter = ws_meter.create_counter(
        "ws.turns.total",
        description="Total conversation turns",
    )

    @sub.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Local WebSocket for development; mimics Lambda chat flow."""
        await websocket.accept()
        session_id = str(uuid.uuid4())
        ws_sessions_counter.add(1)
        try:
            with ws_tracer.start_as_current_span(
                "ws.session",
                attributes={"session.id": session_id},
            ):
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

                # Shared dashboard convention; no separate greeting RPC in this app.
                with ws_tracer.start_as_current_span(
                    "ws.greeting",
                    attributes={"session.id": session_id},
                ):
                    pass

                turn = 0
                while True:
                    data = await websocket.receive_text()
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        payload = {}
                    user_text = (payload.get("text") or "").strip()
                    conversation = (payload.get("conversation") or "").strip()
                    form_data = dict(payload.get("form_data") or {})
                    if payload.get("last_display_data") is not None:
                        form_data["last_display_data"] = payload["last_display_data"]
                    if payload.get("last_file_content"):
                        form_data["last_file_content"] = payload["last_file_content"]
                    if payload.get("invoice_pages_base64"):
                        form_data["invoice_pages_base64"] = payload["invoice_pages_base64"]
                    if not conversation and user_text:
                        conversation = f"USER: {user_text}"

                    turn += 1
                    ws_turns_counter.add(1)
                    with ws_tracer.start_as_current_span(
                        "ws.turn",
                        attributes={
                            "session.id": session_id,
                            "turn.number": turn,
                            "user.message_length": len(user_text),
                        },
                    ):
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
                            "display_data": getattr(result, "display_data", None),
                            "reasoning_stages": getattr(result, "reasoning_stages", None),
                            "confirmation_prompt": getattr(result, "confirmation_prompt", None),
                        }
                        await websocket.send_json(final)
        except Exception as e:
            span = trace.get_current_span()
            if span.is_recording():
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
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

    @sub.post("/api/upload-invoice")
    async def upload_invoice(invoice: UploadFile = File(...)) -> dict[str, str]:
        """Upload invoice to S3, or to .local_s3_mirror/ when S3_AP_BUCKET is unset (local dev)."""
        ext = ""
        if invoice.filename and "." in invoice.filename:
            ext = "." + invoice.filename.rsplit(".", 1)[-1].lower()
        key = f"invoices/uploads/{uuid.uuid4()}{ext}"
        contents = await invoice.read()
        bucket = os.getenv("S3_AP_BUCKET", "").strip()
        if not bucket:
            root = Path(__file__).resolve().parent.parent
            dest = root / ".local_s3_mirror" / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(contents)
            return {"file_path": key}

        try:
            import boto3
            client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=contents,
                ContentType=invoice.content_type or "application/octet-stream",
            )
            return {"file_path": key}
        except Exception as e:
            return {"error": str(e), "file_path": ""}

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
    init_telemetry()
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
