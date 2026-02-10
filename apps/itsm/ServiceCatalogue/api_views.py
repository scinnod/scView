# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
Service Catalogue REST API Views

Public, read-only REST API endpoints for external integrations (e.g. SharePoint).
These endpoints mirror the publicly accessible pages of the application and
respect all access-control and field-visibility settings.

Security design:
  • The API never requires authentication itself.
  • Instead, each endpoint is gated on the same ``*_REQUIRE_LOGIN`` setting
    that controls the corresponding web page.  If a page requires login,
    the matching API endpoint returns 403 — because the underlying data
    is not considered public.
  • Exposed fields are limited to exactly those shown on the respective
    public web page.

Available endpoints (all under ``/sc/api/``):
  /api/online-services/   –  online services directory   (gated by ONLINE_SERVICES_REQUIRE_LOGIN)
  /api/service-catalogue/ –  full listed catalogue       (gated by SERVICE_CATALOGUE_REQUIRE_LOGIN)
  /api/service/<id>/      –  single service detail       (gated by SERVICE_CATALOGUE_REQUIRE_LOGIN)
  /api/service-by-key/<key>/ – service detail by key     (gated by SERVICE_CATALOGUE_REQUIRE_LOGIN)
  /api/metadata/          –  API self-description        (always available)
"""

import datetime
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods

from ServiceCatalogue.models import (
    Clientele,
    ServiceCategory,
    ServiceRevision,
)


# ---------------------------------------------------------------------------
# Access-control helpers
# ---------------------------------------------------------------------------

def _api_gated(setting_name):
    """Decorator: return 403 when the corresponding page requires login.

    Because the API is unauthenticated, we cannot serve data that the
    web interface would hide behind a login wall.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if getattr(settings, setting_name, True):
                return JsonResponse({
                    'success': False,
                    'error': _(
                        'This information is not publicly available. '
                        'The corresponding page requires authentication.'
                    ),
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _activate_language(request):
    """Activate the requested language if valid, else keep the current one."""
    lang = request.GET.get('lang')
    if lang and lang in [code for code, _ in settings.LANGUAGES]:
        translation.activate(lang)


# ---------------------------------------------------------------------------
# Serializers – expose *exactly* the fields shown on the web pages
# ---------------------------------------------------------------------------

def _serialize_online_service(revision, base_url):
    """Serialize a service revision for the **online services directory**.

    The online-services page (``ServiceJumpView``) shows:
      • service name (as link to ``revision.url``)
      • service URL
      • version badge
      • link to service-detail page (info icon)
      • "new" badge when recently available
      • discontinuation warning when ``available_until`` is near

    It does NOT show: purpose, description, contact, responsible, providers…
    """
    today = datetime.date.today()
    new_until = today - datetime.timedelta(weeks=1)
    discontinuation_warning_from = today + datetime.timedelta(weeks=4)

    data = {
        'id': revision.id,
        'service_key': revision.service.key,
        'service_name': revision.service.name,
        'category': {
            'name': revision.service.category.name,
            'acronym': revision.service.category.acronym,
        },
        'version': revision.version,
        'url': revision.url,
        'detail_url': '{}{}'.format(
            base_url,
            reverse('service_detail', kwargs={'pk': revision.pk}),
        ),
        'is_new': (
            revision.available_from is not None
            and revision.available_from > new_until
        ),
    }

    # Discontinuation warning (mirrors template logic)
    if revision.available_until and revision.available_until <= discontinuation_warning_from:
        data['discontinuation_warning'] = {
            'available_until': revision.available_until.isoformat(),
            'message': str(_('Availability currently scheduled only until {date}.')).format(
                date=revision.available_until,
            ),
        }

    return data


def _serialize_catalogue_service(revision, base_url):
    """Serialize a service revision for the **service catalogue**.

    The catalogue page (``ServiceListedView``) shows:
      • service key, name, category, purpose
      • description
      • URL and contact (if set)
      • availability dates and clienteles with cost info
      • optional fields gated by SERVICECATALOGUE_FIELD_* settings
      • link to detail page

    It does NOT show: responsible, service_providers, internal description…
    """
    # Clienteles with cost information (as shown on catalogue page)
    clienteles = []
    for availability in revision.availability_set.all():
        entry = {
            'name': availability.clientele.name,
            'acronym': availability.clientele.acronym,
        }
        if availability.charged:
            entry['charged'] = True
            if availability.fee > 0:
                entry['fee'] = str(availability.fee)
                entry['fee_unit'] = str(availability.fee_unit) if availability.fee_unit else None
            if availability.comment:
                entry['comment'] = availability.comment
        elif availability.comment:
            entry['comment'] = availability.comment
        clienteles.append(entry)

    data = {
        'id': revision.id,
        'service_key': revision.service.key,
        'service_name': revision.service.name,
        'service_purpose': revision.service.purpose,
        'category': {
            'name': revision.service.category.name,
            'acronym': revision.service.category.acronym,
        },
        'version': revision.version,
        'description': revision.description,
        'detail_url': '{}{}'.format(
            base_url,
            reverse('service_detail', kwargs={'pk': revision.pk}),
        ),
        'clienteles': clienteles,
    }

    # Optional direct link and contact
    if revision.url:
        data['url'] = revision.url
    if revision.contact:
        data['contact'] = revision.contact

    # Availability dates
    if revision.available_from:
        data['available_from'] = revision.available_from.isoformat()
    if revision.available_until:
        data['available_until'] = revision.available_until.isoformat()

    # Honor SERVICECATALOGUE_FIELD_* settings – only include enabled fields
    if settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION and revision.usage_information:
        data['usage_information'] = revision.usage_information
    if settings.SERVICECATALOGUE_FIELD_REQUIREMENTS and revision.requirements:
        data['requirements'] = revision.requirements
    if settings.SERVICECATALOGUE_FIELD_DETAILS and revision.details:
        data['details'] = revision.details
    if settings.SERVICECATALOGUE_FIELD_OPTIONS and revision.options:
        data['options'] = revision.options
    if settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL and revision.service_level:
        data['service_level'] = revision.service_level

    return data


# ---------------------------------------------------------------------------
# Helper – build absolute base URL from request
# ---------------------------------------------------------------------------

def _base_url(request):
    """Return scheme + host (no trailing slash)."""
    return '{}://{}'.format(request.scheme, request.get_host())


# ---------------------------------------------------------------------------
# API views
# ---------------------------------------------------------------------------

@cache_page(60 * 15)
@require_http_methods(["GET"])
@_api_gated('ONLINE_SERVICES_REQUIRE_LOGIN')
def api_online_services(request):
    """Online services directory – mirrors ``ServiceJumpView``.

    Only available when ``ONLINE_SERVICES_REQUIRE_LOGIN`` is ``False``.

    Query parameters:
      ``lang``      – language code (``de``, ``en``)
      ``clientele`` – filter by clientele acronym
    """
    _activate_language(request)
    today = datetime.date.today()
    base = _base_url(request)

    queryset = (
        ServiceRevision.objects
        .filter(listed_from__lte=today, available_from__lte=today)
        .exclude(listed_until__lt=today)
        .exclude(available_until__lt=today)
        .exclude(url=None)
        .select_related('service', 'service__category')
        .prefetch_related('availability_set', 'availability_set__clientele')
    )

    clientele_filter = request.GET.get('clientele')
    if clientele_filter:
        queryset = queryset.filter(
            availability__clientele__acronym__iexact=clientele_filter,
        ).distinct()

    services = [_serialize_online_service(sr, base) for sr in queryset]

    # Group by category
    categories = {}
    for svc in services:
        key = svc['category']['acronym']
        if key not in categories:
            categories[key] = {
                'name': svc['category']['name'],
                'acronym': key,
                'services': [],
            }
        categories[key]['services'].append(svc)

    return JsonResponse({
        'success': True,
        'timestamp': datetime.datetime.now().isoformat(),
        'language': translation.get_language(),
        'total_count': len(services),
        'categories': list(categories.values()),
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})


@cache_page(60 * 15)
@require_http_methods(["GET"])
@_api_gated('SERVICE_CATALOGUE_REQUIRE_LOGIN')
def api_service_catalogue(request):
    """Full service catalogue – mirrors ``ServiceListedView``.

    Only available when ``SERVICE_CATALOGUE_REQUIRE_LOGIN`` is ``False``.

    Query parameters:
      ``lang``      – language code (``de``, ``en``)
      ``clientele`` – filter by clientele acronym
    """
    _activate_language(request)
    today = datetime.date.today()
    base = _base_url(request)

    queryset = (
        ServiceRevision.objects
        .filter(listed_from__lte=today)
        .exclude(listed_until__lt=today)
        .select_related('service', 'service__category')
        .prefetch_related(
            'availability_set',
            'availability_set__clientele',
            'availability_set__fee_unit',
        )
    )

    clientele_filter = request.GET.get('clientele')
    if clientele_filter:
        queryset = queryset.filter(
            availability__clientele__acronym__iexact=clientele_filter,
        ).distinct()

    services = [_serialize_catalogue_service(sr, base) for sr in queryset]

    # Group by category
    categories = {}
    for svc in services:
        key = svc['category']['acronym']
        if key not in categories:
            categories[key] = {
                'name': svc['category']['name'],
                'acronym': key,
                'services': [],
            }
        categories[key]['services'].append(svc)

    return JsonResponse({
        'success': True,
        'timestamp': datetime.datetime.now().isoformat(),
        'language': translation.get_language(),
        'total_count': len(services),
        'categories': list(categories.values()),
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})


@cache_page(60 * 15)
@require_http_methods(["GET"])
@_api_gated('SERVICE_CATALOGUE_REQUIRE_LOGIN')
def api_service_detail(request, service_id):
    """Single service detail – mirrors ``ServiceDetailView``.

    Only available when ``SERVICE_CATALOGUE_REQUIRE_LOGIN`` is ``False``.

    Query parameters:
      ``lang`` – language code (``de``, ``en``)
    """
    _activate_language(request)
    today = datetime.date.today()
    base = _base_url(request)

    try:
        revision = (
            ServiceRevision.objects
            .filter(id=service_id, listed_from__lte=today)
            .exclude(listed_until__lt=today)
            .select_related('service', 'service__category')
            .prefetch_related(
                'availability_set',
                'availability_set__clientele',
                'availability_set__fee_unit',
            )
            .get()
        )
    except ServiceRevision.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Service not found or not publicly available.'),
        }, status=404)

    return JsonResponse({
        'success': True,
        'timestamp': datetime.datetime.now().isoformat(),
        'language': translation.get_language(),
        'service': _serialize_catalogue_service(revision, base),
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})


@cache_page(60 * 15)
@require_http_methods(["GET"])
@_api_gated('SERVICE_CATALOGUE_REQUIRE_LOGIN')
def api_service_by_key(request, service_key):
    """Single service detail by key – mirrors ``ServiceDetailView``.

    Only available when ``SERVICE_CATALOGUE_REQUIRE_LOGIN`` is ``False``.
    The key format is ``CATEGORY-ACRONYM`` (e.g. ``ITD-EMAIL``).

    Query parameters:
      ``lang`` – language code (``de``, ``en``)
    """
    _activate_language(request)
    today = datetime.date.today()
    base = _base_url(request)

    parts = service_key.split('-')
    if len(parts) < 2:
        return JsonResponse({
            'success': False,
            'error': _('Invalid service key format. Expected: CATEGORY-ACRONYM'),
        }, status=400)

    category_acronym = parts[0]
    service_acronym = '-'.join(parts[1:])

    revision = (
        ServiceRevision.objects
        .filter(
            service__category__acronym__iexact=category_acronym,
            service__acronym__iexact=service_acronym,
            listed_from__lte=today,
        )
        .exclude(listed_until__lt=today)
        .select_related('service', 'service__category')
        .prefetch_related(
            'availability_set',
            'availability_set__clientele',
            'availability_set__fee_unit',
        )
        .first()
    )

    if not revision:
        return JsonResponse({
            'success': False,
            'error': _('Service with key "%(key)s" not found or not publicly available.') % {
                'key': service_key,
            },
        }, status=404)

    return JsonResponse({
        'success': True,
        'timestamp': datetime.datetime.now().isoformat(),
        'language': translation.get_language(),
        'service': _serialize_catalogue_service(revision, base),
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})


@cache_page(60 * 60)
@require_http_methods(["GET"])
def api_metadata(request):
    """API self-description with available endpoints and filter options.

    Always available (no login gate) as it does not expose service data.
    Indicates which endpoints are currently enabled based on configuration.
    """
    _activate_language(request)

    clienteles = [
        {'acronym': c.acronym, 'name': c.name}
        for c in Clientele.objects.all()
    ]
    categories = [
        {'acronym': c.acronym, 'name': c.name}
        for c in ServiceCategory.objects.all()
    ]

    online_enabled = not settings.ONLINE_SERVICES_REQUIRE_LOGIN
    catalogue_enabled = not settings.SERVICE_CATALOGUE_REQUIRE_LOGIN

    endpoints = {
        'online_services': {
            'url': '/api/online-services/',
            'description': _('Online services directory'),
            'parameters': ['lang', 'clientele'],
            'enabled': online_enabled,
        },
        'service_catalogue': {
            'url': '/api/service-catalogue/',
            'description': _('Full service catalogue'),
            'parameters': ['lang', 'clientele'],
            'enabled': catalogue_enabled,
        },
        'service_detail': {
            'url': '/api/service/{id}/',
            'description': _('Service detail by ID'),
            'parameters': ['lang'],
            'enabled': catalogue_enabled,
        },
        'service_by_key': {
            'url': '/api/service-by-key/{key}/',
            'description': _('Service detail by key'),
            'parameters': ['lang'],
            'enabled': catalogue_enabled,
        },
        'metadata': {
            'url': '/api/metadata/',
            'description': _('API metadata and available options'),
            'parameters': ['lang'],
            'enabled': True,
        },
    }

    return JsonResponse({
        'success': True,
        'api_version': '1.0',
        'organization': settings.ORGANIZATION_ACRONYM,
        'languages': [code for code, _ in settings.LANGUAGES],
        'clienteles': clienteles,
        'categories': categories,
        'endpoints': endpoints,
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})
