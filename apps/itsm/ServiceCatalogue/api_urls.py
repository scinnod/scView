# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
REST API URL patterns for the Service Catalogue.

These are included directly in urlpatterns (outside i18n_patterns)
so that API endpoints are language-neutral and not subject to
automatic language-prefix redirects.  Language selection is handled
via the ``?lang=`` query parameter instead.
"""

from django.urls import path

from . import api_views

urlpatterns = [
    path(
        "online-services/",
        api_views.api_online_services,
        name="api_online_services"
    ),
    path(
        "service-catalogue/",
        api_views.api_service_catalogue,
        name="api_service_catalogue"
    ),
    path(
        "service/<int:service_id>/",
        api_views.api_service_detail,
        name="api_service_detail"
    ),
    path(
        "service-by-key/<str:service_key>/",
        api_views.api_service_by_key,
        name="api_service_by_key"
    ),
    path(
        "metadata/",
        api_views.api_metadata,
        name="api_metadata"
    ),
]
