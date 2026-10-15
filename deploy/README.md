# Deploying

The server deploys as a **Databricks App** — see [databricks/README.md](databricks/README.md).

`app.py` auto-selects its transport: a platform port (`DATABRICKS_APP_PORT` or `PORT`) → HTTP on that port; `MCP_TRANSPORT=streamable-http` → HTTP on `MCP_HOST:MCP_PORT`; otherwise stdio. Databricks Apps injects the port, so no code changes are needed; `/mcp` and `/health` are served.

Databricks Apps are gated by workspace auth, so MCP clients must present a bearer token. Never commit secrets — the kit's `.env` is git-ignored and holds coordinates only.
