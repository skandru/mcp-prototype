"""Static context: data provenance and citations."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.resource("waterboards://about")
    def about() -> str:
        """Data provenance, citations, and caveats for this server."""
        return (
            "Waterboards MCP — California drinking water open data served from "
            "curated Databricks Gold views.\n\n"
            "Sources (California Open Data, https://data.ca.gov/):\n"
            "- SDWIS public water system inventory (State Water Board)\n"
            "- SAFER failing/at-risk water system risk assessment\n"
            "- DDW/GAMA drinking water source (well) chemistry, 2020-present\n"
            "- K-12 school lead sampling, 2020 onward\n"
            "- Tap/treated water sample results by ZIP (DDW SDWIS, 2023 onward)\n\n"
            "Caveats:\n"
            "- Results reflect the last pipeline refresh, not live conditions; "
            "each result carries data_as_of or last_observed.\n"
            "- ZIP searches use ZIP centroids; a nearby system may not serve "
            "that ZIP.\n"
            "- Source chemistry is untreated well water, not tap water.\n"
            "- Values are regulatory/monitoring data, not a health "
            "determination; contact the local water utility for health "
            "questions.\n"
            "- Every result includes a source_url for the original record."
        )
