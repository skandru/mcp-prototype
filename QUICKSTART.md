# Quickstart

1. `pip install uv`
2. `cp .env.example .env` and set `DATABRICKS_SQL_WAREHOUSE_ID`
3. `databricks auth login --host https://<workspace>.cloud.databricks.com`
4. `uv sync --group dev && uv run pytest tests/ -v`
5. `uv run python main.py` — starts in **stdio** mode and waits for a client (no URL is printed; the client launches it).

Connect a client (Claude Code `.mcp.json` / Claude Desktop config) — see [README](README.md#run-locally) — then ask:

> "What water quality information is available near ZIP 94103?"

Next: [deploy to Databricks](deploy/databricks/README.md) · [evaluate](eval/README.md).
