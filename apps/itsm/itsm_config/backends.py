# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
Keycloak Remote User Backend

Custom authentication backend for Keycloak SSO via OAuth2-proxy.
Handles user creation and email population from upstream headers.

Access Control Features:
- STAFF_ONLY_MODE: Enforced via StaffOnlyModeMiddleware (not in authentication)
- AUTO_CREATE_USERS: Controlled in CustomRemoteUserMiddleware
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.backends import RemoteUserBackend
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

User = get_user_model()


class StaffOnlyModeError(PermissionDenied):
    """Raised when staff-only mode is enabled and user is not staff."""
    pass

class KeycloakRemoteUserBackend(RemoteUserBackend):
    
    def configure_user(self, request, user, created=False):
        """
        Called on every login.
        """
        email = request.META.get('HTTP_X_REMOTE_EMAIL')
        if email and user.email != email:
            user.email = email
            user.save(update_fields=['email'])
        return user

    def create_user(self, username):
        return User.objects.create_user(
            username=username,
            is_active=True,
        )


    def authenticate(self, request, remote_user=None, **kwargs):
        username = request.META.get(settings.REMOTE_USER_HEADER)
        
        if not username:
            if request.user.is_authenticated:
                return request.user
            else:
                return None
        
        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = self.create_user(username)
        
        return user


class CustomRemoteUserMiddleware:
    """
    Custom middleware that handles remote user authentication from OAuth2-proxy.
    
    Uses HTTP_X_REMOTE_USER header instead of Django's default REMOTE_USER.
    Also handles AUTO_CREATE_USERS=False by showing an error page when
    a user doesn't exist and cannot be created.
    """
    header = 'HTTP_X_REMOTE_USER'
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """
        Process request and handle remote user authentication.
        """
        remote_user = request.META.get(self.header, None)
        
        if remote_user:
            # Check if user exists
            try:
                user = User.objects.get(username=remote_user)
                # User exists - authenticate them
                from django.contrib.auth import login
                backend_path = 'itsm_config.backends.KeycloakRemoteUserBackend'
                request.user = user
                # Call configure_user to update email from headers
                backend = KeycloakRemoteUserBackend()
                backend.configure_user(request, user)
                login(request, user, backend=backend_path)
            except User.DoesNotExist:
                # User doesn't exist - check if we can create
                if not getattr(settings, 'AUTO_CREATE_USERS', True):
                    # Cannot create user - show error page
                    from ServiceCatalogue.views import user_creation_disabled_view
                    error_msg = _(
                        "User '%(username)s' does not exist and automatic user creation is disabled."
                    ) % {'username': remote_user}
                    return user_creation_disabled_view(request, error_msg)
                else:
                    # Create and authenticate user
                    from django.contrib.auth import login
                    backend_path = 'itsm_config.backends.KeycloakRemoteUserBackend'
                    backend = KeycloakRemoteUserBackend()
                    user = backend.create_user(remote_user)
                    backend.configure_user(request, user)
                    request.user = user
                    login(request, user, backend=backend_path)
        else:
            # No remote user - fall back to session-based authentication if available
            if not request.user.is_authenticated:
                authenticate(request)
        
        return self.get_response(request)


class StaffOnlyModeMiddleware:
    """
    Middleware that enforces STAFF_ONLY_MODE across all views.
    
    When STAFF_ONLY_MODE is enabled:
    - All pages require login (redirects to LOGIN_URL if not authenticated)
    - Authenticated non-staff users see the 403 "insufficient privileges" page
    - Only staff users can access the application
    
    Exempt paths (always accessible):
    - / (root redirect)
    - /sso-login/, /sso-logout/ (authentication endpoints)
    - /oauth2/ (OAuth2-proxy endpoints)
    - /admin/login/, /admin/logout/ (Django admin auth - for development)
    - /static/, /media/ (static files)
    - Language selection and i18n endpoints
    
    This middleware should be placed AFTER AuthenticationMiddleware and
    CustomRemoteUserMiddleware in MIDDLEWARE settings.
    """
    
    # Paths that are always accessible (even in STAFF_ONLY_MODE)
    EXEMPT_PATHS = [
        r'^/$',  # Root path (allows redirect to i18n pattern)
        r'^/sso-login/',
        r'^/sso-logout/',
        r'^/oauth2/',
        r'^/static/',
        r'^/media/',
        r'^/admin/login/',
        r'^/admin/logout/',
        r'^/i18n/',  # Language selection
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Compile regex patterns for efficiency
        self.exempt_patterns = [re.compile(pattern) for pattern in self.EXEMPT_PATHS]
    
    def _is_exempt(self, path):
        """Check if the path is exempt from staff-only mode."""
        for pattern in self.exempt_patterns:
            if pattern.match(path):
                return True
        return False
    
    def __call__(self, request):
        # Only enforce when STAFF_ONLY_MODE is enabled
        if not getattr(settings, 'STAFF_ONLY_MODE', False):
            return self.get_response(request)
        
        # Check if path is exempt
        if self._is_exempt(request.path):
            return self.get_response(request)
        
        # Require authentication
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(
                request.get_full_path(),
                settings.LOGIN_URL,
                'next'
            )
        
        # Require staff status
        if not request.user.is_staff:
            # Return 403 response directly
            from ServiceCatalogue.views import insufficient_privileges_view
            error = StaffOnlyModeError(
                _("User '%(username)s' does not have staff privileges. Staff-only mode is currently enabled.") % {
                    'username': request.user.username
                }
            )
            return insufficient_privileges_view(request, error)
        
        return self.get_response(request)