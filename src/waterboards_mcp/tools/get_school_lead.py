"""Lead sampling at schools near a ZIP code."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from waterboards_mcp.models import PaginationParams, RadiusKm, ZipCode
from waterboards_mcp.warehouse import Param, qualified_view, query_gold


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="waterboards_get_school_lead_near_zip",
        annotations={
            "title": "Get school drinking water lead results near a ZIP code",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def get_school_lead_near_zip(
        zip_code: ZipCode,
        radius_km: RadiusKm = 10,
        exceedances_only: bool = False,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """Get lead-in-drinking-water results at K-12 schools near a ZIP code.

        Source: Gold view v_school_lead_near_zip (California State Water Board
        school lead sampling, 2020 onward; the data on file stops at the
        newest `last_observed`, so say so when results are old). Distance is
        between ZIP centroids. Ordered nearest first, then most recent.

        `exceedances_only` returns only samples the state flagged as above the
        lead action level.

        Each result has school_name, district, school_zip, sample_location,
        result_numeric and units (UG/L), reporting_limit, is_non_detect
        (result_numeric is null when true), action_level_exceeded,
        follow_up_action, `last_observed` (sample date), pws_id, and
        `source_url`. These are point-in-time samples, not a health
        determination.
        """
        return await query_gold(
            qualified_view("v_school_lead_near_zip"),
            where=(
                "zip = :zip AND distance_km <= :radius_km "
                "AND (:exceedances_only = 0 OR action_level_exceeded)"
            ),
            order_by="distance_km ASC, last_observed DESC, school_name",
            params=[
                Param("zip", zip_code),
                Param("radius_km", radius_km, "DOUBLE"),
                Param("exceedances_only", int(exceedances_only), "INT"),
            ],
            pagination=pagination,
            empty_hint=(
                "No school lead results for this ZIP code and radius. Try a "
                "nearby ZIP code or a larger radius_km."
            ),
        )
