"""Read-only access to the Gold layer through the Databricks SQL Statement API.

This is the only module that talks to Databricks. Tools call `query_gold`,
which:
  - authenticates with the Databricks SDK's unified auth (the Databricks Apps
    service principal when deployed; a CLI profile or token locally),
  - targets only `<catalog>.<schema>.<view>` from operator configuration,
  - binds every caller-supplied value as a named SQL parameter, never by
    string interpolation,
  - returns a pagination envelope, or an `{"error", "hint"}` dict. Upstream
    error bodies are never returned or logged.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import (
    ExecuteStatementRequestOnWaitTimeout,
    StatementParameterListItem,
    StatementState,
)

from waterboards_mcp.config import settings
from waterboards_mcp.models import PaginationParams

logger = logging.getLogger(__name__)

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INTEGER_TYPES = {"BYTE", "SHORT", "INT", "LONG"}
_FLOAT_TYPES = {"FLOAT", "DOUBLE", "DECIMAL"}

_client: WorkspaceClient | None = None


class WarehouseError(RuntimeError):
    """Sanitized failure that is safe to turn into a client-facing hint."""

    def __init__(self, code: str, hint: str) -> None:
        super().__init__(code)
        self.code = code
        self.hint = hint


@dataclass(frozen=True)
class Param:
    """A named SQL parameter; reference it in SQL as `:name`."""

    name: str
    value: str | int | float
    type: str = "STRING"


def qualified_view(view: str) -> str:
    """Return the fully qualified name of a Gold view in the configured schema."""
    if not _IDENTIFIER.fullmatch(view):
        raise ValueError("view must be a plain SQL identifier")
    return f"{settings.databricks_catalog}.{settings.databricks_schema}.{view}"


def _get_client() -> WorkspaceClient:
    global _client
    if _client is None:
        _client = WorkspaceClient()
    return _client


def _cast(value: str | None, type_name: str) -> Any:
    if value is None:
        return None
    if type_name in _INTEGER_TYPES:
        return int(value)
    if type_name in _FLOAT_TYPES:
        return float(value)
    if type_name == "BOOLEAN":
        return value.lower() == "true"
    return value


def _execute(statement: str, params: list[Param]) -> list[dict[str, Any]]:
    """Run one statement synchronously and return rows as dicts."""
    if not settings.databricks_sql_warehouse_id:
        raise WarehouseError(
            "databricks_not_configured",
            "Set DATABRICKS_SQL_WAREHOUSE_ID (and Databricks credentials) for "
            "the server.",
        )
    try:
        response = _get_client().statement_execution.execute_statement(
            statement=statement,
            warehouse_id=settings.databricks_sql_warehouse_id,
            catalog=settings.databricks_catalog,
            schema=settings.databricks_schema,
            parameters=[
                StatementParameterListItem(name=p.name, value=str(p.value), type=p.type)
                for p in params
            ],
            wait_timeout=f"{settings.sql_timeout_seconds}s",
            on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CANCEL,
        )
    except Exception as exc:  # SDK raises many types; log the class only
        logger.warning("Databricks SQL request failed: %s", type(exc).__name__)
        raise WarehouseError(
            "databricks_unavailable",
            "The Databricks SQL request failed. Check the workspace host, "
            "credentials, SQL warehouse, and Unity Catalog permissions.",
        ) from None

    state = response.status.state if response.status else None
    if state is not StatementState.SUCCEEDED:
        logger.warning("Databricks SQL statement ended in state %s", state)
        raise WarehouseError(
            "databricks_query_failed",
            "The query did not complete. The SQL warehouse may be starting or "
            "the query timed out; try again or use a smaller radius/limit.",
        )

    columns = response.manifest.schema.columns if response.manifest else None
    if not columns:
        return []
    names = [c.name for c in columns]
    types = [c.type_name.value if c.type_name else "STRING" for c in columns]
    data = response.result.data_array if response.result else None
    return [
        {n: _cast(v, t) for n, t, v in zip(names, types, row, strict=False)}
        for row in data or []
    ]


_DATA_CA_GOV = "California State Water Board open data (data.ca.gov)"
_SOURCES = {
    "v_water_systems": f"{_DATA_CA_GOV}: Drinking Water Public Water Systems (SDWIS)",
    "v_water_systems_near_zip": (
        f"{_DATA_CA_GOV}: Drinking Water Public Water Systems (SDWIS), "
        "SAFER risk assessment; ZIP locations from US Census ZCTA Gazetteer"
    ),
    "v_school_lead_near_zip": (
        f"{_DATA_CA_GOV}: Lead Sampling in California Schools; "
        "ZIP locations from US Census ZCTA Gazetteer"
    ),
    "v_source_chemistry_near_zip": (
        f"{_DATA_CA_GOV}: DDW Drinking Water Source Chemistry (GAMA); "
        "ZIP locations from US Census ZCTA Gazetteer"
    ),
    "v_source_chemistry_latest": (
        f"{_DATA_CA_GOV}: DDW Drinking Water Source Chemistry (GAMA)"
    ),
    "v_tap_water_for_zip": (
        "California State Water Board DDW SDWIS water quality monitoring results; "
        "ZIP-to-system mapping from ZIP and water-system service-area boundaries"
    ),
}


def _source_label(relation: str) -> str:
    """Describe the public dataset behind a relation, not the internal view."""
    name = relation.rsplit(".", 1)[-1]
    if name == "tables" and relation.endswith("information_schema.tables"):
        return "Server catalog of available datasets"
    return _SOURCES.get(name, _DATA_CA_GOV)


async def query_gold(
    relation: str,
    *,
    columns: str = "*",
    where: str = "",
    order_by: str = "",
    params: list[Param] | None = None,
    pagination: PaginationParams | None = None,
    empty_hint: str = "No matching records were found.",
) -> dict[str, Any]:
    """Query a relation and return a pagination envelope (or an error dict).

    `relation` comes from `qualified_view()`. `columns`, `where` and `order_by`
    must be static SQL written in the tool; pass user values only through
    `params` and reference them as `:name`.
    """
    pagination = pagination or PaginationParams()
    sql = f"SELECT {columns} FROM {relation}"
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    sql += " LIMIT :_limit OFFSET :_offset"

    # Fetch one extra row to learn whether another page exists.
    bound = [
        *(params or []),
        Param("_limit", pagination.limit + 1, "INT"),
        Param("_offset", pagination.offset, "INT"),
    ]
    try:
        rows = await asyncio.to_thread(_execute, sql, bound)
    except WarehouseError as exc:
        return {"error": exc.code, "hint": exc.hint}

    has_more = len(rows) > pagination.limit
    page = rows[: pagination.limit]
    envelope: dict[str, Any] = {
        "results": page,
        "count": len(page),
        "offset": pagination.offset,
        "has_more": has_more,
        "next_offset": pagination.offset + len(page) if has_more else None,
        "source": _source_label(relation),
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not page and pagination.offset == 0:
        envelope["hint"] = empty_hint
    return envelope
