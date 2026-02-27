"""Tools for Press Release Drafting Assistant: DynamoDB lookups and S3 fetch/save."""

from __future__ import annotations

import os
from typing import Any

from core.config import Settings, get_settings


def _get_dynamodb_table(settings: Settings):
    """Return DynamoDB knowledge table resource."""
    table_name = settings.dynamodb_knowledge_table or os.getenv("DYNAMODB_KNOWLEDGE_TABLE", "")
    region = settings.aws_region or os.getenv("AWS_REGION", "us-east-1")
    import boto3
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(table_name)


def _get_s3_client(settings: Settings):
    """Return S3 client."""
    region = settings.aws_region or os.getenv("AWS_REGION", "us-east-1")
    import boto3
    return boto3.client("s3", region_name=region)


# --- DynamoDB lookup tools ---

def lookup_company_boilerplate(company_id: str = "acme") -> dict[str, Any]:
    """Fetch canonical company boilerplate and description from internal knowledge.
    Use company_id like 'acme' for id company:acme."""
    settings = get_settings()
    try:
        table = _get_dynamodb_table(settings)
        resp = table.get_item(Key={"id": f"company:{company_id}"})
        item = resp.get("Item") or {}
        return {
            "id": item.get("id", f"company:{company_id}"),
            "boilerplate": item.get("boilerplate", item.get("content", "")),
            "description": item.get("description", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def lookup_product_facts(product_id: str = "skyline-2") -> dict[str, Any]:
    """Fetch product facts and differentiators from internal knowledge.
    Use product_id like 'skyline-2' for id product:skyline-2."""
    settings = get_settings()
    try:
        table = _get_dynamodb_table(settings)
        resp = table.get_item(Key={"id": f"product:{product_id}"})
        item = resp.get("Item") or {}
        return {
            "id": item.get("id", f"product:{product_id}"),
            "facts": item.get("facts", item.get("content", "")),
            "differentiators": item.get("differentiators", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def lookup_quotes(quote_id: str = "ceo") -> dict[str, Any]:
    """Fetch approved executive quotes from internal knowledge.
    Use quote_id like 'ceo', 'cmo', etc."""
    settings = get_settings()
    try:
        table = _get_dynamodb_table(settings)
        resp = table.get_item(Key={"id": f"quote:{quote_id}"})
        item = resp.get("Item") or {}
        return {
            "id": item.get("id", f"quote:{quote_id}"),
            "quote": item.get("quote", item.get("content", "")),
            "attribution": item.get("attribution", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def lookup_partner_info(partner_id: str = "globex") -> dict[str, Any]:
    """Fetch partner blurbs and announcement-specific facts from internal knowledge."""
    settings = get_settings()
    try:
        table = _get_dynamodb_table(settings)
        resp = table.get_item(Key={"id": f"partner:{partner_id}"})
        item = resp.get("Item") or {}
        return {
            "id": item.get("id", f"partner:{partner_id}"),
            "blurb": item.get("blurb", item.get("content", "")),
            "facts": item.get("facts", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def lookup_metrics(metrics_id: str = "q1-2026") -> dict[str, Any]:
    """Fetch metrics (toy metrics, dates, locations) from internal knowledge."""
    settings = get_settings()
    try:
        table = _get_dynamodb_table(settings)
        resp = table.get_item(Key={"id": f"metrics:{metrics_id}"})
        item = resp.get("Item") or {}
        return {
            "id": item.get("id", f"metrics:{metrics_id}"),
            "metrics": item.get("metrics", item.get("content", "")),
        }
    except Exception as e:
        return {"error": str(e)}


# --- S3 fetch tool ---

def fetch_press_kit_document(doc_key: str) -> dict[str, Any]:
    """Fetch a press-kit document from S3. Use keys like:
    docs/press-kit/company_overview.md
    docs/press-kit/product_one_pager.md
    docs/press-kit/partner_blurb.md
    docs/press-kit/metrics_summary.json"""
    settings = get_settings()
    bucket = settings.s3_press_kit_bucket or os.getenv("S3_PRESS_KIT_BUCKET", "")
    if not bucket:
        return {"error": "S3_PRESS_KIT_BUCKET not configured"}
    try:
        client = _get_s3_client(settings)
        resp = client.get_object(Bucket=bucket, Key=doc_key)
        content = resp["Body"].read().decode("utf-8", errors="replace")
        return {"key": doc_key, "content": content}
    except Exception as e:
        return {"error": str(e), "key": doc_key}


# --- S3 save tool ---

def save_press_release(session_id: str, content: str, filename: str = "PressRelease.md") -> dict[str, Any]:
    """Save the generated press release to S3 under exports/press-releases/{session_id}/.
    Returns the S3 key for reference."""
    settings = get_settings()
    bucket = settings.s3_press_kit_bucket or os.getenv("S3_PRESS_KIT_BUCKET", "")
    if not bucket:
        return {"error": "S3_PRESS_KIT_BUCKET not configured"}
    key = f"exports/press-releases/{session_id}/{filename}"
    try:
        client = _get_s3_client(settings)
        client.put_object(Bucket=bucket, Key=key, Body=content.encode("utf-8"), ContentType="text/markdown")
        return {"key": key, "success": True}
    except Exception as e:
        return {"error": str(e), "key": key}
