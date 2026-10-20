# Waterboards MCP Server

An [MCP](https://modelcontextprotocol.io) server that answers California **drinking water** questions — public water systems and their SAFER risk/violation status, source-water chemistry, and school lead results, by ZIP code or water system ID — from curated **Databricks Gold views** over State Water Board open data (data.ca.gov). Built with [FastMCP](https://github.com/jlowin/fastmcp) and [uv](https://docs.astral.sh/uv/); deployed as a **Databricks App**.

Design decisions and the review of the original plan: [req/mcp_design_review.md](req/mcp_design_review.md) (local, git-ignored).

## Architecture

```
data.ca.gov drinking water files (+ Census ZCTA centroids)
   └─ sql/drinking_water/  Bronze → Silver → Gold   (run in a Databricks SQL warehouse)
        └─ users.suresh_kandru.v_* views  (the contract in this README)
             └─ Databricks SQL warehouse
                  └─ this server (FastMCP, Databricks Apps, /mcp over HTTP)
                       └─ MCP client / agent
```

The server is read-only and queries **only** `<catalog>.<schema>.v_*` Gold views (plus `information_schema` for dataset discovery). Every caller-supplied value is bound as a named SQL parameter.

## Data pipeline

`scripts/download_drinking_water_data.py` downloads the source files. Upload them (plus the Census ZCTA gazetteer as `zcta_centroids.txt`) to `/Volumes/users/suresh_kandru/raw/drinking_water/current/`, then run in order:

| Script | Layer | Output |
|---|---|---|
| `sql/drinking_water/00_setup.sql` | setup | volume, `silver_clean_str` helper |
| `sql/drinking_water/01_bronze.sql` | Bronze | raw all-string tables `bronze_dw_*`, `bronze_zcta_centroids` |
| `sql/drinking_water/02_silver.sql` | Silver | typed `dw_systems`, `dw_safer`, `dw_lead_schools`, `dw_source_chemistry(_latest)`, `dw_wells`, and 50 km ZIP pair tables |
| `sql/drinking_water/03_gold.sql` | Gold | the `v_*` views below |
| `sql/drinking_water/04_tap_water.sql` | Bronze/Silver/Gold | DDW SDWIS tap-water results and ZIP-to-service-area lookup → `v_tap_water_for_zip`. Inputs `tap_water_results.csv.gz` and `zip_service_areas.csv` are built by `scripts/build_tap_water_results.py` and `scripts/build_zip_service_areas.py` |

Silver turns `NULL`/`NaN`/`N/A` into SQL NULL, parses dates, keeps non-detects explicit (`is_non_detect`, `result_numeric` NULL, `reporting_limit`), and drops street addresses. Systems are located by SAFER coordinates, wells by their own coordinates, and schools by the ZIP parsed from their address.

## Tools

| Tool | Gold view | Purpose |
|---|---|---|
| `waterboards_list_datasets` | `information_schema.tables` | What datasets are available |
| `waterboards_find_water_systems_near_zip` | `v_water_systems_near_zip` | Water systems near a ZIP, optionally only failing/at-risk/violating |
| `waterboards_get_water_system` | `v_water_systems` | Profile, SAFER status, violations for one `pws_id` |
| `waterboards_get_source_chemistry_near_zip` | `v_source_chemistry_near_zip` | Latest well chemistry near a ZIP, filter by chemical |
| `waterboards_get_system_source_chemistry` | `v_source_chemistry_latest` | Latest well chemistry for one `pws_id` |
| `waterboards_get_school_lead_near_zip` | `v_school_lead_near_zip` | School lead sampling near a ZIP |
| `waterboards_get_tap_water_for_zip` | `v_tap_water_for_zip` | Latest tap/treated-water sample results for the systems serving a ZIP |

All return `{results, count, offset, has_more, next_offset, source, retrieved_at}`, or `{error, hint}`. Empty results include an actionable `hint`.

### Gold view contract

The views must exist with at least these columns (the server does `SELECT *` then filters/orders on them):

| View | Required columns |
|---|---|
| `v_water_systems` | `pws_id, system_name, safer_status, is_failing, has_primary_mcl_violation, has_ecoli_violation, has_treatment_technique_violation, data_as_of, source_url` + profile/risk columns |
| `v_water_systems_near_zip` | `zip, distance_km` + all `v_water_systems` columns |
| `v_source_chemistry_latest` | `pws_id, well_id, chemical_name, is_non_detect, result_numeric, units, reporting_limit, last_observed, source_url` |
| `v_source_chemistry_near_zip` | `zip, distance_km` + all `v_source_chemistry_latest` columns |
| `v_tap_water_for_zip` | `zip, pct_of_zip_covered, pws_id, system_name, water_stage, analyte_name, result_numeric, units, is_non_detect, mcl, exceeds_mcl, last_observed, source_url` |
| `v_school_lead_near_zip` | `zip, distance_km, school_name, action_level_exceeded, result_numeric, last_observed, source_url` + school/system columns |

`zip` + `distance_km` are precomputed (pairs up to 50 km), so the server filters `distance_km <= :radius_km` (the tools take `radius_miles`, max 31, and convert to km) rather than doing geospatial math per request. Keep PII (street addresses, phone numbers) out of Gold.
## Run locally

```bash
cp .env.example .env          # set DATABRICKS_SQL_WAREHOUSE_ID
databricks auth login --host https://<workspace>.cloud.databricks.com
uv sync --group dev
uv run python main.py         # stdio
```

Local auth uses the Databricks SDK's unified auth (CLI profile via `DATABRICKS_CONFIG_PROFILE`, or `DATABRICKS_HOST` + `DATABRICKS_TOKEN`). Connect a client with an entry like:

```json
{
  "mcpServers": {
    "waterboards": {
      "command": "uv",
      "args": ["run", "waterboards-mcp"],
      "cwd": "/absolute/path/to/this/repo"
    }
  }
}
```

HTTP mode (what Databricks Apps runs): `MCP_TRANSPORT=streamable-http uv run python main.py`, then `curl localhost:8000/health`.

## Verify

```bash
uv run pytest tests/ -v
uv run ruff check . && uv run ruff format --check .
```

Tests mock the Databricks SDK; no workspace is needed.

## Add a tool

One tool per file in `src/waterboards_mcp/tools/`, exposing `register(mcp)`; add it to `register_tools` in `tools/__init__.py`. Use `ZipCode`/`RadiusMiles`/`PaginationParams` from `models.py` for validated inputs and call `warehouse.query_gold(...)` with static `where`/`order_by` SQL and `Param`s for values. Document source, refresh cadence, and result shape in the docstring — the model reads it.

## Deploy

See [deploy/databricks/README.md](deploy/databricks/README.md).

## Evaluate

See [eval/README.md](eval/README.md) and the `mcp-eval` skill.

## License

See [LICENSE](LICENSE).
