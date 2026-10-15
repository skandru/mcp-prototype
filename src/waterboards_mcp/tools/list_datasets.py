"""List the Gold views exposed by this server."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from waterboards_mcp.config import settings
from waterboards_mcp.models import PaginationParams
from waterboards_mcp.warehouse import Param, query_gold


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="waterboards_list_datasets",
        annotations={
            "title": "List waterboard datasets",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def list_datasets(
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """List the water datasets (Gold views) available through this server.

        Source: Unity Catalog information_schema for the configured Gold schema.
        Refresh cadence: reflects the current catalog; underlying data refresh
        varies by dataset (see each view's comment).

        Returns a pagination envelope; each result has `table_name` and
        `table_comment`.
        """
        return await query_gold(
            f"{settings.databricks_catalog}.information_schema.tables",
            columns="table_name, table_comment",
            where="table_schema = :schema",
            order_by="table_name",
            params=[Param("schema", settings.databricks_schema)],
            pagination=pagination,
            empty_hint="No datasets are visible to the server's service principal.",
        )
