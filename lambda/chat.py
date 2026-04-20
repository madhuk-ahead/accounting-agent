"""Lambda handler for WebSocket $default route (chat messages)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Internal flag when this function is invoked asynchronously (not from API Gateway).
# API Gateway WebSocket integrations time out at ~29s; long LLM + LangGraph runs continue here.
_ASYNC_CHAT_WORKER = "_async_chat_worker"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print(f"[CHAT] Cold start: path[0]={sys.path[0]}", file=sys.stderr)

from core.telemetry import flush_telemetry, get_meter, get_tracer, init_telemetry

init_telemetry()
_chat_meter = get_meter("lambda.chat")
_ws_turns_counter = _chat_meter.create_counter(
    "ws.turns.total",
    description="Total conversation turns",
)
_chat_tracer = get_tracer("lambda.chat")

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore


def _get_session_id_from_connection(connection_id: str) -> str | None:
    if not HAS_BOTO3:
        return None
    table_name = os.getenv("DYNAMODB_SESSIONS_TABLE", "agent-template-sessions")
    try:
        dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
        table = dynamodb.Table(table_name)
        response = table.query(
            IndexName="connection_id-index",
            KeyConditionExpression="connection_id = :cid",
            ExpressionAttributeValues={":cid": connection_id},
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0].get("session_id") if items else None
    except Exception as e:
        print(f"[CHAT] Failed to look up session: {e}")
        return None


def _turn_number(payload: dict[str, Any], conversation: str) -> int:
    """Align with app/main.py turn counter: optional client ``turn``, else count ``USER:`` in transcript."""
    raw = payload.get("turn")
    if raw is not None:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    if conversation:
        return max(1, conversation.count("USER:"))
    return 1


def _send_websocket_message(
    domain_name: str,
    stage: str,
    connection_id: str,
    message: dict[str, Any],
) -> bool:
    if not HAS_BOTO3:
        return False
    try:
        endpoint_url = f"https://{domain_name}/{stage}"
        client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=endpoint_url,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message, ensure_ascii=False).encode("utf-8"),
        )
        return True
    except Exception as e:
        print(f"[CHAT] Failed to send WebSocket message: {e}")
        return False


def _load_openai_key_from_secrets() -> None:
    if os.getenv("OPENAI_API_KEY") or not HAS_BOTO3:
        return
    secret_name = os.getenv("OPENAI_API_KEY_SECRET", "openai_api_key")
    region_name = os.getenv("AWS_REGION", "us-east-1")
    try:
        secrets_client = boto3.client("secretsmanager", region_name=region_name)
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_string = response["SecretString"]
        try:
            secret_json = json.loads(secret_string)
            api_key = secret_json.get("OPENAI_API_KEY", secret_string) if isinstance(secret_json, dict) else secret_string
        except (json.JSONDecodeError, TypeError):
            api_key = secret_string
        os.environ["OPENAI_API_KEY"] = api_key
        from core.config import get_settings
        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()
    except Exception as e:
        print(f"[CHAT] WARNING: Could not load OpenAI key: {e}")


def _invoke_self_async(event: dict[str, Any], context: Any) -> None:
    if not HAS_BOTO3:
        raise RuntimeError("boto3 required for async chat dispatch")
    fn_arn = getattr(context, "invoked_function_arn", None)
    if not fn_arn:
        raise RuntimeError("invoked_function_arn missing; cannot async invoke")
    worker_event = dict(event)
    worker_event[_ASYNC_CHAT_WORKER] = True
    payload_bytes = json.dumps(worker_event, default=str).encode("utf-8")
    if len(payload_bytes) > 250_000:
        print(f"[CHAT] Payload {len(payload_bytes)} bytes — async invoke limit risk; running synchronously", file=sys.stderr)
        raise _PayloadTooLargeForAsync()
    boto3.client("lambda", region_name=os.getenv("AWS_REGION", "us-east-1")).invoke(
        FunctionName=fn_arn,
        InvocationType="Event",
        Payload=payload_bytes,
    )


class _PayloadTooLargeForAsync(Exception):
    """Fall back to synchronous handler."""


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle chat message: look up session, run agent, stream and send final response."""
    print(f"[CHAT] Invoked. RequestId: {context.aws_request_id if context else 'unknown'}")

    _load_openai_key_from_secrets()

    # Worker path: full agent run (no API Gateway time limit).
    if event.get(_ASYNC_CHAT_WORKER):
        try:
            return _chat_handler_body(event, context)
        finally:
            flush_telemetry()

    # API Gateway path: return fast so the ~29s integration limit does not kill long LLM triage.
    try:
        try:
            _invoke_self_async(event, context)
        except _PayloadTooLargeForAsync:
            return _chat_handler_body(event, context)
        return {"statusCode": 200}
    except Exception as e:
        print(f"[CHAT] Async dispatch failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return _chat_handler_body(event, context)
    finally:
        flush_telemetry()


def _chat_handler_body(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        request_context = event.get("requestContext", {})
        connection_id = request_context.get("connectionId")
        domain_name = request_context.get("domainName")
        stage = request_context.get("stage")
        if not connection_id:
            return {"statusCode": 400}

        session_id = _get_session_id_from_connection(connection_id)
        if not session_id:
            if domain_name and stage:
                _send_websocket_message(domain_name, stage, connection_id, {"type": "error", "content": "Session not found. Please reconnect."})
            return {"statusCode": 400}

        body = event.get("body", "{}")
        payload = json.loads(body) if isinstance(body, str) else body
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

        turn_number = _turn_number(payload, conversation)

        os.environ["SESSION_ID"] = session_id
        os.environ["USE_DYNAMODB"] = "true"

        def stream_callback(message: str, msg_type: str = "status") -> None:
            if domain_name and stage:
                _send_websocket_message(domain_name, stage, connection_id, {"type": msg_type, "content": message})

        _ws_turns_counter.add(1)
        with _chat_tracer.start_as_current_span(
            "ws.turn",
            attributes={
                "session.id": session_id,
                "turn.number": turn_number,
                "user.message_length": len(user_text),
            },
        ):
            from core.agent import get_agent_manager
            agent_manager = get_agent_manager()
            result = agent_manager.run(
                conversation_id=session_id,
                user_text=user_text,
                transcript=conversation,
                on_stream_message=stream_callback,
                form_data=form_data,
            )

        final_message = {
            "type": "final",
            "content": result.message,
            "buttons": getattr(result, "buttons", []),
            "conversation_id": result.conversation_id,
            "file_content": getattr(result, "file_content", None),
            "display_data": getattr(result, "display_data", None),
            "reasoning_stages": getattr(result, "reasoning_stages", None),
            "confirmation_prompt": getattr(result, "confirmation_prompt", None),
        }
        if domain_name and stage:
            _send_websocket_message(domain_name, stage, connection_id, final_message)

        return {"statusCode": 200}
    except Exception as e:
        import traceback
        err_msg = (str(e) or repr(e) or "Internal error. Check CloudWatch logs for the chat Lambda.").strip()
        print(f"[CHAT] ERROR: {err_msg}")
        traceback.print_exc()
        request_context = event.get("requestContext", {})
        connection_id = request_context.get("connectionId")
        domain_name = request_context.get("domainName")
        stage = request_context.get("stage")
        if connection_id and domain_name and stage:
            _send_websocket_message(domain_name, stage, connection_id, {"type": "error", "content": err_msg})
        return {"statusCode": 500}
