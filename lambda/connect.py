"""Lambda handler for WebSocket $connect route. Creates a new session."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler for WebSocket $connect."""
    print(f"[CONNECT] Lambda invoked. RequestId: {context.aws_request_id if context else 'unknown'}")

    try:
        request_context = event.get("requestContext", {})
        connection_id = request_context.get("connectionId")
        if not connection_id:
            print("[CONNECT] ERROR: No connectionId in request context")
            return {"statusCode": 500}

        session_id = str(uuid.uuid4())
        sessions_table_name = os.getenv("DYNAMODB_SESSIONS_TABLE", "agent-template-sessions")

        if HAS_BOTO3:
            try:
                dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
                sessions_table = dynamodb.Table(sessions_table_name)
                ttl = int(datetime.now(timezone.utc).timestamp() + 86400)
                sessions_table.put_item(
                    Item={
                        "session_id": session_id,
                        "connection_id": connection_id,
                        "created_at": datetime.now(tz=timezone.utc).isoformat(),
                        "last_activity": datetime.now(tz=timezone.utc).isoformat(),
                        "ttl": ttl,
                    }
                )
                print(f"[CONNECT] Created session {session_id} for connection {connection_id}")
            except ClientError as e:
                print(f"[CONNECT] ERROR: Failed to store session: {e}")
                return {"statusCode": 500}
        else:
            print(f"[CONNECT] WARNING: boto3 not available. Session: {session_id}")

        return {
            "statusCode": 200,
            "headers": {"X-Session-Id": session_id},
        }
    except Exception as e:
        print(f"[CONNECT] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"statusCode": 500}
