#!/usr/bin/env bash
# MCP server with the stand's tools, started by Hermes (profile «pulse») over stdio as user hermes.
# No secrets needed: the tools read the stand's SQLite in /opt/pulse/var.
export PYTHONUNBUFFERED=1
cd /opt/pulse/apps/api
exec .venv/bin/python -m pulse.agents.mcp_server
