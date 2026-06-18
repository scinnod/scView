# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""Unit tests for the MCP server tool functions.

Tools are tested by calling them directly as async functions (FastMCP's
@mcp.tool() decorator returns the original function unchanged).
The shared ScViewApiClient is replaced with an AsyncMock before each test.
"""
from __future__ import annotations

import json
import sys
import os

# Allow importing from apps/mcp/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import server
from api_client import ScViewApiClient

# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

METADATA_ENABLED = {
    "success": True,
    "api_version": "1.0",
    "organization": "Test University",
    "languages": ["de", "en"],
    "clienteles": [
        {"acronym": "STAFF", "name": "Staff"},
        {"acronym": "STUDENT", "name": "Students"},
    ],
    "categories": [{"acronym": "IT", "name": "IT Services"}],
    "endpoints": {
        "online_services": {"enabled": True, "url": "/api/online-services/"},
        "service_catalogue": {"enabled": True, "url": "/api/service-catalogue/"},
        "service_detail": {"enabled": True, "url": "/api/service/{id}/"},
        "service_by_key": {"enabled": True, "url": "/api/service-by-key/{key}/"},
        "metadata": {"enabled": True, "url": "/api/metadata/"},
    },
}

METADATA_GATED = {
    **METADATA_ENABLED,
    "endpoints": {
        **METADATA_ENABLED["endpoints"],
        "online_services": {"enabled": False, "url": "/api/online-services/"},
        "service_catalogue": {"enabled": False, "url": "/api/service-catalogue/"},
        "service_detail": {"enabled": False, "url": "/api/service/{id}/"},
        "service_by_key": {"enabled": False, "url": "/api/service-by-key/{key}/"},
    },
}

ONLINE_SERVICES_RESPONSE = {
    "success": True,
    "timestamp": "2026-06-18T10:00:00",
    "language": "en",
    "total_count": 2,
    "categories": [
        {
            "name": "IT Services",
            "acronym": "IT",
            "services": [
                {
                    "id": 1,
                    "service_key": "IT-EMAIL",
                    "service_name": "Email",
                    "version": "1.0",
                    "url": "https://mail.example.com",
                    "is_new": False,
                }
            ],
        }
    ],
}

CATALOGUE_RESPONSE = {
    "success": True,
    "total_count": 1,
    "categories": [
        {
            "name": "IT",
            "acronym": "IT",
            "services": [
                {
                    "id": 1,
                    "service_key": "IT-EMAIL",
                    "service_name": "Email",
                    "service_purpose": "Electronic mail",
                    "description": "Our email service.",
                    "clienteles": [],
                }
            ],
        }
    ],
}

SERVICE_DETAIL_RESPONSE = {
    "success": True,
    "service": {
        "id": 42,
        "service_key": "COMPUTE-HPC",
        "service_name": "HPC Cluster",
        "description": "High-performance computing.",
        "clienteles": [],
    },
}

API_UNAVAILABLE = {
    "success": False,
    "reason": "api_unavailable",
    "message": "The scView API is currently unreachable.",
}

LOGIN_REQUIRED = {
    "success": False,
    "reason": "login_required",
    "message": "Authentication required.",
    "http_status": 403,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """An AsyncMock that mimics ScViewApiClient."""
    c = AsyncMock(spec=ScViewApiClient)
    # Default: all endpoints enabled
    c.is_endpoint_enabled.return_value = True
    c.get_metadata.return_value = METADATA_ENABLED
    c.get_online_services.return_value = ONLINE_SERVICES_RESPONSE
    c.get_service_catalogue.return_value = CATALOGUE_RESPONSE
    c.get_service.return_value = SERVICE_DETAIL_RESPONSE
    c.get_service_by_key.return_value = SERVICE_DETAIL_RESPONSE
    return c


@pytest.fixture(autouse=True)
def inject_client(mock_client):
    """Replace the module-level API client with the mock for every test."""
    original = server._api_client
    server._api_client = mock_client
    yield
    server._api_client = original


# ---------------------------------------------------------------------------
# get_api_metadata
# ---------------------------------------------------------------------------

class TestGetApiMetadata:
    @pytest.mark.asyncio
    async def test_success_returns_json_string(self, mock_client):
        result = await server.get_api_metadata("en")
        data = json.loads(result)
        assert data["success"] is True
        assert data["organization"] == "Test University"
        mock_client.get_metadata.assert_called_once_with(lang="en", force=True)

    @pytest.mark.asyncio
    async def test_invalid_lang_falls_back_to_default(self, mock_client):
        await server.get_api_metadata("xx")
        call_kwargs = mock_client.get_metadata.call_args
        assert call_kwargs.kwargs.get("lang") == server.MCP_DEFAULT_LANG

    @pytest.mark.asyncio
    async def test_api_unavailable_returns_message(self, mock_client):
        mock_client.get_metadata.return_value = API_UNAVAILABLE
        result = await server.get_api_metadata("en")
        assert "unreachable" in result.lower()
        assert not result.startswith("{")  # Should be a plain message, not JSON

    @pytest.mark.asyncio
    async def test_always_forces_cache_refresh(self, mock_client):
        await server.get_api_metadata()
        await server.get_api_metadata()
        assert mock_client.get_metadata.call_count == 2
        for call in mock_client.get_metadata.call_args_list:
            assert call.kwargs.get("force") is True


# ---------------------------------------------------------------------------
# list_online_services
# ---------------------------------------------------------------------------

class TestListOnlineServices:
    @pytest.mark.asyncio
    async def test_success(self, mock_client):
        result = await server.list_online_services("en")
        data = json.loads(result)
        assert data["success"] is True
        assert data["total_count"] == 2

    @pytest.mark.asyncio
    async def test_clientele_filter_validated(self, mock_client):
        await server.list_online_services("en", clientele="STAFF")
        mock_client.get_online_services.assert_called_once_with(
            lang="en", clientele="STAFF"
        )

    @pytest.mark.asyncio
    async def test_invalid_clientele_stripped(self, mock_client):
        """An invalid clientele string should be silently dropped."""
        await server.list_online_services("en", clientele="'; DROP TABLE--")
        mock_client.get_online_services.assert_called_once_with(
            lang="en", clientele=None
        )

    @pytest.mark.asyncio
    async def test_gated_endpoint_returns_message(self, mock_client):
        mock_client.is_endpoint_enabled.return_value = False
        result = await server.list_online_services("en")
        assert "🔒" in result
        mock_client.get_online_services.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_unavailable_returns_message(self, mock_client):
        mock_client.get_online_services.return_value = API_UNAVAILABLE
        result = await server.list_online_services()
        assert "unreachable" in result.lower()

    @pytest.mark.asyncio
    async def test_login_required_returns_descriptive_message(self, mock_client):
        mock_client.get_online_services.return_value = LOGIN_REQUIRED
        result = await server.list_online_services()
        assert "authentication" in result.lower()


# ---------------------------------------------------------------------------
# search_service_catalogue
# ---------------------------------------------------------------------------

class TestSearchServiceCatalogue:
    @pytest.mark.asyncio
    async def test_success(self, mock_client):
        result = await server.search_service_catalogue("de")
        data = json.loads(result)
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_gated_endpoint_returns_message(self, mock_client):
        mock_client.is_endpoint_enabled.return_value = False
        result = await server.search_service_catalogue()
        assert "🔒" in result
        mock_client.get_service_catalogue.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_metadata_cache_still_calls_api(self, mock_client):
        """When is_endpoint_enabled returns None (no cache), proceed with the call."""
        mock_client.is_endpoint_enabled.return_value = None
        result = await server.search_service_catalogue("en")
        mock_client.get_service_catalogue.assert_called_once()


# ---------------------------------------------------------------------------
# get_service
# ---------------------------------------------------------------------------

class TestGetService:
    @pytest.mark.asyncio
    async def test_success(self, mock_client):
        result = await server.get_service(42, "en")
        data = json.loads(result)
        assert data["success"] is True
        assert data["service"]["id"] == 42

    @pytest.mark.asyncio
    async def test_negative_id_returns_error(self, mock_client):
        result = await server.get_service(-1)
        assert "❌" in result
        mock_client.get_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_id_returns_error(self, mock_client):
        result = await server.get_service(0)
        assert "❌" in result
        mock_client.get_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found_returns_message(self, mock_client):
        mock_client.get_service.return_value = {
            "success": False,
            "reason": "not_found",
            "message": "Service not found.",
        }
        result = await server.get_service(99999)
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_gated_endpoint_returns_message(self, mock_client):
        mock_client.is_endpoint_enabled.return_value = False
        result = await server.get_service(1)
        assert "🔒" in result
        mock_client.get_service.assert_not_called()


# ---------------------------------------------------------------------------
# get_service_by_key
# ---------------------------------------------------------------------------

class TestGetServiceByKey:
    @pytest.mark.asyncio
    async def test_success(self, mock_client):
        result = await server.get_service_by_key("COMPUTE-HPC", "en")
        data = json.loads(result)
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_key_normalised_to_upper(self, mock_client):
        await server.get_service_by_key("compute-hpc", "en")
        mock_client.get_service_by_key.assert_called_once_with("COMPUTE-HPC", lang="en")

    @pytest.mark.asyncio
    async def test_invalid_key_no_dash_returns_error(self, mock_client):
        result = await server.get_service_by_key("NOKEY")
        assert "❌" in result
        mock_client.get_service_by_key.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_key_special_chars_returns_error(self, mock_client):
        result = await server.get_service_by_key("'; DROP TABLE--")
        assert "❌" in result
        mock_client.get_service_by_key.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_key_with_multiple_dashes(self, mock_client):
        """Keys like 'ITD-EMAIL-LEGACY' should be accepted."""
        await server.get_service_by_key("ITD-EMAIL-LEGACY")
        mock_client.get_service_by_key.assert_called_once_with(
            "ITD-EMAIL-LEGACY", lang=server.MCP_DEFAULT_LANG
        )

    @pytest.mark.asyncio
    async def test_gated_endpoint_returns_message(self, mock_client):
        mock_client.is_endpoint_enabled.return_value = False
        result = await server.get_service_by_key("COMPUTE-HPC")
        assert "🔒" in result
        mock_client.get_service_by_key.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found_returns_descriptive_message(self, mock_client):
        mock_client.get_service_by_key.return_value = {
            "success": False,
            "reason": "not_found",
            "message": "Service with key NONE-EXIST not found.",
        }
        result = await server.get_service_by_key("NONE-EXIST")
        assert "❌" in result


# ---------------------------------------------------------------------------
# Graceful degradation: no API client (server not started)
# ---------------------------------------------------------------------------

class TestNoClient:
    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_client_none(self):
        original = server._api_client
        server._api_client = None
        try:
            with pytest.raises(RuntimeError, match="not been initialised"):
                await server.get_api_metadata()
        finally:
            server._api_client = original
