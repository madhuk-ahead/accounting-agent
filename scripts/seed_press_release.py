#!/usr/bin/env python3
"""
Seed DynamoDB knowledge table and S3 press-kit bucket with spoofed press release assets.
Run after Terraform apply. Uses DYNAMODB_KNOWLEDGE_TABLE, S3_PRESS_KIT_BUCKET, AWS_REGION from env.
"""
import argparse
import json
import os
from datetime import datetime, timezone

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Install boto3: pip install boto3")
    raise

# --- DynamoDB knowledge items ---
KNOWLEDGE_ITEMS = [
    {
        "id": "company:acme",
        "boilerplate": (
            "Acme Corp is a leading provider of enterprise software solutions, "
            "helping businesses worldwide streamline operations and accelerate growth. "
            "Founded in 2018, Acme serves over 2,000 customers across 45 countries. "
            "For more information, visit www.acmecorp.com."
        ),
        "description": "Acme Corp delivers cloud-native platforms that empower teams to work smarter.",
        "media_contact": "Sarah Chen, Director of Communications, pr@acmecorp.com, (555) 123-4567",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "product:skyline-2",
        "facts": (
            "Skyline 2 is the next-generation analytics platform with real-time dashboards, "
            "AI-powered insights, and seamless integration with 200+ data sources. "
            "Key features: sub-second query performance, no-code report builder, "
            "row-level security, and multi-cloud deployment options."
        ),
        "differentiators": (
            "10x faster than legacy tools; 90% reduction in time-to-insight; "
            "built-in governance and audit trails; SOC 2 Type II certified."
        ),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "product:securevault-ai",
        "facts": (
            "SecureVault AI is an encrypted storage system with real-time AI threat detection, "
            "edge computing performance, and HIPAA compliance. Key features: automated threat response, "
            "zero-trust architecture, end-to-end encryption, and audit trails for healthcare data."
        ),
        "differentiators": (
            "Real-time AI threat detection; HIPAA-compliant by design; edge-first for low latency; "
            "Built for healthcare CTOs and Data Security Officers."
        ),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "quote:ceo",
        "quote": "SecureVault AI represents a major milestone in our mission to bring enterprise-grade security to healthcare. We're giving CTOs and Data Security Officers the tools they need to protect patient data while meeting HIPAA requirements.",
        "attribution": "Jane Doe, CEO, Acme Corp",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "quote:cmo",
        "quote": "Skyline 2 transforms how marketing teams understand customer behavior and optimize campaigns in real time.",
        "attribution": "Alex Rivera, CMO, Acme Corp",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "partner:globex",
        "blurb": (
            "Globex Industries is a Fortune 500 logistics and supply chain leader "
            "with operations in North America, Europe, and Asia Pacific. "
            "The company manages over $15B in annual shipments."
        ),
        "facts": "Partnership announced Q1 2026; joint solution available in H1 2026; pilot customers include three Fortune 100 retailers.",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
    {
        "id": "metrics:q1-2026",
        "metrics": json.dumps({
            "arr_growth": "85% YoY",
            "customer_count": "2,100+",
            "nps": "72",
            "q1_revenue": "$45M",
        }),
        "content": "ARR growth 85% YoY; 2,100+ customers; NPS 72; Q1 revenue $45M.",
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    },
]

# --- S3 press-kit documents ---
S3_DOCS = {
    "docs/press-kit/company_overview.md": """# Acme Corp – Company Overview

## Mission
Acme Corp empowers enterprises to make data-driven decisions with confidence. Our cloud-native platform delivers real-time analytics, AI-powered insights, and seamless integrations.

## Key Facts
- Founded: 2018
- Headquarters: San Francisco, CA
- Customers: 2,000+
- Countries: 45
- Employees: 450+

## Product Suite
- **Skyline** – Enterprise analytics platform
- **Skyline 2** – Next-generation analytics (launched Q4 2025)
- **Acme Connect** – Integration hub

## Awards
- Gartner Magic Quadrant Leader (2024)
- Inc. 5000 Fastest-Growing Companies (2023, 2024)
""",
    "docs/press-kit/product_one_pager.md": """# Skyline 2 – Product One Pager

## Overview
Skyline 2 is the next-generation analytics platform built for modern data teams. Delivering sub-second queries, no-code report building, and AI-assisted insights.

## Key Features
- Real-time dashboards with <1s refresh
- 200+ data source connectors
- Row-level security & audit trails
- Multi-cloud (AWS, Azure, GCP)
- SOC 2 Type II certified

## Metrics
- 10x faster than legacy tools
- 90% reduction in time-to-insight
- 50% lower total cost of ownership

## Launch
Generally available: November 2025
""",
    "docs/press-kit/partner_blurb.md": """# Globex Industries – Partner Blurb

Globex Industries is a Fortune 500 leader in logistics and supply chain management. With operations across North America, Europe, and Asia Pacific, Globex manages over $15 billion in annual shipments for retail, manufacturing, and e-commerce customers.

The Acme–Globex partnership combines Acme's analytics platform with Globex's supply chain data to deliver end-to-end visibility and predictive logistics insights.
""",
    "docs/press-kit/metrics_summary.json": """{
  "q1_2026": {
    "arr_growth_yoy": "85%",
    "customer_count": 2100,
    "nps": 72,
    "revenue_m": 45
  },
  "fy2025": {
    "revenue_m": 142,
    "employee_count": 450
  }
}
""",
}


def seed_dynamodb(table_name: str, region: str) -> int:
    """Seed DynamoDB knowledge table. Returns count of items written."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)
    for item in KNOWLEDGE_ITEMS:
        table.put_item(Item=item)
        print(f"  Put {item['id']}")
    return len(KNOWLEDGE_ITEMS)


def seed_s3(bucket: str, region: str) -> int:
    """Seed S3 press-kit documents. Returns count of objects written."""
    client = boto3.client("s3", region_name=region)
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            print(f"  S3 bucket {bucket} does not exist. Run: cd infra && terraform apply")
        else:
            print(f"  S3 error: {e}")
        return 0
    except Exception as e:
        print(f"  S3 error: {e}")
        return 0

    for key, content in S3_DOCS.items():
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/markdown" if key.endswith(".md") else "application/json",
        )
        print(f"  Put s3://{bucket}/{key}")
    return len(S3_DOCS)


def main():
    parser = argparse.ArgumentParser(description="Seed DynamoDB and S3 with press release assets")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_KNOWLEDGE_TABLE"), help="DynamoDB knowledge table")
    parser.add_argument("--bucket", default=os.environ.get("S3_PRESS_KIT_BUCKET"), help="S3 press-kit bucket")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"), help="AWS region")
    args = parser.parse_args()

    count = 0
    if args.table:
        print(f"Seeding DynamoDB table: {args.table}")
        count += seed_dynamodb(args.table, args.region)
    else:
        print("Skipping DynamoDB: DYNAMODB_KNOWLEDGE_TABLE not set")

    if args.bucket:
        print(f"\nSeeding S3 bucket: {args.bucket}")
        count += seed_s3(args.bucket, args.region)
    else:
        print("\nSkipping S3: S3_PRESS_KIT_BUCKET not set (run terraform apply first)")

    print(f"\nDone. Seeded {count} items total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
