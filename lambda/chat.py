"""Lambda handler for WebSocket $default route (chat messages)."""

from __future__ import annotations

import json
import os
from typing import Any

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print(f"[CHAT] Cold start: path[0]={sys.path[0]}", file=sys.stderr)

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


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle chat message: look up session, run agent, stream and send final response."""
    print(f"[CHAT] Invoked. RequestId: {context.aws_request_id if context else 'unknown'}")

    # Load OpenAI API key from Secrets Manager before get_settings
    if not os.getenv("OPENAI_API_KEY") and HAS_BOTO3:
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
        form_data = payload.get("form_data") or {}
        if not conversation and user_text:
            conversation = f"USER: {user_text}"

        os.environ["SESSION_ID"] = session_id
        os.environ["USE_DYNAMODB"] = "true"

        def stream_callback(message: str, msg_type: str = "status") -> None:
            if domain_name and stage:
                _send_websocket_message(domain_name, stage, connection_id, {"type": msg_type, "content": message})

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
