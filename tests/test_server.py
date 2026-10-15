"""Smoke tests: the server imports and every submodule registers."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from waterboards_mcp.app import mcp
from waterboards_mcp.config import settings

EXPECTED_TOOLS = {
    "waterboards_list_datasets",
    "waterboards_find_water_systems_near_zip",
    "waterboards_get_water_system",
    "waterboards_get_source_chemistry_near_zip",
    "waterboards_get_system_source_chemistry",
    "waterboards_get_school_lead_near_zip",
    "waterboards_get_tap_water_for_zip",
}


def test_default_transport_is_stdio():
    """Guard against accidentally shipping with a non-stdio default."""
    assert settings.mcp_transport == "stdio"


@pytest.mark.parametrize("name", ["tools", "prompts", "resources", "routes"])
def test_submodules_register_without_error(name: str):
    module = __import__(f"waterboards_mcp.{name}", fromlist=["register"])
    getattr(module, f"register_{name}")(FastMCP("test"))


async def test_tools_are_discoverable_and_read_only():
    tools = {t.name: t for t in await mcp.list_tools()}
    assert set(tools) == EXPECTED_TOOLS
    assert all(t.annotations.readOnlyHint for t in tools.values())
