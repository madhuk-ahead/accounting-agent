"""Settings from environment (used by Lambda and app)."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import List


class Settings:
    """Application settings from environment."""

    def __init__(
        self,
        *,
        openai_api_key: str | None = None,
        openai_model: str = "gpt-4o",
        aws_region: str = "us-east-1",
        dynamodb_sessions_table: str = "",
        dynamodb_knowledge_table: str = "",
        orchestrator_type: str = "press_release",
        s3_press_kit_bucket: str = "",
    ):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", openai_model)
        self.aws_region = os.getenv("AWS_REGION", aws_region)
        self.dynamodb_sessions_table = dynamodb_sessions_table or os.getenv("DYNAMODB_SESSIONS_TABLE", "")
        self.dynamodb_knowledge_table = dynamodb_knowledge_table or os.getenv("DYNAMODB_KNOWLEDGE_TABLE", "")
        self.orchestrator_type = os.getenv("ORCHESTRATOR_TYPE", orchestrator_type or "press_release").lower()
        self.s3_press_kit_bucket = os.getenv("S3_PRESS_KIT_BUCKET", "")
        self.cors_allow_origins: List[str] = ["*"]
        # Paths for frontend (app)
        project_root = Path(__file__).resolve().parent.parent
        self.templates_dir = project_root / "frontend" / "templates"
        self.static_dir = project_root / "frontend" / "static"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
