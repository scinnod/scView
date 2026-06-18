#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
#
# Entrypoint for the scView MCP server container.
#
# Activation: set MCP_ENABLED=true in env/itsm.env, then:
#   docker compose restart itsm_mcp
#
# Deactivation: set MCP_ENABLED=false in env/itsm.env, then:
#   docker compose restart itsm_mcp
#
# Design note — why sleep infinity instead of exit 0:
#   The container always stays running regardless of MCP_ENABLED.  This keeps
#   the Docker-internal hostname 'itsm_mcp' permanently resolvable, so nginx
#   can start and reload cleanly even when the MCP server is disabled.
#   When disabled, port 8080 is not listening; nginx returns 502 for /sc/mcp,
#   which is the intended graceful-degradation signal to API consumers.
#   Exiting the container would remove the DNS record and cause nginx to fail
#   on startup or reload with "host not found in upstream".

set -e

MCP_ENABLED=$(echo "${MCP_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')

case "${MCP_ENABLED}" in
    true|1|yes)
        echo "[itsm_mcp] MCP_ENABLED=${MCP_ENABLED} — starting MCP server on port ${MCP_PORT:-8080}"
        exec python server.py
        ;;
    *)
        echo "[itsm_mcp] MCP_ENABLED=${MCP_ENABLED} — MCP server is disabled."
        echo "[itsm_mcp] Container is standing by (not serving). nginx returns 502 for /sc/mcp."
        echo "[itsm_mcp] To enable: set MCP_ENABLED=true in env/itsm.env and run:"
        echo "[itsm_mcp]   docker compose restart itsm_mcp"
        exec sleep infinity
        ;;
esac
