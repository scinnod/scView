<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Authentication & Login Flow Documentation

## Overview

The application uses a **unified login endpoint** (`/sso-login/`) that automatically handles both production (Keycloak SSO) and development (Django admin) authentication modes.

## Configuration Summary

### Settings (itsm_config/settings.py)

| Setting | Production | Development |
|---------|-----------|-------------|
| `DJANGO_ENV` | `production` | `development` |
| `LOGIN_URL` | `/sso-login/` | `/sso-login/` |
| `AUTHENTICATION_BACKENDS` | KeycloakRemoteUserBackend + ModelBackend | ModelBackend |

**Key Point:** Both modes use `/sso-login/` as `LOGIN_URL`. The `sso_login` view detects the environment and routes accordingly.

## Login Flow

### Development Mode Flow

```
User accesses protected page (e.g., /sc/services)
                ↓
        Not authenticated?
                ↓
    @login_required decorator
                ↓
    Redirect to LOGIN_URL: /sso-login/?next=/sc/services
                ↓
    sso_login view (views.py)
                ↓
    Detects IS_PRODUCTION=False
                ↓
    Redirects to: /admin/login/?next=/sc/services
                ↓
    Django admin login page
                ↓
    User enters credentials
                ↓
    Django authenticates via ModelBackend
                ↓
    Redirect to: /sc/services (original page)
```

### Production Mode Flow

```
User accesses protected page (e.g., /sc/services)
                ↓
        Not authenticated?
                ↓
    @login_required decorator
                ↓
    Redirect to LOGIN_URL: /sso-login/?next=/sc/services
                ↓
    nginx intercepts /sso-login/
                ↓
    OAuth2-proxy checks session
                ↓
    Not authenticated? Redirect to Keycloak
                ↓
    User authenticates with Keycloak
                ↓
    OAuth2-proxy sets session cookie
                ↓
    Request passes to sso_login view with headers:
        - X-Remote-User: username
        - X-Remote-Email: user@example.com
                ↓
    RemoteUserMiddleware authenticates user
                ↓
    sso_login view calls login(request, user)
                ↓
    Redirect to: /sc/services (original page)
```

## URL Endpoints

### `/sso-login/` (Main Login Endpoint)
- **URL Pattern:** Defined in `itsm_config/urls.py`
- **View:** `ServiceCatalogue.views.sso_login`
- **Purpose:** Unified entry point for all login flows
- **Behavior:**
  - **Development:** Redirects to `/admin/login/?next=...`
  - **Production:** Processes Keycloak authentication headers and creates session

### `/sc/login_required` (Login Landing Page)
- **URL Pattern:** Defined in `ServiceCatalogue/urls.py`
- **View:** `ServiceCatalogue.views.landing`
- **Purpose:** Display login-related messages and information
- **Behavior:** Redirects to `settings.LOGIN_URL` (which is `/sso-login/`)

### `/admin/login/` (Django Admin Login)
- **Framework:** Django built-in
- **Purpose:** Development mode authentication
- **Usage:** Only accessed in development mode via `/sso-login/` redirect

### `/sso-logout/` (Logout Endpoint)
- **View:** `ServiceCatalogue.views.logout_view`
- **Behavior:**
  - **Development:** Clears Django session, redirects to `/`
  - **Production:** Clears Django session, redirects to OAuth2-proxy logout

## Template Integration

### Login Button (services_base.html)

```django
<a class="nav-link" href="{% url 'sso_login' %}?next={{ request.path|urlencode }}">
    <i class="bi bi-box-arrow-in-right me-1"></i>{% translate "Login" %}
</a>
```

**Important:** Always URL-encode the `next` parameter to handle special characters.

### View Decorators

```python
from django.contrib.auth.decorators import login_required

@login_required
def protected_view(request):
    # This automatically redirects to settings.LOGIN_URL if not authenticated
    pass
```

## Code Reference

### Key Views (ServiceCatalogue/views.py)

#### sso_login
```python
def sso_login(request):
    if not settings.IS_PRODUCTION:
        # Development: redirect to Django admin
        next_url = request.GET.get('next', '/')
        redirect_url = f"{reverse('admin:login')}?{urlencode({'next': next_url})}"
        return redirect(redirect_url)
    
    # Production: process Keycloak headers and create session
    user = authenticate(request)
    if user and user.is_authenticated:
        login(request, user)
    
    next_url = request.GET.get('next', '/')
    return redirect(next_url)
```

#### landing
```python
def landing(request, **kwargs):
    if request.user.is_authenticated:
        return redirect("services_listed")
    
    # Redirect to LOGIN_URL with next parameter
    next_url = request.GET.get('next', '/')
    redirect_url = f"{settings.LOGIN_URL}?{urlencode({'next': next_url})}"
    return redirect(redirect_url)
```

## Common Issues & Solutions

### Issue: Redirect Loop
**Symptom:** Browser shows "too many redirects" error

**Cause:** `LOGIN_URL` pointing to a view that redirects back to `LOGIN_URL`

**Solution:** Ensure:
- `LOGIN_URL = '/sso-login/'` (not `/sc/login_required`)
- `sso_login` view redirects to actual login page (Django admin in dev)
- Never use `settings.LOGIN_URL` within the `sso_login` view itself

### Issue: Login Button Not Working
**Symptom:** Clicking login does nothing or redirects incorrectly

**Causes & Solutions:**
1. **Missing `next` parameter:**
   - Always include: `?next={{ request.path|urlencode }}`
   
2. **Incorrect `next` default:**
   - Use `request.GET.get('next', '/')` (NOT `request.path`)
   
3. **Missing URL encoding:**
   - Use `{{ request.path|urlencode }}` in templates
   - Use `urlencode({'next': next_url})` in Python

## Testing

### Development Mode
```bash
# 1. Start services
docker-compose up -d

# 2. Create superuser
docker-compose exec itsm python manage.py createsuperuser

# 3. Test login flow
# - Access: http://localhost/sc/services
# - Should redirect to: /sso-login/?next=/sc/services
# - Then redirect to: /admin/login/?next=/sc/services
# - Login with superuser credentials
# - Should redirect back to: /sc/services
```

### Production Mode
```bash
# 1. Ensure DJANGO_ENV=production in env/itsm.env
# 2. Configure OAuth2-proxy to pass headers
# 3. Access protected page
# 4. Should redirect through Keycloak
# 5. After Keycloak login, should return to original page
```

## Best Practices

1. **Always use `settings.LOGIN_URL`** - Don't hardcode login URLs
2. **URL-encode the `next` parameter** - Prevents issues with special characters
3. **Default to `/` not `request.path`** - Prevents redirect loops
4. **Test both environments** - Ensure login works in dev and production
5. **Document login flow** - Help future developers understand the authentication chain

## Troubleshooting Commands

```bash
# Check current LOGIN_URL setting
docker-compose exec itsm python manage.py shell
>>> from django.conf import settings
>>> print(f"LOGIN_URL: {settings.LOGIN_URL}")
>>> print(f"IS_PRODUCTION: {settings.IS_PRODUCTION}")

# View Django authentication backends
>>> print(settings.AUTHENTICATION_BACKENDS)

# Test login redirect
>>> from django.contrib.auth.decorators import login_required
>>> from django.urls import reverse
>>> print(reverse('sso_login'))
```
