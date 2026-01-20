# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
Keycloak Remote User Backend

Custom authentication backend for Keycloak SSO via OAuth2-proxy.
Handles user creation and email population from upstream headers.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.backends import RemoteUserBackend
from django.contrib.auth.middleware import RemoteUserMiddleware

User = get_user_model()
logger = logging.getLogger(__name__)

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
        logger.warning("Creating user: %s", username)
        return User.objects.create_user(
            username=username,
            is_active=True,
        )


    def authenticate(self, request, remote_user=None, **kwargs):
        username = request.META.get(settings.REMOTE_USER_HEADER)
        logger.warning("Authenticating user with header value: %s", username)
        
        if not username:
            if request.user.is_authenticated:
                logger.warning("User logged in via session: %s", request.user.username)
                return request.user
            else:
                logger.warning("No REMOTE_USER header found in request and no session user. ")
                return None
        
        # Check if user exists
        try:
            user = User.objects.get(username=username)
            logger.warning("User found in database: %s", user.username)
        except User.DoesNotExist:
            logger.warning("User does not exist, creating user: %s", username)
            user = self.create_user(username)
        
        return user


class CustomRemoteUserMiddleware(RemoteUserMiddleware):
    def process_request(self, request):
        """
        Modified process_request to always trigger session-based authentication
        if REMOTE_USER is missing.
        """
        remote_user = request.META.get(self.header, None)
        
        # If REMOTE_USER is present, let the parent class handle it
        if remote_user:
            # If REMOTE_USER is set, use the default behavior
            request.META[self.header] = remote_user
            super().process_request(request)
        else:
            # If REMOTE_USER is missing, fall back to session-based authentication
            if not request.user.is_authenticated:
                # Explicitly call authenticate to check session (fallback)
                authenticate(request)  # Trigger session-based authentication