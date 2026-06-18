# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""scView MCP Server.

Exposes the scView IT Service Catalogue as five MCP tools via the public
REST API.  The server is intentionally stateless beyond a short-lived
metadata cache that tracks which endpoints are currently available.

Tools
-----
get_api_metadata         – API self-description (always available).
list_online_services     – Online services directory (gated by ONLINE_SERVICES_REQUIRE_LOGIN).
search_service_catalogue – Full service catalogue (gated by SERVICE_CATALOGUE_REQUIRE_LOGIN).
get_service              – Single service detail by numeric ID.
get_service_by_key       – Single service detail by key (e.g. 'ITD-EMAIL').

Startup / shutdown
------------------
The shared ``ScViewApiClient`` is created on the first MCP session and
reused for all subsequent sessions (see module-level ``_api_client``).
The metadata probe runs once at startup and is cached for 60 seconds.

Graceful degradation
--------------------
If the upstream API is unreachable the server still starts.  Every tool
call returns a descriptive message without raising an exception.  When
the API returns HTTP 403 (login-gated endpoint) the tool returns a
human-readable explanation rather than an error.
"""
from __future__ import annotations

import json
import logging
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from api_client import ScViewApiClient
from config import ALLOWED_LANGS, MCP_DEFAULT_LANG, MCP_PORT

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

# ---------------------------------------------------------------------------
# Shared API client
# The client is created once on the first MCP session and reused for the
# lifetime of the process.  Using a module-level variable keeps access
# simple and makes it easy to replace with a mock in tests.
# ---------------------------------------------------------------------------
_api_client: ScViewApiClient | None = None


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:  # type: ignore[type-arg]
    """Initialise the shared API client and probe the upstream API once."""
    global _api_client
    if _api_client is None:
        _api_client = ScViewApiClient()
        result = await _api_client.get_metadata(force=True)
        if result.get("success") is False:
            logger.warning(
                "scView API unreachable on startup (reason: %s). "
                "Tools will return an availability message until the API responds.",
                result.get("reason", "unknown"),
            )
        else:
            org = result.get("organization", "scView")
            logger.info(
                "Connected to scView API — organisation: %s, "
                "online_services: %s, service_catalogue: %s",
                org,
                result.get("endpoints", {}).get("online_services", {}).get("enabled"),
                result.get("endpoints", {}).get("service_catalogue", {}).get("enabled"),
            )
    yield {}


# ---------------------------------------------------------------------------
# FastMCP server
# host="0.0.0.0" disables DNS-rebinding protection (correct behind nginx).
# streamable_http_path="/mcp" is the default; nginx rewrites /sc/mcp → /mcp.
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "scView Service Catalogue",
    instructions=(
        "This server provides access to an IT service catalogue. "
        "Call get_api_metadata first to discover which tools are currently available "
        "and what languages and clientele filters are supported. "
        "Tools whose corresponding catalogue page requires authentication will return "
        "a descriptive message rather than raising an error."
    ),
    host="0.0.0.0",
    port=MCP_PORT,
    streamable_http_path="/mcp",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Shared helper functions
# ---------------------------------------------------------------------------

def _get_client() -> ScViewApiClient:
    """Return the shared API client, raising clearly if server is not started."""
    if _api_client is None:
        raise RuntimeError(
            "API client has not been initialised. "
            "Has the MCP server lifespan started?"
        )
    return _api_client


def _validate_lang(lang: str | None) -> str | None:
    """Validate and normalise a language code against the allowed list."""
    if lang is None:
        return None
    lang = lang.strip().lower()
    return lang if lang in ALLOWED_LANGS else None


def _validate_clientele(clientele: str | None) -> str | None:
    """Validate a clientele acronym: alphanumeric, hyphen, underscore, max 50 chars."""
    if clientele is None:
        return None
    if not re.match(r"^[A-Za-z0-9_-]{1,50}$", clientele):
        return None
    return clientele.upper()


def _describe_error(result: dict) -> str:  # type: ignore[type-arg]
    """Convert an API error dict to a human-readable tool response string."""
    reason = result.get("reason", "unknown")
    message = result.get("message", "An unknown error occurred.")
    if reason == "api_unavailable":
        return (
            "⚠️  The scView service catalogue API is currently unreachable. "
            "Please try again later."
        )
    if reason == "login_required":
        return (
            "🔒  This information is not publicly available. "
            "The corresponding catalogue page requires authentication. "
            "Contact your administrator if you need access."
        )
    if reason == "not_found":
        return f"❌  {message}"
    if reason == "timeout":
        return "⏱️  The API request timed out. Please try again."
    return f"⚠️  {message}"


def _check_endpoint(client: ScViewApiClient, endpoint_name: str, label: str) -> str | None:
    """Return a message if the endpoint is known to be disabled; None if available."""
    enabled = client.is_endpoint_enabled(endpoint_name)
    if enabled is False:
        return (
            f"🔒  The {label} endpoint is not publicly available. "
            "The corresponding catalogue page requires authentication."
        )
    return None


def _to_json(data: dict) -> str:  # type: ignore[type-arg]
    """Serialise a dict to a pretty-printed JSON string for the MCP response."""
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_api_metadata(lang: str = MCP_DEFAULT_LANG) -> str:
    """Return service catalogue API metadata.

    Includes available endpoints with their enabled/disabled status, supported
    languages, clientele groups, and service categories.  This tool is always
    available and should be called first to discover which other tools can be
    used and what filter values are accepted.

    Args:
        lang: Language code for the response. Supported values: 'de', 'en'.
    """
    client = _get_client()
    validated_lang = _validate_lang(lang) or MCP_DEFAULT_LANG
    result = await client.get_metadata(lang=validated_lang, force=True)
    if result.get("success") is False:
        return _describe_error(result)
    return _to_json(result)


@mcp.tool()
async def list_online_services(
    lang: str = MCP_DEFAULT_LANG,
    clientele: str | None = None,
) -> str:
    """List all online services – services with a direct access URL.

    Returns services grouped by category with their name, version, direct URL,
    and a flag indicating whether they are newly available.  This endpoint
    mirrors the online services directory page of the catalogue.

    Args:
        lang:      Language code. Supported: 'de', 'en'.
        clientele: Optional filter by clientele acronym (e.g. 'STAFF', 'STUDENT').
                   Call get_api_metadata to see available clientele groups.
    """
    client = _get_client()
    blocked = _check_endpoint(client, "online_services", "Online Services")
    if blocked:
        return blocked

    validated_lang = _validate_lang(lang) or MCP_DEFAULT_LANG
    validated_clientele = _validate_clientele(clientele)
    result = await client.get_online_services(
        lang=validated_lang, clientele=validated_clientele
    )
    if result.get("success") is False:
        return _describe_error(result)
    return _to_json(result)


@mcp.tool()
async def search_service_catalogue(
    lang: str = MCP_DEFAULT_LANG,
    clientele: str | None = None,
) -> str:
    """Return the full IT service catalogue with detailed service information.

    Returns services grouped by category including name, purpose, description,
    contact information, availability dates, and cost details per clientele.
    This endpoint mirrors the full service catalogue list page.

    Args:
        lang:      Language code. Supported: 'de', 'en'.
        clientele: Optional filter by clientele acronym (e.g. 'STAFF', 'EXTERNAL').
                   Call get_api_metadata to see available clientele groups.
    """
    client = _get_client()
    blocked = _check_endpoint(client, "service_catalogue", "Service Catalogue")
    if blocked:
        return blocked

    validated_lang = _validate_lang(lang) or MCP_DEFAULT_LANG
    validated_clientele = _validate_clientele(clientele)
    result = await client.get_service_catalogue(
        lang=validated_lang, clientele=validated_clientele
    )
    if result.get("success") is False:
        return _describe_error(result)
    return _to_json(result)


@mcp.tool()
async def get_service(service_id: int, lang: str = MCP_DEFAULT_LANG) -> str:
    """Return full details of a single service by its numeric ID.

    Provides the same information as search_service_catalogue but for a single
    service.  Obtain the numeric ID from a catalogue or online-services listing.

    Args:
        service_id: Positive integer service revision ID.
        lang:       Language code. Supported: 'de', 'en'.
    """
    client = _get_client()
    blocked = _check_endpoint(client, "service_detail", "Service Detail")
    if blocked:
        return blocked

    if not isinstance(service_id, int) or service_id <= 0:
        return "❌  service_id must be a positive integer."

    validated_lang = _validate_lang(lang) or MCP_DEFAULT_LANG
    result = await client.get_service(service_id, lang=validated_lang)
    if result.get("success") is False:
        return _describe_error(result)
    return _to_json(result)


@mcp.tool()
async def get_service_by_key(service_key: str, lang: str = MCP_DEFAULT_LANG) -> str:
    """Return full details of a single service by its unique key.

    The key format is CATEGORY-ACRONYM, for example 'ITD-EMAIL' or 'COMPUTE-HPC'.
    Keys are case-insensitive and will be normalised to upper case.

    Args:
        service_key: Service key in the format CATEGORY-ACRONYM (e.g. 'ITD-EMAIL').
        lang:        Language code. Supported: 'de', 'en'.
    """
    client = _get_client()
    blocked = _check_endpoint(client, "service_by_key", "Service Detail")
    if blocked:
        return blocked

    normalised_key = service_key.strip().upper()
    if not re.match(r"^[A-Z0-9]{1,20}-[A-Z0-9-]{1,50}$", normalised_key):
        return (
            "❌  Invalid service key format. "
            "Expected CATEGORY-ACRONYM, e.g. 'ITD-EMAIL' or 'COMPUTE-HPC'."
        )

    validated_lang = _validate_lang(lang) or MCP_DEFAULT_LANG
    result = await client.get_service_by_key(normalised_key, lang=validated_lang)
    if result.get("success") is False:
        return _describe_error(result)
    return _to_json(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
