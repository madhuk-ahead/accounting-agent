#!/usr/bin/env python3
"""
Seed DynamoDB tables and S3 bucket for AP Invoice Triage + Coding Copilot demo.

Tables (Terraform): vendor_master, po_ledger, receipts, invoice_status
Env vars: DYNAMODB_VENDORS_TABLE (=vendor_master), DYNAMODB_POS_TABLE (=po_ledger),
         DYNAMODB_RECEIPTS_TABLE (=receipts), DYNAMODB_INVOICE_STATUS_TABLE, S3_AP_BUCKET

After terraform apply:
  export S3_AP_BUCKET=$(terraform -chdir=infra output -raw s3_ap_bucket)
  export DYNAMODB_VENDORS_TABLE=$(terraform -chdir=infra output -raw dynamodb_vendor_master_table)
  export DYNAMODB_POS_TABLE=$(terraform -chdir=infra output -raw dynamodb_po_ledger_table)
  export DYNAMODB_RECEIPTS_TABLE=$(terraform -chdir=infra output -raw dynamodb_receipts_table)
  export DYNAMODB_INVOICE_STATUS_TABLE=$(terraform -chdir=infra output -raw dynamodb_invoice_status_table)
  python scripts/seed_ap_invoice.py
"""
import argparse
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Install boto3: pip install boto3")
    raise

# ---------------------------------------------------------------------------
# DynamoDB: Vendors (default GL codes, payment terms)
# ---------------------------------------------------------------------------
# vendor_master: remit-to, payment terms, tax IDs, default GL/cost center
VENDORS_ITEMS = [
    {
        "id": "vendor:acme",
        "name": "Acme IT Services",
        "default_gl_code": "6105",
        "default_cost_center": "IT-100",
        "entity": "Corp",
        "payment_terms": "Net 30",
        "remit_to": "123 Commerce St, San Francisco, CA 94105",
        "tax_id": "94-1234567",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "vendor:techsupply",
        "name": "TechSupply Inc.",
        "default_gl_code": "6105",
        "default_cost_center": "IT-100",
        "entity": "Corp",
        "payment_terms": "Net 30",
        "remit_to": "456 Tech Ave, San Francisco, CA 94102",
        "tax_id": "94-7654321",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "vendor:brightmarketing",
        "name": "BrightMarketing Corp",
        "default_gl_code": "6200",
        "default_cost_center": "MKT-300",
        "entity": "Corp",
        "payment_terms": "Net 15",
        "remit_to": "789 Marketing Way, San Jose, CA 95110",
        "tax_id": "94-1112233",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
]

# ---------------------------------------------------------------------------
# DynamoDB: PurchaseOrders (3-way match)
# ---------------------------------------------------------------------------
# po_ledger: PO number, vendor, line items, amounts, cost center
# DynamoDB requires Decimal, not float
PO_ITEMS = [
    {
        "po_id": "PO-5001",
        "vendor_id": "vendor:techsupply",
        "amount": Decimal("4500.0"),
        "cost_center": "IT-100",
        "line_items": [
            {"description": "IT Equipment (Laptops)", "amount": Decimal("3200.0")},
            {"description": "Software License (Annual)", "amount": Decimal("1300.0")},
        ],
        "status": "approved",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "po_id": "PO-5002",
        "vendor_id": "vendor:techsupply",
        "amount": Decimal("2800.0"),
        "cost_center": "IT-100",
        "line_items": [
            {"description": "Cloud Services (Annual)", "amount": Decimal("2800.0")},
        ],
        "status": "approved",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "po_id": "PO-5003",
        "vendor_id": "vendor:acme",
        "amount": Decimal("4500.0"),
        "cost_center": "IT-100",
        "line_items": [
            {"description": "IT Equipment (Laptops)", "amount": Decimal("3200.0")},
            {"description": "Software License (Annual)", "amount": Decimal("1300.0")},
        ],
        "status": "approved",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
]

# ---------------------------------------------------------------------------
# DynamoDB: Receipts (goods/services received)
# ---------------------------------------------------------------------------
RECEIPTS_ITEMS = [
    {
        "po_id": "PO-5001",
        "receipt_id": "REC-001",
        "received": True,
        "received_date": "2026-02-25",
        "received_quantity": 1,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "po_id": "PO-5002",
        "receipt_id": "REC-002",
        "received": True,
        "received_date": "2026-02-20",
        "received_quantity": 1,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "po_id": "PO-5003",
        "receipt_id": "REC-003",
        "received": True,
        "received_date": "2026-02-26",
        "received_quantity": 1,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
]

# ---------------------------------------------------------------------------
# DynamoDB: InvoiceStatus (duplicate check) – empty for demo (no duplicates)
# ---------------------------------------------------------------------------
# InvoiceStatus is queried for duplicates; seeding with nothing = no duplicates.
INVOICE_STATUS_ITEMS = []

# ---------------------------------------------------------------------------
# S3: invoices/ prefix – toy dataset (text versions for demo)
# PDFs: invoice_clean_acme_it_services.pdf, invoice_missing_po_brightmarketing.pdf, etc.
# ---------------------------------------------------------------------------
S3_INVOICES = {
    "invoices/invoice_clean_acme_it_services.txt": """Invoice #INV-2026-001
Vendor: Acme IT Services (vendor:acme)
Date: 2026-02-28
Due Date: 2026-03-30
PO Reference: PO-5003
Line Items:
  - IT Equipment (Laptops): $3,200
  - Software License (Annual): $1,300
Subtotal: $4,500.00
Tax: $360.00
Total: $4,860.00 USD
Terms: Net 30

Remit to:
Acme IT Services
123 Commerce St
San Francisco, CA 94105
""",
    "invoices/invoice_missing_po_brightmarketing.txt": """Invoice #INV-BM-002
Vendor: BrightMarketing Corp (vendor:brightmarketing)
Date: 2026-02-25
Total: $2,400.00 USD
Terms: Net 15
Note: No PO reference provided.
""",
    "invoices/INV-2026-001.txt": """Invoice #INV-2026-001
Vendor: TechSupply Inc. (vendor:techsupply)
Date: 2026-02-28
PO Reference: PO-5001
Amount: $4,500.00 USD
Line Items:
  - IT Equipment (Laptops): $3,200
  - Software License (Annual): $1,300
Total: $4,500.00
Terms: Net 30
""",
}

# ---------------------------------------------------------------------------
# S3: policies/ prefix – AP policy docs
# - AP policy overview (match rules, mandatory fields, payment terms)
# - Approval threshold matrix (by spend/category)
# - Exception handling SOP
# ---------------------------------------------------------------------------
S3_POLICIES = {
    "policies/ap_policy_overview.md": """# AP Policy Overview

## Match Rules
- All invoices require 2-way match (Invoice vs PO) before payment
- 3-way match (Invoice + PO + Receipt) required for inventory/merchandise
- Amount match: invoice subtotal vs PO amount (within 0.01 tolerance)

## Mandatory Fields
- Vendor name, invoice number, date, amount, currency
- PO reference (when applicable)
- Line items with description and amount

## Payment Terms
- Net 30: default for IT and office supplies
- Net 15: marketing and advertising
- Pre-payment: prohibited without VP approval
""",
    "policies/approval_threshold_matrix.md": """# Approval Threshold Matrix

| Spend (USD) | Category       | Approval Path     |
|-------------|----------------|-------------------|
| ≤ $5,000    | IT, Office     | Auto-approve      |
| $5,001–$10K | Any            | Manager approval  |
| > $10,000   | Any            | VP approval       |

By category:
- IT (GL 6105): under $5k auto-code
- Marketing (GL 6200): under $5k auto-code
- Capital: all require VP approval
""",
    "policies/exception_handling_sop.md": """# Exception Handling SOP

## PO Missing
- Route to AP supervisor for PO creation or exception approval
- Do not pay without documented approval

## Price Mismatch
- Hold invoice; notify requester and vendor
- Require PO amendment or credit memo before payment

## Duplicate Invoice
- Block payment; flag for AP review
- Contact vendor if genuine duplicate

## Bank Change
- Require updated W-9 and direct deposit form
- Confirm with vendor by phone before updating
""",
    "policies/gl_coding_policy.md": """# GL Coding Policy

## Policy 4.1 – IT Spend Under $5k
IT equipment and software under $5,000 → GL 6105, cost center IT-100.

## Policy 4.2 – Pre-approved Vendors
TechSupply: GL 6105. Acme IT: GL 6105. BrightMarketing: GL 6200.

## Policy 4.3 – Approval Thresholds
Under $5k: Auto-approve. $5k–$10k: Manager. Over $10k: VP.

## Policy 4.4 – 3-Way Match
Exceptions route to handle_exceptions for manual review.
""",
}


def seed_table(table_name: str, items: list[dict], key_attrs: list[str], region: str) -> int:
    """Put items into DynamoDB table. key_attrs: e.g. ['id'] or ['po_id']."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)
    for item in items:
        table.put_item(Item=item)
        pk = "/".join(str(item.get(k, "")) for k in key_attrs)
        print(f"  Put {table_name} {pk}")
    return len(items)


def seed_s3(bucket: str, prefix_content: dict[str, str], region: str) -> int:
    """Upload objects to S3 under given prefix."""
    client = boto3.client("s3", region_name=region)
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            print(f"  S3 bucket {bucket} does not exist. Run: cd infra && terraform apply")
        else:
            print(f"  S3 error: {e}")
        return 0

    count = 0
    for key, content in prefix_content.items():
        ct = "text/plain"
        if key.endswith(".md"):
            ct = "text/markdown"
        elif key.endswith(".json"):
            ct = "application/json"
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType=ct,
        )
        print(f"  Put s3://{bucket}/{key}")
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Seed AP Invoice Triage DynamoDB and S3")
    parser.add_argument("--vendors-table", default=os.environ.get("DYNAMODB_VENDORS_TABLE"))
    parser.add_argument("--pos-table", default=os.environ.get("DYNAMODB_POS_TABLE"))
    parser.add_argument("--receipts-table", default=os.environ.get("DYNAMODB_RECEIPTS_TABLE"))
    parser.add_argument("--invoice-status-table", default=os.environ.get("DYNAMODB_INVOICE_STATUS_TABLE"))
    parser.add_argument("--bucket", default=os.environ.get("S3_AP_BUCKET"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()

    # Check if any targets configured
    has_targets = any([
        args.vendors_table, args.pos_table, args.receipts_table,
        args.invoice_status_table and INVOICE_STATUS_ITEMS,
        args.bucket,
    ])
    if not has_targets:
        print("No tables or bucket configured. Set env vars or pass args:")
        print("  After terraform apply:")
        print("  export S3_AP_BUCKET=$(terraform -chdir=infra output -raw s3_ap_bucket)")
        print("  export DYNAMODB_VENDORS_TABLE=$(terraform -chdir=infra output -raw dynamodb_vendor_master_table)")
        print("  export DYNAMODB_POS_TABLE=$(terraform -chdir=infra output -raw dynamodb_po_ledger_table)")
        print("  export DYNAMODB_RECEIPTS_TABLE=$(terraform -chdir=infra output -raw dynamodb_receipts_table)")
        print("  export DYNAMODB_INVOICE_STATUS_TABLE=$(terraform -chdir=infra output -raw dynamodb_invoice_status_table)")
        print("  python scripts/seed_ap_invoice.py")
        return 1

    count = 0
    region = args.region

    if args.vendors_table:
        print(f"Seeding Vendors: {args.vendors_table}")
        count += seed_table(args.vendors_table, VENDORS_ITEMS, ["id"], region)

    if args.pos_table:
        print(f"\nSeeding PurchaseOrders: {args.pos_table}")
        count += seed_table(args.pos_table, PO_ITEMS, ["po_id"], region)

    if args.receipts_table:
        print(f"\nSeeding Receipts: {args.receipts_table}")
        count += seed_table(args.receipts_table, RECEIPTS_ITEMS, ["po_id", "receipt_id"], region)

    if args.invoice_status_table and INVOICE_STATUS_ITEMS:
        print(f"\nSeeding InvoiceStatus: {args.invoice_status_table}")
        count += seed_table(args.invoice_status_table, INVOICE_STATUS_ITEMS, ["vendor_id", "invoice_no"], region)

    if args.bucket:
        print(f"\nSeeding S3 bucket: {args.bucket}")
        count += seed_s3(args.bucket, {**S3_INVOICES, **S3_POLICIES}, region)

    print(f"\nDone. Seeded {count} items total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
