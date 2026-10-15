"""MCP server entry point.

Keep this file THIN. It only:
  1. creates the FastMCP instance,
  2. registers tools / prompts / resources / routes from the submodules, and
  3. decides which transport to run (stdio locally vs. HTTP when deployed).

All real logic lives in the submodules:
  - tools/      one file per tool (each exposes `register(mcp)`)
  - prompts/    reusable conversation starters
  - resources/  static/semi-static data the client can read directly
  - routes.py   HTTP-only infrastructure (health check, etc.)
  - config.py   settings loaded from env vars / .env
  - models.py   Pydantic models & enums for tool parameters
  - warehouse.py  read-only Databricks SQL access to the Gold views
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from waterboards_mcp.config import settings
from waterboards_mcp.prompts import register_prompts
from waterboards_mcp.resources import register_resources
from waterboards_mcp.routes import register_routes
from waterboards_mcp.tools import register_tools

# The server name is what MCP clients display. Rename it to your service.
mcp = FastMCP(
    name="Waterboards MCP Server",
    instructions=(
        "California drinking water open data (State Water Board SDWIS, SAFER "
        "risk assessment, source-water chemistry, school lead sampling) served "
        "from curated Databricks Gold views. Find water systems, source "
        "chemistry, and school lead results by ZIP code or water system ID. "
        "Report only what the tools return, always cite the result's "
        "source_url and its data_as_of/last_observed date, and say so when "
        "no data is found. Values are not a health determination."
    ),
)

# Wire up everything the server exposes. Each aggregator lives in its submodule.
register_tools(mcp)
register_prompts(mcp)
register_resources(mcp)
register_routes(mcp)


def main() -> None:
    """Start the server, choosing a transport based on the environment.

    Precedence:
      1. A platform-injected port (Databricks `DATABRICKS_APP_PORT` or a generic
         `PORT`) → run HTTP on that port. Cloud hosts set this for you.
      2. `MCP_TRANSPORT=streamable-http` in the environment → run HTTP on
         `MCP_HOST`:`MCP_PORT` (see config.py / .env).
      3. Otherwise → stdio, which is how local clients (Claude Desktop, Claude
         Code, Zed) launch the server as a subprocess.
    """
    platform_port = os.getenv("DATABRICKS_APP_PORT") or os.getenv("PORT")

    if platform_port:
        mcp.run(transport="http", host="0.0.0.0", port=int(platform_port))
    elif settings.mcp_transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
