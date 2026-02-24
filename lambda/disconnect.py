"""Lambda handler for WebSocket $disconnect route. Cleans up session."""

from __future__ import annotations

import os
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
    """AWS Lambda handler for WebSocket $disconnect."""
    print(f"[DISCONNECT] Lambda invoked. RequestId: {context.aws_request_id if context else 'unknown'}")

    try:
        request_context = event.get("requestContext", {})
        connection_id = request_context.get("connectionId")
        if not connection_id:
            return {"statusCode": 200}

        sessions_table_name = os.getenv("DYNAMODB_SESSIONS_TABLE", "agent-template-sessions")

        if HAS_BOTO3:
            try:
                dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
                sessions_table = dynamodb.Table(sessions_table_name)
                response = sessions_table.query(
                    IndexName="connection_id-index",
                    KeyConditionExpression="connection_id = :cid",
                    ExpressionAttributeValues={":cid": connection_id},
                    Limit=1,
                )
                items = response.get("Items", [])
                if items and items[0].get("session_id"):
                    sessions_table.delete_item(Key={"session_id": items[0]["session_id"]})
                    print(f"[DISCONNECT] Deleted session for connection {connection_id}")
            except ClientError as e:
                print(f"[DISCONNECT] WARNING: Failed to delete session: {e}")
        return {"statusCode": 200}
    except Exception as e:
        print(f"[DISCONNECT] WARNING: {e}")
        import traceback
        traceback.print_exc()
        return {"statusCode": 200}
