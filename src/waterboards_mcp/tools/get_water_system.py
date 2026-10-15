"""Profile of one public water system."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from waterboards_mcp.models import PaginationParams, PwsId
from waterboards_mcp.warehouse import Param, qualified_view, query_gold


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="waterboards_get_water_system",
        annotations={
            "title": "Get a public water system profile",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def get_water_system(pws_id: PwsId) -> dict[str, Any]:
        """Get the profile and compliance/risk summary of one water system.

        Source: Gold view v_water_systems (California State Water Board SDWIS
        inventory + SAFER risk assessment). Refreshed when the pipeline reloads
        the open data; the result carries `data_as_of`.

        The single result has system name, county, city, type, owner, source
        type, population, service connections, last sanitary survey,
        safer_status, is_failing, economic_status (DAC/SDAC), violation
        flags with analytes (primary/secondary MCL, E. coli, treatment
        technique, monitoring), risk levels by category, and `source_url`.
        `has_risk_assessment` is false when the system is not in the SAFER
        file, in which case the violation/risk fields are null (unknown, not
        "none"). This is a regulatory screening, not a tap-water safety
        determination.
        """
        return await query_gold(
            qualified_view("v_water_systems"),
            where="pws_id = :pws_id",
            order_by="pws_id",
            params=[Param("pws_id", pws_id)],
            pagination=PaginationParams(limit=1),
            empty_hint=(
                "No water system with this ID. Use "
                "waterboards_find_water_systems_near_zip to look up IDs."
            ),
        )
