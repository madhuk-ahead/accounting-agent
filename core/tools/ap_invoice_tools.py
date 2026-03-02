"""Tools for AP Invoice Triage + Coding Copilot: extraction, ERP, duplicates, packet generation."""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _get_dynamodb_resource(settings: Settings | None = None):
    settings = settings or get_settings()
    region = settings.aws_region or os.getenv("AWS_REGION", "us-east-1")
    import boto3
    return boto3.resource("dynamodb", region_name=region)


def _get_s3_client(settings: Settings | None = None):
    settings = settings or get_settings()
    region = settings.aws_region or os.getenv("AWS_REGION", "us-east-1")
    import boto3
    return boto3.client("s3", region_name=region)


def _json_dumps_safe(obj: Any, **kwargs: Any) -> str:
    """JSON dumps with Decimal support (DynamoDB returns Decimal for numbers)."""

    class DecimalEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, Decimal):
                return float(o)
            return super().default(o)

    return json.dumps(obj, cls=DecimalEncoder, **kwargs)


def _get_bucket(settings: Settings | None = None) -> str:
    """AP bucket: holds invoices/, policies/, outputs/."""
    settings = settings or get_settings()
    return getattr(settings, "s3_ap_bucket", None) or os.getenv("S3_AP_BUCKET", "")


# ---------------------------------------------------------------------------
# 1. extract_invoice(file_path, image_base64, image_media_type)
# ---------------------------------------------------------------------------

def extract_invoice(
    file_path: str = "",
    image_base64: str | None = None,
    image_media_type: str | None = None,
    image_pages_base64: list[str] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Extract invoice fields from an invoice document or image using LLM parsing.

    Args:
        file_path: S3 key (e.g. invoices/INV-2026-001.pdf) or local path.
        image_base64: Base64-encoded image (single-page upload).
        image_media_type: e.g. image/png, image/jpeg.
        image_pages_base64: List of base64-encoded PNGs (multi-page PDF).
        use_llm: If True, use LLM to parse; else return mock for demo.

    Returns:
        Dict with vendor_name, dates, amounts, line_items, tax, remit_to,
        payment_terms, vendor_id, invoice_no, po_reference, currency, etc.
    """
    settings = get_settings()
    bucket = _get_bucket(settings)
    source = file_path or "uploaded"

    # Multi-page PDF: use vision model with all pages
    if image_pages_base64 and len(image_pages_base64) > 0:
        if use_llm:
            return _extract_from_images(image_pages_base64, source)
        return _parse_mock_invoice(_mock_invoice_content(source), source)

    # Single image/PDF upload: use vision model
    if image_base64 and image_media_type:
        if use_llm:
            return _extract_from_image(image_base64, image_media_type, source)
        return _parse_mock_invoice(_mock_invoice_content(source), source)

    # Try S3 first (invoices/ prefix)
    raw_text = ""
    if bucket and file_path and file_path.startswith("invoices/"):
        try:
            client = _get_s3_client(settings)
            resp = client.get_object(Bucket=bucket, Key=file_path)
            raw_text = resp["Body"].read().decode("utf-8", errors="replace")
        except Exception as e:
            return {"error": str(e), "file_path": file_path}

    # For local or missing file, use mock content
    if not raw_text:
        if not bucket:
            logger.warning("MOCK DATA: S3_AP_BUCKET not set. Using mock invoice content. Set S3_AP_BUCKET and upload invoices to S3 for real extraction.")
        else:
            logger.warning("MOCK DATA: Invoice file not found in S3 (%s). Using mock content. Run seed_ap_invoice.py to upload sample invoices.", file_path)
        raw_text = _mock_invoice_content(file_path or source)

    if use_llm and raw_text:
        return _extract_with_llm(raw_text, file_path or source)
    return _parse_mock_invoice(raw_text, file_path or source)


def _mock_invoice_content(file_path: str) -> str:
    """Return mock invoice text for demo when S3/local file is missing."""
    return """Invoice #INV-2026-001
Vendor: TechSupply Inc. (vendor:techsupply)
Date: 2026-02-28
Due Date: 2026-03-30
PO Reference: PO-5001
Line Items:
  - IT Equipment (Laptops): $3,200
  - Software License (Annual): $1,300
Subtotal: $4,500.00
Tax: $360.00
Total: $4,860.00 USD
Terms: Net 30

Remit to:
TechSupply Inc.
123 Commerce St
San Francisco, CA 94105
"""


INVOICE_EXTRACTION_SCHEMA = """Extract invoice fields. Return valid JSON with:
- vendor_name (string)
- vendor_id (string, e.g. vendor:techsupply if inferable)
- invoice_no (string)
- invoice_date (string, ISO date if possible)
- due_date (string, if present)
- po_reference (string)
- line_items (array of objects with description and amount)
- subtotal (number)
- tax (number)
- amount or total (number, final payable amount)
- currency (string)
- payment_terms (string, e.g. Net 30)
- remit_to (string or object with address lines)
Use vendor_id format like "vendor:techsupply" if you can infer it."""


def _extract_with_llm(raw_text: str, file_path: str) -> dict[str, Any]:
    """Use LLM to parse invoice text into structured fields."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
    except ImportError:
        logger.warning("MOCK DATA: langchain_openai not installed. Using mock parser. pip install langchain-openai langchain-core")
        return _parse_mock_invoice(raw_text, file_path)

    api_key = get_settings().openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("MOCK DATA: OPENAI_API_KEY not set. Using mock parser. Set OPENAI_API_KEY for real LLM extraction.")
        return _parse_mock_invoice(raw_text, file_path)

    prompt = ChatPromptTemplate.from_messages([
        ("system", INVOICE_EXTRACTION_SCHEMA),
        ("human", "{text}"),
    ])

    model = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0)
    chain = prompt | model | JsonOutputParser()
    parsed = chain.invoke({"text": raw_text})
    parsed.setdefault("amount", parsed.get("total"))
    parsed["_source"] = file_path
    parsed["_extracted_at"] = datetime.now(tz=timezone.utc).isoformat()
    return parsed


def _extract_from_images(image_pages_base64: list[str], source: str) -> dict[str, Any]:
    """Use vision model to extract invoice fields from multiple page images (multi-page PDF)."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        from langchain_core.output_parsers import JsonOutputParser
    except ImportError:
        logger.warning("MOCK DATA: langchain_openai not installed. Using mock. pip install langchain-openai langchain-core")
        return _parse_mock_invoice(_mock_invoice_content(source), source)

    api_key = get_settings().openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("MOCK DATA: OPENAI_API_KEY not set. Using mock for image extraction. Set OPENAI_API_KEY for real LLM extraction.")
        return _parse_mock_invoice(_mock_invoice_content(source), source)

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": f"Extract invoice fields from this multi-page invoice document. Combine information from all pages. {INVOICE_EXTRACTION_SCHEMA}",
        },
    ]
    for b64 in image_pages_base64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    msg = HumanMessage(content=content)
    model = ChatOpenAI(model="gpt-4o", api_key=api_key, temperature=0)
    try:
        response = model.invoke([msg])
        text = response.content if hasattr(response, "content") else str(response)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        return {"error": f"Could not parse extraction: {e}", "_source": source}

    parsed.setdefault("amount", parsed.get("total"))
    parsed["_source"] = source
    parsed["_extracted_at"] = datetime.now(tz=timezone.utc).isoformat()
    return parsed


def _extract_from_image(image_base64: str, media_type: str, source: str) -> dict[str, Any]:
    """Use vision model to extract invoice fields from image or PDF."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        from langchain_core.output_parsers import JsonOutputParser
    except ImportError:
        logger.warning("MOCK DATA: langchain_openai not installed. Using mock. pip install langchain-openai langchain-core")
        return _parse_mock_invoice(_mock_invoice_content(source), source)

    api_key = get_settings().openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("MOCK DATA: OPENAI_API_KEY not set. Using mock for image extraction. Set OPENAI_API_KEY for real LLM extraction.")
        return _parse_mock_invoice(_mock_invoice_content(source), source)

    # Build image message for vision model
    image_url = f"data:{media_type};base64,{image_base64}"
    msg = HumanMessage(
        content=[
            {"type": "text", "text": f"Extract invoice fields from this invoice image. {INVOICE_EXTRACTION_SCHEMA}"},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    )
    model = ChatOpenAI(model="gpt-4o", api_key=api_key, temperature=0)
    parser = JsonOutputParser()
    try:
        response = model.invoke([msg])
        text = response.content if hasattr(response, "content") else str(response)
        # Try to parse JSON from response (handle markdown code blocks)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        return {"error": f"Could not parse extraction: {e}", "_source": source}

    parsed.setdefault("amount", parsed.get("total"))
    parsed["_source"] = source
    parsed["_extracted_at"] = datetime.now(tz=timezone.utc).isoformat()
    return parsed


def _parse_mock_invoice(raw_text: str, file_path: str) -> dict[str, Any]:
    """Simple fallback parser for demo when LLM not available."""
    lines = raw_text.strip().split("\n")
    data: dict[str, Any] = {"_source": file_path}
    remit_lines: list[str] = []
    in_remit = False
    for line in lines:
        if "Invoice #" in line or "Invoice No" in line:
            data["invoice_no"] = line.split("#")[-1].strip() or line.split(":")[-1].strip()
        elif "Vendor:" in line:
            parts = line.split("Vendor:")[-1].strip().split("(")
            data["vendor_name"] = parts[0].strip()
            if len(parts) > 1:
                data["vendor_id"] = parts[1].replace(")", "").strip()
        elif "Date:" in line and "Due" not in line:
            data["invoice_date"] = data.get("date") or line.split(":")[-1].strip()
        elif "Due Date:" in line:
            data["due_date"] = line.split(":")[-1].strip()
        elif "PO Reference:" in line:
            data["po_reference"] = line.split(":")[-1].strip()
        elif "Subtotal:" in line:
            amt = _parse_amount(line.split(":")[-1])
            if amt is not None:
                data["subtotal"] = amt
        elif "Tax:" in line:
            amt = _parse_amount(line.split(":")[-1])
            if amt is not None:
                data["tax"] = amt
        elif "Total:" in line:
            amt = _parse_amount(line.split(":")[-1])
            if amt is not None:
                data["amount"] = amt
        elif "Terms:" in line:
            data["payment_terms"] = line.split(":")[-1].strip()
        elif line.strip().lower() == "remit to:":
            in_remit = True
        elif in_remit and line.strip():
            remit_lines.append(line.strip())
        elif line.strip().startswith("- ") and ":" in line and not in_remit:
            # Simple line item: "- IT Equipment (Laptops): $3,200"
            parts = line.strip()[2:].rsplit(":", 1)
            if len(parts) == 2:
                desc, amt = parts[0].strip(), _parse_amount(parts[1])
                data.setdefault("line_items", []).append({"description": desc, "amount": amt})
        if "currency" not in data and ("USD" in line or "EUR" in line):
            data["currency"] = "USD" if "USD" in line else "EUR"
    if remit_lines:
        data["remit_to"] = "\n".join(remit_lines)
    data.setdefault("vendor_id", "vendor:techsupply")
    data.setdefault("line_items", [])
    data.setdefault("currency", "USD")
    data.setdefault("payment_terms", "Net 30")
    data["_extracted_at"] = datetime.now(tz=timezone.utc).isoformat()
    return data


def _parse_amount(s: str) -> float | None:
    """Extract numeric amount from string like '$4,500.00 USD'."""
    s = (s or "").replace("$", "").replace(",", "").strip().split()[0]
    try:
        return float(s)
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# 2. query_mock_erp(vendor_id, po_id)
# ---------------------------------------------------------------------------

def query_mock_erp(vendor_id: str, po_id: str) -> dict[str, Any]:
    """Query mock DynamoDB tables: Vendors, PurchaseOrders, Receipts.

    Returns vendor defaults (GL, payment terms), PO details (amount, line items),
    and receipt status for 3-way matching.
    """
    # reload settings on each call in case the process started before the
    # environment vars were exported (uvicorn --reload spawns workers that may
    # cache a stale Settings instance).  the cache is small so this is cheap.
    try:
        get_settings.cache_clear()
    except AttributeError:
        pass
    settings = get_settings()

    dynamodb = _get_dynamodb_resource(settings)
    region = settings.aws_region or os.getenv("AWS_REGION", "us-east-1")

    # some callers (tests, lambda bootstrapping) may set table names on the
    # settings object directly, but we always want the *current* value from the
    # environment as a fallback.  reading os.getenv() here ensures we don't
    # accidentally continue using an empty string if env vars were populated
    # after the Settings instance was created.
    vendors_table = getattr(settings, "dynamodb_vendors_table", None) or os.getenv("DYNAMODB_VENDORS_TABLE", "")
    pos_table = getattr(settings, "dynamodb_pos_table", None) or os.getenv("DYNAMODB_POS_TABLE", "")
    receipts_table = os.getenv("DYNAMODB_RECEIPTS_TABLE", "") or getattr(settings, "dynamodb_receipts_table", "")

    logger.info(f"tables: vendors={vendors_table!r} pos={pos_table!r} receipts={receipts_table!r} region={region!r}")

    result: dict[str, Any] = {"vendor": None, "po": None, "receipt": None}

    if vendors_table:
        try:
            t = dynamodb.Table(vendors_table)
            vid = vendor_id if ":" in vendor_id else f"vendor:{vendor_id}"
            resp = t.get_item(Key={"id": vid})
            result["vendor"] = resp.get("Item") or {}
        except Exception as e:
            result["vendor_error"] = str(e)
    else:
        logger.warning("MOCK DATA: DYNAMODB_VENDORS_TABLE not set. Using mock vendor/PO/receipt. Set env vars and run seed_ap_invoice.py for real data.")
        result["vendor"] = _mock_vendor(vendor_id)

    if pos_table:
        try:
            t = dynamodb.Table(pos_table)
            pid = po_id if "PO-" in po_id else f"PO-{po_id}"
            resp = t.get_item(Key={"po_id": pid})
            result["po"] = resp.get("Item") or {}
        except Exception as e:
            result["po_error"] = str(e)
    else:
        if vendors_table:
            logger.warning("MOCK DATA: DYNAMODB_POS_TABLE not set. Using mock PO.")
        result["po"] = _mock_po(po_id)

    if receipts_table and result.get("po"):
        po_id_val = result["po"].get("po_id") or po_id
        try:
            t = dynamodb.Table(receipts_table)
            resp = t.query(KeyConditionExpression="po_id = :pid", ExpressionAttributeValues={":pid": po_id_val}, Limit=1)
            items = resp.get("Items", [])
            result["receipt"] = items[0] if items else {}
        except Exception as e:
            result["receipt_error"] = str(e)
    elif result.get("po"):
        # PO found but receipts_table not configured → use mock receipt
        if pos_table:
            logger.warning("MOCK DATA: DYNAMODB_RECEIPTS_TABLE not set. Using mock receipt.")
        result["receipt"] = _mock_receipt(po_id)
    else:
        # No PO found → no receipt to match; do not return mock receipt
        result["receipt"] = {}

    return result


def _mock_vendor(vendor_id: str) -> dict:
    vendors = {
        "vendor:acme": {"name": "Acme IT Services", "default_gl_code": "6105", "default_cost_center": "IT-100"},
        "vendor:techsupply": {"name": "TechSupply Inc.", "default_gl_code": "6105", "default_cost_center": "IT-100"},
        "vendor:brightmarketing": {"name": "BrightMarketing Corp", "default_gl_code": "6200", "default_cost_center": "MKT-300"},
    }
    v = vendors.get(vendor_id, {"name": "Vendor", "default_gl_code": "6105", "default_cost_center": "IT-100"})
    return {
        "id": vendor_id,
        "name": v["name"],
        "default_gl_code": v["default_gl_code"],
        "default_cost_center": v["default_cost_center"],
        "entity": "Corp",
        "payment_terms": "Net 30",
    }


def _mock_po(po_id: str) -> dict:
    pid = po_id if "PO-" in po_id else f"PO-{po_id}"
    pos = {
        "PO-5001": {"vendor_id": "vendor:techsupply", "amount": 4500.0, "cost_center": "IT-100",
            "line_items": [{"description": "IT Equipment (Laptops)", "amount": 3200.0}, {"description": "Software License (Annual)", "amount": 1300.0}]},
        "PO-5002": {"vendor_id": "vendor:techsupply", "amount": 2800.0, "cost_center": "IT-100",
            "line_items": [{"description": "Cloud Services (Annual)", "amount": 2800.0}]},
        "PO-5003": {"vendor_id": "vendor:acme", "amount": 4500.0, "cost_center": "IT-100",
            "line_items": [{"description": "IT Equipment (Laptops)", "amount": 3200.0}, {"description": "Software License (Annual)", "amount": 1300.0}]},
    }
    p = pos.get(pid, {"vendor_id": "vendor:techsupply", "amount": 4500.0, "cost_center": "IT-100", "line_items": []})
    return {"po_id": pid, "status": "approved", **p}


def _mock_receipt(po_id: str) -> dict:
    pid = po_id if "PO-" in po_id else f"PO-{po_id}"
    receipts = {"PO-5001": "REC-001", "PO-5002": "REC-002", "PO-5003": "REC-003"}
    return {
        "po_id": pid,
        "receipt_id": receipts.get(pid, "REC-001"),
        "received": True,
        "received_date": "2026-02-25",
    }


# ---------------------------------------------------------------------------
# 3. check_duplicates(invoice_no, vendor)
# ---------------------------------------------------------------------------

def check_duplicates(invoice_no: str, vendor: str) -> dict[str, Any]:
    """Check the invoice_status table for existing invoices (duplicate detection)."""
    settings = get_settings()
    table_name = getattr(settings, "dynamodb_invoice_status_table", None) or os.getenv("DYNAMODB_INVOICE_STATUS_TABLE", "")

    if table_name:
        try:
            dynamodb = _get_dynamodb_resource(settings)
            t = dynamodb.Table(table_name)
            # Composite key: vendor_id + invoice_no
            vid = vendor if ":" in vendor else f"vendor:{vendor}"
            resp = t.get_item(Key={"vendor_id": vid, "invoice_no": invoice_no})
            item = resp.get("Item")
            return {
                "duplicate": item is not None,
                "existing_record": item,
                "invoice_no": invoice_no,
                "vendor": vid,
            }
        except Exception as e:
            return {"error": str(e), "duplicate": False, "invoice_no": invoice_no, "vendor": vendor}

    # Mock: no duplicates in demo
    return {"duplicate": False, "invoice_no": invoice_no, "vendor": vendor}


# ---------------------------------------------------------------------------
# 4. generate_accounting_packet(state)
# ---------------------------------------------------------------------------

def generate_accounting_packet(state: dict[str, Any], session_id: str = "") -> dict[str, Any]:
    """Format the final GL coding into a structured ERP-ready JSON.

    Saves to S3 outputs/ prefix. Returns paths to generated artifacts.
    """
    settings = get_settings()
    bucket = _get_bucket(settings)

    gl = state.get("gl_coding") or {}
    invoice = state.get("invoice_data") or {}
    po_match = state.get("po_match_results") or {}

    packet = {
        "version": "1.0",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "invoice": {
            "vendor_name": invoice.get("vendor_name"),
            "invoice_no": invoice.get("invoice_no"),
            "invoice_date": invoice.get("invoice_date", invoice.get("date")),
            "due_date": invoice.get("due_date"),
            "amount": invoice.get("amount", invoice.get("total")),
            "subtotal": invoice.get("subtotal"),
            "tax": invoice.get("tax"),
            "line_items": invoice.get("line_items", []),
            "payment_terms": invoice.get("payment_terms"),
            "remit_to": invoice.get("remit_to"),
            "vendor_id": invoice.get("vendor_id"),
            "currency": invoice.get("currency", "USD"),
        },
        "gl_coding": {
            "account_code": gl.get("account_code"),
            "cost_center": gl.get("cost_center"),
            "department": gl.get("department"),
            "entity": gl.get("entity"),
            "approval_path": gl.get("approval_path"),
            "next_actions": gl.get("next_actions", []),
            "rationale": gl.get("rationale"),
        },
        "validation_and_reconciliation": {
            "po_found": po_match.get("po_found", False),
            "two_way_match": po_match.get("two_way_match", False),
            "three_way_match": po_match.get("three_way_match", False),
            "po_details": po_match.get("po_details"),
            "receipt_details": po_match.get("receipt_details"),
            "reconciliation": po_match.get("reconciliation"),
        },
        "flags": state.get("flags", []),
    }

    paths: list[str] = []
    if bucket:
        key = f"outputs/erp_packet_{invoice.get('invoice_no', session_id or 'unknown')}.json"
        try:
            client = _get_s3_client(settings)
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=_json_dumps_safe(packet, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            paths.append(key)
        except Exception as e:
            packet["_s3_error"] = str(e)

    return {"packet": packet, "output_paths": paths}


def generate_raw_erp_export(state: dict[str, Any], session_id: str = "") -> dict[str, Any]:
    """Build minimal raw data for ERP export download (no metadata, UI copy, or audit)."""
    gl = state.get("gl_coding") or {}
    invoice = state.get("invoice_data") or {}
    po_match = state.get("po_match_results") or {}
    po = po_match.get("po_details") or {}
    receipt = po_match.get("receipt_details") or {}
    recon = po_match.get("reconciliation") or {}

    return {
        "invoice": {
            "vendor_name": invoice.get("vendor_name"),
            "invoice_no": invoice.get("invoice_no"),
            "invoice_date": invoice.get("invoice_date", invoice.get("date")),
            "due_date": invoice.get("due_date"),
            "amount": invoice.get("amount", invoice.get("total")),
            "line_items": invoice.get("line_items", []),
            "currency": invoice.get("currency", "USD"),
        },
        "po_match": {
            "po_id": po.get("po_id"),
            "matched": bool(po_match.get("po_found", False)),
            "two_way_match": po_match.get("two_way_match", False),
            "three_way_match": po_match.get("three_way_match", False),
            "po_amount": recon.get("po_amount") or po.get("amount"),
        },
        "receipt_match": {
            "receipt_id": receipt.get("receipt_id"),
            "received": bool(receipt.get("received", False)),
            "received_date": receipt.get("received_date"),
        },
        "gl_coding": {
            "account_code": gl.get("account_code"),
            "cost_center": gl.get("cost_center"),
            "entity": gl.get("entity"),
            "approval_path": gl.get("approval_path"),
            "next_actions": gl.get("next_actions", []),
            "rationale": gl.get("rationale"),
        },
    }
