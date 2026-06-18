# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""Async HTTP client for the scView REST API.

Wraps all five public REST API endpoints.  Every method returns a plain
dict so that tool handlers never have to deal with low-level exceptions.
On any error (network, timeout, HTTP 4xx/5xx) a structured error dict is
returned with a ``success: false`` flag and a ``reason`` key.

Reason codes:
  api_unavailable  – Network/connection error; the Django app cannot be reached.
  timeout          – The upstream API did not respond within the configured timeout.
  login_required   – HTTP 403: the endpoint is gated by *_REQUIRE_LOGIN.
  not_found        – HTTP 404: the requested service ID/key does not exist.
  bad_request      – HTTP 400: malformed query parameters.
  upstream_error   – Any other non-2xx response.
  parse_error      – Response body is not valid JSON.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from config import (
    MCP_API_BASE_URL,
    MCP_API_PATH_PREFIX,
    MCP_API_TIMEOUT,
)

logger = logging.getLogger(__name__)

# How long (in seconds) to cache the metadata response.
_METADATA_CACHE_TTL: int = 60


def _err(reason: str, message: str, status: int | None = None) -> dict[str, Any]:
    """Build a structured error result dict."""
    result: dict[str, Any] = {"success": False, "reason": reason, "message": message}
    if status is not None:
        result["http_status"] = status
    return result


class ScViewApiClient:
    """Lightweight async wrapper around the scView public REST API.

    A single shared instance should be used for the lifetime of the MCP
    server process.  Thread-safety is not a concern because httpx's async
    client is designed for concurrent async use.
    """

    def __init__(
        self,
        base_url: str = MCP_API_BASE_URL,
        path_prefix: str = MCP_API_PATH_PREFIX,
        timeout: float = MCP_API_TIMEOUT,
    ) -> None:
        self._api_root = f"{base_url.rstrip('/')}{path_prefix}/api"
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True,
        )
        self._metadata_cache: dict[str, Any] | None = None
        self._metadata_cached_at: float = 0.0

    async def aclose(self) -> None:
        """Release the underlying connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal request helper
    # ------------------------------------------------------------------

    async def _request(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Execute a GET request; convert all errors to structured error dicts."""
        url = f"{self._api_root}{path}"
        try:
            response = await self._client.get(url, params=params or {})
        except httpx.TimeoutException:
            logger.warning("Timeout calling %s", url)
            return _err("timeout", f"The upstream API did not respond in time ({url}).")
        except httpx.RequestError as exc:
            logger.warning("API unavailable: %s – %s", url, exc)
            return _err("api_unavailable", "The scView API is currently unreachable.")

        if response.status_code == 403:
            return _err(
                "login_required",
                "This information is not publicly available. "
                "The corresponding catalogue page requires authentication.",
                status=403,
            )
        if response.status_code == 404:
            return _err("not_found", "The requested service was not found.", status=404)
        if response.status_code == 400:
            return _err("bad_request", "Invalid request parameters.", status=400)
        if not response.is_success:
            return _err(
                "upstream_error",
                f"Unexpected response from the API (HTTP {response.status_code}).",
                status=response.status_code,
            )

        try:
            return response.json()
        except Exception:
            return _err("parse_error", "The API response could not be parsed as JSON.")

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_metadata(
        self, lang: str | None = None, force: bool = False
    ) -> dict[str, Any]:
        """Return API self-description with endpoint availability flags.

        Results are cached for ``_METADATA_CACHE_TTL`` seconds.
        Pass ``force=True`` to bypass the cache.
        """
        now = time.monotonic()
        if (
            not force
            and self._metadata_cache is not None
            and now - self._metadata_cached_at < _METADATA_CACHE_TTL
        ):
            return self._metadata_cache

        params: dict[str, str] = {}
        if lang:
            params["lang"] = lang
        result = await self._request("/metadata/", params)
        if result.get("success") is not False:
            self._metadata_cache = result
            self._metadata_cached_at = now
        return result

    async def get_online_services(
        self, lang: str | None = None, clientele: str | None = None
    ) -> dict[str, Any]:
        """Return the online services directory."""
        params: dict[str, str] = {}
        if lang:
            params["lang"] = lang
        if clientele:
            params["clientele"] = clientele
        return await self._request("/online-services/", params)

    async def get_service_catalogue(
        self, lang: str | None = None, clientele: str | None = None
    ) -> dict[str, Any]:
        """Return the full listed service catalogue."""
        params: dict[str, str] = {}
        if lang:
            params["lang"] = lang
        if clientele:
            params["clientele"] = clientele
        return await self._request("/service-catalogue/", params)

    async def get_service(
        self, service_id: int, lang: str | None = None
    ) -> dict[str, Any]:
        """Return details for a single service by numeric ID."""
        params: dict[str, str] = {}
        if lang:
            params["lang"] = lang
        return await self._request(f"/service/{service_id}/", params)

    async def get_service_by_key(
        self, service_key: str, lang: str | None = None
    ) -> dict[str, Any]:
        """Return details for a single service by its CATEGORY-ACRONYM key."""
        params: dict[str, str] = {}
        if lang:
            params["lang"] = lang
        return await self._request(f"/service-by-key/{service_key}/", params)

    # ------------------------------------------------------------------
    # Cached metadata helpers
    # ------------------------------------------------------------------

    def is_endpoint_enabled(self, endpoint_name: str) -> bool | None:
        """Return True/False from cached metadata, or None if cache is absent.

        Used by tool handlers to short-circuit API calls when an endpoint
        is known to be gated behind login.
        """
        if self._metadata_cache is None:
            return None
        endpoints = self._metadata_cache.get("endpoints", {})
        ep = endpoints.get(endpoint_name)
        if ep is None:
            return None
        return bool(ep.get("enabled", False))
