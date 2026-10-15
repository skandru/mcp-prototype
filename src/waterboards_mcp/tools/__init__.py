"""Tools submodule — one tool per file.

Each tool module (e.g. `get_school_lead.py`) exposes a `register(mcp)` function
that attaches its `@mcp.tool`-decorated function to the server. This file
aggregates them into a single `register_tools(mcp)` that `app.py` calls.

To add a tool:
  1. Create `tools/<your_tool>.py` with a `register(mcp)` function.
  2. Import it below and call `<your_tool>.register(mcp)` inside register_tools.
"""

from __future__ import annotations

from waterboards_mcp.tools import (
    find_water_systems,
    get_school_lead,
    get_source_chemistry,
    get_tap_water,
    get_water_system,
    list_datasets,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    list_datasets.register(mcp)
    find_water_systems.register(mcp)
    get_water_system.register(mcp)
    get_source_chemistry.register(mcp)
    get_school_lead.register(mcp)
    get_tap_water.register(mcp)


__all__ = ["register_tools"]
