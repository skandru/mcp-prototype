"""Behavior of the Databricks SQL layer and the tools built on it (no network)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from databricks.sdk.service.sql import StatementState
from fastmcp import Client
from fastmcp.exceptions import ToolError

from waterboards_mcp import warehouse
from waterboards_mcp.app import mcp
from waterboards_mcp.config import Settings


def _response(columns: list[tuple[str, str]], rows: list[list[str | None]]):
    return SimpleNamespace(
        status=SimpleNamespace(state=StatementState.SUCCEEDED),
        manifest=SimpleNamespace(
            schema=SimpleNamespace(
                columns=[
                    SimpleNamespace(name=n, type_name=SimpleNamespace(value=t))
                    for n, t in columns
                ]
            )
        ),
        result=SimpleNamespace(data_array=rows),
    )


class _FakeStatements:
    def __init__(self, response: Any = None, error: Exception | None = None):
        self.response, self.error, self.calls = response, error, []

    def execute_statement(self, **kwargs: Any):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def fake_warehouse(monkeypatch: pytest.MonkeyPatch):
    def install(response: Any = None, error: Exception | None = None):
        statements = _FakeStatements(response, error)
        monkeypatch.setattr(
            warehouse,
            "_get_client",
            lambda: SimpleNamespace(statement_execution=statements),
        )
        monkeypatch.setattr(warehouse.settings, "databricks_sql_warehouse_id", "wh-1")
        return statements

    return install


async def _call(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    async with Client(mcp) as client:
        result = await client.call_tool(tool, args)
    return result.data


async def test_chemistry_binds_params_and_types_rows(fake_warehouse):
    statements = fake_warehouse(
        _response(
            [("well_id", "STRING"), ("result_numeric", "DOUBLE"), ("n", "INT")],
            [["CA0110005_001_001", "120.5", "3"]],
        )
    )

    data = await _call(
        "waterboards_get_source_chemistry_near_zip",
        {"zip_code": "94103", "radius_miles": 5, "chemical": "arsenic"},
    )

    assert data["results"] == [
        {"well_id": "CA0110005_001_001", "result_numeric": 120.5, "n": 3}
    ]
    assert data["has_more"] is False
    call = statements.calls[0]
    assert "94103" not in call["statement"]
    assert {p.name: p.value for p in call["parameters"]} == {
        "zip": "94103",
        "radius_km": "8.04672",
        "chemical": "arsenic",
        "detected_only": "0",
        "_limit": "21",
        "_offset": "0",
    }
    assert call["wait_timeout"] == "30s"


async def test_tap_water_binds_stage_and_filters(fake_warehouse):
    statements = fake_warehouse(_response([("pws_id", "STRING")], [["CA3810011"]]))

    data = await _call(
        "waterboards_get_tap_water_for_zip",
        {"zip_code": "94103", "chemical": "lead", "exceeds_mcl_only": True},
    )

    assert data["count"] == 1
    call = statements.calls[0]
    assert "94103" not in call["statement"]
    assert {p.name: p.value for p in call["parameters"]} == {
        "zip": "94103",
        "stage": "distribution",
        "min_coverage": "10.0",
        "chemical": "lead",
        "detected_only": "1",
        "exceeds_only": "1",
        "_limit": "21",
        "_offset": "0",
    }


async def test_pagination_reports_next_page(fake_warehouse):
    rows = [[str(i)] for i in range(21)]
    fake_warehouse(_response([("siteid", "STRING")], rows))

    data = await _call("waterboards_find_water_systems_near_zip", {"zip_code": "94103"})

    assert data["count"] == 20
    assert data["has_more"] is True
    assert data["next_offset"] == 20


async def test_source_names_public_dataset_not_internal_view(fake_warehouse):
    fake_warehouse(_response([("siteid", "STRING")], [["1"]]))

    data = await _call("waterboards_find_water_systems_near_zip", {"zip_code": "94103"})

    assert "data.ca.gov" in data["source"]
    assert "v_water_systems_near_zip" not in data["source"]
    assert "users" not in data["source"]


async def test_empty_result_returns_actionable_hint(fake_warehouse):
    fake_warehouse(_response([("siteid", "STRING")], []))

    data = await _call("waterboards_get_school_lead_near_zip", {"zip_code": "99999"})

    assert data["results"] == []
    assert "nearby ZIP" in data["hint"]


async def test_get_water_system_validates_id_and_limits_to_one(fake_warehouse):
    statements = fake_warehouse(_response([("pws_id", "STRING")], [["CA0110005"]]))

    data = await _call("waterboards_get_water_system", {"pws_id": "CA0110005"})

    assert data["count"] == 1
    assert {p.name: p.value for p in statements.calls[0]["parameters"]} == {
        "pws_id": "CA0110005",
        "_limit": "2",
        "_offset": "0",
    }
    with pytest.raises(ToolError):
        await _call("waterboards_get_water_system", {"pws_id": "x' OR 1=1"})


async def test_upstream_error_is_sanitized(fake_warehouse):
    fake_warehouse(error=RuntimeError("token=secret-value host=internal"))

    data = await _call("waterboards_list_datasets", {})

    assert data["error"] == "databricks_unavailable"
    assert "secret-value" not in str(data)


async def test_missing_warehouse_is_reported(monkeypatch):
    monkeypatch.setattr(warehouse.settings, "databricks_sql_warehouse_id", "")

    data = await _call("waterboards_list_datasets", {})

    assert data["error"] == "databricks_not_configured"


@pytest.mark.parametrize(
    "args",
    [
        {"zip_code": "94103'; DROP TABLE x;--"},
        {"zip_code": "9410"},
        {"zip_code": "94103", "radius_miles": 500},
        {"zip_code": "94103", "chemical": "x%"},
    ],
)
async def test_invalid_inputs_are_rejected_before_any_query(fake_warehouse, args):
    statements = fake_warehouse(_response([], []))

    with pytest.raises(ToolError):
        await _call("waterboards_get_source_chemistry_near_zip", args)

    assert statements.calls == []


def test_catalog_and_schema_must_be_plain_identifiers():
    with pytest.raises(ValueError):
        Settings(databricks_catalog="waterboards; DROP CATALOG x")
