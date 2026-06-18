# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""Unit tests for ScViewApiClient.

All HTTP calls are intercepted by respx so no real network is required.
The Django application does not need to be running.
"""
from __future__ import annotations

import sys
import os

# Allow importing from the parent apps/mcp/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import respx
import httpx

from api_client import ScViewApiClient

BASE = "http://test-itsm:8000"
PREFIX = "/sc"
API_ROOT = f"{BASE}{PREFIX}/api"


@pytest.fixture
def client():
    """Return a ScViewApiClient configured to hit the mock base URL."""
    c = ScViewApiClient(base_url=BASE, path_prefix=PREFIX, timeout=5)
    yield c


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestGetMetadata:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self, client):
        payload = {
            "success": True,
            "organization": "Test Org",
            "endpoints": {
                "online_services": {"enabled": True},
                "service_catalogue": {"enabled": False},
                "metadata": {"enabled": True},
            },
        }
        respx.get(f"{API_ROOT}/metadata/").mock(return_value=httpx.Response(200, json=payload))
        result = await client.get_metadata()
        assert result["success"] is True
        assert result["organization"] == "Test Org"

    @pytest.mark.asyncio
    @respx.mock
    async def test_cached(self, client):
        """Second call within TTL should not make another HTTP request."""
        payload = {"success": True, "organization": "Cached Org", "endpoints": {}}
        route = respx.get(f"{API_ROOT}/metadata/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        await client.get_metadata()
        await client.get_metadata()  # Should use cache
        assert route.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_force_bypasses_cache(self, client):
        payload = {"success": True, "organization": "Org", "endpoints": {}}
        route = respx.get(f"{API_ROOT}/metadata/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        await client.get_metadata()
        await client.get_metadata(force=True)
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_error(self, client):
        respx.get(f"{API_ROOT}/metadata/").mock(side_effect=httpx.ConnectError("refused"))
        result = await client.get_metadata()
        assert result["success"] is False
        assert result["reason"] == "api_unavailable"

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout(self, client):
        respx.get(f"{API_ROOT}/metadata/").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        result = await client.get_metadata()
        assert result["success"] is False
        assert result["reason"] == "timeout"


# ---------------------------------------------------------------------------
# Online services
# ---------------------------------------------------------------------------

class TestGetOnlineServices:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self, client):
        payload = {"success": True, "total_count": 3, "categories": []}
        respx.get(f"{API_ROOT}/online-services/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.get_online_services(lang="en")
        assert result["success"] is True
        assert result["total_count"] == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_403_returns_login_required(self, client):
        respx.get(f"{API_ROOT}/online-services/").mock(
            return_value=httpx.Response(403, json={"success": False, "error": "login required"})
        )
        result = await client.get_online_services()
        assert result["success"] is False
        assert result["reason"] == "login_required"
        assert result["http_status"] == 403

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_error(self, client):
        respx.get(f"{API_ROOT}/online-services/").mock(
            side_effect=httpx.ConnectError("refused")
        )
        result = await client.get_online_services()
        assert result["success"] is False
        assert result["reason"] == "api_unavailable"

    @pytest.mark.asyncio
    @respx.mock
    async def test_clientele_param_forwarded(self, client):
        route = respx.get(f"{API_ROOT}/online-services/").mock(
            return_value=httpx.Response(200, json={"success": True, "categories": [], "total_count": 0})
        )
        await client.get_online_services(lang="de", clientele="STAFF")
        assert "clientele=STAFF" in str(route.calls[0].request.url)
        assert "lang=de" in str(route.calls[0].request.url)


# ---------------------------------------------------------------------------
# Service catalogue
# ---------------------------------------------------------------------------

class TestGetServiceCatalogue:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self, client):
        payload = {"success": True, "total_count": 8, "categories": []}
        respx.get(f"{API_ROOT}/service-catalogue/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.get_service_catalogue()
        assert result["success"] is True
        assert result["total_count"] == 8

    @pytest.mark.asyncio
    @respx.mock
    async def test_403(self, client):
        respx.get(f"{API_ROOT}/service-catalogue/").mock(
            return_value=httpx.Response(403, json={})
        )
        result = await client.get_service_catalogue()
        assert result["reason"] == "login_required"

    @pytest.mark.asyncio
    @respx.mock
    async def test_unexpected_5xx(self, client):
        respx.get(f"{API_ROOT}/service-catalogue/").mock(
            return_value=httpx.Response(500, json={})
        )
        result = await client.get_service_catalogue()
        assert result["success"] is False
        assert result["reason"] == "upstream_error"
        assert result["http_status"] == 500


# ---------------------------------------------------------------------------
# Service detail by ID
# ---------------------------------------------------------------------------

class TestGetService:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self, client):
        payload = {"success": True, "service": {"id": 42, "service_name": "Test"}}
        respx.get(f"{API_ROOT}/service/42/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.get_service(42)
        assert result["success"] is True
        assert result["service"]["id"] == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_404(self, client):
        respx.get(f"{API_ROOT}/service/99999/").mock(
            return_value=httpx.Response(404, json={"success": False, "error": "not found"})
        )
        result = await client.get_service(99999)
        assert result["success"] is False
        assert result["reason"] == "not_found"
        assert result["http_status"] == 404

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout(self, client):
        respx.get(f"{API_ROOT}/service/1/").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        result = await client.get_service(1)
        assert result["reason"] == "timeout"


# ---------------------------------------------------------------------------
# Service detail by key
# ---------------------------------------------------------------------------

class TestGetServiceByKey:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self, client):
        payload = {"success": True, "service": {"service_key": "COMPUTE-HPC"}}
        respx.get(f"{API_ROOT}/service-by-key/COMPUTE-HPC/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.get_service_by_key("COMPUTE-HPC")
        assert result["success"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_400_malformed_key(self, client):
        respx.get(f"{API_ROOT}/service-by-key/NOKEY/").mock(
            return_value=httpx.Response(400, json={"success": False, "error": "bad key"})
        )
        result = await client.get_service_by_key("NOKEY")
        assert result["reason"] == "bad_request"

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_unknown_key(self, client):
        respx.get(f"{API_ROOT}/service-by-key/NONE-EXIST/").mock(
            return_value=httpx.Response(404, json={})
        )
        result = await client.get_service_by_key("NONE-EXIST")
        assert result["reason"] == "not_found"


# ---------------------------------------------------------------------------
# is_endpoint_enabled helper
# ---------------------------------------------------------------------------

class TestIsEndpointEnabled:
    def test_returns_none_when_no_cache(self, client):
        assert client.is_endpoint_enabled("online_services") is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_true_when_enabled(self, client):
        payload = {
            "success": True,
            "endpoints": {"online_services": {"enabled": True}},
        }
        respx.get(f"{API_ROOT}/metadata/").mock(return_value=httpx.Response(200, json=payload))
        await client.get_metadata()
        assert client.is_endpoint_enabled("online_services") is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_when_disabled(self, client):
        payload = {
            "success": True,
            "endpoints": {"service_catalogue": {"enabled": False}},
        }
        respx.get(f"{API_ROOT}/metadata/").mock(return_value=httpx.Response(200, json=payload))
        await client.get_metadata()
        assert client.is_endpoint_enabled("service_catalogue") is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_none_for_unknown_endpoint(self, client):
        payload = {"success": True, "endpoints": {}}
        respx.get(f"{API_ROOT}/metadata/").mock(return_value=httpx.Response(200, json=payload))
        await client.get_metadata()
        assert client.is_endpoint_enabled("nonexistent") is None
