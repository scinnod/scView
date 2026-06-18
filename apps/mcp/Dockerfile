# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
#
# Multi-stage Dockerfile for the scView MCP Server.
# The server is a standalone Python service with no Django dependency.

FROM python:3.12-slim AS base

# Security: run as a non-root user
RUN groupadd --system mcpuser \
    && useradd --system --gid mcpuser --no-create-home mcpuser

WORKDIR /app

# Install Python dependencies as root (before switching user)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py api_client.py server.py entrypoint.sh ./

# Set correct permissions
RUN chmod +x /app/entrypoint.sh \
    && chown -R mcpuser:mcpuser /app

USER mcpuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx, sys; r=httpx.get('http://localhost:8080/health', timeout=5); sys.exit(0 if r.status_code < 500 else 1)" \
    || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
