"""Public water systems near a ZIP code."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from waterboards_mcp.models import PaginationParams, RadiusKm, ZipCode
from waterboards_mcp.warehouse import Param, qualified_view, query_gold


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="waterboards_find_water_systems_near_zip",
        annotations={
            "title": "Find public water systems near a ZIP code",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def find_water_systems_near_zip(
        zip_code: ZipCode,
        radius_km: RadiusKm = 10,
        flagged_only: bool = False,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """Find drinking water systems serving the area near a ZIP code.

        Source: Gold view v_water_systems_near_zip (California State Water
        Board SDWIS inventory + SAFER risk assessment). Refreshed when the
        pipeline reloads the open data; each result has `data_as_of`. Only
        systems with coordinates in the SAFER assessment can be located.
        Distance is from the ZIP centroid to the system's location, so a
        nearby system does not necessarily serve that ZIP. Ordered nearest
        first.

        Set `flagged_only` to return only systems that are Failing, At-Risk,
        or have an MCL, E. coli, or treatment-technique violation.

        Each result has pws_id, system_name, county, city, federal_type,
        total_population, distance_km, safer_status, is_failing,
        violation flags/analytes, risk levels, and `source_url`. Use
        `pws_id` with waterboards_get_water_system for the full profile. SAFER
        status is a regulatory screening, not a tap-water safety determination.
        """
        return await query_gold(
            qualified_view("v_water_systems_near_zip"),
            where=(
                "zip = :zip AND distance_km <= :radius_km AND "
                "(:flagged_only = 0 OR is_failing "
                "OR safer_status IN ('Failing', 'At-Risk') "
                "OR has_primary_mcl_violation OR has_ecoli_violation "
                "OR has_treatment_technique_violation)"
            ),
            order_by="distance_km ASC, pws_id ASC",
            params=[
                Param("zip", zip_code),
                Param("radius_km", radius_km, "DOUBLE"),
                Param("flagged_only", int(flagged_only), "INT"),
            ],
            pagination=pagination,
            empty_hint=(
                "No located water systems for this ZIP code and radius. Try a "
                "nearby ZIP code or a larger radius_km, or turn off flagged_only."
            ),
        )
