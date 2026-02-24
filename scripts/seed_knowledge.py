#!/usr/bin/env python3
"""
Seed the knowledge DynamoDB table with the demo weather record (Chicago polar vortex).
Run after first Terraform apply. Table name from env DYNAMODB_KNOWLEDGE_TABLE or --table.
"""
import argparse
import os
from datetime import datetime, timezone

try:
    import boto3
except ImportError:
    print("Install boto3: pip install boto3")
    raise

# Campy, scary Chicago polar vortex weather record for the agent to recall
POLAR_VORTEX_RECORD = {
    "id": "polar-vortex-chicago",
    "title": "THE POLAR VORTEX COMETH — Chicago Weather Alert",
    "content": (
        "⚠️ DARKNESS DESCENDS UPON THE WINDY CITY ⚠️\n\n"
        "The POLAR VORTEX has descended upon Chicago like an icy fist from the void! "
        "Temperatures have plunged to -23°F (-31°C) — cold enough to freeze your words before they leave your mouth. "
        "The National Weather Service has issued a LIFE-THREATENING COLD WARNING. "
        "Exposed skin freezes in MINUTES. Streets have become rivers of black ice. "
        "The lake effect snow swirls in the streetlights like something from a horror movie. "
        "They say the vortex will linger for days. Days! "
        "Stay indoors. Wrap yourself in blankets. And whatever you do — DO NOT anger the vortex. "
        "It is watching. It is patient. And it is VERY, VERY COLD.\n\n"
        "— Your friendly (and terrified) weather service."
    ),
    "updated_at": datetime.now(tz=timezone.utc).isoformat(),
}


def main():
    parser = argparse.ArgumentParser(description="Seed knowledge table with demo weather record")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_KNOWLEDGE_TABLE"), help="DynamoDB table name")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"), help="AWS region")
    args = parser.parse_args()
    if not args.table:
        print("Error: Set DYNAMODB_KNOWLEDGE_TABLE or pass --table")
        return 1

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(args.table)
    table.put_item(Item=POLAR_VORTEX_RECORD)
    print(f"Inserted record id={POLAR_VORTEX_RECORD['id']} into {args.table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
