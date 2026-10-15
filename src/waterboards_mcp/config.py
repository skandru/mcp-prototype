"""Server configuration loaded from environment variables or a .env file.

Every field can be overridden by an environment variable of the same name
(upper- or lower-case). Copy `.env.example` to `.env` for local development.
"""

from __future__ import annotations

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP server settings. Override any field via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Transport ─────────────────────────────────────────────────────────────
    # "stdio"           — local subprocess (Claude Desktop / Claude Code / Zed)
    # "streamable-http" — remote HTTP server (containers, cloud deploys)
    #
    # NOTE: app.py also auto-selects HTTP when a platform injects DATABRICKS_APP_PORT
    # or PORT, so you usually do NOT need to set this on a cloud host.
    mcp_transport: str = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000

    # ── Databricks SQL backend ────────────────────────────────────────────────
    # Auth is handled by the Databricks SDK's unified auth: on Databricks Apps
    # it uses the injected DATABRICKS_HOST / CLIENT_ID / CLIENT_SECRET; locally
    # it uses DATABRICKS_HOST + DATABRICKS_TOKEN or a CLI profile
    # (DATABRICKS_CONFIG_PROFILE). Nothing credential-related is read here.
    databricks_sql_warehouse_id: str = ""
    databricks_catalog: str = "waterboards"
    databricks_schema: str = "gold"
    sql_timeout_seconds: int = Field(default=30, ge=5, le=50)

    @field_validator("databricks_catalog", "databricks_schema")
    @classmethod
    def _safe_identifier(cls, value: str) -> str:
        # These are interpolated into SQL, so only allow plain identifiers.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("must be a plain SQL identifier")
        return value


settings = Settings()
