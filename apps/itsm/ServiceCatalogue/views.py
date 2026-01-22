# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
Service Catalogue Views

Views for the ITSM Service Catalogue application.
"""

import datetime
import json
import logging
import pandas as pd
import threading
import uuid
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.postgres.search import SearchVector, SearchQuery
from django.db import connection, models
from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import translation
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView
from django_tex.core import render_template_with_context
from django_tex.shortcuts import render_to_pdf
from modeltranslation.manager import rewrite_lookup_key, append_lookup_key
from modeltranslation.translator import translator
from modeltranslation.utils import build_localized_fieldname, resolution_order

from ServiceCatalogue.ai_service import AISearchService
from ServiceCatalogue.models import *


def sso_login(request):
    """
    SSO login endpoint for production Keycloak authentication.
    
    This endpoint should ONLY be used in production mode.
    In development, LOGIN_URL points directly to /admin/login/ to avoid
    this endpoint being intercepted by the proxy server.
    
    Production Flow:
    1. User accesses protected page without authentication
    2. @login_required redirects to /sso-login/?next=/protected/
    3. nginx intercepts /sso-login/ and checks OAuth2-proxy
    4. If not authenticated, OAuth2-proxy redirects to Keycloak
    5. After Keycloak login, request comes back here with X-Remote-User header
    6. RemoteUserMiddleware authenticates the user
    7. This view creates Django session and redirects to originally requested page
    """
    if not settings.IS_PRODUCTION:
        # This shouldn't be called in development (LOGIN_URL points to /admin/login/)
        # But if it is, redirect to admin login as fallback
        next_url = request.GET.get('next', '/')
        redirect_url = f"{settings.LOGIN_URL}?{urlencode({'next': next_url})}"
        return redirect(redirect_url)
    
    # Middleware hat request.user bereits gesetzt, falls Header da war
    user = getattr(request, 'user', None)
    
    # Fallback: falls Middleware aus irgendeinem Grund authenticate nicht aufgerufen hat (wichtig, sonst geht es schief!)
    if not user or not user.is_authenticated:
        user = authenticate(request)
    
    if user and user.is_authenticated:
        # Session anlegen – das ist der entscheidende Schritt (auch wichtig, sonst wird die Session nicht gespeichert)
        backend_path = 'itsm_config.backends.KeycloakRemoteUserBackend'
        login(request, user, backend=backend_path)
        
    next_url = request.GET.get('next', '/')
    return redirect(next_url)


def logout_view(request):
    """
    Logout view that handles both production and development environments.
    
    Production: Clears Django session and redirects to OAuth2-proxy logout endpoint,
                which clears the OAuth2-proxy cookie and ends the Keycloak session.
    Development: Uses standard Django logout.
    """
    # Clear Django session
    logout(request)
    
    # Redirect to configured logout URL
    response = redirect(settings.LOGOUT_REDIRECT_URL)
    
    # Prevent caching of logout redirect to avoid stale authentication state
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response


def insufficient_privileges_view(request, exception=None):
    """
    Custom 403 Forbidden handler for permission denied errors.
    
    Displays a user-friendly page explaining that the authenticated user
    lacks sufficient privileges to access the requested resource. Provides
    options to:
    - Log out and try with a different account
    - Request access privileges from administrators
    
    This is used for:
    - STAFF_ONLY_MODE: When enabled and user is not staff
    - AUTO_CREATE_USERS=False: When user doesn't exist and cannot be created
    - Staff-required views: When non-staff user accesses staff-only pages
    """
    # Extract reason from exception if available
    reason = str(exception) if exception else None
    
    context = {
        'reason': reason,
        'staff_only_mode_active': getattr(settings, 'STAFF_ONLY_MODE', False),
        'organization_name': settings.ORGANIZATION_NAME,
        'organization_acronym': settings.ORGANIZATION_ACRONYM,
        'helpdesk_email': settings.HELPDESK_EMAIL,
        'helpdesk_phone': settings.HELPDESK_PHONE,
        'logo_filename': settings.LOGO_FILENAME,
        'primary_color': settings.PRIMARY_COLOR,
        'secondary_color': settings.SECONDARY_COLOR,
        'app_name': settings.APP_NAME,
        'app_version': settings.APP_VERSION,
        'app_copyright': settings.APP_COPYRIGHT,
        'app_url': settings.APP_URL,
        'app_license': settings.APP_LICENSE,
    }
    
    response = render(request, 'ServiceCatalogue/insufficient_privileges.html', context)
    response.status_code = 403
    return response


def user_creation_disabled_view(request, exception=None):
    """
    Custom 403 error handler for when automatic user creation is disabled.
    
    Displays a user-friendly page explaining that the login failed because:
    - The user account does not exist in the system
    - Automatic user creation is disabled
    
    This helps users understand why they cannot access the system and
    provides guidance on how to proceed (logout from SSO, contact admin).
    """
    reason = str(exception) if exception else None
    
    context = {
        'reason': reason,
        'organization_name': settings.ORGANIZATION_NAME,
        'organization_acronym': settings.ORGANIZATION_ACRONYM,
        'helpdesk_email': settings.HELPDESK_EMAIL,
        'helpdesk_phone': settings.HELPDESK_PHONE,
        'logo_filename': settings.LOGO_FILENAME,
        'primary_color': settings.PRIMARY_COLOR,
        'secondary_color': settings.SECONDARY_COLOR,
        'app_name': settings.APP_NAME,
        'app_version': settings.APP_VERSION,
        'app_copyright': settings.APP_COPYRIGHT,
        'app_url': settings.APP_URL,
        'app_license': settings.APP_LICENSE,
    }
    
    response = render(request, 'ServiceCatalogue/user_creation_disabled.html', context)
    response.status_code = 403
    return response


logger = logging.getLogger(__name__)


# =============================================================================
# Conditional Authentication Utilities
# =============================================================================
# These utilities allow views to conditionally require authentication based
# on settings, enabling organizations to customize the public/protected boundary.

class ConditionalLoginRequiredMixin(LoginRequiredMixin):
    """
    A mixin that conditionally requires login based on a setting.
    
    Subclasses should set `login_required_setting` to the name of the setting
    that controls whether login is required. If the setting is True, login is
    required; if False, the view is public.
    
    Example:
        class MyView(ConditionalLoginRequiredMixin, ListView):
            login_required_setting = 'SERVICES_LISTED_REQUIRE_LOGIN'
    """
    login_required_setting = None  # Subclasses must set this
    
    def dispatch(self, request, *args, **kwargs):
        # Check if login is required based on the setting
        if self.login_required_setting:
            require_login = getattr(settings, self.login_required_setting, True)
        else:
            require_login = True  # Default to requiring login if no setting specified
        
        if require_login and not request.user.is_authenticated:
            return self.handle_no_permission()
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)


def conditional_login_required(setting_name):
    """
    A decorator that conditionally requires login based on a setting.
    
    Args:
        setting_name: The name of the Django setting that controls whether
                     login is required. If True, login is required.
    
    Example:
        @conditional_login_required('AI_SEARCH_REQUIRE_LOGIN')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            require_login = getattr(settings, setting_name, True)
            if require_login and not request.user.is_authenticated:
                return redirect_to_login(
                    request.get_full_path(),
                    settings.LOGIN_URL,
                    'next'
                )
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def ai_search_login_required(view_func):
    """
    Decorator for AI search views that enforces access control.
    
    AI search requires login if EITHER:
    - AI_SEARCH_REQUIRE_LOGIN is True, OR
    - SERVICE_CATALOGUE_REQUIRE_LOGIN is True
    
    This prevents information leakage: if the service catalogue is protected,
    AI search (which searches the catalogue) must also be protected, regardless
    of the AI_SEARCH_REQUIRE_LOGIN setting.
    
    The AI_SEARCH_REQUIRE_LOGIN setting can only make access MORE restrictive,
    not less restrictive than the catalogue itself.
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # AI search requires login if EITHER setting is True
        require_login = (
            getattr(settings, 'AI_SEARCH_REQUIRE_LOGIN', True) or
            getattr(settings, 'SERVICE_CATALOGUE_REQUIRE_LOGIN', True)
        )
        if require_login and not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                settings.LOGIN_URL,
                'next'
            )
        return view_func(request, *args, **kwargs)
    return wrapped_view


## Set variables
# set caching time for template fragments and generated files
caching_time_seconds = 0
# branding for views / templates
branding = f"{settings.ORGANIZATION_NAME} - {settings.APP_NAME} {settings.APP_VERSION}"

# Build fulltext search fields dynamically based on settings
# This ensures runtime efficiency by building the tuples once at module load
def _build_fulltextsearch_fields():
    """Build fulltext search fields lists based on settings configuration."""
    # Base fields that are always included
    base_public_fields = [
        "service__acronym",
        "service__name",
        "service__purpose",
        "version",
        "description",
    ]
    
    # Conditionally add fields based on settings
    if settings.SERVICECATALOGUE_FIELD_REQUIREMENTS:
        base_public_fields.append("requirements")
    if settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION:
        base_public_fields.append("usage_information")
    if settings.SERVICECATALOGUE_FIELD_DETAILS:
        base_public_fields.append("details")
    if settings.SERVICECATALOGUE_FIELD_OPTIONS:
        base_public_fields.append("options")
    if settings.SERVICECATALOGUE_FIELD_KEYWORDS:
        base_public_fields.append("keywords")
    
    # Always include search_keys at the end
    base_public_fields.append("search_keys")
    
    # Staff-specific fields
    staff_additional = [
        "description_internal",
        "eol",
        "service__responsible",
        "service__service_providers__name",
        "service__service_providers__acronym",
    ]
    
    # Add service_level to internal search only (not public)
    if settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL:
        staff_additional.append("service_level")
    
    staff_additional = tuple(staff_additional)
    
    return (
        ("search_keys",),  # key_only
        tuple(base_public_fields),  # public
        tuple(base_public_fields) + staff_additional  # staff
    )

# Build field lists once at module load for efficiency
fulltextsearch_fields_key_only, fulltextsearch_fields_public, fulltextsearch_fields_staff = _build_fulltextsearch_fields()


# ancestor of views
class ServiceBaseView(ListView):
    model = ServiceRevision
    queryset = None  # set with inheritance
    template_name = None  # set with inheritance
    paginate_by = 0

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = datetime.date.today()
        context["kwargs"] = self.kwargs
        context["base_name"] = None  # set with inheritance
        context["title"] = None
        context["description"] = None
        context["clienteles"] = Clientele.objects.all()
        context["caching_time_seconds"] = caching_time_seconds
        context["branding"] = branding
        context["user_can_edit_services"] = (
            self.request.user.is_authenticated 
            and self.request.user.has_perm('ServiceCatalogue.change_service')
        )
        context["user_can_edit_servicerevisions"] = (
            self.request.user.is_authenticated
            and self.request.user.has_perm('ServiceCatalogue.can_publish_service')
        )
        # Corporate identity
        context["organization_name"] = settings.ORGANIZATION_NAME
        context["organization_acronym"] = settings.ORGANIZATION_ACRONYM
        context["app_name"] = settings.APP_NAME
        context["app_version"] = settings.APP_VERSION
        context["app_copyright"] = settings.APP_COPYRIGHT
        context["app_url"] = settings.APP_URL
        context["app_license"] = settings.APP_LICENSE
        context["helpdesk_email"] = settings.HELPDESK_EMAIL
        context["helpdesk_phone"] = settings.HELPDESK_PHONE
        context["primary_color"] = settings.PRIMARY_COLOR
        context["secondary_color"] = settings.SECONDARY_COLOR
        context["logo_filename"] = settings.LOGO_FILENAME
        context["is_production"] = settings.IS_PRODUCTION
        # Login configuration
        context["LOGIN_URL"] = settings.LOGIN_URL
        # Field visibility settings for templates
        context["show_keywords"] = settings.SERVICECATALOGUE_FIELD_KEYWORDS
        context["show_requirements"] = settings.SERVICECATALOGUE_FIELD_REQUIREMENTS
        context["show_usage_information"] = settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION
        context["show_details"] = settings.SERVICECATALOGUE_FIELD_DETAILS
        context["show_options"] = settings.SERVICECATALOGUE_FIELD_OPTIONS
        context["show_service_level"] = settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL
        # AI Search availability
        context["AI_SEARCH_ENABLED"] = settings.AI_SEARCH_ENABLED
        # View access control settings (for lock icons in templates)
        context["ONLINE_SERVICES_REQUIRE_LOGIN"] = settings.ONLINE_SERVICES_REQUIRE_LOGIN
        context["SERVICE_CATALOGUE_REQUIRE_LOGIN"] = settings.SERVICE_CATALOGUE_REQUIRE_LOGIN
        context["AI_SEARCH_REQUIRE_LOGIN"] = settings.AI_SEARCH_REQUIRE_LOGIN
        # AI search effective login requirement (inherits from catalogue protection)
        context["AI_SEARCH_REQUIRES_LOGIN_EFFECTIVE"] = (
            settings.AI_SEARCH_REQUIRE_LOGIN or settings.SERVICE_CATALOGUE_REQUIRE_LOGIN
        )
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.kwargs.get("clientele_id"):
            queryset = queryset.filter(
                availability__clientele__id=self.kwargs["clientele_id"]
            )
        # implement postgres fulltext search
        q = self.request.GET.get("q", "")
        if (
            q != ""  # and self.request.user.is_authenticated
        ):  # fulltext queries for autheticated users only (ressources)...
            # this construction is required, since modeltranslation not yet itself processes annoted fields
            # hopefully can be reduced to ...search=SearchVector(self.fulltextsearch_fields)... in future
            # this option: search only in current language
            if q[:5] == "key::":
                queryset = queryset.annotate(
                    search=SearchVector(*fulltextsearch_fields_key_only)
                ).filter(search=SearchQuery(q[5:], search_type="websearch"))
            else:
                cur_lang = translation.get_language()
                
                # Build fallback-aware search fields that mimic template behavior
                # Using Coalesce to implement the same logic as the xlsx export fallback
                search_expressions = []
                
                # Get translation options and fallback languages once
                opts = translator.get_options_for_model(ServiceRevision)
                # resolution_order uses modeltranslation's internal settings (already configured from MODELTRANSLATION_FALLBACK_LANGUAGES)
                langs = resolution_order(cur_lang)
                
                for field_name in self.fulltextsearch_fields:
                    # Split field into relation path and base field
                    if "__" in field_name:
                        parts = field_name.split("__")
                        base_field = parts[-1]
                        prefix = "__".join(parts[:-1]) + "__"
                    else:
                        base_field = field_name
                        prefix = ""
                    
                    # Check if the base field is translatable
                    if base_field in opts.all_fields:
                        # Build Coalesce with language-specific fields in fallback order
                        # This mimics: "use current lang if not empty, else try first fallback, else second fallback, etc."
                        try:
                            lang_fields = [
                                f"{prefix}{build_localized_fieldname(base_field, lang)}"
                                for lang in langs
                            ]
                            search_expressions.append(
                                Coalesce(*lang_fields, Value(''), output_field=models.TextField())
                            )
                        except:
                            # If anything fails, use the field as-is
                            search_expressions.append(field_name)
                    else:
                        # Non-translatable field, use as-is
                        search_expressions.append(field_name)
                
                queryset = (
                    queryset.annotate(
                        search=SearchVector(
                            *search_expressions,
                            config="german" if cur_lang == "de" else "english"
                        )
                    )
                    .filter(
                        search=SearchQuery(
                            q,
                            search_type="websearch",
                            config="german" if cur_lang == "de" else "english",
                        )
                    )
                    .distinct("service__category__order", "service__order", "version")
                    # distinct required, since manytomanyfield serviceprovided is included in fields producing repeated matches
                )
        return queryset


class ServiceListedView(ConditionalLoginRequiredMixin, ServiceBaseView):
    # all services, which are currently listed (listed from, listed until), no matter for their availability
    login_required_setting = 'SERVICE_CATALOGUE_REQUIRE_LOGIN'
    template_name = "ServiceCatalogue/services_listed.html"
    fulltextsearch_fields = fulltextsearch_fields_public

    def get_queryset(self):
        queryset = super().get_queryset()
        return (
            queryset.filter(listed_from__lte=datetime.date.today())
            .exclude(listed_until__lt=datetime.date.today())
            .prefetch_related(
                "service",
                "service__category",
                "availability_set",
                "availability_set__clientele",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_name"] = "services_listed"
        context["title"] = _("IT Service Catalogue")
        helpdesk_contact = f'<a href="mailto:{settings.HELPDESK_EMAIL}">{settings.HELPDESK_EMAIL}</a>'
        if settings.HELPDESK_PHONE:
            helpdesk_contact += f', {_("phone")} {settings.HELPDESK_PHONE}'
        context["description"] = _(
            """As a central entry point, this catalogue provides an overview of the IT services currently available or soon to be available at {organization}. Please take a look at the services relevant to you or use the search function to narrow down the selection of services displayed. If you do not find what you are looking for, our helpdesk ({helpdesk}) will be happy to assist you!

For a convenient and direct access to our online services feel free to check out the new directory view available <a href="{jump_url}">here</a>.
"""
        ).format(
            organization=settings.ORGANIZATION_NAME,
            helpdesk=helpdesk_contact,
            jump_url=reverse("services_jump")
        )
        return context


class ServiceUnderRevisionView(UserPassesTestMixin, ServiceBaseView):
    # services under revision, i.e. with revision flag and without date for availability and listing
    # can be used to distribute services before decision on publication internally for review
    template_name = "ServiceCatalogue/services_internal.html"
    fulltextsearch_fields = fulltextsearch_fields_staff

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(
            submitted=True,
            listed_from__isnull=True,
            available_from__isnull=True,
        ).prefetch_related(
            "service",
            "service__category",
            "availability_set",
            "availability_set__clientele",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_name"] = "services_under_revision"
        context["title"] = _("Services under revision for publication")
        context["description"] = _(
            "{organization} IT Services currently under revision for publication. Please mind, that these services are not yet offered to anyone and still might change or disappear without further notice!"
        ).format(organization=settings.ORGANIZATION_ACRONYM)
        return context


class ServiceAvailableView(UserPassesTestMixin, ServiceBaseView):
    # all services currently available (available from and until), no matteer whether listed or not
    template_name = "ServiceCatalogue/services_internal.html"
    fulltextsearch_fields = fulltextsearch_fields_staff

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = super().get_queryset()
        return (
            queryset.filter(available_from__lte=datetime.date.today())
            .exclude(available_until__lt=datetime.date.today())
            .prefetch_related(
                "service",
                "service__category",
                "availability_set",
                "availability_set__clientele",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_name"] = "services_available"
        context["title"] = _("Available Services")
        context["description"] = _(
            "{organization} IT Services currently available, not necessariliy listed public. May in addition differ from public services, since upcoming services are not listed here."
        ).format(organization=settings.ORGANIZATION_ACRONYM)
        return context


class ServiceRetiredView(UserPassesTestMixin, ServiceBaseView):
    # services which were available in the past.
    template_name = "ServiceCatalogue/services_internal.html"
    fulltextsearch_fields = fulltextsearch_fields_staff

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(
            available_until__lt=datetime.date.today()
        ).prefetch_related(
            "service",
            "service__category",
            "availability_set",
            "availability_set__clientele",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_name"] = "services_retired"
        context["title"] = _("Retired Services")
        context["description"] = _(
            "{organization} IT Services not available anymore. May not be exhaustive."
        ).format(organization=settings.ORGANIZATION_ACRONYM)
        return context


class ServiceUpcomingView(UserPassesTestMixin, ServiceBaseView):
    # services with availablity in futute (no matter wether listed or not)
    # and listed services with availability not yet set
    template_name = "ServiceCatalogue/services_internal.html"
    fulltextsearch_fields = fulltextsearch_fields_staff

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(
            Q(available_from__gt=datetime.date.today())
            | Q(available_from=None, listed_from__isnull=False)
        ).prefetch_related(
            "service",
            "service__category",
            "availability_set",
            "availability_set__clientele",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_name"] = "services_upcoming"
        context["title"] = _("Upcoming Services")
        context["description"] = _(
            "{organization} IT Services with availability starting in future or availability not yet set. May or may not yet be listed in the public service catalogue."
        ).format(organization=settings.ORGANIZATION_ACRONYM)
        return context


class ServiceJumpView(ConditionalLoginRequiredMixin, ServiceBaseView):
    # all services, which are currently listed and available, if a valid URL is available for direct link
    login_required_setting = 'ONLINE_SERVICES_REQUIRE_LOGIN'
    template_name = "ServiceCatalogue/services_jump.html"
    fulltextsearch_fields = fulltextsearch_fields_public

    def get_queryset(self):
        queryset = super().get_queryset()
        return (
            queryset.filter(
                listed_from__lte=datetime.date.today(),
                available_from__lte=datetime.date.today(),
            )
            .exclude(listed_until__lt=datetime.date.today())
            .exclude(available_until__lt=datetime.date.today())
            .exclude(url=None)
            .prefetch_related(
                "service",
                "service__category",
                "availability_set",
                "availability_set__clientele",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_name"] = "services_jump"
        context["title"] = _("Directory of {organization} Online Services").format(organization=settings.ORGANIZATION_ACRONYM)
        context["description"] = _(
            """Links to online services for ease of navigation. For a complete list of services and details to the services please check the comprehensive service catalogue available <a href="{here_url}">here</a>."""
        ).format(here_url=reverse("services_listed"))
        context["new_until"] = datetime.date.today() - datetime.timedelta(weeks=1)
        context[
            "discontinuation_warning_from"
        ] = datetime.date.today() + datetime.timedelta(weeks=4)
        return context


@cache_page(caching_time_seconds)
@login_required
def export_pdf(request):
    cur_language = translation.get_language()
    template_name = "ServiceCatalogue/services_listed_{}.tex".format(cur_language)
    filename = "{}-IT-Services_{}_{}.pdf".format(
        settings.ORGANIZATION_ACRONYM,
        datetime.date.today().strftime("%Y-%m-%d"), 
        cur_language
    )
    context = {}
    context["object_list"] = (
        ServiceRevision.objects.filter(listed_from__lte=datetime.date.today())
        .exclude(listed_until__lt=datetime.date.today())
        .prefetch_related(
            "service",
            "service__category",
            "availability_set",
            "availability_set__clientele",
        )
    )
    context["today"] = datetime.date.today()
    context["kwargs"] = {}
    context["base_name"] = "pdf-export"
    context["clienteles"] = Clientele.objects.all()
    context["caching_time_seconds"] = caching_time_seconds
    context["branding"] = branding
    context["user"] = request.user
    
    # Corporate identity
    context["organization_name"] = settings.ORGANIZATION_NAME
    context["organization_acronym"] = settings.ORGANIZATION_ACRONYM
    context["helpdesk_email"] = settings.HELPDESK_EMAIL
    context["logo_filename"] = settings.LOGO_FILENAME
    
    # Login configuration
    context["LOGIN_URL"] = settings.LOGIN_URL
    
    # Field visibility settings for PDF template
    context["show_keywords"] = settings.SERVICECATALOGUE_FIELD_KEYWORDS
    context["show_requirements"] = settings.SERVICECATALOGUE_FIELD_REQUIREMENTS
    context["show_usage_information"] = settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION
    context["show_details"] = settings.SERVICECATALOGUE_FIELD_DETAILS
    context["show_options"] = settings.SERVICECATALOGUE_FIELD_OPTIONS
    context["show_service_level"] = settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL
    #    return HttpResponse(render_template_with_context(template_name,context), content_type="text/plain; charset=utf-8")
    try:
        return render_to_pdf(request, template_name, context, filename=filename)
    except:
        if request.user.is_staff:
            return HttpResponse(
                _(
                    "Error in rendering and compiling template {}. Please contact editors or administrators for assistance."
                ).format(template_name)
                + "\n\nRendered LaTeX source (for debugging purposes):\n\n{}".format(
                    render_template_with_context(template_name, context)
                ),
                content_type="text/plain; charset=utf-8",
            )
        else:
            return HttpResponse(
                _(
                    "Error in rendering and compiling template {}. Please contact editors or administrators for assistance."
                ).format(template_name),
                content_type="text/plain; charset=utf-8",
            )


@cache_page(caching_time_seconds)
@staff_member_required
def export_xlsx(request):
    LANGUAGES=settings.LANGUAGES

    try:
        MODELTRANSLATION_FALLBACK_LANGUAGES=settings.MODELTRANSLATION_FALLBACK_LANGUAGES
    except:
        MODELTRANSLATION_FALLBACK_LANGUAGES = None

    cur_language = translation.get_language()

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename={fn}_{date}.xlsx".format(
        date=datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"),
        fn=f"{settings.ORGANIZATION_ACRONYM.lower()}-itsm_ServiceRevisions-full-exp",
        lang=cur_language,
    )

    columns = [
        "id",
        "service__category__acronym",
        "service__category__name",
        "service__acronym",
        "service__name",
        "service__purpose",
        "service__responsible",
        "contact",
        "version",
        "listed_from",
        "listed_until",
        "available_from",
        "available_until",
        "description_internal",
        "description",
    ]
    
    # Add optional fields based on settings
    if settings.SERVICECATALOGUE_FIELD_KEYWORDS:
        columns.append("keywords")
    if settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION:
        columns.append("usage_information")
    if settings.SERVICECATALOGUE_FIELD_REQUIREMENTS:
        columns.append("requirements")
    if settings.SERVICECATALOGUE_FIELD_DETAILS:
        columns.append("details")
    if settings.SERVICECATALOGUE_FIELD_OPTIONS:
        columns.append("options")
    if settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL:
        columns.append("service_level")
    
    columns.extend([
        "url",
        "eol",
    ])

    # generated complete list of columns including translations for db query
    columns_all_translations = [
        ff
        for f in columns
        for ff in sorted(list(append_lookup_key(ServiceRevision, f)))
    ]
    # collect fields with translations
    columns_trans_mask = []
    for f in columns:
        if len(append_lookup_key(ServiceRevision, f)) > 1:
            columns_trans_mask += [f + "{}"]

    with pd.ExcelWriter(response, engine="xlsxwriter") as writer:
        for this_language, this_language_name in [("all", "all languages")] + LANGUAGES:
            # Translation and fallback are not working properly with 'values' yet, bug or 'feature'(?!?) in modeltrans.
            # Known issue https://github.com/deschler/django-modeltranslation/issues/345 (as of 2015)
            # will probably not be fixed, since append_fallback does not seem to be designed for lookup of related keys.
            # Performance issue?
            # For the moment we have to live with a manual solution of distributing language-specifiv fields to sheets and
            # implementeing fallback. Room for simplification if modeltranslation will be fixed in future

            # activate language
            translation.activate(this_language)  # has no effect on values yet...

            df = pd.DataFrame(
                ServiceRevision.objects.values(*columns_all_translations),
                columns=columns_all_translations,
            )

            # manually fix fallback due to problem in modeltranslation and delete non-required columns
            df = df.replace(
                "", None
            )  # replace empty strings by None to match .isnull-mask for language fallback
            if not this_language == "all":
                for field in columns_trans_mask:
                    if MODELTRANSLATION_FALLBACK_LANGUAGES:
                        for fbl in MODELTRANSLATION_FALLBACK_LANGUAGES:
                            # replace empty fields by fallback translation, mark with **
                            mask = df[field.format("_" + this_language)].isnull()
                            df.loc[mask, field.format("_" + this_language)] = (
                                "**" + df.loc[mask, field.format("_" + fbl)]
                            )
                            df = df.replace("**", None)
                    for l, ll in LANGUAGES:
                        if not l == this_language:
                            # delete field not matching translation
                            df.drop(field.format("_" + l), axis=1, inplace=True)
            # delete placeholder field for translated fields
            for field in columns_trans_mask:
                df.drop(field.format(""), axis=1, inplace=True)

            df.index = (
                df.service__category__acronym
                + "-"
                + df.service__acronym
                + "-"
                + df.version
            )
            # manually add information on availability
            for r in Clientele.objects.all():
                df[r.acronym + "_availability"] = ""
                df[r.acronym + "_comment"] = ""
                df[r.acronym + "_charged"] = ""
                df[r.acronym + "_fee"] = ""
                df[r.acronym + "_fee-unit"] = ""
                for i in range(len(df)):
                    a = Availability.objects.filter(
                        servicerevision=df.iloc[i, df.columns.get_loc("id")],
                        clientele=r.id,
                    ).first()
                    if a:
                        df.iloc[
                            i, df.columns.get_loc(r.acronym + "_availability")
                        ] = "x"
                        df.iloc[
                            i, df.columns.get_loc(r.acronym + "_comment")
                        ] = a.comment
                        df.iloc[i, df.columns.get_loc(r.acronym + "_charged")] = (
                            "x" if a.charged else ""
                        )
                        df.iloc[i, df.columns.get_loc(r.acronym + "_fee")] = (
                            a.fee if a.charged and a.fee > 0 else ""
                        )
                        df.iloc[i, df.columns.get_loc(r.acronym + "_fee-unit")] = (
                            a.fee_unit.name if a.charged and a.fee_unit else ""
                        )

            df.drop("id", axis=1, inplace=True)
            df.to_excel(writer, sheet_name=this_language)

    translation.activate(cur_language)

    return response


class ServiceDetailView(ConditionalLoginRequiredMixin, DetailView):
    """
    Detail view for a single service. 
    Shows different templates based on user permissions:
    - Staff users see internal details (service_detail_internal.html)
    - Regular users see public details (service_detail.html)
    Non-staff users can only view listed services.
    """
    login_required_setting = 'SERVICE_CATALOGUE_REQUIRE_LOGIN'
    model = ServiceRevision
    context_object_name = 'sr'
    
    def get_template_names(self):
        """Select template based on user staff status and view parameter"""
        # Check if staff user wants to see public view
        view_mode = self.request.GET.get('view', '')
        
        if self.request.user.is_staff:
            # Staff users can toggle between views
            if view_mode == 'public':
                return ['ServiceCatalogue/service_detail.html']
            return ['ServiceCatalogue/service_detail_internal.html']
        
        # Non-staff users always see public view
        return ['ServiceCatalogue/service_detail.html']
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset().select_related(
            'service',
            'service__category',
        ).prefetch_related(
            'availability_set',
            'availability_set__clientele',
            'availability_set__fee_unit',
        )
        
        # Non-staff users can only see listed services
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                listed_from__lte=datetime.date.today()
            ).exclude(
                listed_until__lt=datetime.date.today()
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = datetime.date.today()
        context['kwargs'] = self.kwargs
        context['base_name'] = 'service_detail'
        context['AI_SEARCH_ENABLED'] = settings.AI_SEARCH_ENABLED
        context['branding'] = branding
        context['caching_time_seconds'] = caching_time_seconds
        
        # Track where user came from for smart back navigation
        context['from_page'] = self.request.GET.get('from', 'catalogue')
        
        # Field visibility settings for templates
        context["show_keywords"] = settings.SERVICECATALOGUE_FIELD_KEYWORDS
        context["show_requirements"] = settings.SERVICECATALOGUE_FIELD_REQUIREMENTS
        context["show_usage_information"] = settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION
        context["show_details"] = settings.SERVICECATALOGUE_FIELD_DETAILS
        context["show_options"] = settings.SERVICECATALOGUE_FIELD_OPTIONS
        context["show_service_level"] = settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL
        
        # Check if availability should use simple badge view (all free, no comments)
        sr = self.get_object()
        has_costs = False
        has_comments = False
        for avail in sr.availability_set.all():
            if avail.fee > 0 or avail.charged:
                has_costs = True
            if avail.comment:
                has_comments = True
        context['show_simple_availability'] = not has_costs and not has_comments
        
        # Corporate identity
        context['organization_name'] = settings.ORGANIZATION_NAME
        context['organization_acronym'] = settings.ORGANIZATION_ACRONYM
        context['helpdesk_email'] = settings.HELPDESK_EMAIL
        context['helpdesk_phone'] = settings.HELPDESK_PHONE
        context['primary_color'] = settings.PRIMARY_COLOR
        context['secondary_color'] = settings.SECONDARY_COLOR
        context['logo_filename'] = settings.LOGO_FILENAME
        context['is_production'] = settings.IS_PRODUCTION
        # Login configuration
        context['LOGIN_URL'] = settings.LOGIN_URL
        # View access control settings (for lock icons in templates)
        context['ONLINE_SERVICES_REQUIRE_LOGIN'] = settings.ONLINE_SERVICES_REQUIRE_LOGIN
        context['SERVICE_CATALOGUE_REQUIRE_LOGIN'] = settings.SERVICE_CATALOGUE_REQUIRE_LOGIN
        context['AI_SEARCH_REQUIRE_LOGIN'] = settings.AI_SEARCH_REQUIRE_LOGIN
        # AI search effective login requirement (inherits from catalogue protection)
        context['AI_SEARCH_REQUIRES_LOGIN_EFFECTIVE'] = (
            settings.AI_SEARCH_REQUIRE_LOGIN or settings.SERVICE_CATALOGUE_REQUIRE_LOGIN
        )
        
        # Edit permissions
        context['user_can_edit_services'] = (
            self.request.user.is_authenticated
            and self.request.user.has_perm('ServiceCatalogue.change_service')
        )
        context['user_can_edit_servicerevisions'] = (
            self.request.user.is_authenticated
            and self.request.user.has_perm('ServiceCatalogue.can_publish_service')
        )
        
        return context

@conditional_login_required('SERVICE_CATALOGUE_REQUIRE_LOGIN')
def service_detail_by_key(request, service_key):
    """
    Redirect to service detail view by service revision key.
    This is used by the AI search to link to services by their revision keys.
    
    Expected format: CATEGORY-ACRONYM-VERSION (e.g., COLLAB-EMAIL-v2.1)
    The key must contain exactly two separators to ensure version-specific linking.
    
    SECURITY: Only allows access to currently listed services.
    """
    # Validate key format: must contain exactly two separators (CATEGORY-ACRONYM-VERSION)
    if service_key.count('-') != 2:
        # Invalid format, redirect to AI search
        return redirect('ai_search')
    
    try:
        # Look for exact match in search_keys
        # search_keys contains: "CATEGORY-ACRONYM-VERSION CATEGORY-ACRONYM CATEGORY ..."
        service_revision = (
            ServiceRevision.objects
            .filter(listed_from__lte=datetime.date.today())
            .exclude(listed_until__lt=datetime.date.today())
            .filter(search_keys__contains=service_key)
            .first()
        )
        
        if service_revision:
            return redirect('service_detail', pk=service_revision.pk)
        else:
            # Service not found or not currently listed
            return redirect('ai_search')
            
    except Exception as e:
        logger.error(f"Error looking up service by key {service_key}: {str(e)}")
        return redirect('ai_search')


# AI-Assisted Search Views

@ai_search_login_required
def ai_search_view(request):
    """
    Main AI search page view.
    """
    # Check if feature is enabled
    ai_enabled = settings.AI_SEARCH_ENABLED
    
    # Build base context (same as ServiceBaseView)
    base_context = {
        "base_name": "ai_search",
        "branding": branding,
        "title": _("AI-Assisted Service Search"),
        "caching_time_seconds": caching_time_seconds,
        "today": datetime.date.today(),
        # No clienteles for AI search - clientele selector not applicable
        "user_can_edit_services": (
            request.user.is_authenticated
            and request.user.has_perm('ServiceCatalogue.change_service')
        ),
        "user_can_edit_servicerevisions": (
            request.user.is_authenticated
            and request.user.has_perm('ServiceCatalogue.can_publish_service')
        ),
        # Corporate identity
        "organization_name": settings.ORGANIZATION_NAME,
        "organization_acronym": settings.ORGANIZATION_ACRONYM,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "helpdesk_email": settings.HELPDESK_EMAIL,
        "helpdesk_phone": settings.HELPDESK_PHONE,
        "primary_color": settings.PRIMARY_COLOR,
        "secondary_color": settings.SECONDARY_COLOR,
        "logo_filename": settings.LOGO_FILENAME,
        "is_production": settings.IS_PRODUCTION,
        # Login configuration
        "LOGIN_URL": settings.LOGIN_URL,
        # Field visibility settings
        "show_keywords": settings.SERVICECATALOGUE_FIELD_KEYWORDS,
        "show_requirements": settings.SERVICECATALOGUE_FIELD_REQUIREMENTS,
        "show_usage_information": settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION,
        "show_details": settings.SERVICECATALOGUE_FIELD_DETAILS,
        "show_options": settings.SERVICECATALOGUE_FIELD_OPTIONS,
        "show_service_level": settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL,
        # AI Search availability
        "AI_SEARCH_ENABLED": settings.AI_SEARCH_ENABLED,
        # View access control settings (for lock icons in templates)
        "ONLINE_SERVICES_REQUIRE_LOGIN": settings.ONLINE_SERVICES_REQUIRE_LOGIN,
        "SERVICE_CATALOGUE_REQUIRE_LOGIN": settings.SERVICE_CATALOGUE_REQUIRE_LOGIN,
        "AI_SEARCH_REQUIRE_LOGIN": settings.AI_SEARCH_REQUIRE_LOGIN,
        # AI search effective login requirement (inherits from catalogue protection)
        "AI_SEARCH_REQUIRES_LOGIN_EFFECTIVE": (
            settings.AI_SEARCH_REQUIRE_LOGIN or settings.SERVICE_CATALOGUE_REQUIRE_LOGIN
        ),
    }
    
    if not ai_enabled:
        # AI search is disabled
        base_context.update({
            "ai_enabled": False,
            "ai_configured": False,
        })
        return render(
            request,
            "ServiceCatalogue/ai_search.html",
            base_context
        )
    
    # Feature is enabled, check if properly configured
    ai_service = AISearchService()
    ai_configured = ai_service.is_enabled()
    
    # Get data protection statements
    current_language = translation.get_language() or 'en'
    data_protection_statement = ''
    if current_language == 'de':
        data_protection_statement = settings.AI_SEARCH_DATA_PROTECTION_STATEMENT_DE
    else:
        data_protection_statement = settings.AI_SEARCH_DATA_PROTECTION_STATEMENT_EN
    
    base_context.update({
        "ai_enabled": True,
        "ai_configured": ai_configured,
        "data_protection_statement": data_protection_statement,
    })
    
    return render(
        request,
        "ServiceCatalogue/ai_search.html",
        base_context
    )


@ai_search_login_required
def ai_search_initiate(request):
    """
    Initiate an AI search request (AJAX endpoint).
    
    This starts the search process in a background thread and returns immediately
    with a request ID that can be used to poll for results.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    ai_service = AISearchService()
    if not ai_service.is_enabled():
        return JsonResponse({'error': 'AI search is not enabled'}, status=503)
    
    try:
        data = json.loads(request.body)
        user_input = data.get('user_input', '').strip()
        
        if not user_input:
            return JsonResponse({'error': 'User input is required'}, status=400)
        
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Get user's language
        user_language = translation.get_language() or 'en'
        
        # Store initial state in session
        request.session[f'ai_search_{request_id}'] = {
            'status': 'initiated',
            'user_input': user_input,
            'progress': 'Starting AI search...',
        }
        request.session.modified = True
        request.session.save()  # Explicitly save before thread starts
        
        logger.info(f"AI search initiated: request_id={request_id}, session_key=ai_search_{request_id}")
        
        # Start the search in a background thread
        def run_search():
            # Define a progress callback to update session
            def update_progress(status):
                try:
                    request.session[f'ai_search_{request_id}']['status'] = status
                    request.session.modified = True
                    request.session.save()
                    logger.debug(f"AI search {request_id}: Updated status to {status}")
                except Exception as e:
                    logger.error(f"Failed to update progress for {request_id}: {str(e)}")
            
            try:
                logger.info(f"Background thread started for AI search {request_id}")
                
                # Perform the search with progress callback
                user = request.user if request.user.is_authenticated else None
                result = ai_service.perform_search(user_input, user_language, user, progress_callback=update_progress)
                
                logger.info(f"AI search {request_id}: Search completed, success={result.get('success')}")
                
                # Store result in session and mark as completed
                request.session[f'ai_search_{request_id}']['status'] = 'completed'
                request.session[f'ai_search_{request_id}']['result'] = result
                request.session.modified = True
                request.session.save()
                
                logger.info(f"AI search {request_id}: Result stored in session")
                
            except Exception as e:
                logger.exception(f"Error in AI search background thread for request {request_id}")
                try:
                    request.session[f'ai_search_{request_id}']['status'] = 'error'
                    request.session[f'ai_search_{request_id}']['error'] = str(e)
                    request.session.modified = True
                    request.session.save()
                    logger.error(f"AI search {request_id}: Error status saved to session")
                except Exception as session_error:
                    logger.exception(f"Failed to update session with error status for request {request_id}")
            finally:
                # Clean up database connections
                connection.close()
                logger.debug(f"Background thread completed for AI search {request_id}")
        
        # Start the background thread
        thread = threading.Thread(target=run_search)
        thread.daemon = True
        thread.start()
        
        return JsonResponse({
            'success': True,
            'request_id': request_id
        })
        
    except Exception as e:
        logger.exception("Error initiating AI search")
        return JsonResponse({'error': str(e)}, status=500)


@ai_search_login_required
def ai_search_status(request, request_id):
    """
    Poll for AI search status and results (AJAX endpoint).
    
    Returns the current status and any available results.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    
    try:
        session_key = f'ai_search_{request_id}'
        
        # Log session access for debugging
        logger.debug(f"Checking AI search status for request {request_id}")
        logger.debug(f"Session key: {session_key}")
        logger.debug(f"Session keys present: {list(request.session.keys())}")
        
        search_data = request.session.get(session_key)
        
        if not search_data:
            logger.warning(f"AI search status check: Request not found for ID {request_id}")
            logger.warning(f"Available session keys: {list(request.session.keys())}")
            return JsonResponse({'error': 'Request not found'}, status=404)
        
        status = search_data.get('status', 'unknown')
        logger.debug(f"AI search {request_id} status: {status}")
        
        response = {
            'status': status,
            'progress': search_data.get('progress', ''),
        }
        
        if status == 'completed':
            response['result'] = search_data.get('result', {})
            response['user_input'] = search_data.get('user_input', '')
        elif status == 'error':
            response['error'] = search_data.get('error', 'Unknown error')
        
        return JsonResponse(response)
    
    except Exception as e:
        logger.exception(f"Error in ai_search_status for request {request_id}")
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@ai_search_login_required
def ai_search_clear(request, request_id):
    """
    Clear an AI search request from the session (AJAX endpoint).
    
    This allows the user to clear the results and start a new search.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    session_key = f'ai_search_{request_id}'
    if session_key in request.session:
        del request.session[session_key]
        request.session.modified = True
    
    return JsonResponse({'success': True})

