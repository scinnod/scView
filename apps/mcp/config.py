# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""Configuration for the scView MCP server.

Internal connection details are hardcoded because this container is intended
to run exclusively alongside the scView / itsm project and is not portable
to other API backends.

User-facing settings (MCP_ENABLED, MCP_API_TIMEOUT) are read from the shared
env/itsm.env file — the same file that configures the Django application.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Startup control
# ---------------------------------------------------------------------------

# Set to true/1/yes to activate the MCP server.
# Default: false — the server is opt-in and does not start unless explicitly enabled.
MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "false").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Upstream API connection (internal — not user-configurable)
# ---------------------------------------------------------------------------

# Internal Docker network address of the Django app.  The MCP container is on
# the same app_itsm bridge network and reaches the Django app directly.
MCP_API_BASE_URL: str = "http://itsm:8000"

# URL prefix under which the Django app lives.
MCP_API_PATH_PREFIX: str = "/sc"

# HTTP request timeout in seconds.  Increase if catalogue responses are slow.
MCP_API_TIMEOUT: float = float(os.getenv("MCP_API_TIMEOUT", "10"))

# ---------------------------------------------------------------------------
# Server settings (internal — not user-configurable)
# ---------------------------------------------------------------------------

# Port the MCP server listens on inside the container (nginx proxies to this).
MCP_PORT: int = 8080

# Default and allowed language codes — must match Django LANGUAGES setting.
MCP_DEFAULT_LANG: str = "en"
ALLOWED_LANGS: list[str] = ["de", "en"]
