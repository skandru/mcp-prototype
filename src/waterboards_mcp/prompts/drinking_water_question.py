"""Prompt for answering a drinking-water question about a ZIP code."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(name="drinking_water_question")
    def drinking_water_question(zip_code: str, radius_km: float = 10) -> str:
        """Ask what drinking water information exists near a ZIP code."""
        return (
            f"What drinking water information is available within {radius_km} km "
            f"of ZIP code {zip_code}?\n\n"
            "Rules:\n"
            "1. Call waterboards_get_tap_water_for_zip for tap-water results "
            "and waterboards_find_water_systems_near_zip for nearby systems.\n"
            "2. For systems that are flagged, call waterboards_get_water_system "
            "and, if relevant, waterboards_get_system_source_chemistry. You may "
            "also check waterboards_get_school_lead_near_zip.\n"
            "3. If a tool returns no results, say no data was found for that "
            "ZIP code and radius; do not guess.\n"
            "4. Summarize in plain English with system names, SAFER status, "
            "violations, the date (data_as_of or last_observed), and source_url. "
            "Note that a nearby system may not serve that ZIP code.\n"
            "5. Never invent values. These are regulatory and monitoring data, "
            "not a health determination; for health concerns, point to the "
            "local water utility."
        )
