"""Tap-water sample results for the water systems serving a ZIP code."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from waterboards_mcp.models import ChemicalName, PaginationParams, ZipCode
from waterboards_mcp.warehouse import Param, qualified_view, query_gold


class WaterStage(str, Enum):
    DISTRIBUTION = "distribution"
    TREATED = "treated"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="waterboards_get_tap_water_for_zip",
        annotations={
            "title": "Get tap water sample results for a California ZIP code",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def get_tap_water_for_zip(
        zip_code: ZipCode,
        chemical: ChemicalName | None = None,
        stage: WaterStage = WaterStage.DISTRIBUTION,
        detected_only: bool = True,
        exceeds_mcl_only: bool = False,
        min_coverage_pct: Annotated[
            float,
            Field(
                ge=0,
                le=100,
                description="Minimum % of the ZIP a water system must cover.",
            ),
        ] = 10.0,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """Get the latest tap-water test results for a California ZIP code.

        Source: Gold view v_tap_water_for_zip (DDW SDWIS sample results, 2023 to
        present, joined to water-system service-area boundaries). Refreshed when
        the pipeline reloads the open data; each result has `last_observed`.
        Systems are ordered by how much of the ZIP they serve
        (`pct_of_zip_covered`, highest first); a ZIP can be served by several
        systems, so use the largest coverage as the likely supplier.

        `stage` is 'distribution' (samples from the pipes that reach customers,
        the closest to tap water; default) or 'treated' (leaving the treatment
        plant). `chemical` is a case-insensitive name fragment (e.g. 'lead',
        'arsenic', 'pfas', 'nitrate'). `detected_only` (default true) hides
        non-detects; `exceeds_mcl_only` shows only results above the legal
        limit. `min_coverage_pct` (default 10) hides systems covering less of
        the ZIP than that; lower it to 0 to see every overlapping system.

        Each result: zip, pct_of_zip_covered, pws_id, system_name,
        total_population, water_stage, analyte_name, result_numeric, units,
        is_non_detect, reporting_limit, mcl, exceeds_mcl, any_exceeds_mcl,
        max_result_numeric, sample_count, last_observed, sampling_point,
        method, source_url. When is_non_detect is true, result_numeric is null
        and the analyte was below reporting_limit.

        These are system-level samples, not results for an individual address
        or home. A single sample above the MCL is not a violation by itself
        (many limits apply to running averages), and this is not a health
        determination. Units vary by analyte; never compare across units.
        """
        return await query_gold(
            qualified_view("v_tap_water_for_zip"),
            where=(
                "zip = :zip AND water_stage = :stage "
                "AND pct_of_zip_covered >= :min_coverage "
                "AND (:chemical = '' OR lower(analyte_name) "
                "LIKE concat('%', lower(:chemical), '%')) "
                "AND (:detected_only = 0 OR NOT is_non_detect) "
                "AND (:exceeds_only = 0 OR any_exceeds_mcl)"
            ),
            order_by=(
                "pct_of_zip_covered DESC, pws_id, exceeds_mcl DESC, "
                "analyte_name, last_observed DESC"
            ),
            params=[
                Param("zip", zip_code),
                Param("stage", stage.value),
                Param("min_coverage", min_coverage_pct, "DOUBLE"),
                Param("chemical", chemical or ""),
                Param("detected_only", int(detected_only), "INT"),
                Param("exceeds_only", int(exceeds_mcl_only), "INT"),
            ],
            pagination=pagination,
            empty_hint=(
                "No tap-water results for this ZIP code with these filters. "
                "Try stage='treated', detected_only=false, or a shorter "
                "chemical name. ZIPs outside California have no data."
            ),
        )
