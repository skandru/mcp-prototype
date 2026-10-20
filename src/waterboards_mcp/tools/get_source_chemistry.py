"""Source-water (well) chemistry, by ZIP code or by water system."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from waterboards_mcp.models import (
    ChemicalName,
    PaginationParams,
    PwsId,
    KM_PER_MILE,
    RadiusMiles,
    ZipCode,
)
from waterboards_mcp.warehouse import Param, qualified_view, query_gold

_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="waterboards_get_source_chemistry_near_zip",
        annotations={
            "title": "Get drinking water source chemistry near a ZIP code",
            **_ANNOTATIONS,
        },
    )
    async def get_source_chemistry_near_zip(
        zip_code: ZipCode,
        chemical: ChemicalName | None = None,
        radius_miles: RadiusMiles = 10,
        detected_only: bool = False,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """Get latest source-water chemistry for wells near a ZIP code.

        Source: Gold view v_source_chemistry_near_zip (DDW/GAMA drinking water
        source chemistry, 2020 to present). Refreshed when the pipeline reloads
        the open data; each result has `last_observed`. Ordered nearest well
        first, then most recent.

        `chemical` is a case-insensitive name fragment (e.g. 'arsenic',
        'nitrate', 'PFOA'); omit it to see every chemical, which is large. Set
        `detected_only` to skip non-detects.

        Each result is the latest sample for one well and chemical: pws_id,
        system_name, well_id, chemical_name, result_numeric, units,
        reporting_limit, is_non_detect, `last_observed` (sample date),
        sample_count, and `source_url`. When is_non_detect is true,
        result_numeric is null and the chemical was not found above
        reporting_limit. This is raw source water before treatment, not tap
        water, and not a health determination; units vary by chemical (UG/L,
        NG/L, MG/L, ...) so never compare across units.
        """
        return await query_gold(
            qualified_view("v_source_chemistry_near_zip"),
            where=(
                "zip = :zip AND distance_km <= :radius_km "
                "AND (:chemical = '' OR lower(chemical_name) "
                "LIKE concat('%', lower(:chemical), '%')) "
                "AND (:detected_only = 0 OR NOT is_non_detect)"
            ),
            order_by="distance_km ASC, last_observed DESC, well_id, chemical_name",
            params=[
                Param("zip", zip_code),
                Param("radius_km", radius_miles * KM_PER_MILE, "DOUBLE"),
                Param("chemical", chemical or ""),
                Param("detected_only", int(detected_only), "INT"),
            ],
            pagination=pagination,
            empty_hint=(
                "No source chemistry for this ZIP code, radius, and chemical. "
                "Try a larger radius_miles or a shorter chemical name."
            ),
        )

    @mcp.tool(
        name="waterboards_get_system_source_chemistry",
        annotations={
            "title": "Get source chemistry for a water system",
            **_ANNOTATIONS,
        },
    )
    async def get_system_source_chemistry(
        pws_id: PwsId,
        chemical: ChemicalName | None = None,
        detected_only: bool = False,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """Get latest source-water chemistry for one water system's wells.

        Source: Gold view v_source_chemistry_latest (DDW/GAMA drinking water
        source chemistry, 2020 to present). Refreshed when the pipeline reloads
        the open data; each result has `last_observed`. Ordered by chemical,
        then well. Get `pws_id` from waterboards_find_water_systems_near_zip.

        `chemical` is a case-insensitive name fragment; `detected_only` skips
        non-detects.

        Each result is the latest sample for one well and chemical: pws_id,
        system_name, well_id, chemical_name, result_numeric, units,
        reporting_limit, is_non_detect, `last_observed` (sample date),
        sample_count, and `source_url`. When is_non_detect is true,
        result_numeric is null and the chemical was not found above
        reporting_limit. This is raw source water before treatment, not tap
        water, and not a health determination; units vary by chemical (UG/L,
        NG/L, MG/L, ...) so never compare across units.
        """
        return await query_gold(
            qualified_view("v_source_chemistry_latest"),
            where=(
                "pws_id = :pws_id "
                "AND (:chemical = '' OR lower(chemical_name) "
                "LIKE concat('%', lower(:chemical), '%')) "
                "AND (:detected_only = 0 OR NOT is_non_detect)"
            ),
            order_by="chemical_name, well_id",
            params=[
                Param("pws_id", pws_id),
                Param("chemical", chemical or ""),
                Param("detected_only", int(detected_only), "INT"),
            ],
            pagination=pagination,
            empty_hint=(
                "No source chemistry for this system and chemical. Not every "
                "system has wells in the 2020-present dataset."
            ),
        )
